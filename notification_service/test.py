import unittest
from unittest.mock import patch, MagicMock
import json
from test.mock_redis import MockRedis

from notification_service.main import process_queue_message

class TestSlackNotifier(unittest.TestCase):

    @patch("notification_service.main.requests.post")
    def test_format_message_user_create(self, mock_post):

        # Mock successful response from Slack
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        redis_conn = MockRedis()
        
        expected_response = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": "User Created on GitLab"}},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Username:* test_user\n*Name:* Test User\n*Email:* test_user@example.com"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Spam Classification:* Spam"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Spam Score*: 0.85"
                    }
                }
            ]
        }

        queue = "classification_user_create"
        message = json.dumps({
            "event_data": {
                "username": "test_user",
                "name": "Test User",
                "email": "test_user@example.com"
            },
            "prediction": 1,
            "score": 0.85
        })

        redis_conn.lpush(queue, message)

        # Call the function
        process_queue_message(r=redis_conn, slack_webhook_url="http://slack.com", testing=True)

        # Assert that the function made a post request with the expected payload
        mock_post.assert_called_once_with("http://slack.com", json=expected_response)


if __name__ == "__main__":
    unittest.main()
