import json
import redis
import requests
import os
import logging
import datetime

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

event_types = (
    user_events
    + project_events
    + issue_events
    + issue_note_events
    + group_events
    + snippet_events
)

queue_names = []

for event_type in event_types:
    queue_names.append(f"classification_{event_type}")

# Get Slack webhook URL from env vars
slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")

# Create a connection to the Redis server
r = redis.Redis(host="localhost", port=6379)


def format_message(queue, message):
    # Parse the JSON data
    data = json.loads(message)

    event_data = data["event_data"]
    prediction = data["prediction"]
    score = data["score"]

    # Convert strings to floats and round the scores to 2 decimal places
    # scores_rounded = {k: round(float(v), 3) for k, v in scores.items()}

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


while True:
    queue, message = r.brpop(queue_names, 0)

    message = message.decode("utf-8")

    data = format_message(queue.decode("utf-8"), message)

    response = requests.post(slack_webhook_url, json=data)

    if response.status_code != 200:
        logging.debug(
            f"Notification service: failed to send message to Slack: {response.content}"
        )
    else:
        logging.debug("Notification service: successfully sent message to Slack")
