import redis
import logging
import gitlab
from time import sleep
import os
from prometheus_client import Counter, Histogram

from common.constants import (
    project_events,
    user_events,
    issue_events,
    issue_note_events,
    group_events,
    snippet_events,
    event_types,
)

from common.event_processor import EventProcessor

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

class GitlabRetrievalProcessor(EventProcessor):
    def __init__(self, GITLAB_URL, GITLAB_ACCESS_TOKEN, redis_conn=None, testing=False):
        super().__init__("verification", event_types, redis_conn)
        self.gitlab_client = gitlab.Gitlab(
            GITLAB_URL, private_token=GITLAB_ACCESS_TOKEN
        )
        self.testing = testing

        self.event_processing_time= Histogram('retrieval_service_event_processing_seconds', 'Time taken to process an event')
        self.events_processed = Counter('retrieval_service_events_processed_total', 'Total number of events processed')

    def process_event(self, queue_name, event_data):
        with self.event_processing_time.time():
            event_type = queue_name.split("_", 1)[
                -1
            ]

            if event_type in user_events:
                gitlab_object = self._process_user_event(event_data)
            elif event_type in project_events:
                gitlab_object = self._process_project_event(event_data)
            elif event_type in issue_events:
                gitlab_object = self._process_issue_event(event_data)
            elif event_type in issue_note_events:
                gitlab_object = self._process_issue_note_event(event_data)
            elif event_type in group_events:
                gitlab_object = self._process_group_event(event_data)
            else:
                logging.info(f"{self.__class__.__name__}: event {event_type} received")
                return

            self.events_processed.inc()
            self.send_to_queue(event_type, gitlab_object, prefix="retrieval")

    def _process_user_event(self, event_data):
        try:
            return self.gitlab_client.users.get(event_data["user_id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: error retrieving user ID {event_data["user_id"]} from GitLab API: {e}'
            )

    def _process_project_event(self, event_data):
        try:
            return self.gitlab_client.projects.get(event_data["project_id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: error retrieving project ID {event_data["project_id"]} from GitLab API: {e}'
            )

    def _process_issue_event(self, event_data):
        try:
            project = self.gitlab_client.projects.get(
                event_data["object_attributes"]["project_id"]
            )
            return project.issues.get(event_data["object_attributes"]["id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: error retrieving issue ID {event_data["object_attributes"]["id"]} from GitLab API: {e}'
            )

    def _process_issue_note_event(self, event_data):
        try:
            project = self.gitlab_client.projects.get(event_data["project_id"])
            issue = project.issues.get(event_data["issue"]["id"])
            return issue.notes.get(event_data["object_attributes"]["id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: error retrieving issue note ID {event_data["object_attributes"]["id"]} from GitLab API: {e}'
            )

    def _process_group_event(self, event_data):
        try:
            return self.gitlab_client.groups.get(event_data["group_id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: error retrieving group ID {event_data["group_id"]} from GitLab API: {e}'
            )

    def send_to_queue(self, event, data, prefix=None):
        queue_name = f"{prefix}_{event}"
        serialized_data = data.to_json()

        try:
            self.redis_client.lpush(queue_name, serialized_data)
            logging.debug(f"{self.__class__.__name__}: pushed data to {queue_name}")
        except Exception as e:
            logging.error(f"Error pushing data to queue {queue_name}: {e}")

    def run(self):
        while True:
            self.retrieve_event()

            if self.testing:
                break

            sleep(1)


def main(
    GITLAB_URL=os.getenv("GITLAB_URL"),
    GITLAB_ACCESS_TOKEN=os.getenv("GITLAB_ACCESS_TOKEN"),
    testing=False,
):

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

    redis_conn = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD
    )

    processor = GitlabRetrievalProcessor(
        GITLAB_URL, GITLAB_ACCESS_TOKEN, redis_conn=redis_conn, testing=testing
    )
    processor.run()



if __name__ == "__main__":
    main()
