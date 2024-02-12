import unittest
from common.event_processor import EventProcessor
import fakeredis
import json
from common.constants import UserEvent

class TestEventProcessor(unittest.TestCase):

    def setUp(self):
        self.redis_conn = fakeredis.FakeRedis()
        self.event_processor = EventProcessor("retrieval", "classification", self.redis_conn)
    
    def test_initialization_with_redis_conn(self):
        self.assertEqual(self.event_processor.redis_client, self.redis_conn)

    def test_poll_and_process_event(self):
        event_data = {"username": "test_user", "some_data": "data"}
        self.redis_conn.xadd("retrieval", {UserEvent.USER_CREATE.value: json.dumps(event_data)})
    
    def test_add_event_to_queue(self):
        event_data = {"test_key": "test_value"}
        self.event_processor.push_event_to_queue(UserEvent.USER_CREATE.value, event_data)

        while True:
            messages = self.redis_conn.xread({self.event_processor.output_stream_name: '0'}, block=10000, count=1)
            if not messages:
                continue
            for message in messages[0][1]:
                message_id = message[0]
                for key in message[1].keys():
                    popped_data = json.loads(message[1][key].decode('utf-8'))

                    self.redis_conn.xdel(self.event_processor.output_stream_name, message_id)

                    self.assertEqual(popped_data, event_data)

                return

    def test_process_event_raises_error(self):
        with self.assertRaises(NotImplementedError):
            self.event_processor.process_event(None, None)

if __name__ == '__main__':
    unittest.main()
