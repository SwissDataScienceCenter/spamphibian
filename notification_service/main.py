import json
import redis
import requests
import os
import logging
import datetime

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

from prometheus_client import (
    generate_latest,
    multiprocess,
    CollectorRegistry,
    Counter,
    Histogram,
    Gauge,
)

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


def format_message(queue, data):
    event_data = data["event_data"]
    prediction = data["prediction"]
    score = data["score"]

    queue_name = queue.removeprefix("classification_")

    if queue_name in user_events:
        message_format = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": ""}},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Username:* {event_data['username']}\n*Name:* {event_data['name']}\n*Email:* {event_data['email']}",
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
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Spam Score*: {score}",
                    },
                },
            ]
        }

        if queue_name == "user_create":
            message_format["blocks"][0]["text"]["text"] = "User Created on GitLab"
        elif queue_name == "user_rename":
            message_format["blocks"][0]["text"]["text"] = "User Renamed on GitLab"

        return message_format

    elif queue_name in issue_events:
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

        if queue_name == "issue_open":
            message_format["blocks"][0]["text"]["text"] = "Issue Opened on GitLab"
        elif queue_name == "issue_update":
            message_format["blocks"][0]["text"]["text"] = "Issue Updated on GitLab"
        elif queue_name == "issue_close":
            message_format["blocks"][0]["text"]["text"] = "Issue Closed on GitLab"
        elif queue_name == "issue_reopen":
            message_format["blocks"][0]["text"]["text"] = "Issue Reopened on GitLab"

        return message_format

    elif queue_name in group_events:
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
                        {"type": "mrkdwn", "text": f"*Created At:*\n{created_at_str}"},
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

        if queue_name == "group_create":
            message_format["blocks"][0]["text"]["text"] = "Group Created on GitLab"
        elif queue_name == "group_rename":
            message_format["blocks"][0]["text"]["text"] = "Group Renamed on GitLab"

    elif queue_name in issue_note_events:
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
                        {"type": "mrkdwn", "text": f"*Created At:*\n{created_at_str}"},
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

        if queue_name == "issue_note_create":
            message_format["blocks"][0]["text"]["text"] = "Issue Note Created on GitLab"
        elif queue_name == "issue_note_update":
            message_format["blocks"][0]["text"]["text"] = "Issue Note Updated on GitLab"

    elif queue_name in project_events:
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
                        {"type": "mrkdwn", "text": f"*Created At:*\n{created_at_str}"},
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

        if queue_name == "project_create":
            message_format["blocks"][0]["text"]["text"] = "Project Created on GitLab"
        elif queue_name == "project_rename":
            message_format["blocks"][0]["text"]["text"] = "Project Renamed on GitLab"
        elif queue_name == "project_transfer":
            message_format["blocks"][0]["text"][
                "text"
            ] = "Project Transferred on GitLab"


class SlackNotifier(EventProcessor):
    def __init__(self, slack_webhook_url, queue_prefix, events, redis_conn=None):
        super().__init__(queue_prefix, events, redis_conn)
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

    def process_event(self, queue_name, data):
        data = format_message(queue_name, data)

        with self.notification_latency_histogram.time():
            response = requests.post(self.slack_webhook_url, json=data)

        if response.status_code != 200:
            logging.debug(
                f"Notification service: failed to send message to Slack: {response.status_code}: {response.content}, queue name: {queue_name}, data: {data}"
            )
            self.notification_failures_counter.labels(self.slack_webhook_url).inc()
        else:
            logging.debug("Notification service: successfully sent message to Slack")
            self.notification_counter.labels(self.slack_webhook_url).inc()


def main(
    slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
    redis_conn=None,
    testing=False,
):
    notifier = SlackNotifier(
        slack_webhook_url, "classification", event_types, redis_conn=redis_conn
    )

    while True:
        notifier.retrieve_event()

        if testing:
            break


if __name__ == "__main__":
    REDIS_SENTINEL_ENABLED = os.getenv("REDIS_SENTINEL_ENABLED", "False") == "True"
    REDIS_MASTER_SET = os.getenv("REDIS_MASTER_SET") or "mymaster"
    REDIS_SENTINEL_HOSTS = os.getenv("REDIS_SENTINEL_HOSTS") or None
    REDIS_SENTINEL_PASSWORD = os.getenv("REDIS_SENTINEL_PASSWORD") or None
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

    sentinel_hosts = [tuple(x.split(":")) for x in REDIS_SENTINEL_HOSTS.split(",")]

    if REDIS_SENTINEL_ENABLED:
        try:
            sentinel_kwargs = {}
            master_for_kwargs = {"db": REDIS_DB}

            if REDIS_PASSWORD:
                master_for_kwargs["password"] = REDIS_PASSWORD

            if REDIS_SENTINEL_PASSWORD:
                sentinel_kwargs["password"] = REDIS_SENTINEL_PASSWORD

            sentinel = redis.Sentinel(
                [sentinel_hosts[0]],
                sentinel_kwargs=sentinel_kwargs,
            )

            r = sentinel.master_for(
                REDIS_MASTER_SET, **master_for_kwargs
            )

            r.ping()
            logging.info(f"Successfully connected to Redis sentinel: {sentinel_hosts[0]}")

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

    main(
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        redis_conn=r,
        testing=False,
    )
