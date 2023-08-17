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

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class GitlabUserSpamClassifier:
    def __init__(self):
        self.redis_client = redis.Redis(host="localhost", port=6379, db=0)
        self.user_event_queue_names = []

        for user_event_type in user_events:
            self.user_event_queue_names.append(f"retrieval_{user_event_type}")

    def run(self, testing=False):
        while True:
            for queue_name in self.user_event_queue_names:
                data = self.redis_client.lpop(queue_name)
                if data:
                    logging.debug(
                        f"Classification service: processing event {queue_name}"
                    )

                    postfix = queue_name.split("_", 1)[-1]

                    data = json.loads(data.decode("utf-8"))

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

                    # Print the prediction
                    print(response)

                    prediction = response.json()["prediction"]

                    score = round(response.json()["score"], 3)

                    results = {
                        "event_data": data,
                        "prediction": prediction,
                        "score": score,
                    }

                    results_json = json.dumps(results)

                    new_list_name = "classification_" + postfix

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
                        f"Classification service: pushing results to Redis queue {new_list_name}"
                    )

                    # Push the results JSON string into the relevant Redis queue
                    self.redis_client.lpush(new_list_name, results_json)

            # If testing, break out of the infinite loop
            if testing:
                break

            time.sleep(0.2)


def main():
    classifier = GitlabUserSpamClassifier()
    classifier.run()


if __name__ == "__main__":
    main()
