import logging
import os
import re
import json
import redis
import requests
import yaml
from time import sleep
from prometheus_client import start_http_server, Counter, Gauge

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

project_events = [
    "project_create",
    "project_rename",
    "project_transfer",
]

user_events = [
    "user_create",
    "user_rename",
]

issue_events = [
    "issue_open",
    "issue_update",
    "issue_close",
    "issue_reopen",
]

issue_note_events = [
    "issue_note_create",
    "issue_note_update",
]

group_events = [
    "group_create",
    "group_rename",
]

snippet_events = [
    "snippet_check",
]

# Define Prometheus metrics
processed_events_total = Counter(
    "processed_events_total", "Total number of processed events"
)
verified_events_total = Counter(
    "verified_events_total", "Total number of verified events"
)
queue_length = Gauge("queue_length", "Current number of events in the queue")


def check_domain_verification(email, verified_domains_file):
    with open(verified_domains_file, "r") as file:
        verified_domains = yaml.safe_load(file)["domains"]

    for domain in verified_domains:
        if re.search(domain, email):
            return True
    return False


def check_user_verification(email, verified_users_file):
    with open(verified_users_file, "r") as file:
        verified_users = yaml.safe_load(file)["users"]

    for verified_user in verified_users:
        if verified_user == email:
            return True
    return False


def get_user_email_address(event_type, event_data):
    if event_type in project_events:
        return event_data.get("owner_email")

    elif event_type in user_events:
        return event_data.get("email")

    elif event_type in issue_events + issue_note_events:
        user_attributes = event_data.get("user", {})
        return user_attributes.get("email")

    else:
        logging.debug(
            f"Unable to get user email address for this event type: {event_type}"
        )
        return None


def process_events(
    verified_users_file, verified_domains_file, gitlab_url, gitlab_access_token
):
    redis_conn = redis.StrictRedis(host="localhost", port=6379, db=0)

    event_types = (
        user_events
        + project_events
        + issue_events
        + issue_note_events
        + group_events
        + snippet_events
    )

    while True:
        for event_type in event_types:
            event = redis_conn.lpop("event_" + event_type)

            if event is None:
                continue

            logging.info(f"Processing event {event_type}")

            processed_events_total.inc()  # Increment the processed events counter

            event_data = json.loads(event)

            user_email_address = None

            user_verified = False

            if (
                event_type
                in project_events + user_events + issue_events + issue_note_events
            ):
                user_email_address = get_user_email_address(event_type, event_data)

            elif event_type in group_events:
                logging.info(
                    f"{event_type} event type received, need to get user email from GitLab API"
                )

                group_id = event_data.get("group_id")

                response = requests.get(
                    f"{gitlab_url}/api/v4/groups/{group_id}/members/all",
                    headers={"PRIVATE-TOKEN": f"{gitlab_access_token}"},
                )

                try:
                    group_members = response.json()
                except ValueError:
                    logging.debug("Failed to decode JSON from response")
                    return

                if not isinstance(group_members, list):
                    logging.debug("Unexpected response from server")
                    return

                for member in group_members:
                    if member.get("access_level") == 50:
                        user_email_address = member.get("email")
                        break

            if user_email_address is None and event_type != "snippet_check":
                logging.debug(
                    f"Unable to get user email address for this event type: {event_type}"
                )
                continue
            elif user_email_address is not None and event_type != "snippet_check":
                user_verified = check_domain_verification(
                    user_email_address, verified_domains_file
                )

                logging.info(
                    f"User email address {user_email_address} domain verification status: {user_verified}"
                )

                if not user_verified:
                    user_verified = check_user_verification(
                        user_email_address, verified_users_file
                    )
                    logging.info(
                        f"User email address {user_email_address} user verification status: {user_verified}"
                    )

            elif event_type != "snippet_check":
                logging.info(
                    f"Snippet check event type received, individual snippet verification will be done at a later point by the GitLab Item Retrieval Service. Passing event to the next queue."
                )

            if user_verified:
                verified_events_total.inc()  # Increment the verified events counter
                continue

            queue_name = "verification_" + event_type
            redis_conn.lpush(queue_name, json.dumps(event_data))

        # Update the queue length gauge
        queue_length.set(redis_conn.llen("event_" + event_type))

        sleep(1)


if __name__ == "__main__":
    # Start the metrics server
    start_http_server(8001)

    process_events(
        verified_domains_file="verification_service/verified_domains.yaml",
        verified_users_file="verification_service/verified_users.yaml",
        # verified_domains_file="verified_domains.yaml",
        # verified_users_file="verified_users.yaml",
        gitlab_url=os.getenv("GITLAB_URL"),
        gitlab_access_token=os.environ.get("GITLAB_ACCESS_TOKEN"),
    )
