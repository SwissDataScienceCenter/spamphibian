import json
import logging
import requests
import os

from common.event_processor import EventProcessor

from prometheus_client import multiprocess, CollectorRegistry, Counter, Histogram

LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(
    level=LOGLEVEL, format="%(asctime)s - %(levelname)s - Classification service: %(message)s"
)


class GitlabUserSpamClassifier(EventProcessor):
    def __init__(self, redis_conn=None, model_url="http://127.0.0.1:5001"):
        super().__init__("retrieval", "classification", redis_conn=redis_conn)
        self.model_url = model_url

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

    def process_event(self, event_type, data):
        logging.debug(f"processing event {event_type}")

        data_json = json.dumps(data)

        url = f"{self.model_url}/predict_{event_type}"

        response = None
        with self.request_latency.time():
            try:
                response = requests.post(
                    url,
                    data=data_json,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
            except requests.Timeout:
                print("The request timed out")

        if response is None:
            self.failed_requests.inc()
            logging.critical("Model did not respond")
            exit(1)

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
                "event_type": event_type,
                "prediction": prediction,
                "score": score,
            }
        )

        self.push_event_to_queue(event_type, results)

        self.event_types.labels(type=event_type).inc()

    def run(self, testing=False):
        self.poll_and_process_event(testing=testing)


def main():
    classifier = GitlabUserSpamClassifier(model_url=os.getenv("MODEL_URL"))
    classifier.run()


if __name__ == "__main__":
    main()
