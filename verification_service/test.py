import unittest
from unittest.mock import patch
import json
from main import process_events
from time import sleep

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
        if key in self.cache and isinstance(self.cache[key], list) and len(self.cache[key]) > 0:
            # print(f"lpop: {self.cache[key]}")
            return self.cache[key].pop(0)
        else:
            return None

    def exists(self, key):
        if key in self.cache:
            return 1
        return 0

    def cache_overwrite(self, cache=dict()):
        self.cache = cache

class TestVerificationService(unittest.TestCase):

    def setUp(self):
        self.redis_mock = MockRedis()
        self.redis_class_patch = patch("redis.StrictRedis", autospec=True)
        self.sleep_patch = patch("main.sleep", side_effect=self.mock_sleep)
        
        # Start patches
        self.mock_redis_class = self.redis_class_patch.start()
        self.mock_sleep = self.sleep_patch.start()

    def tearDown(self):
        # Stop patches
        self.redis_class_patch.stop()
        self.sleep_patch.stop()

    # Counter for the number of times mock_sleep is called
    sleep_counter = 0

    def mock_sleep(self, time_to_sleep):
        self.sleep_counter += 1
        print(f"Sleeping for 1 second...")
        if self.sleep_counter > 3:
            raise KeyboardInterrupt()

    def test_process_events(self):

        event_types = ['project_create', 'project_rename', 'project_transfer', 'user_create', 'user_rename','issue_open', 'issue_reopen', 'issue_update', 'issue_close', 'issue_note_create']
        email_replacements = ["js@blbla.gov", "js@gitlabhq.com"]
        test_cases = []
        json_data = {}

        for event_type in event_types:
            # load json data from file
            with open(f'test_json_data/{event_type}.json', 'r') as file:
                data = json.load(file)
            json_data[event_type] = json.dumps(data)

            # true cases, i.e. not verified
            test_cases.append((
                f"event_{event_type}",
                json_data[event_type],
                f"verification_{event_type}",
                True
            ))

            # false cases, i.e. verified domains / users
            for replacement in email_replacements:
                test_cases.append((
                    f"event_{event_type}",
                    json_data[event_type].replace("js@blbla.com", replacement),
                    f"verification_{event_type}",
                    False
                ))

        for input_event_type, event_data, output_event_type, output_value_expected in test_cases:
            with self.subTest(input_event_type=input_event_type, 
                            event_data=event_data, 
                            output_event_type=output_event_type, 
                            output_value_expected=output_value_expected):

                mock_redis = MockRedis()
                self.mock_redis_class.return_value = mock_redis

                mock_redis.lpush(input_event_type, event_data)

                try:
                    process_events(verified_domains_file="verified_domains.yaml", 
                                verified_users_file="verified_users.yaml")
                except KeyboardInterrupt:
                    pass

                output_value = mock_redis.get(output_event_type)
                if output_value_expected:
                    self.assertIsNotNone(output_value)
                    self.assertIn(event_data, output_value)
                else:
                    if output_value is not None:
                        self.assertNotIn(event_data, output_value)

if __name__ == '__main__':
    unittest.main()
