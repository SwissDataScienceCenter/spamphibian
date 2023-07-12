import json
import redis
import requests
import os

# Configure the Redis queue you want to monitor
queue_names = ["retrieval_user_create", "retrieval_user_rename"]

# Configure your Slack webhook URL
slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")

# Create a connection to the Redis server
r = redis.Redis(host="localhost", port=6379)

def format_message(queue, message):
    # Parse the JSON data
    data = json.loads(message)
    
    if queue == "retrieval_user_create":
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"User Created on GitLab:"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Username:* {data['username']}\n*Name:* {data['name']}\n*Profile URL:* <{data['web_url']}|Link>"
                    },
                    "accessory": {
                        "type": "image",
                        "image_url": data['avatar_url'],
                        "alt_text": "User avatar"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Email:* {data['email']}\n*Bio:* {data['bio']}\n*Admin Status:* {'Yes' if data['is_admin'] else 'No'}"
                    }
                }
            ]
        }
    elif queue == "retrieval_user_rename":
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"User Renamed on GitLab:"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Username:* {data['username']}\n*Name:* {data['name']}\n*Profile URL:* <{data['web_url']}|Link>"
                    },
                    "accessory": {
                        "type": "image",
                        "image_url": data['avatar_url'],
                        "alt_text": "User avatar"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Email:* {data['email']}\n*Sign In Count:* {data['sign_in_count']}\n*Admin Status:* {'Yes' if data['is_admin'] else 'No'}"
                    }
                }
            ]
        }
            

while True:
    queue, message = r.brpop(queue_names, 0)

    message = message.decode("utf-8")

    data = format_message(queue.decode("utf-8"), message)

    response = requests.post(slack_webhook_url, json=data)

    if response.status_code != 200:
        print(f"Failed to send message to Slack: {response.content}")
