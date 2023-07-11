import unittest
import json
from unittest.mock import patch
from sanic_testing import TestManager

from main import create_app

class MockRedis:
    def __init__(self, cache=dict()):
        self.cache = cache

    def get(self, key):
        if key in self.cache:
            return self.cache[key]
        return None  # return nil

    def set(self, key, value, *args, **kwargs):
        if self.cache:
            self.cache[key] = value
            return "OK"
        return None  # return nil in case of some issue

    def hget(self, hash, key):
        if hash in self.cache:
            if key in self.cache[hash]:
                return self.cache[hash][key]
        return None  # return nil

    def hset(self, hash, key, value, *args, **kwargs):
        if self.cache:
            self.cache[hash][key] = value
            return 1
        return None  # return nil in case of some issue

    def lpush(self, key, value):
        # Simulate the LPUSH command in Redis
        # print(f"lpush: {key} {value}")
        if key not in self.cache:
            self.cache[key] = []
        self.cache[key].insert(0, value)

    def lpop(self, key):
        # Simulate the LPOP command in Redis
        if (
            key in self.cache
            and isinstance(self.cache[key], list)
            and len(self.cache[key]) > 0
        ):
            # print(f"lpop: {self.cache[key]}")
            return self.cache[key].pop(0)
        else:
            return None
    
    def lpeek(self, key):
        if key in self.cache and isinstance(self.cache[key], list) and len(self.cache[key]) > 0:
            return self.cache[key][0]
        else:
            return None

    def exists(self, key):
        if key in self.cache:
            return 1
        return 0

    def cache_overwrite(self, cache=dict()):
        self.cache = cache

class TestEventService(unittest.TestCase):

    def setUp(self):
        self.redis_mock = MockRedis()
        self.redis_class_patch = patch("redis.StrictRedis", return_value=self.redis_mock, autospec=True)
        self.mock_redis_class = self.redis_class_patch.start()
        self.app = create_app('TestApp')
        self.test_manager = TestManager(self.app)

    def tearDown(self):
        # Stop patches
        self.redis_class_patch.stop()

    def test_handle_event_project_create(self):
        # load json data from file
        with open(f"../test_json_data/project_create.json", "r") as file:
            event = json.load(file)

        self.mock_redis_class.return_value = self.redis_mock

        request, response = self.test_manager.test_client.post('/event', data=json.dumps(event))

        self.assertEqual(response.status, 200)
        self.assertDictEqual(response.json, {'message': 'Event received'})

        output_value = self.redis_mock.get('event_project_create')
        print(f"Output value: {output_value}")
        self.assertIsNotNone(output_value)
        self.assertIn(json.dumps(event), output_value)

if __name__ == '__main__':
    unittest.main()
