import json
import redis
from time import sleep
import yaml
import re

def check_domain_verification(email):
    # Load verified domains from yaml file
    with open('verification_service/verified_domains.yaml', 'r') as file:
        verified_domains = yaml.safe_load(file)['domains']

    for domain in verified_domains:
        if re.search(domain, email):
            return True
    return False

def get_user_email_address(event_type, event_data):
    if event_type in ['project_create', 'project_rename', 'project_transfer']:
        return event_data.get('owner_email')

    elif event_type in ['user_create', 'user_rename']:
        return event_data.get('email')

    elif event_type in ['issue_open', 'issue_update', 'issue_close', 'issue_reopen', 'issue_note_create', 'issue_note_update']:
        user_attributes = event_data.get('user', {})
        return user_attributes.get('email')

    else:
        print(f"Unable to get user email address for this event type: {event_type}")
        return None

def process_events():
    # Set up Redis connection
    redis_conn = redis.Redis(host='localhost', port=6379, db=0)

    # List of event types to listen for
    event_types = ['project_create', 'project_rename', 'project_transfer',
                   'issue_open', 'issue_close', 'issue_reopen', 'issue_update',
                   'user_create', 'user_rename', 'group_create', 'group_rename',
                   'snippet_check', 'issue_note_update', 'issue_note_create']

    while True:
        for event_type in event_types:

            # Pop the next event off the queue
            event = redis_conn.lpop("event_" + event_type)
            
            # If there was no event, continue to the next event type
            if event is None:
                continue

            # Parse the event data from JSON
            event_data = json.loads(event)

            # Perform an action based on the event type
            if event_type in ['project_create', 'project_rename', 'project_transfer',
                              'user_create', 'user_rename', 'issue_open', 'issue_update',
                              'issue_close', 'issue_reopen', 'issue_note_create', 'issue_note_update']:

                user_email_address = get_user_email_address(event_type, event_data)

                if user_email_address is None:
                    print(f"Unable to get user email address for this event type: {event_type}")
                    

                domain_verified = check_domain_verification(user_email_address)

                print(f"User email address {user_email_address} verification status: {domain_verified}")

                if domain_verified:
                    continue

                queue_name = "verification_" + event_type
                redis_conn.lpush(queue_name, json.dumps(event_data))

            else:
                print(f"{event_type} event type received, need to get user email from GitLab API")
                # todo: get owner email address from gitlab api and check domain verification status

        # Sleep for a bit before checking the queues again
        sleep(1)

if __name__ == "__main__":
    process_events()
