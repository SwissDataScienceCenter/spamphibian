import json
import redis
import time
import logging
import requests
import os
import time

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

from prometheus_client import multiprocess, CollectorRegistry, Counter, Histogram, Gauge

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class GitlabUserSpamClassifier(EventProcessor):
    def __init__(self, redis_conn, base_url):
        super().__init__("retrieval", user_events, redis_conn=redis_conn)
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
        logging.debug(f"Classification service: processing event {queue_name}")

        postfix = queue_name.split("_", 1)[-1]

        # Convert dictionary to json
        data_json = json.dumps(data)

        url = f"{self.base_url}/predict_{postfix}"

        with self.request_latency.time():
            response = requests.post(
                url,
                data=data_json,
                headers={"Content-Type": "application/json"},
            )

        # Check if the request was successful
        if response.status_code != 200:
            self.failed_requests.inc()
            logging.error(
                f"Classification service: Unexpected status code {response.status_code} from prediction service. Response text: {response.text}"
            )
            return
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

        self.event_types.labels(type=postfix).inc()

    def run(self, testing=False):
        while True:
            self.retrieve_event()

            if testing:
                break

            time.sleep(0.2)


def main():
    REDIS_SENTINEL_ENABLED = os.getenv("REDIS_SENTINEL_ENABLED", "False") == "True"
    REDIS_MASTER_SET = os.getenv("REDIS_MASTER_SET") or "mymaster"
    REDIS_SENTINEL_HOSTS = os.getenv("REDIS_SENTINEL_HOSTS") or None
    REDIS_SENTINEL_PASSWORD = os.getenv("REDIS_SENTINEL_PASSWORD") or None
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

    sentinel_hosts = [tuple(x.split(":")) for x in REDIS_SENTINEL_HOSTS.split(",")]

    logging.debug("Redis config:")
    logging.debug(f"REDIS_SENTINEL_ENABLED: {REDIS_SENTINEL_ENABLED}")
    logging.debug(f"REDIS_SENTINEL_HOSTS: {REDIS_SENTINEL_HOSTS}")
    logging.debug(f"REDIS_SENTINEL_PASSWORD: {REDIS_SENTINEL_PASSWORD}")
    logging.debug(f"REDIS_MASTER_SET: {REDIS_MASTER_SET}")
    logging.debug(f"REDIS_HOST: {REDIS_HOST}")
    logging.debug(f"REDIS_PORT: {REDIS_PORT}")
    logging.debug(f"REDIS_DB: {REDIS_DB}")
    logging.debug(f"REDIS_PASSWORD: {REDIS_PASSWORD}")

    if REDIS_SENTINEL_ENABLED:
        try:
            sentinel_kwargs = {}
            master_for_kwargs = {"db": REDIS_DB}

            if REDIS_PASSWORD:
                master_for_kwargs["password"] = REDIS_PASSWORD

            if REDIS_SENTINEL_PASSWORD:
                sentinel_kwargs["password"] = REDIS_SENTINEL_PASSWORD

            sentinel = redis.Sentinel(
                [sentinel_hosts[0]],
                sentinel_kwargs=sentinel_kwargs,
            )

            r = sentinel.master_for(
                REDIS_MASTER_SET, **master_for_kwargs
            )

            r.ping()
            logging.info(f"Successfully connected to Redis sentinel: {sentinel_hosts[0]}")

        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logging.error(f"Could not connect to any sentinel. Error: {e}")
            exit(1)

    else:
        r = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_PASSWORD
            )

    try:
        r.ping()
    except redis.exceptions.ConnectionError as e:
        logging.error(f"Error connecting to Redis: {e}")
        exit(1)

    classifier = GitlabUserSpamClassifier(redis_conn=r, base_url=os.getenv("MODEL_URL", "http://127.0.0.1:5001"))
    classifier.run()


if __name__ == "__main__":
    main()
