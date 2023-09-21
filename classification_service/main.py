import json
import logging
import requests
import os
import time

from common.constants import event_types

from common.event_processor import EventProcessor

from prometheus_client import multiprocess, CollectorRegistry, Counter, Histogram

LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(
    level=LOGLEVEL, format="%(asctime)s - %(levelname)s - Classification service: %(message)s"
)


class GitlabUserSpamClassifier(EventProcessor):
    def __init__(self, redis_conn=None, base_url="http://127.0.0.1:5001"):
        super().__init__("retrieval", event_types, redis_conn=redis_conn)
        self.base_url = base_url

        prometheus_multiproc_dir = "prometheus_multiproc_dir"

        os.makedirs(prometheus_multiproc_dir, exist_ok=True)

        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)

        self.score_histogram = Histogram(
            "spam_classifier_scores",
            "Spam score returned by spam classifier",
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self.request_latency = Histogram(
            "spam_classifier_request_latency_seconds",
            "Time taken for spam classifier to respond",
        )

        self.successful_requests = Counter(
            "spam_classifier_successful_requests_total",
            "Number of successful requests to spam classifier",
        )

        self.failed_requests = Counter(
            "spam_classifier_failed_requests_total",
            "Number of failed requests to spam classifier",
        )

        self.event_types = Counter(
            "spam_classifier_event_types_total",
            "Number of events processed by type",
            ["type"],
        )

    def process_event(self, queue_name, data):
        logging.debug(f"processing event {queue_name}")

        postfix = queue_name.split("_", 1)[-1]

        data_json = json.dumps(data)

        url = f"{self.base_url}/predict_{postfix}"

        with self.request_latency.time():
            response = requests.post(
                url,
                data=data_json,
                headers={"Content-Type": "application/json"},
            )

        if response.status_code != 200:
            self.failed_requests.inc()
            logging.error(
                f"Model returned code {response.status_code}",
                f"Response: {response.text}"
            )

            prediction = "N/A"
            score = "0.0"
        else:
            self.successful_requests.inc()

            prediction = response.json()["prediction"]

            score = round(response.json()["score"], 3)

            self.score_histogram.observe(score)

        results = {
            "event_data": data,
            "prediction": prediction,
            "score": score,
        }

        logging.debug(
            {
                "Classification service:": "pushing results to Redis queue",
                "event_type": postfix,
                "prediction": prediction,
                "score": score,
            }
        )

        self.send_to_queue(postfix, results, prefix="classification")

        self.event_types.labels(type=postfix).inc()

    def run(self, testing=False):
        while True:
            self.retrieve_event()

            if testing:
                break

            time.sleep(0.2)


def main():
    classifier = GitlabUserSpamClassifier(base_url=os.getenv("MODEL_URL"))
    classifier.run()


if __name__ == "__main__":
    main()
