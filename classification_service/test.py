import unittest
from unittest.mock import patch, MagicMock
from classification_service.main import GitlabUserSpamClassifier
from test.mock_redis import MockRedis
import json


class TestGitlabUserSpamClassifier(unittest.TestCase):
    @patch("classification_service.main.redis.Redis", autospec=True)
    @patch("classification_service.main.requests.post", autospec=True)
    def test_run_with_data_in_queue(self, mock_requests_post, mock_redis):
        redis_conn = MockRedis()

        redis_conn.lpush(
            "retrieval_user_create",
            json.dumps({"username": "test_user", "some_data": "data"}),
        )

        mock_redis.return_value = redis_conn

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"prediction": "spam", "score": 0.9}
        mock_requests_post.return_value = mock_response

        classifier = GitlabUserSpamClassifier(
            redis_conn=redis_conn, base_url="http://test-model-url"
        )
        classifier.run(testing=True)

        expected_url = "http://test-model-url/predict_user_create"
        expected_data = json.dumps({"username": "test_user", "some_data": "data"})

        mock_requests_post.assert_called_once_with(
            expected_url,
            data=expected_data,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(
            redis_conn.lpop("classification_user_create").decode("utf-8"),
            json.dumps(
                {
                    "event_data": {"username": "test_user", "some_data": "data"},
                    "prediction": "spam",
                    "score": 0.9,
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()
