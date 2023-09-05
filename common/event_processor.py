import redis
import json
import logging
import os

class EventProcessor:
    def __init__(self, prefix, events, redis_conn=None):
        self.event_queue_names = [f"{prefix}_{event}" for event in events]

        if redis_conn:
            self.redis_client = redis_conn
        else:
            REDIS_SENTINEL_ENABLED = os.getenv("REDIS_SENTINEL_ENABLED", "False") == "True"
            REDIS_MASTER_SET = os.getenv("REDIS_MASTER_SET") or "mymaster"
            REDIS_SENTINEL_HOSTS = os.getenv("REDIS_SENTINEL_HOSTS") or None
            REDIS_SENTINEL_PASSWORD = os.getenv("REDIS_SENTINEL_PASSWORD") or None
            REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
            REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
            REDIS_DB = int(os.getenv("REDIS_DB", 0))
            REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

            logging.debug(
                "Redis config:",
                f"REDIS_SENTINEL_ENABLED: {REDIS_SENTINEL_ENABLED}",
                f"REDIS_SENTINEL_HOSTS: {REDIS_SENTINEL_HOSTS}",
                f"REDIS_SENTINEL_PASSWORD: {REDIS_SENTINEL_PASSWORD}",
                f"REDIS_MASTER_SET: {REDIS_MASTER_SET}",
                f"REDIS_HOST: {REDIS_HOST}",
                f"REDIS_PORT: {REDIS_PORT}",
                f"REDIS_DB: {REDIS_DB}",
                f"REDIS_PASSWORD: {REDIS_PASSWORD}",
            )

            if REDIS_SENTINEL_ENABLED:
                try:
                    sentinel_kwargs = {}
                    master_for_kwargs = {"db": REDIS_DB}

                    if REDIS_PASSWORD:
                        master_for_kwargs["password"] = REDIS_PASSWORD

                    if REDIS_SENTINEL_PASSWORD:
                        sentinel_kwargs["password"] = REDIS_SENTINEL_PASSWORD

                    sentinel_hosts = [tuple(x.split(":")) for x in REDIS_SENTINEL_HOSTS.split(",")]

                    sentinel = redis.Sentinel(
                        [sentinel_hosts[0]],
                        sentinel_kwargs=sentinel_kwargs,
                    )

                    self.redis_client = sentinel.master_for(
                        REDIS_MASTER_SET, **master_for_kwargs
                    )

                    logging.info(f"Successfully connected to Redis sentinel: {sentinel_hosts[0]}")

                except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
                    logging.error(f"Could not connect to any sentinel. Error: {e}")
                    exit(1)

            else:
                self.redis_client = redis.Redis(
                        host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_PASSWORD
                    )

            try:
                self.redis_client.ping()
            except redis.exceptions.ConnectionError as e:
                logging.error(f"Error connecting to Redis: {e}")
                exit(1)
    
    def retrieve_event(self):
        for queue_name in self.event_queue_names:
            data = self.redis_client.lpop(queue_name)
            if data:
                logging.debug(f"{self.__class__.__name__}: processing event {queue_name}")
                data = json.loads(data.decode("utf-8"))
                self.process_event(queue_name, data)
    
    def process_event(self, queue_name, data):
        raise NotImplementedError("Child classes must implement this method")

    def send_to_queue(self, event, data, prefix=None):
        """
        Send data to a specified Redis list with the given event type.
        
        :param event: Type of the event.
        :param data: Data to be sent.
        :param prefix: Optional prefix for the queue name. If not provided, the default prefix from initialization will be used.
        """
        queue_name = f"{prefix}_{event}"
        serialized_data = json.dumps(data)
        
        try:
            self.redis_client.lpush(queue_name, serialized_data)
            logging.debug(f"{self.__class__.__name__}: pushed data to {queue_name}")
        except Exception as e:
            logging.error(f"Error pushing data to queue {queue_name}: {e}")
