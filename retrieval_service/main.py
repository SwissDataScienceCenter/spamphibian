import logging
import gitlab
import os
from prometheus_client import Counter, Histogram

from common.constants import (
    project_events,
    user_events,
    issue_events,
    issue_note_events,
    group_events,
    event_types,
)

from common.event_processor import EventProcessor

LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(
    level=LOGLEVEL, format="%(asctime)s - %(levelname)s - Retrieval service: %(message)s"
)

# GitlabRetrievalProcessor class is used to process events from Redis queues
# and push events back into to Redis queues after processing.
# It is a subclass of EventProcessor.
# It is used to retrieve data from GitLab using the GitLab API.
class GitlabRetrievalProcessor(EventProcessor):
    def __init__(self, GITLAB_URL, GITLAB_ACCESS_TOKEN, redis_conn=None, testing=False):
        super().__init__("verification", redis_conn)
        self.gitlab_client = gitlab.Gitlab(
            GITLAB_URL, private_token=GITLAB_ACCESS_TOKEN
        )
        self.testing = testing

        self.event_processing_time = Histogram(
            "retrieval_service_event_processing_seconds",
            "Time taken to process an event",
        )
        self.events_processed = Counter(
            "retrieval_service_events_processed_total",
            "Total number of events processed",
        )

    def process_event(self, event_type, event_data):
        with self.event_processing_time.time():

            # Determine how to retrieve data based on event type
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
            if gitlab_object:
                self.push_event_to_queue(event_type, gitlab_object, stream_name="retrieval")

    def _process_user_event(self, event_data):
        try:
            return self.gitlab_client.users.get(event_data["user_id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: GitLab API error retrieving user ID {event_data["user_id"]}: {e}'
            )

    def _process_project_event(self, event_data):
        try:
            return self.gitlab_client.projects.get(event_data["project_id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: GitLab API error retrieving project ID {event_data["project_id"]}: {e}'
            )

    def _process_issue_event(self, event_data):
        try:
            project = self.gitlab_client.projects.get(
                event_data["object_attributes"]["project_id"]
            )
            return project.issues.get(event_data["object_attributes"]["id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: GitLab API error retrieving issue ID {event_data["object_attributes"]["id"]}: {e}'
            )

    def _process_issue_note_event(self, event_data):
        try:
            project = self.gitlab_client.projects.get(event_data["project_id"])
            issue = project.issues.get(event_data["issue"]["id"])
            return issue.notes.get(event_data["object_attributes"]["id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: GitLab API error retrieving issue note ID {event_data["object_attributes"]["id"]}: {e}'
            )

    def _process_group_event(self, event_data):
        try:
            return self.gitlab_client.groups.get(event_data["group_id"])
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(
                f'{self.__class__.__name__}: GitLab API error retrieving group ID {event_data["group_id"]}: {e}'
            )

    def push_event_to_queue(self, event_type, data, stream_name=None):
        serialized_data = data.to_json()

        try:
            self.redis_client.xadd(stream_name, {event_type: serialized_data})
            logging.debug(f"{self.__class__.__name__}: added data to {stream_name}")
        except Exception as e:
            logging.error(f"Error adding data to queue {stream_name}: {e}")

    def run(self):
        while True:
            self.poll_and_process_event()

def main(
    GITLAB_URL=os.getenv("GITLAB_URL"),
    GITLAB_ACCESS_TOKEN=os.getenv("GITLAB_ACCESS_TOKEN"),
    redis_conn=None,
    testing=False,
):
    processor = GitlabRetrievalProcessor(
        GITLAB_URL, GITLAB_ACCESS_TOKEN, redis_conn=redis_conn, testing=testing
    )
    processor.run()


if __name__ == "__main__":
    main(
        GITLAB_URL=os.getenv("GITLAB_URL"),
        GITLAB_ACCESS_TOKEN=os.getenv("GITLAB_ACCESS_TOKEN"),
        testing=False,
    )
