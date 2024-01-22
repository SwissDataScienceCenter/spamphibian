import requests
import os
import logging
import datetime

from common.constants import (
    UserEvent,
    ProjectEvent,
    IssueEvent,
    IssueNoteEvent,
    GroupEvent,
)

from common.event_processor import EventProcessor

from prometheus_client import (
    multiprocess,
    CollectorRegistry,
    Counter,
    Histogram,
    Gauge,
)

LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(
    level=LOGLEVEL, format="%(asctime)s - %(levelname)s - Notification service: %(message)s"
)


# Format message for Slack
def format_message(event_type, data):
    event_data = data["event_data"]
    prediction = data["prediction"]
    score = data["score"]

    if event_type in [e.value for e in UserEvent]:
        message_format = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": ""}},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Username:* {event_data['username']}\n*Name:* {event_data['name']}\n*Email:* {event_data['email']}",
                    },
                    "accessory": {
                        "type": "image",
                        "image_url": event_data["avatar_url"],
                        "alt_text": "avatar",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Spam Classification:* {'Spam' if prediction == 1 else 'Not Spam'}",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Spam Score*: {score}"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*State:* {event_data['state']}"
                        + "\n"
                        + f"*Web URL:* <{event_data['web_url']}|Profile>"
                        + (
                            ""
                            if not event_data["bio"]
                            else "\n*Bio:* " + event_data["bio"]
                        ),
                    },
                },
            ]
        }

        if event_data["website_url"]:
            message_format["blocks"].append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Website:* <{event_data['website_url']}|Website>",
                    },
                }
            )

        if event_type == UserEvent.USER_CREATE.value:
            message_format["blocks"][0]["text"]["text"] = "User Created on GitLab"
        elif event_type == UserEvent.USER_RENAME.value:
            message_format["blocks"][0]["text"]["text"] = "User Renamed on GitLab"

    elif event_type in [e.value for e in IssueEvent]:
        message_format = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": ""}},
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Title:*\n{event_data['title']}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Description:*\n{event_data['description']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Author:*\n{event_data['author']['name']}",
                        },
                        {"type": "mrkdwn", "text": f"*State:*\n{event_data['state']}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Link:*\n<{event_data['web_url']}|View Issue>",
                    },
                },
            ]
        }

        if event_type == IssueEvent.ISSUE_OPEN.value:
            message_format["blocks"][0]["text"]["text"] = "Issue Opened on GitLab"
        elif event_type == IssueEvent.ISSUE_UPDATE.value:
            message_format["blocks"][0]["text"]["text"] = "Issue Updated on GitLab"
        elif event_type == IssueEvent.ISSUE_CLOSE.value:
            message_format["blocks"][0]["text"]["text"] = "Issue Closed on GitLab"
        elif event_type == IssueEvent.ISSUE_REOPEN.value:
            message_format["blocks"][0]["text"]["text"] = "Issue Reopened on GitLab"

    elif event_type in [e.value for e in GroupEvent]:
        created_at = datetime.datetime.strptime(
            event_data["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        created_at_str = created_at.strftime("%d %B %Y %H:%M:%S")

        message_format = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": ""}},
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Name:*\n{event_data['name']}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Visibility:*\n{event_data['visibility']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Created At:*\n{created_at_str} GMT",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Spam Classification:* {'Spam' if prediction == 1 else 'Not Spam'}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Spam Score*: {score}",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Link:*\n<{event_data['web_url']}|View Group>",
                    },
                },
            ]
        }

        if event_type == GroupEvent.GROUP_CREATE.value:
            message_format["blocks"][0]["text"]["text"] = "Group Created on GitLab"
        elif event_type == GroupEvent.GROUP_RENAME.value:
            message_format["blocks"][0]["text"]["text"] = "Group Renamed on GitLab"

    elif event_type in [e.value for e in IssueNoteEvent]:
        created_at = datetime.datetime.strptime(
            event_data["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        created_at_str = created_at.strftime("%d %B %Y %H:%M:%S")

        message_format = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": ""}},
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Project ID:*\n{event_data['project_id']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Issue IID:*\n{event_data['issue_iid']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Author:*\n{event_data['author']['name']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Created At:*\n{created_at_str} GMT",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Spam Classification:* {'Spam' if prediction == 1 else 'Not Spam'}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Spam Score*: {score}",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Content:*\n{event_data['body']}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Link:*\n<{event_data['author']['web_url']}|View Author Profile>",
                    },
                },
            ]
        }

        if event_type == IssueNoteEvent.ISSUE_NOTE_CREATE.value:
            message_format["blocks"][0]["text"]["text"] = "Issue Note Created on GitLab"
        elif event_type == IssueNoteEvent.ISSUE_NOTE_UPDATE.value:
            message_format["blocks"][0]["text"]["text"] = "Issue Note Updated on GitLab"

    elif event_type in [e.value for e in ProjectEvent]:
        created_at = datetime.datetime.strptime(
            event_data["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        created_at_str = created_at.strftime("%d %B %Y %H:%M:%S")

        message_format = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": ""},
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Project ID:*\n{event_data['id']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Project Name:*\n{event_data['name']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Namespace:*\n{event_data['namespace']['name']}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Created At:*\n{created_at_str} GMT",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Spam Classification:* {'Spam' if prediction == 1 else 'Not Spam'}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Spam Score*: {score}",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Link:*\n<{event_data['web_url']}|View Project>",
                    },
                },
            ]
        }

        if event_type == ProjectEvent.PROJECT_CREATE.value:
            message_format["blocks"][0]["text"]["text"] = "Project Created on GitLab"
        elif event_type == ProjectEvent.PROJECT_RENAME.value:
            message_format["blocks"][0]["text"]["text"] = "Project Renamed on GitLab"
        elif event_type == ProjectEvent.PROJECT_TRANSFER.value:
            message_format["blocks"][0]["text"][
                "text"
            ] = "Project Ownership Transferred on GitLab"

    return message_format


# SlackNotifier class, inherits from EventProcessor.
# Used to retrieve events from Redis and send them to Slack.
class SlackNotifier(EventProcessor):
    def __init__(self, slack_webhook_url, input_stream_name, redis_conn=None):
        super().__init__(input_stream_name, "", redis_conn)
        self.slack_webhook_url = slack_webhook_url

        prometheus_multiproc_dir = "prometheus_multiproc_dir"

        os.makedirs(prometheus_multiproc_dir, exist_ok=True)

        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)

        self.notification_counter = Counter(
            "notification_service_notifications_total",
            "The number of times a notification has been sent",
            ["notification_endpoint"],
        )

        self.notification_failures_counter = Counter(
            "notification_service_notification_failures_total",
            "The number of times a notification has failed to be sent",
            ["notification_endpoint"],
        )

        self.notification_latency_histogram = Histogram(
            "notification_service_notification_latency_seconds",
            "Time taken to send a notification",
        )

        self.queue_size_gauge = Gauge(
            "notification_service_queue_size", "Number of events waiting in the queue"
        )

    def process_event(self, event_type, data):
        formatted_message = format_message(event_type, data)

        with self.notification_latency_histogram.time():
            response = requests.post(self.slack_webhook_url, json=formatted_message, timeout=10)

        if response.status_code != 200:
            logging.debug(
                f"Failed to send message to Slack: event: {event_type}, data: {formatted_message}. "
                f"Response code: {response.status_code} message: {response.content}"
            )
            self.notification_failures_counter.labels(self.slack_webhook_url).inc()
        else:
            logging.debug("Successfully sent message to Slack")
            self.notification_counter.labels(self.slack_webhook_url).inc()


def main(
    slack_webhook_url="",
    redis_conn=None,
    testing=False,
):
    notifier = SlackNotifier(
        slack_webhook_url, "classification", redis_conn=redis_conn
    )

    notifier.poll_and_process_event(testing=testing)


if __name__ == "__main__":
    main(
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        testing=False,
    )
