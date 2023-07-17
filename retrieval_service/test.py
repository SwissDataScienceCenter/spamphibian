import unittest
from unittest.mock import patch, MagicMock
import json
import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

from retrieval_service.main import retrieve_gitlab_objects

from test.mock_redis import MockRedis

class TestService(unittest.TestCase):

    @patch('gitlab.Gitlab')
    def test_retrieve_gitlab_objects(self, mock_gitlab):
        redis_conn = MockRedis()

        mock_gl = MagicMock()
        mock_gitlab.return_value = mock_gl

        mock_user = MagicMock()
        mock_user.to_json.return_value = json.dumps({"user_id": "123"})
        mock_gl.users.get.return_value = mock_user

        redis_conn.lpush("verification_user_create", json.dumps({"user_id": "123"}))

        retrieve_gitlab_objects('https://gitlab.com', 'token', redis_conn, testing=True)

        mock_gitlab.assert_called_once_with('https://gitlab.com', private_token='token')
        mock_gl.users.get.assert_called_once_with("123")
        self.assertEqual(redis_conn.lpop("retrieval_user_create"), json.dumps({"user_id": "123"}))

if __name__ == '__main__':
    unittest.main()
