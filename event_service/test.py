import unittest
import json
from sanic_testing import TestManager
import logging
import fakeredis
from common.constants import (
    UserEvent,
    ProjectEvent,
    GroupEvent,
    SnippetEvent,
    IssueNoteEvent,
    IssueEvent,
)
from event_service.main import create_app

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class TestEventService(unittest.TestCase):
    def setUp(self):
        self.redis_mock = fakeredis.FakeRedis()
        self.app = create_app("TestApp", redis_conn=self.redis_mock, testing=True)
        self.test_manager = TestManager(self.app)

    def test_handle_event_types(self):
        json_data = {}
        test_cases = []

        all_event_types = [
            e.value for e in UserEvent
        ] + [
            e.value for e in ProjectEvent
        ] + [
            e.value for e in GroupEvent
        ] + [
            e.value for e in IssueEvent
        ] + [
            e.value for e in IssueNoteEvent
        ] + [
            e.value for e in SnippetEvent
        ]

        for event_type in all_event_types:
            with open(f"test/json_data/{event_type}.json", "r") as file:
                data = json.load(file)
            json_data[event_type] = json.dumps(data)

            test_cases.append(
                (
                    event_type,
                    json_data[event_type]
                )
            )

        for (
            event_type,
            event_data,
        ) in test_cases:
            with self.subTest(
                input_event_type=event_type,
                event_data=event_data,
                output_event_type=event_type,
            ):
                logging.info(f"Testing event type: {event_type}")
                print(f"Testing event type: {event_type}")

                print(f"Sending request to event service. Output queue length: {self.redis_mock.xlen('event')}")
                request, response = self.test_manager.test_client.post(
                    "/event", data=event_data
                )

                self.assertEqual(response.status, 200)
                self.assertDictEqual(response.json, {"message": "Event received"})

                messages = self.redis_mock.xread({"event": '0'}, block=1000, count=1)
                if messages:
                    for message in messages[0][1]:
                        for key in message[1].keys():
                            decoded_value = message[1][key].decode('utf-8')

                            self.assertIsNotNone(decoded_value)
                            self.assertIn(event_data, decoded_value)

                            print("Deleting message %s from output queue", message[0])
                            self.redis_mock.xtrim('event', maxlen=0)
                
                print


if __name__ == "__main__":
    unittest.main()
