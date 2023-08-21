import redis
import json
import logging

from common.constants import (
    project_events,
    user_events,
    issue_events,
    issue_note_events,
    group_events,
    snippet_events,
    event_types,
)

class EventProcessor:
    def __init__(self, prefix, events, redis_conn=None):
        self.redis_client = redis_conn if redis_conn else redis.Redis(host="localhost", port=6379, db=0)
        self.event_queue_names = [f"{prefix}_{event}" for event in events]
    
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
