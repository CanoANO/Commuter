from flask import Blueprint, request, jsonify, render_template

from applications.data_analyzer import build_task_analysis
from components.database.gateways import RoutePlanGateway
from components.jobs import BackgroundJobManager
from components.messaging import AnalysisCache, MetricsStore

plan_routes = Blueprint('plan', __name__)
route_plan_gateway = RoutePlanGateway()
job_manager = BackgroundJobManager()
analysis_cache = AnalysisCache()
metrics_store = MetricsStore()
ANALYSIS_VERSION = 2

@plan_routes.route('/route-plans', methods=['POST'])
def create_route_plan():
    data = request.get_json(silent=True) or {}
    metrics_store.increment('route_plans.requests_total')

    start_text = (data.get('start_address') or '').strip()
    destination_text = (data.get('destination_address') or '').strip()
    transfer_text = (data.get('transfer_address') or '').strip() or None
    mode = (data.get('mode') or 'drive').strip()
    drive_part = data.get('drive_part')

    if not start_text or not destination_text:
        metrics_store.increment('route_plans.validation_failed_total')
        return jsonify({'error': 'start_address and destination_address are required'}), 400

    if mode not in {'drive', 'transit', 'mixed'}:
        metrics_store.increment('route_plans.validation_failed_total')
        return jsonify({'error': 'invalid mode'}), 400

    if drive_part not in {'first', 'second', None}:
        metrics_store.increment('route_plans.validation_failed_total')
        return jsonify({'error': 'invalid drive_part'}), 400

    if mode == 'mixed' and not transfer_text:
        metrics_store.increment('route_plans.validation_failed_total')
        return jsonify({'error': 'transfer_address is required for mixed mode'}), 400

    task_id = route_plan_gateway.create_route_plan(
        start_text=start_text,
        transfer_text=transfer_text,
        destination_text=destination_text,
        drive_part=drive_part,
        mode=mode,
        arrive_time_raw=data.get('arrive_time'),
    )

    job_manager.trigger_route_processing(task_id)

    metrics_store.increment('route_plans.created_total')
    metrics_store.increment(f'route_plans.mode.{mode}_total')

    return jsonify({'task_id': task_id}), 201

@plan_routes.route('/route-plans/<task_id>', methods=['GET'])
def get_route_plan(task_id):
    metrics_store.increment('route_plans.query_total')
    task = route_plan_gateway.get_route_plan(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.get('result'):
        cached_analysis = analysis_cache.get_analysis(task_id)
        if cached_analysis and cached_analysis.get('version') == ANALYSIS_VERSION:
            metrics_store.increment('route_plans.analysis_cache_hit_total')
            task['analysis'] = cached_analysis
        else:
            metrics_store.increment('route_plans.analysis_cache_miss_total')
            computed_analysis = build_task_analysis(task)
            task['analysis'] = computed_analysis
            analysis_cache.set_analysis(task_id, computed_analysis)

    accept = request.headers.get('Accept', '')
    if 'application/json' in accept or request.args.get('format') == 'json':
        return jsonify(task)

    return render_template('plan.html', task_id=task['task_id'])
