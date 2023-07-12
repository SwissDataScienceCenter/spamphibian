import unittest
from unittest.mock import patch
import json
from time import sleep
import responses
import copy

from main import process_events, app


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

    def exists(self, key):
        if key in self.cache:
            return 1
        return 0

    def cache_overwrite(self, cache=dict()):
        self.cache = cache

    def llen(self, key):
        # Simulate the LLEN command in Redis
        if key in self.cache and isinstance(self.cache[key], list):
            return len(self.cache[key])
        else:
            return 0


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

        with open(f"../test_json_data/group_members_response.json", "r") as file:
            group_members_response = json.load(file)

        webhook_event_types = [
            event_type for event_type in event_types if event_type != "snippet_check"
        ]

        for event_type in webhook_event_types:
            # load json data from file
            with open(f"../test_json_data/{event_type}.json", "r") as file:
                data = json.load(file)
            json_data[event_type] = json.dumps(data)

            # true cases, i.e. not verified
            test_cases.append(
                (
                    f"event_{event_type}",
                    json_data[event_type],
                    f"verification_{event_type}",
                    True,
                )
            )

            # false cases, i.e. verified domains / users
            if event_type == "group_create":
                for group_id in ["2", "3"]:
                    test_cases.append(
                        (
                            "event_group_create",
                            json_data[event_type].replace("1", group_id),
                            "verification_group_create",
                            False,
                        )
                    )

                    mock_api_responses["event_group_create_1"] = copy.deepcopy(
                        group_members_response
                    )

                    patched_data = copy.deepcopy(group_members_response)
                    patched_data[1]["email"] = patched_data[1]["email"].replace(
                        "non-verified-user@non-verified-domain.com",
                        "user@verified-domain.gov",
                    )
                    mock_api_responses["event_group_create_2"] = patched_data

                    patched_data = copy.deepcopy(patched_data)  # Make a new deep copy
                    patched_data[1]["email"] = patched_data[1]["email"].replace(
                        "user@verified-domain.gov",
                        "verified-user@non-verified-domain.com",
                    )
                    mock_api_responses["event_group_create_3"] = patched_data

            elif event_type == "group_rename":
                for group_id in ["6", "7"]:
                    test_cases.append(
                        (
                            f"event_group_rename",
                            json_data[event_type].replace("5", group_id),
                            f"verification_group_rename",
                            False,
                        )
                    )

                mock_api_responses["event_group_rename_5"] = copy.deepcopy(
                    group_members_response
                )

                patched_data = copy.deepcopy(group_members_response)
                patched_data[1]["email"] = patched_data[1]["email"].replace(
                    "non-verified-user@non-verified-domain.com",
                    "user@verified-domain.gov",
                )
                mock_api_responses["event_group_rename_6"] = patched_data

                patched_data = copy.deepcopy(patched_data)
                patched_data[1]["email"] = patched_data[1]["email"].replace(
                    "user@verified-domain.gov", "verified-user@non-verified-domain.com"
                )
                mock_api_responses["event_group_rename_7"] = patched_data

            else:
                for replacement in email_replacements:
                    test_cases.append(
                        (
                            f"event_{event_type}",
                            json_data[event_type].replace(
                                "non-verified-user@non-verified-domain.com", replacement
                            ),
                            f"verification_{event_type}",
                            False,
                        )
                    )

        # Test case for snippet check

        # load json data from file
        with open(f"../test_json_data/snippet_check.json", "r") as file:
            data = json.load(file)
        json_data["snippet_check"] = json.dumps(data)

        test_cases.append(
            (
                f"event_snippet_check",
                json_data["snippet_check"],
                f"verification_snippet_check",
                True,
            )
        )

        # Set up mock API responses for group members queries
        group_id_to_key = {
            1: "event_group_create_1",
            2: "event_group_create_2",
            3: "event_group_create_3",
            5: "event_group_rename_5",
            6: "event_group_rename_6",
            7: "event_group_rename_7",
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
            input_event_type,
            event_data,
            output_event_type,
            output_value_expected,
        ) in test_cases:
            with self.subTest(
                input_event_type=input_event_type,
                event_data=event_data,
                output_event_type=output_event_type,
                output_value_expected=output_value_expected,
            ):
                mock_redis = MockRedis()
                self.mock_redis_class.return_value = mock_redis

                mock_redis.lpush(input_event_type, event_data)

                try:
                    process_events(
                        verified_domains_file="verified_domains.yaml",
                        verified_users_file="verified_users.yaml",
                        gitlab_url="http://gitlab.com",
                        gitlab_access_token="1234567890",
                    )
                except KeyboardInterrupt:
                    pass

                output_value = mock_redis.get(output_event_type)
                if output_value_expected:
                    self.assertIsNotNone(output_value)
                    self.assertIn(event_data, output_value)
                else:
                    if output_value is not None:
                        self.assertNotIn(event_data, output_value)


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

    def test_metrics_endpoint(self):
        response = self.client.get("/metrics", follow_redirects=True)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
