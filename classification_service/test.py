import unittest
from unittest.mock import patch, MagicMock
from classification_service.main import GitlabUserSpamClassifier
import json
import fakeredis
from common.constants import UserEvent


class TestGitlabUserSpamClassifier(unittest.TestCase):
    @patch("classification_service.main.GitlabUserSpamClassifier.retry", autospec=True)
    def test_run_with_data_in_queue(self, mock_retry):
        redis_conn = fakeredis.FakeRedis()

        redis_conn.xadd(
            "retrieval",
            {UserEvent.USER_CREATE.value: json.dumps({"username": "test_user", "some_data": "data"})},
        )

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"prediction": 1, "score": 0.9}
        mock_session.post.return_value = mock_response

        # Configure the retry context manager to use the mock session
        mock_retry.return_value.__enter__.return_value = mock_session

        classifier = GitlabUserSpamClassifier(
            redis_conn=redis_conn, model_url="http://test-model-url"
        )
        classifier.run(testing=True)

        expected_url = "http://test-model-url/predict_user_create"
        expected_data = json.dumps({"username": "test_user", "some_data": "data"})

        mock_session.post.assert_called_once_with(
            expected_url,
            data=expected_data,
            headers={"Content-Type": "application/json"},
        )

        messages = redis_conn.xread({"retrieval": '0'}, block=1000, count=1)
        if messages:
            for message in messages[0][1]:
                for key in message[1].keys():
                    decoded_key = key.decode('utf-8')
                    decoded_value = json.loads(message[1][key].decode('utf-8'))

                    expected_key = UserEvent.USER_CREATE.value
                    expected_value ={
                        "event_data": {"username": "test_user", "some_data": "data"},
                        "prediction": "spam",
                        "score": 0.9,
                    }

                    self.assertEqual(decoded_key, expected_key)
                    self.assertEqual(decoded_value, expected_value)


if __name__ == "__main__":
    unittest.main()
