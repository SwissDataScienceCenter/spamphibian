import argparse
from sanic import Sanic
from sanic.response import json as sanic_json
from sanic.worker.loader import AppLoader
import redis
import json

def create_app():
    app = Sanic("EventListener")

    # Create Redis connection
    redis_conn = redis.Redis(host='localhost', port=6379, db=0)

    @app.post('/event')
    async def handle_event(request):
        gitlab_event = request.json

        # Determine the type of event
        event_name = gitlab_event.get('event_name')
        object_kind = gitlab_event.get('object_kind')
        action = gitlab_event.get('object_attributes', {}).get('action')

        # Project-related events
        if event_name in ['project_create',
                        'project_rename',
                        'project_transfer',
                        'user_create',
                        'user_rename',
                        'group_create',
                        'group_rename',
                        'snippet_check']:
            queue_name = event_name

        # Issue-related events
        elif object_kind == 'issue' and action in ['open', 'close', 'reopen', 'update']:
            queue_name = f'issue_{action}'
        
        else:
            print(f'Unhandled event: {event_name if event_name else object_kind}')
        
        await redis_conn.lpush(queue_name, json.dumps(gitlab_event))

        return sanic_json({"message": "Event received"})

    return app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="EventListener")
    parser.add_argument("-H", "--host", default="0.0.0.0", help="Host to listen on")
    parser.add_argument("-p", "--port", default=8000, type=int, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable Sanic debug mode")
    parser.add_argument("--fast", action="store_true", help="Enable Sanic fast mode")
    parser.add_argument("-d", "--dev", action="store_true", help="Enable Sanic development mode")
    parser.add_argument("--single-process", action="store_true", help="Do not use multiprocessing.")
    args = vars(parser.parse_args())
    loader = AppLoader(factory=create_app)
    app = loader.load()
    app.prepare(**args)
    Sanic.serve(primary=app, app_loader=loader)
