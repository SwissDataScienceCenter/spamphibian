import unittest
from unittest.mock import patch
import json
import responses
import copy
import fakeredis

from verification_service.main import process_events, app


class TestVerificationService(unittest.TestCase):
    def setUp(self):
        self.redis_mock = fakeredis.FakeRedis()
        self.redis_class_patch = patch("redis.StrictRedis", autospec=True)

        # Start patches
        self.mock_redis_class = self.redis_class_patch.start()

    def tearDown(self):
        # Stop patches
        self.redis_class_patch.stop()

    def test_process_events(self):
        event_types = [
            "project_create",
            "project_rename",
            "project_transfer",
            "user_create",
            "user_rename",
            "issue_open",
            "issue_reopen",
            "issue_update",
            "issue_close",
            "issue_note_create",
            "group_create",
            "group_rename",
            "snippet_check",
        ]
        email_replacements = [
            "user@verified-domain.gov",
            "verified-user@non-verified-domain.com",
        ]
        mock_api_responses = {}
        test_cases = []
        json_data = {}

        with open("test/json_data/group_members_response.json", "r") as file:
            group_members_response = json.load(file)

        webhook_event_types = [
            event_type for event_type in event_types if event_type != "snippet_check"
        ]

        for event_type in webhook_event_types:
            # load json data from file
            with open(f"test/json_data/{event_type}.json", "r") as file:
                data = json.load(file)
            json_data[event_type] = json.dumps(data)

            # true cases, i.e. not verified
            test_cases.append(
                (
                    event_type,
                    json_data[event_type],
                    True,
                )
            )

            # false cases, i.e. verified domains / users
            if event_type == "group_create":
                for group_id in ["2", "3"]:
                    test_cases.append(
                        (
                            "group_create",
                            json_data[event_type].replace("1", group_id),
                            False,
                        )
                    )

                    mock_api_responses["group_create_1"] = copy.deepcopy(
                        group_members_response
                    )

                    patched_data = copy.deepcopy(group_members_response)
                    patched_data[1]["email"] = patched_data[1]["email"].replace(
                        "non-verified-user@non-verified-domain.com",
                        "user@verified-domain.gov",
                    )
                    mock_api_responses["group_create_2"] = patched_data

                    patched_data = copy.deepcopy(patched_data)
                    patched_data[1]["email"] = patched_data[1]["email"].replace(
                        "user@verified-domain.gov",
                        "verified-user@non-verified-domain.com",
                    )
                    mock_api_responses["group_create_3"] = patched_data

            elif event_type == "group_rename":
                for group_id in ["6", "7"]:
                    test_cases.append(
                        (
                            "group_rename",
                            json_data[event_type].replace("5", group_id),
                            False,
                        )
                    )

                mock_api_responses["group_rename_5"] = copy.deepcopy(
                    group_members_response
                )

                patched_data = copy.deepcopy(group_members_response)
                patched_data[1]["email"] = patched_data[1]["email"].replace(
                    "non-verified-user@non-verified-domain.com",
                    "user@verified-domain.gov",
                )
                mock_api_responses["group_rename_6"] = patched_data

                patched_data = copy.deepcopy(patched_data)
                patched_data[1]["email"] = patched_data[1]["email"].replace(
                    "user@verified-domain.gov", "verified-user@non-verified-domain.com"
                )
                mock_api_responses["group_rename_7"] = patched_data

            else:
                for replacement in email_replacements:
                    test_cases.append(
                        (
                            event_type,
                            json_data[event_type].replace(
                                "non-verified-user@non-verified-domain.com", replacement
                            ),
                            False,
                        )
                    )

        # Test case for snippet check
        # load json data from file
        with open("test/json_data/snippet_check.json", "r") as file:
            data = json.load(file)
        json_data["snippet_check"] = json.dumps(data)

        test_cases.append(
            (
                "snippet_check",
                json_data["snippet_check"],
                True,
            )
        )

        # Set up mock API responses for group members queries
        group_id_to_key = {
            1: "group_create_1",
            2: "group_create_2",
            3: "group_create_3",
            5: "group_rename_5",
            6: "group_rename_6",
            7: "group_rename_7",
        }

        for group_id, key in group_id_to_key.items():
            responses.add(
                responses.GET,
                f"http://gitlab.com/api/v4/groups/{group_id}/members/all",
                json=mock_api_responses[key],
                status=200,
            )

        responses.start()

        for (
            event_type,
            event_data,
            output_value_expected,
        ) in test_cases:
            with self.subTest(
                event_type=event_type,
                event_data=event_data,
                output_value_expected=output_value_expected,
            ):
                print(f"Testing event type: {event_type}, output value expected: {output_value_expected}")

                self.redis_mock.xadd("event", {event_type: json.dumps(event_data)})

                try:
                    print(f"Start processing event: {event_type}. Input stream messages: {self.redis_mock.xlen('event')} Output stream messages: {self.redis_mock.xlen('verification')}")
                    process_events(
                        verified_domains_file="verification_service/verified_domains.yaml",
                        verified_users_file="verification_service/verified_users.yaml",
                        gitlab_url="http://gitlab.com",
                        gitlab_access_token="1234567890",
                        redis_conn=self.redis_mock,
                        testing=True,
                    )
                    print(f"Finished processing event: {event_type}. Input stream messages: {self.redis_mock.xlen('event')} Output stream messages: {self.redis_mock.xlen('verification')}")

                    if output_value_expected == False:
                        queue_length = self.redis_mock.xlen('verification')
                        if queue_length > 0:
                            print("Output stream contains unexpected message(s): ", self.redis_mock.xrange('verification', count=queue_length))
                        self.assertEqual(self.redis_mock.xlen('verification'), 0)
                    else:
                        messages = self.redis_mock.xread({"verification": '0'}, block=1000, count=1)
                        if messages:
                            for message in messages[0][1]:
                                for key in message[1].keys():
                                    decoded_key = key.decode('utf-8')
                                    decoded_value = json.loads(message[1][key].decode('utf-8'))

                                    print(f"Message in output stream arrived: {decoded_key}")

                                    self.assertIsNotNone(decoded_value)
                                    self.assertIn(event_data, decoded_value)

                                    print("Clearing all messages from output stream")
                                    self.redis_mock.xtrim('verification', maxlen=0)

                    print("\n-----------------\n")
                except KeyboardInterrupt:
                    pass




class TestEmailVerificationAPI(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()

    def test_email_verification_api(self):
        test_cases = [
            ("verified-user@non-verified-domain.com", False, True),
            ("user@verified-domain.gov", True, False),
            ("non-verified-user@non-verified-domain.com", False, False),
        ]

        for (
            email_address,
            domain_verified,
            user_verified,
        ) in test_cases:
            with self.subTest(
                email_address=email_address,
                domain_verified=domain_verified,
                user_verified=user_verified,
            ):
                response = self.client.post(
                    "/verify_email",
                    json={"email": email_address},
                    follow_redirects=True,
                )
                self.assertEqual(response.status_code, 200)
                json_data = response.get_json()

                # check if response is as expected
                self.assertEqual(json_data.get("email"), email_address)
                self.assertEqual(json_data.get("domain_verified"), domain_verified)
                self.assertEqual(json_data.get("user_verified"), user_verified)


if __name__ == "__main__":
    unittest.main()
