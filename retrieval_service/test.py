import unittest
from unittest.mock import patch, MagicMock
import json
import logging
from retrieval_service.main import main
import fakeredis

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

class TestService(unittest.TestCase):
    @patch("gitlab.Gitlab")
    def test_retrieve_gitlab_objects(self, mock_gitlab):
        redis_conn = fakeredis.FakeRedis()

        mock_gl = MagicMock()
        mock_gitlab.return_value = mock_gl

        mock_user = MagicMock()
        mock_user.to_json.return_value = json.dumps({"user_id": "123"})
        mock_gl.users.get.return_value = mock_user

        redis_conn.xadd("verification", {"user_create": json.dumps({"user_id": "123"})})
        print("Pushed message to input stream")

        main(
            GITLAB_URL="https://gitlab.com",
            GITLAB_ACCESS_TOKEN="token",
            redis_conn=redis_conn,
            testing=True,
        )

        print("Polling output stream")

        messages = redis_conn.xread({"retrieval": '0'}, block=1000, count=1)
        if messages:
            for message in messages[0][1]:
                for key in message[1].keys():
                    decoded_key = key.decode('utf-8')
                    decoded_value = json.loads(message[1][key].decode('utf-8'))

                    print(f"Message in output stream arrived: {decoded_key}")
                    print(f"Message value: {decoded_value}")

                    self.assertIsNotNone(decoded_value)

                    mock_gitlab.assert_called_once_with("https://gitlab.com", private_token="token")
                    mock_gl.users.get.assert_called_once_with("123")

                    self.assertEqual(
                        message[1][key],
                        json.dumps({"user_id": "123"}).encode("utf-8"),
                    )

                    print("Clearing all messages from output stream")
                    redis_conn.xtrim('retrieval', maxlen=0)

if __name__ == "__main__":
    unittest.main()
