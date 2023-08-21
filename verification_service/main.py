import logging
import os
import re
import redis
import requests
import yaml
from time import sleep
from prometheus_client import Counter, Gauge, make_wsgi_app
from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from threading import Thread

from common.event_processor import EventProcessor

from common.constants import (
    project_events,
    user_events,
    issue_events,
    issue_note_events,
    group_events,
    snippet_events,
    event_types,
)

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define Prometheus metrics
processed_events_total = Counter(
    "processed_events_total", "Total number of processed events"
)
verified_events_total = Counter(
    "verified_events_total", "Total number of verified events"
)
queue_length = Gauge("queue_length", "Current number of events in the queue")

app = Flask(__name__)
metrics = PrometheusMetrics(app)
CONTENT_TYPE_LATEST = str("text/plain; version=0.0.4; charset=utf-8")


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
        f"{email} Domain verification status: {domain_verified}, user verification status: {user_verified}"
    )

    return jsonify(
        {
            "email": email,
            "domain_verified": domain_verified,
            "user_verified": user_verified,
        }
    )


# Add prometheus wsgi middleware to route /metrics requests
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": make_wsgi_app()})


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


class VerificationEventProcessor(EventProcessor):
    def __init__(
        self,
        prefix,
        redis_conn=None,
        verified_users_file=None,
        verified_domains_file=None,
        gitlab_url=None,
        gitlab_access_token=None,
    ):
        super().__init__(prefix, event_types, redis_conn)
        self.verified_users_file = verified_users_file
        self.verified_domains_file = verified_domains_file
        self.gitlab_url = gitlab_url
        self.gitlab_access_token = gitlab_access_token

    def process_event(self, queue_name, data):
        event_type = queue_name.split("_", 1)[-1]

        logging.debug(f"Verification service: processing event {event_type}")

        processed_events_total.inc()

        user_email_address = None
        user_verified = False

        if (
            event_type
            in project_events + user_events + issue_events + issue_note_events
        ):
            user_email_address = get_user_email_address(event_type, data)

        elif event_type in group_events:
            logging.info(
                f"Verification service: {event_type} event type received, need to get user email from GitLab API"
            )
            max_access_level = 0
            user_id_with_max_access = None
            group_id = data.get("group_id")

            response = requests.get(
                f"{self.gitlab_url}/api/v4/groups/{group_id}/members/all",
                headers={"PRIVATE-TOKEN": f"{self.gitlab_access_token}"},
            )

            try:
                group_members = response.json()
            except ValueError:
                logging.debug(
                    "Verification service: failed to decode JSON from response"
                )
                return

            if not isinstance(group_members, list):
                logging.debug("Verification service: unexpected response from server")
                return

            for member in group_members:
                access_level = member.get("access_level")
                if access_level > max_access_level:
                    max_access_level = access_level
                    user_id_with_max_access = member.get("id")
                    user_email_address = member.get("email")

            # If no email address was found in the group_members list, get it from GitLab.
            if not user_email_address and user_id_with_max_access is not None:
                response = requests.get(
                    f"{self.gitlab_url}/api/v4/users/{user_id_with_max_access}",
                    headers={"PRIVATE-TOKEN": f"{self.gitlab_access_token}"},
                )
                user = response.json()
                user_email_address = user.get("email")

        if user_email_address is None and event_type != "snippet_check":
            logging.debug(
                f"Verification service: unable to get user email address for this event type: {event_type}"
            )
            return
        elif user_email_address is not None and event_type != "snippet_check":
            user_verified = check_domain_verification(
                user_email_address, self.verified_domains_file
            )
            logging.info(
                f"Verification service: {user_email_address} domain verification: {user_verified}"
            )

            if not user_verified:
                user_verified = check_user_verification(
                    user_email_address, self.verified_users_file
                )
                logging.info(
                    f"Verification service: {user_email_address} user verification: {user_verified}"
                )

        elif event_type == "snippet_check":
            logging.info(
                f"Verification service: snippet check event type received, individual snippet verification will be done at a later point by the GitLab Item Retrieval Service. Passing event to the next queue."
            )

        if not user_verified:
            self.send_to_queue(event_type, data, prefix="verification")
            logging.debug(
                f"Verification service: pushed event to queue: verification_{event_type}"
            )
        else:
            verified_events_total.inc()
            logging.info(
                f"Verification service: verified event type {event_type} for user {user_email_address}"
            )


def process_events(
    redis_conn=None,
    verified_users_file=None,
    verified_domains_file=None,
    gitlab_url=None,
    gitlab_access_token=None,
):
    processor = VerificationEventProcessor(
        "event",
        redis_conn=redis_conn,
        verified_users_file=verified_users_file,
        verified_domains_file=verified_domains_file,
        gitlab_url=gitlab_url,
        gitlab_access_token=gitlab_access_token,
    )

    while True:
        processor.retrieve_event()
        sleep(1)


def main():
    Thread(target=app.run, kwargs={"port": 8001}).start()

    process_events(
        redis_conn=redis.Redis(host="localhost", port=6379),
        verified_users_file="verification_service/verified_users.yaml",
        verified_domains_file="verification_service/verified_domains.yaml",
        gitlab_url=os.getenv("GITLAB_URL"),
        gitlab_access_token=os.environ.get("GITLAB_ACCESS_TOKEN"),
    )


if __name__ == "__main__":
    # Start the Flask server in a separate thread
    main()
