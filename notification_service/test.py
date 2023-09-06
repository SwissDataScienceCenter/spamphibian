import unittest
from unittest.mock import patch, MagicMock
import json
from test.mock_redis import MockRedis

from notification_service.main import main


class TestSlackNotifier(unittest.TestCase):
    @patch("notification_service.main.requests.post")
    def test_format_message_user_create(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        redis_conn = MockRedis()

        expected_response = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "User Created on GitLab"}
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Username:* test_user\n*Name:* Test User\n*Email:* test_user@example.com"
                    },
                    "accessory": {
                        "type": "image",
                        "image_url": "http://example.not.a.real.url",
                        "alt_text": "avatar"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Spam Classification:* Spam"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Spam Score*: 0.85"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*State:* active\n*Web URL:* <http://example.not.a.real.url|Profile>\n*Bio:* This is a test user"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Website:* <http://example.not.a.real.url|Website>"
                    }
                }
            ]
        }

        queue = "classification_user_create"
        message = json.dumps(
            {
                "event_data": {
                    "username": "test_user",
                    "name": "Test User",
                    "email": "test_user@example.com",
                    "avatar_url": "http://example.not.a.real.url",
                    "state": "active",
                    "website_url": "http://example.not.a.real.url",
                    "web_url": "http://example.not.a.real.url",
                    "bio": "This is a test user",
                },
                "prediction": 1,
                "score": 0.85,
            }
        )

        redis_conn.lpush(queue, message)

        main(redis_conn=redis_conn, slack_webhook_url="http://slack.com", testing=True)

        mock_post.assert_called_once_with("http://slack.com", json=expected_response)


if __name__ == "__main__":
    unittest.main()
