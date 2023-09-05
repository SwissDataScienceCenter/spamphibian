import logging
import os
from prometheus_client import multiprocess, CollectorRegistry, Counter
from prometheus_client import (
    generate_latest,
    multiprocess,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)
from sanic import Sanic
from sanic.response import json as sanic_json
from sanic.response import HTTPResponse
from sanic.worker.loader import AppLoader
from common.event_processor import EventProcessor
from functools import partial

from common.constants import (
    project_events,
    user_events,
    group_events,
    snippet_events,
    event_types,
)

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

prometheus_multiproc_dir = "prometheus_multiproc_dir"

try:
    if not os.path.exists(prometheus_multiproc_dir):
        os.makedirs(prometheus_multiproc_dir)
except Exception as e:
    print(f"An error occurred: {e}")

requests_counter = Counter(
    "event_service_requests_total",
    "The number of times my API was accessed",
    ["method", "endpoint"],
)
event_types_counter = Counter(
    "event_service_event_types_total",
    "The number of times an event_type was received",
    ["event_type"],
)

event_errors = Counter(
    "event_service_errors_total",
    "Number of errors encountered in the event service",
)
queue_size_gauge = Gauge(
    "event_service_queue_size", "Size of the Redis event queue", ["queue_name"]
)

request_latency_histogram = Histogram(
    "event_service_request_latency_seconds",
    "Time taken to handle and process incoming events",
)


def create_app(app_name: str, redis_conn=None, testing=False) -> Sanic:
    app = Sanic("myApp")

    sanic_event_processor = EventProcessor(
        events=event_types, prefix="event", redis_conn=redis_conn
    )

    @app.route("/metrics")
    async def get_metrics(request):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        metrics = generate_latest(registry)
        return HTTPResponse(
            metrics,
            headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
        )

    if not testing:

        @app.before_server_stop
        async def cleanup_metrics(app, _):
            multiprocess.mark_process_dead(os.getpid())

    @app.post("/event")
    async def handle_event(request):
        with request_latency_histogram.time():
            requests_counter.labels("POST", "/event").inc()
            event_name = ""
            gitlab_event = request.json

            # Determine the type of event
            event_name = gitlab_event.get("event_name")
            object_kind = gitlab_event.get("object_kind")
            action = gitlab_event.get("object_attributes", {}).get("action")

            logging.debug(f"Event service: received event: {event_name}")

            # Project-related events

            # Issue-related events
            if object_kind == "issue" and action in [
                "open",
                "close",
                "reopen",
                "update",
            ]:
                event_name = f"issue_{action}"

            # Note-related events
            elif object_kind == "note":
                try:
                    # Check if 'note' exists in 'object_attributes'
                    noteable_type = gitlab_event["object_attributes"]["noteable_type"]
                    # Check if 'noteable_type' is 'Issue'
                    if noteable_type == "Issue":
                        # Check if 'created_at' and 'updated_at' are equal, meaning the note was just created
                        if (
                            gitlab_event["object_attributes"]["created_at"]
                            == gitlab_event["object_attributes"]["updated_at"]
                        ):
                            event_name = f"issue_note_create"
                        else:
                            event_name = f"issue_note_update"

                except KeyError:
                    logging.debug(
                        "Event service: object_attributes.note does not exist in gitlab_event"
                    )

            elif (
                event_name in project_events
                or event_name in user_events
                or event_name in group_events
                or event_name in snippet_events
            ):
                event_name = event_name

            else:
                logging.debug(
                    f"Event service: unhandled event: {event_name if event_name else object_kind}"
                )
                return sanic_json({"message": "Event received"})

            event_types_counter.labels(event_name).inc()

            logging.debug(
                f"Event service: sending event to queue: {event_name} with data: {gitlab_event}"
            )

            sanic_event_processor.send_to_queue(
                event_name, gitlab_event, prefix="event"
            )

            return sanic_json({"message": "Event received"})

    return app


def main():
    loader = AppLoader(factory=partial(create_app, "EventService"))
    app = loader.load()
    app.prepare(host="0.0.0.0", port=8000, dev=True)
    Sanic.serve(primary=app, app_loader=loader)


if __name__ == "__main__":
    main()
