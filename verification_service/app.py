import json
import redis
from time import sleep

def action_based_on_event_type(event_type, event_data):
    print(f"Event type: {event_type}")
    print(f"Event data: {event_data}")

async def process_events():
    # Set up Redis connection
    redis_conn = redis.Redis(host='localhost', port=6379, db=0)

    # List of event types to listen for
    event_types = ['project_create', 'project_destroy', 'project_rename', 'project_transfer',
                   'issue_open', 'issue_close', 'issue_reopen', 'issue_update', 'snippet_check', 'user_create', 'user_rename', 'group_create', 'group_rename']

    while True:
        for event_type in event_types:
            while True:
                # Pop the next event off the queue (non-blocking)
                event = redis_conn.lpop(event_type)
                
                # If there was no event, break the loop and move on to the next event type
                if event is None:
                    break

                # Parse the event data from JSON
                event_data = json.loads(event)

                print(event_data)

                # Perform an action based on the event type
                action_based_on_event_type(event_type, event_data)

        # Sleep for a bit before checking the queues again
        sleep(1)

if __name__ == "__main__":
    process_events()
