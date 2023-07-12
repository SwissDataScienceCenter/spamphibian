import redis
import json
import logging
import gitlab
from time import sleep
import os

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

project_events = [
    "project_create",
    "project_rename",
    "project_transfer",
]

user_events = [
    "user_create",
    "user_rename",
]

issue_events = [
    "issue_open",
    "issue_update",
    "issue_close",
    "issue_reopen",
]

issue_note_events = [
    "issue_note_create",
    "issue_note_update",
]

group_events = [
    "group_create",
    "group_rename",
]

snippet_events = [
    "snippet_check",
]


def retrieve_gitlab_objects(GITLAB_URL, GITLAB_ACCESS_TOKEN):
    redis_conn = redis.Redis(host="localhost", port=6379, db=0)

    # Create a GitLab instance
    gl = gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_ACCESS_TOKEN)

    event_types = (
        user_events
        + project_events
        + issue_events
        + issue_note_events
        + group_events
        + snippet_events
    )

    while True:
        for event_type in event_types:
            event = redis_conn.lpop("verification_" + event_type)

            if event is None:
                continue

            logging.info(f"Retrieval service: processing event {event_type}")

            event_data = json.loads(event)

            if event_type in user_events:
                try:
                    gitlab_object = gl.users.get(event_data["user_id"])

                except gitlab.exceptions.GitlabGetError as e:
                    logging.info(
                        f'Retrieval service: error retrieving user ID {event_data["user_id"]} from GitLab API: {e}'
                    )

                logging.debug(
                    f"Retrieval service: gitlab_object received for {event_type}: {gitlab_object.attributes}"
                )

            elif event_type in project_events:
                try:
                    gitlab_object = gl.projects.get(event_data["project_id"])

                except gitlab.exceptions.GitlabGetError as e:
                    logging.info(
                        f'Retrieval service: error retrieving project ID {event_data["project_id"]} from GitLab API: {e}'
                    )

                logging.debug(
                    f"Retrieval service: gitlab_object received for {event_type}: {gitlab_object.attributes}"
                )

            elif event_type in issue_events:
                try:
                    project = gl.projects.get(
                        event_data["object_attributes"]["project_id"]
                    )
                    gitlab_object = project.issues.get(
                        event_data["object_attributes"]["id"]
                    )

                except gitlab.exceptions.GitlabGetError as e:
                    logging.info(
                        f'Retrieval service: error retrieving issue ID {event_data["object_attributes"]["id"]} from GitLab API: {e}'
                    )

                logging.debug(
                    f"Retrieval service: gitlab_object received for {event_type}: {gitlab_object.attributes}"
                )

            elif event_type in issue_note_events:
                try:
                    project = gl.projects.get(event_data["project_id"])
                    issue = project.issues.get(event_data["issue"]["id"])
                    gitlab_object = issue.notes.get(
                        event_data["object_attributes"]["id"]
                    )

                except gitlab.exceptions.GitlabGetError as e:
                    logging.info(
                        f'Retrieval service: error retrieving issue note ID {event_data["object_attributes"]["id"]} from GitLab API: {e}'
                    )

                logging.debug(
                    f"Retrieval service: gitlab_object received for {event_type}: {gitlab_object.attributes}"
                )

            elif event_type in group_events:
                try:
                    gitlab_object = gl.groups.get(event_data["group_id"])

                except gitlab.exceptions.GitlabGetError as e:
                    logging.info(
                        f'Retrieval service: error retrieving group ID {event_data["group_id"]} from GitLab API: {e}'
                    )

                logging.debug(
                    f"Retrieval service: gitlab_object received for {event_type}: {gitlab_object.attributes}"
                )

            else:
                logging.info(f"Retrieval service: event {event_type} received")

            queue_name = "retrieval_" + event_type

            try:
                redis_conn.lpush(queue_name, json.dumps(gitlab_object.to_json()))
                logging.debug(f"Retrieval service: pushed event to queue: {queue_name}")
            except Exception as e:
                logging.error(
                    f"Retrieval service: error pushing event to queue {queue_name}: {e}"
                )

        sleep(1)


if __name__ == "__main__":
    retrieve_gitlab_objects(
        GITLAB_URL=os.getenv("GITLAB_URL"),
        GITLAB_ACCESS_TOKEN=os.environ.get("GITLAB_ACCESS_TOKEN"),
    )
