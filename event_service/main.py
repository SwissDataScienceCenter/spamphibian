from sanic import Sanic
from sanic.response import json as sanic_json
from sanic.response import HTTPResponse
from sanic.worker.loader import AppLoader
import redis
import json
from functools import partial
import logging
from prometheus_client import (
    generate_latest,
    multiprocess,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)
import os

from common.constants import (
    project_events,
    user_events,
    issue_events,
    issue_note_events,
    group_events,
    snippet_events,
    event_types,
)

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

prometheus_multiproc_dir = "prometheus_multiproc_dir"

if not os.path.exists(prometheus_multiproc_dir):
    os.makedirs(prometheus_multiproc_dir)


def create_app(app_name: str) -> Sanic:
    app = Sanic(app_name)

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

    # Redis connection
    REDIS_SENTINEL_ENABLED = os.getenv("REDIS_SENTINEL_ENABLED", "False") == "True"
    REDIS_SENTINEL_HOSTS = os.getenv("REDIS_SENTINEL_HOSTS", "")
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

    sentinel_hosts = [tuple(x.split(":")) for x in REDIS_SENTINEL_HOSTS.split(",")]

    if REDIS_SENTINEL_ENABLED:
        try:
            sentinel = redis.Sentinel(
                sentinel_hosts,
                sentinel_kwargs={"password": REDIS_PASSWORD},
            )

            master_info = sentinel.sentinel_masters()
            first_master_name = list(master_info.keys())[0]

            r = sentinel.master_for(
                first_master_name, db=REDIS_DB, password=REDIS_PASSWORD
            )
            
            r.ping()
            logging.info(f"Successfully connected to master: {first_master_name}")

        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logging.error(f"Could not connect to any sentinel. Error: {e}")
            exit(1)

    else:
        r = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_PASSWORD
            )

    try:
        r.ping()
    except redis.exceptions.ConnectionError as e:
        logging.error(f"Error connecting to Redis: {e}")
        exit(1)

    @app.route("/metrics")
    async def get_metrics(request):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        metrics = generate_latest(registry)
        return HTTPResponse(
            metrics,
            headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
        )

    @app.before_server_stop
    async def cleanup_metrics(app, _):
        multiprocess.mark_process_dead(os.getpid())

    @app.post("/event")
    async def handle_event(request):
        with request_latency_histogram.time():
            requests_counter.labels("POST", "/event").inc()
            queue_name = ""
            gitlab_event = request.json

            # Determine the type of event
            event_name = gitlab_event.get("event_name")
            object_kind = gitlab_event.get("object_kind")
            action = gitlab_event.get("object_attributes", {}).get("action")

            logging.debug(f"Event service: received event: {event_name}")

            # Project-related events
            if (
                event_name in project_events
                or event_name in user_events
                or event_name in group_events
                or event_name in snippet_events
            ):
                queue_name = event_name

            # Issue-related events
            elif object_kind == "issue" and action in [
                "open",
                "close",
                "reopen",
                "update",
            ]:
                queue_name = f"issue_{action}"

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
                            queue_name = f"issue_note_create"
                        else:
                            queue_name = f"issue_note_update"

                except KeyError:
                    logging.debug(
                        "Event service: object_attributes.note does not exist in gitlab_event"
                    )

            else:
                logging.debug(
                    f"Event service: unhandled event: {event_name if event_name else object_kind}"
                )

            event_types_counter.labels(queue_name).inc()

            queue_name = "event_" + queue_name

            try:
                r.lpush(queue_name, json.dumps(gitlab_event))
                logging.debug(f"Event service: pushed event to queue: {queue_name}")
                queue_size_gauge.labels(queue_name).set(r.llen(queue_name))
            except Exception as e:
                logging.error(
                    f"Event service: error pushing event to queue {queue_name}: {e}"
                )
                event_errors.inc()

            return sanic_json({"message": "Event received"})

    return app


def main():
    loader = AppLoader(factory=partial(create_app, "EventService"))
    app = loader.load()
    app.prepare(host="0.0.0.0", port=8000, dev=True)
    Sanic.serve(primary=app, app_loader=loader)


if __name__ == "__main__":
    main()
