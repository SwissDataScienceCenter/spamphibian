import json
import redis
from time import sleep
import yaml
import re

def check_domain(email):
    # Load verified domains from yaml file
    with open('verification_service/verified_domains.yaml', 'r') as file:
        verified_domains = yaml.safe_load(file)['domains']

    for domain in verified_domains:
        if re.search(domain, email):
            return True
    return False

def action_based_on_event_type(event_type, event_data):
    print(f"New event, type: {event_type}")
    #print(f"Event data: {event_data}")

    if event_type == 'project_create':
        print(f"Project {event_data.get('name')} created by {event_data.get('owner_email')}")
        domain_verified = check_domain(event_data.get('owner_email'))
        print(f"Email domain verified: {domain_verified}")

    if event_type == 'user_create':
        print(f"User {event_data.get('name')} created")
        domain_verified = check_domain(event_data.get('email'))
        print(f"Email domain verified: {domain_verified}")

    if event_type == 'issue_create' or event_type == 'issue_update':
        user_attributes = event_data.get('user', {})
        issue_attributes = event_data.get('object_attributes', {})
        print(f"Issue {issue_attributes.get('title')} opened by {user_attributes.get('email')}")
        domain_verified = check_domain(user_attributes.get('email'))
        print(f"Email domain verified: {domain_verified}")
    
    if event_type == 'issue_note_create' or event_type == 'issue_note_update':
        user_attributes = event_data.get('user', {})
        issue_attributes = event_data.get('issue', {})
        print(f"Note on issue {issue_attributes.get('title')} created by {user_attributes.get('email')}")
        domain_verified = check_domain(user_attributes.get('email'))
        print(f"Email domain verified: {domain_verified}")

def process_events():
    # Set up Redis connection
    redis_conn = redis.Redis(host='localhost', port=6379, db=0)

    # List of event types to listen for
    event_types = ['project_create', 'user_create', 'project_destroy', 'project_rename', 'project_transfer', 'issue_open', 'issue_close', 'issue_reopen', 'issue_update', 'snippet_check', 'user_rename', 'group_create', 'group_rename', 'issue_note_update', 'issue_note_create']

    while True:
        for event_type in event_types:

            # Pop the next event off the queue
            event = redis_conn.lpop(event_type)
            #print(f"Attempting to pop event of type {event_type}, got: {event}")
            
            # If there was no event, continue to the next event type
            if event is None:
                continue

            # Parse the event data from JSON
            event_data = json.loads(event)

            # Perform an action based on the event type
            action_based_on_event_type(event_type, event_data)

        # Sleep for a bit before checking the queues again
        sleep(1)

if __name__ == "__main__":
    process_events()
