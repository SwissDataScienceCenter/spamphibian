import logging
import os
import re
import requests
import yaml
from prometheus_client import multiprocess, CollectorRegistry, Counter
from flask import Flask, request, jsonify
from threading import Thread
import json

from common.event_processor import EventProcessor

from common.constants import (
    UserEvent,
    ProjectEvent,
    GroupEvent,
    SnippetEvent,
    IssueNoteEvent,
    IssueEvent,
)

LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(
    level=LOGLEVEL, format="%(asctime)s - %(levelname)s - Verification service: %(message)s"
)

# Prometheus metrics
prometheus_multiproc_dir = "prometheus_multiproc_dir"

os.makedirs(prometheus_multiproc_dir, exist_ok=True)

registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)

processed_events_total = Counter(
    "verification_service_processed_events_total", "Total number of processed events"
)
verified_events_total = Counter(
    "verification_service_verified_events_total", "Total number of verified events"
)

verification_failures_total = Counter(
    "verification_service_verification_failures_total",
    "Total number of verification failures",
)
gitlab_api_calls_total = Counter(
    "verification_service_gitlab_api_calls_total",
    "Total number of GitLab API calls",
    ["status"],
)
snippet_check_events_total = Counter(
    "verification_service_snippet_check_events_total",
    "Total number of snippet check events processed",
)

# Flask app for verification at a later point in the Spampibian pipeline
# This is used to verify individual snippets that first need to be
# retrieved from GitLab by the retrieval service.
app = Flask(__name__)

CONTENT_TYPE_LATEST = str("text/plain; version=0.0.4; charset=utf-8")


# User email domain verification endpoint
@app.route("/verify_email", methods=["POST"])
def verify_email():
    data = request.get_json()
    email = data.get("email")
    if not email:
        return jsonify({"error": "Missing email"}), 400

    logging.debug(f"Request received on /verify_email for email: {email}")

    domain_verified = check_domain_verification(
        email, "verification_service/verified_domains.yaml"
    )
    user_verified = check_user_verification(
        email, "verification_service/verified_users.yaml"
    )

    logging.debug(
        f"{email} status: Domain: {domain_verified}. User: {user_verified}"
    )

    return jsonify(
        {
            "email": email,
            "domain_verified": domain_verified,
            "user_verified": user_verified,
        }
    )


def check_domain_verification(email, verified_domains_file):
    try:
        with open(verified_domains_file, "r") as file:
            verified_domains = yaml.safe_load(file).get("domains", [])

        for domain in verified_domains:
            if re.search(domain, email):
                return True
    except (FileNotFoundError, yaml.YAMLError, KeyError) as e:
        print(f"Error: {e}")

    return False


def check_user_verification(email, verified_users_file):
    with open(verified_users_file, "r") as file:
        verified_users = yaml.safe_load(file)["users"]

    for verified_user in verified_users:
        if verified_user == email:
            return True
    return False


def get_user_email_address(event_type, event_data):
    if event_type in [e.value for e in ProjectEvent]:
        return event_data.get("owner_email")

    elif event_type in [e.value for e in UserEvent]:
        return event_data.get("email")

    elif event_type in [e.value for e in IssueEvent] or event_type in [e.value for e in IssueNoteEvent]:
        user_attributes = event_data.get("user", {})
        return user_attributes.get("email")

    else:
        logging.debug(
            f"Unable to get user email address for this event type: {event_type}"
        )
        return None


