import json
import redis
import time
import logging
import requests

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
    def __init__(self):
        super().__init__("retrieval", user_events, redis_conn=None)

    def process_event(self, queue_name, data):
        logging.debug(f"Classification service: processing event {queue_name}")

        postfix = queue_name.split("_", 1)[-1]

        # Convert dictionary to json
        data_json = json.dumps(data)

        # Define the url for the prediction service
        url = f"http://127.0.0.1:5000/predict_{postfix}"

        # Send the POST request
        response = requests.post(
            url,
            data=data_json,
            headers={"Content-Type": "application/json"},
        )

        logging.debug(f"Classification service: response: {response}")

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
            f"Classification service: results for event {postfix} by {data['username']}: prediction: {prediction}, scores: {score}"
        )

        logging.debug(
            f"Classification service: pushing results to Redis queue classification_{postfix}"
        )

        # Push the results JSON into the relevant Redis queue
        self.send_to_queue(postfix, results, prefix="classification")
    
    def run(self, testing=False):
        while True:
            self.retrieve_event()

            # If testing, break out of the infinite loop
            if testing:
                break

            time.sleep(0.2)



def main():
    classifier = GitlabUserSpamClassifier()
    classifier.run()


if __name__ == "__main__":
    main()
