import unittest
from common.event_processor import EventProcessor
from test.mock_redis import MockRedis
import json

class TestEventProcessor(unittest.TestCase):

    def setUp(self):
        self.redis_conn = MockRedis()
        self.event_processor = EventProcessor("retrieval", ["user_create"], self.redis_conn)
    
    def test_initialization_with_redis_conn(self):
        self.assertEqual(self.event_processor.redis_client, self.redis_conn)

    def test_poll_and_process_event(self):
        event_data = {"username": "test_user", "some_data": "data"}
        self.redis_conn.lpush("retrieval_user_create", json.dumps(event_data))
    
    def test_push_event_to_queue(self):
        event_data = {"test_key": "test_value"}
        self.event_processor.push_event_to_queue("user_create", event_data, "retrieval")
        
        popped_data = json.loads(self.redis_conn.lpop("retrieval_user_create").decode("utf-8"))
        self.assertEqual(popped_data, event_data)

    def test_process_event_raises_error(self):
        with self.assertRaises(NotImplementedError):
            self.event_processor.process_event(None, None)

if __name__ == '__main__':
    unittest.main()
