from components.messaging import QueueNames, RabbitMQPublisher

class BackgroundJobManager:
    def __init__(self):
        self.publisher = RabbitMQPublisher()

    def trigger_route_processing(self, task_id: str):
        self.publisher.publish_json(
            queue_name=QueueNames.ROUTE_TASKS,
            payload={"task_id": task_id},
        )