# VerificationEventProcessor class, which inherits from EventProcessor.
# It is used to process events received from redis and push them back
# into redis after processing, if the user or their email domain is
# not verified.
class VerificationEventProcessor(EventProcessor):
    def __init__(
        self,
        input_stream_name,
        output_stream_name,
        redis_conn=None,
        verified_users_file=None,
        verified_domains_file=None,
        gitlab_url=None,
        gitlab_access_token=None,
    ):
        super().__init__(input_stream_name, output_stream_name, redis_conn)
        self.verified_users_file = verified_users_file
        self.verified_domains_file = verified_domains_file
        self.gitlab_url = gitlab_url
        self.gitlab_access_token = gitlab_access_token

    def process_event(self, event_type, data):

        logging.debug(f"Processing event {event_type}")

        processed_events_total.inc()

        user_email_address = None
        user_verified = False

        # Determine how to get the user email address based on event type
        if event_type in [e.value for e in ProjectEvent] \
        or event_type in [e.value for e in UserEvent] \
        or event_type in [e.value for e in IssueEvent] \
        or event_type in [e.value for e in IssueNoteEvent]:
            user_email_address = get_user_email_address(event_type, data)

        # If the event is a group event, get the user email address by
        # getting all members of the group, and then checking the
        # verification status of the user with the highest access
        # level in the group.
        elif event_type in [e.value for e in GroupEvent]:
            logging.info(
                f"{event_type} event type received, getting user email from GitLab API"
            )
            max_access_level = 0
            user_id_with_max_access = None
            group_id = data.get("group_id")

            # Get all members of the group
            response = requests.get(
                f"{self.gitlab_url}/api/v4/groups/{group_id}/members/all",
                headers={"PRIVATE-TOKEN": f"{self.gitlab_access_token}"},
            )

            if response.status_code == 200:
                gitlab_api_calls_total.labels("success").inc()
            else:
                gitlab_api_calls_total.labels("failure").inc()

            try:
                group_members = response.json()
            except ValueError:
                logging.debug(
                    "Failed to decode JSON from response"
                )
                return

            if not isinstance(group_members, list):
                logging.debug("Unexpected response from server")
                return

            # Get the user with the highest access level in the group
            for member in group_members:
                access_level = member.get("access_level")
                if access_level > max_access_level:
                    max_access_level = access_level
                    user_id_with_max_access = member.get("id")
                    user_email_address = member.get("email")

            # If no group member with the highest access level had no
            # public email address present in the list of group members,
            # get it from their GitLab user attributes.
            if not user_email_address and user_id_with_max_access is not None:
                response = requests.get(
                    f"{self.gitlab_url}/api/v4/users/{user_id_with_max_access}",
                    headers={"PRIVATE-TOKEN": f"{self.gitlab_access_token}"},
                )
                user = response.json()
                user_email_address = user.get("email")

        # If an email address is still not located and the event type
        # is not snippet_check, log the situation and return.
        if user_email_address is None and event_type != SnippetEvent.SNIPPET_CHECK.value:
            logging.debug(
                f"Unable to get user email address for event type: {event_type}"
            )
            return

        # If an email address is located, check if the user or their
        # email domain is verified.
        elif user_email_address is not None and event_type != SnippetEvent.SNIPPET_CHECK.value:
            user_verified = check_domain_verification(
                user_email_address, self.verified_domains_file
            )

            if not user_verified:
                user_verified = check_user_verification(
                    user_email_address, self.verified_users_file
                )

            logging.info(
                f"{user_email_address}, domain verification: {user_verified}"
            )

        # Check if the event type is snippet_check.
        elif event_type == SnippetEvent.SNIPPET_CHECK.value:
            logging.info(
                "Snippet check event received."
                "Individual snippet verification will be done at a later point."
                "Passing event to the next service."
            )
            snippet_check_events_total.inc()

        # If the user or their email domain is not verified, push the
        # event to the next service. If the user or their email domain
        # is verified, log the situation and return.
        if not user_verified:
            verification_failures_total.inc()
            self.push_event_to_queue(event_type, data)
            logging.debug(
                f"Pushed event to queue: verification_{event_type}"
            )
        else:
            verified_events_total.inc()
            logging.info(
                f"Verified event type {event_type} for user {user_email_address}"
            )


def process_events(
    redis_conn=None,
    verified_users_file=None,
    verified_domains_file=None,
    gitlab_url=None,
    gitlab_access_token=None,
    testing=False,
):
    processor = VerificationEventProcessor(
        input_stream_name="event",
        output_stream_name="verification",
        redis_conn=redis_conn,
        verified_users_file=verified_users_file,
        verified_domains_file=verified_domains_file,
        gitlab_url=gitlab_url,
        gitlab_access_token=gitlab_access_token,
    )

    print("Verification service starting")
    processor.poll_and_process_event(testing=testing)
    print("Verification service stopping")


def main():
    Thread(target=app.run, kwargs={"port": 8001}).start()

    process_events(
        verified_users_file="verification_service/verified_users.yaml",
        verified_domains_file="verification_service/verified_domains.yaml",
        gitlab_url=os.getenv("GITLAB_URL"),
        gitlab_access_token=os.environ.get("GITLAB_ACCESS_TOKEN"),
    )


if __name__ == "__main__":
    main()
