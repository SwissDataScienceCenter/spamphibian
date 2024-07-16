import redis
import json
import logging
import os

# EventProcessor class is used to process events from Redis streams
# and add events back into to Redis streams after processing.
class EventProcessor:
    def __init__(self, input_stream_name, output_stream_name, redis_conn=None):
        self.input_stream_name = input_stream_name
        self.output_stream_name = output_stream_name

        if redis_conn:
            self.redis_client = redis_conn
        else:
            self._establish_redis_connection()

        try:
            self.redis_client.ping()
        except redis.exceptions.ConnectionError as e:
            logging.error(f"Error connecting to Redis: {e}")
            exit(1)

    def _establish_redis_connection(self):

        REDIS_SENTINEL_ENABLED = (
            os.getenv("REDIS_SENTINEL_ENABLED", "False") == "True"
        )
        REDIS_MASTER_SET = os.getenv("REDIS_MASTER_SET") or "mymaster"
        REDIS_SENTINEL_HOSTS = os.getenv("REDIS_SENTINEL_HOSTS") or None
        REDIS_SENTINEL_PASSWORD = os.getenv("REDIS_SENTINEL_PASSWORD") or None
        REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
        REDIS_DB = int(os.getenv("REDIS_DB", 0))
        REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

        redis_sentinel_password_display = '*****' if REDIS_SENTINEL_PASSWORD else 'Not provided'
        redis_password_display = '*****' if REDIS_PASSWORD else 'Not provided'

        # Logging the debug message
        logging.debug("\n".join([
            "Redis config:",
            f"REDIS_SENTINEL_ENABLED: {REDIS_SENTINEL_ENABLED}",
            f"REDIS_SENTINEL_HOSTS: {REDIS_SENTINEL_HOSTS}",
            f"REDIS_SENTINEL_PASSWORD: {redis_sentinel_password_display}",
            f"REDIS_MASTER_SET: {REDIS_MASTER_SET}",
            f"REDIS_HOST: {REDIS_HOST}",
            f"REDIS_PORT: {REDIS_PORT}",
            f"REDIS_DB: {REDIS_DB}",
            f"REDIS_PASSWORD: {redis_password_display}",
        ]))

        if REDIS_SENTINEL_ENABLED:
            try:
                sentinel_kwargs = {}
                master_for_kwargs = {"db": REDIS_DB}

                if REDIS_PASSWORD:
                    master_for_kwargs["password"] = REDIS_PASSWORD

                if REDIS_SENTINEL_PASSWORD:
                    sentinel_kwargs["password"] = REDIS_SENTINEL_PASSWORD

                sentinel_hosts = [
                    tuple(x.split(":")) for x in REDIS_SENTINEL_HOSTS.split(",")
                ]

                sentinel = redis.Sentinel(
                    [sentinel_hosts[0]],
                    socket_timeout=0.1,
                    sentinel_kwargs=sentinel_kwargs,
                )

                self.redis_client = sentinel.master_for(
                    REDIS_MASTER_SET, 
                    **master_for_kwargs,
                    retry_on_timeout=True,
                    health_check_interval=60,
                )

                logging.info(
                    f"Successfully connected to Redis sentinel: {sentinel_hosts[0]}"
                )

            except (
                redis.exceptions.ConnectionError,
                redis.exceptions.TimeoutError,
            ) as e:
                logging.error(f"Could not connect to any sentinel. Error: {e}")
                exit(1)

        else:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                retry_on_error=[redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, redis.exceptions.BusyLoadingError],
                retry=redis.retry.Retry(redis.backoff.ExponentialBackoff(), -1),
                health_check_interval=60,
            )

    def poll_and_process_event(self, testing=False):
    # TODO: Send heartbeat to Prometheus
        while True:
            messages = self.redis_client.xread({self.input_stream_name: '0'}, block=10000, count=1)
            if not messages:
                continue

            for message in messages[0][1]:
                message_id = message[0]
                for key in message[1].keys():
                    decoded_key = key.decode('utf-8')
                    logging.debug(
                        f"{self.__class__.__name__}: processing event {decoded_key}"
                    )
                    data = json.loads(message[1][key].decode('utf-8'))

                    print(f"Processing message {message_id} from {self.input_stream_name}")

                    self.process_event(decoded_key, data)

                    # Delete the message from the stream after processing
                    self.redis_client.xdel(self.input_stream_name, message_id)
                    print(f"Deleted message {message_id} from {self.input_stream_name}")

                if testing:
                    return

    def process_event(self, event_type, data):
        raise NotImplementedError("Child classes must implement this method")

    def push_event_to_queue(self, event_type, data):
        serialized_data = json.dumps(data)

        try:
            self.redis_client.xadd(self.output_stream_name, {event_type: serialized_data})
            logging.debug(f"{self.__class__.__name__}: added data to {self.output_stream_name}")
        except Exception as e:
            logging.critical(f"Error adding data to stream {self.output_stream_name}: {e}")
