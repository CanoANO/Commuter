from applications.data_analyzer.route_analysis import build_task_analysis


def test_build_task_analysis_returns_empty_when_result_missing():
    analysis = build_task_analysis({"query_time": "2026-02-25T20:00:00+00:00"})

    assert analysis == {"summary": {}, "segments": []}


def test_build_task_analysis_falls_back_to_query_time_for_non_transit_segment():
    task_payload = {
        "query_time": "2026-02-25T20:00:00+00:00",
        "arrive_time": None,
        "result": {
            "mode": "drive",
            "segments": [
                {
                    "from": "start",
                    "to": "destination",
                    "travel_mode": "DRIVE",
                    "route": {
                        "routes": [
                            {
                                "distanceMeters": 1000,
                                "duration": "300s",
                                "legs": [
                                    {
                                        "steps": [
                                            {
                                                "travelMode": "DRIVE",
                                                "staticDuration": "300s",
                                                "navigationInstruction": {"instructions": "Drive straight"},
                                            }
                                        ]
                                    }
                                ],
                            }
                        ]
                    },
                }
            ],
        },
    }

    analysis = build_task_analysis(task_payload)

    assert analysis["summary"]["departure_time"] == "2026-02-25T20:00:00+00:00"
    assert analysis["summary"]["arrival_time"] == "2026-02-25T20:05:00+00:00"
    assert analysis["summary"]["total_duration_text"] == "5m 0s"
