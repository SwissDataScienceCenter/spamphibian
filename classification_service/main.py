import json
import redis
import time
import logging
import requests
import os

from common.constants import (
    project_events,
    user_events,
    issue_events,
    issue_note_events,
    group_events,
    snippet_events,
    event_types,
)

from common.event_processor import EventProcessor

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class GitlabUserSpamClassifier(EventProcessor):
    def __init__(self, redis_conn, base_url):
        super().__init__("retrieval", user_events, redis_conn=redis_conn)
        self.base_url = base_url

    def process_event(self, queue_name, data):
        logging.debug(f"Classification service: processing event {queue_name}")

        postfix = queue_name.split("_", 1)[-1]

        # Convert dictionary to json
        data_json = json.dumps(data)

        url = f"{self.base_url}/predict_{postfix}"

        # Send the POST request
        response = requests.post(
            url,
            data=data_json,
            headers={"Content-Type": "application/json"},
        )

        # Check if the request was successful
        if response.status_code != 200:
            logging.error(
                f"Classification service: Unexpected status code {response.status_code} from prediction service. Response text: {response.text}"
            )
            return

        prediction = response.json()["prediction"]

        score = round(response.json()["score"], 3)

        results = {
            "event_data": data,
            "prediction": prediction,
            "score": score,
        }

        logging.debug(
            {
                "Classification service:": "pushing results to Redis queue",
                "username": data["username"],
                "event_type": postfix,
                "prediction": prediction,
                "score": score,
            }
        )

        logging.debug(
            f"Classification service: pushing results to Redis queue classification_{postfix}"
        )
        self.send_to_queue(postfix, results, prefix="classification")

    def run(self, testing=False):
        while True:
            self.retrieve_event()

            if testing:
                break

            time.sleep(0.2)


def main():
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

    MODEL_URL = os.getenv("MODEL_URL", "http://127.0.0.1:5001")

    r = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_PASSWORD
    )

    classifier = GitlabUserSpamClassifier(redis_conn=r, base_url=MODEL_URL)
    classifier.run()


if __name__ == "__main__":
    main()
