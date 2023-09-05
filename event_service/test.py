import unittest
import json
from unittest.mock import patch
from sanic_testing import TestManager
import logging

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

from test.mock_redis import MockRedis

from common.constants import event_types

from event_service.main import create_app

class TestEventService(unittest.TestCase):
    def setUp(self):
        self.redis_mock = MockRedis()
        self.app = create_app("TestApp", redis_conn=self.redis_mock, testing=True)
        self.test_manager = TestManager(self.app)

    def test_handle_event_types(self):
        json_data = {}
        test_cases = []

        for event_type in event_types:
            with open(f"test/json_data/{event_type}.json", "r") as file:
                data = json.load(file)
            json_data[event_type] = json.dumps(data)

            test_cases.append(
                (
                    event_type,
                    json_data[event_type],
                    f"event_{event_type}",
                )
            )

        for (
            input_event_type,
            event_data,
            output_event_type,
        ) in test_cases:
            with self.subTest(
                input_event_type=input_event_type,
                event_data=event_data,
                output_event_type=output_event_type,
            ):

                logging.info(f"Testing event type: {input_event_type}")

                request, response = self.test_manager.test_client.post(
                    "/event", data=event_data
                )

                self.assertEqual(response.status, 200)
                self.assertDictEqual(response.json, {"message": "Event received"})

                output_value = self.redis_mock.get(output_event_type)

                logging.debug("Testing: output queue data: %s", output_value)
                self.assertIsNotNone(output_value)
                self.assertIn(event_data, output_value)


if __name__ == "__main__":
    unittest.main()
