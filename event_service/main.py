from sanic import Sanic
from sanic.response import json as sanic_json
from sanic.worker.loader import AppLoader
import redis
import json
from functools import partial
import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


def create_app(app_name: str) -> Sanic:
    app = Sanic(app_name)

    # Create Redis connection
    redis_conn = redis.StrictRedis(host="localhost", port=6379, db=0)

    @app.post("/event")
    async def handle_event(request):
        queue_name = ""
        gitlab_event = request.json

        # Determine the type of event
        event_name = gitlab_event.get("event_name")
        object_kind = gitlab_event.get("object_kind")
        action = gitlab_event.get("object_attributes", {}).get("action")

        logging.debug(f"Received event: {event_name}")

        # Project-related events
        if event_name in [
            "project_create",
            "project_rename",
            "project_transfer",
            "user_create",
            "user_rename",
            "group_create",
            "group_rename",
            "snippet_check",
        ]:
            queue_name = event_name

        # Issue-related events
        elif object_kind == "issue" and action in ["open", "close", "reopen", "update"]:
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
                logging.debug("object_attributes.note does not exist in gitlab_event")

        else:
            logging.debug(
                f"Unhandled event: {event_name if event_name else object_kind}"
            )

        queue_name = "event_" + queue_name

        try:
            redis_conn.lpush(queue_name, json.dumps(gitlab_event))
            logging.debug(f"Pushed event to queue: {queue_name}")
        except Exception as e:
            logging.error(f"Error pushing event to queue {queue_name}: {e}")

        return sanic_json({"message": "Event received"})

    return app


if __name__ == "__main__":
    loader = AppLoader(factory=partial(create_app, "EventService"))
    app = loader.load()
    app.prepare(port=8000, dev=True)
    Sanic.serve(primary=app, app_loader=loader)
