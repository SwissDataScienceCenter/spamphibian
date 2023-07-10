import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

import json
import redis
from time import sleep
import yaml
import re
import requests
import os


def check_domain_verification(email, verified_domains_file):
    # Load verified domains from yaml file
    with open(verified_domains_file, "r") as file:
        verified_domains = yaml.safe_load(file)["domains"]

    for domain in verified_domains:
        if re.search(domain, email):
            return True
    return False


def check_user_verification(email, verified_users_file):
    # Load verified users from yaml file
    with open(verified_users_file, "r") as file:
        verified_users = yaml.safe_load(file)["users"]

    for verified_user in verified_users:
        if verified_user == email:
            return True
    return False


def get_user_email_address(event_type, event_data):
    if event_type in ["project_create", "project_rename", "project_transfer"]:
        return event_data.get("owner_email")

    elif event_type in ["user_create", "user_rename"]:
        return event_data.get("email")

    elif event_type in [
        "issue_open",
        "issue_update",
        "issue_close",
        "issue_reopen",
        "issue_note_create",
        "issue_note_update",
    ]:
        user_attributes = event_data.get("user", {})
        return user_attributes.get("email")

    else:
        print(f"Unable to get user email address for this event type: {event_type}")
        return None


def process_events(verified_users_file, verified_domains_file):
    # Get GitLab URL and access token from environment variables
    GITLAB_URL = os.getenv("GITLAB_URL")
    GITLAB_ACCESS_TOKEN = os.environ.get("GITLAB_ACCESS_TOKEN")

    redis_conn = redis.StrictRedis(host="localhost", port=6379, db=0)

    # List of event types to listen for
    event_types = [
        "project_create",
        "project_rename",
        "project_transfer",
        "issue_open",
        "issue_close",
        "issue_reopen",
        "issue_update",
        "user_create",
        "user_rename",
        "group_create",
        "group_rename",
        "snippet_check",
        "issue_note_update",
        "issue_note_create",
    ]

    while True:
        for event_type in event_types:
            # Pop the next event off the queue
            event = redis_conn.lpop("event_" + event_type)

            # If there was no event, continue to the next event type
            if event is None:
                continue

            logging.info(f"Processing event {event_type}")

            # Parse the event data from JSON
            event_data = json.loads(event)

            user_email_address = None

            # Perform an action based on the event type
            if event_type in [
                "project_create",
                "project_rename",
                "project_transfer",
                "user_create",
                "user_rename",
                "issue_open",
                "issue_update",
                "issue_close",
                "issue_reopen",
                "issue_note_create",
                "issue_note_update",
            ]:
                user_email_address = get_user_email_address(event_type, event_data)

            elif event_type in ["group_create", "group_rename"]:
                print(
                    f"{event_type} event type received, need to get user email from GitLab API"
                )

                group_id = event_data.get("id")

                response = requests.get(
                    f"{GITLAB_URL}/api/v4/groups/{group_id}/members",
                    headers={"PRIVATE-TOKEN": f"{GITLAB_ACCESS_TOKEN}"},
                )
                group_members = response.json()

                for member in group_members:
                    if member.get("access_level") == 50:
                        user_email_address = member.get("email")
                        break

            ## add snippet_check event type

            if user_email_address is None:
                print(
                    f"Unable to get user email address for this event type: {event_type}"
                )
                continue

            user_verified = check_domain_verification(user_email_address, verified_domains_file)
            print(
                f"User email address {user_email_address} domain verification status: {user_verified}"
            )
            if not user_verified:
                user_verified = check_user_verification(user_email_address, verified_users_file)
                print(
                    f"User email address {user_email_address} user verification status: {user_verified}"
                )

            if user_verified:
                continue

            queue_name = "verification_" + event_type
            redis_conn.lpush(queue_name, json.dumps(event_data))

        # Sleep for a bit before checking the queues again
        sleep(1)


if __name__ == "__main__":
    process_events(verified_domains_file="verification_service/verified_domains.yaml", verified_users_file="verification_service/verified_users.yaml")
