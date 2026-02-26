from applications.data_analyzer.route_analysis import build_task_analysis


def test_summary_uses_first_segment_departure_derived_from_transit_anchor():
    task_payload = {
        "query_time": "2026-02-25T20:00:00+00:00",
        "arrive_time": None,
        "result": {
            "mode": "mixed",
            "segments": [
                {
                    "from": "start",
                    "to": "transfer",
                    "travel_mode": "DRIVE",
                    "route": {
                        "routes": [
                            {
                                "distanceMeters": 6000,
                                "duration": "600s",
                                "legs": [
                                    {
                                        "steps": [
                                            {
                                                "travelMode": "DRIVE",
                                                "staticDuration": "600s",
                                                "navigationInstruction": {"instructions": "Drive to transfer"},
                                            }
                                        ]
                                    }
                                ],
                            }
                        ]
                    },
                },
                {
                    "from": "transfer",
                    "to": "destination",
                    "travel_mode": "TRANSIT",
                    "route": {
                        "routes": [
                            {
                                "distanceMeters": 15000,
                                "duration": "1800s",
                                "legs": [
                                    {
                                        "steps": [
                                            {
                                                "travelMode": "TRANSIT",
                                                "staticDuration": "1800s",
                                                "transitDetails": {
                                                    "headsign": "Union",
                                                    "stopCount": 5,
                                                    "stopDetails": {
                                                        "departureStop": {"name": "Clarkson GO"},
                                                        "arrivalStop": {"name": "Union Station"},
                                                        "departureTime": "2026-02-25T21:00:00Z",
                                                        "arrivalTime": "2026-02-25T21:30:00Z",
                                                    },
                                                    "transitLine": {
                                                        "nameShort": "LW",
                                                        "vehicle": {"name": {"text": "Train"}, "type": "RAIL"},
                                                    },
                                                },
                                            }
                                        ]
                                    }
                                ],
                            }
                        ]
                    },
                },
            ],
        },
    }

    analysis = build_task_analysis(task_payload)

    summary = analysis["summary"]
    segments = analysis["segments"]

    assert summary["departure_time"] == "2026-02-25T20:50:00+00:00"
    assert summary["arrival_time"] == "2026-02-25T21:30:00+00:00"
    assert segments[0]["departure_time"] == "2026-02-25T20:50:00+00:00"
    assert segments[0]["arrival_time"] == "2026-02-25T21:00:00+00:00"
    assert segments[1]["departure_time"] == "2026-02-25T21:00:00+00:00"
    assert segments[1]["arrival_time"] == "2026-02-25T21:30:00+00:00"


def test_transit_timeline_time_text_uses_local_timezone_format():
    task_payload = {
        "query_time": "2026-02-25T20:00:00+00:00",
        "arrive_time": None,
        "result": {
            "mode": "transit",
            "segments": [
                {
                    "from": "start",
                    "to": "destination",
                    "travel_mode": "TRANSIT",
                    "route": {
                        "routes": [
                            {
                                "distanceMeters": 12000,
                                "duration": "2100s",
                                "legs": [
                                    {
                                        "steps": [
                                            {
                                                "travelMode": "TRANSIT",
                                                "staticDuration": "2100s",
                                                "transitDetails": {
                                                    "headsign": "Union",
                                                    "stopCount": 6,
                                                    "stopDetails": {
                                                        "departureStop": {"name": "Clarkson GO"},
                                                        "arrivalStop": {"name": "Union Station"},
                                                        "departureTime": "2026-02-25T21:09:42Z",
                                                        "arrivalTime": "2026-02-25T21:44:15Z",
                                                    },
                                                    "transitLine": {
                                                        "nameShort": "LW",
                                                        "vehicle": {"name": {"text": "Train"}, "type": "RAIL"},
                                                    },
                                                },
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
    timeline = analysis["segments"][0]["timeline"]

    assert timeline
    transit_row = timeline[0]
    assert "T" not in transit_row["time_text"]
    assert "Z" not in transit_row["time_text"]
    assert "→" in transit_row["time_text"]
