import argparse
import asyncio
import logging
from sanic import Sanic
from sanic.worker.loader import AppLoader

from verification_service.app import process_events as create_verification_app
from event_service.app import create_app  as create_event_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Start the event service
    parser = argparse.ArgumentParser(prog="GitLabEventListener")
    parser.add_argument("-H", "--host", default="0.0.0.0", help="Host to listen on")
    parser.add_argument("-p", "--port", default=8000, type=int, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable Sanic debug mode")
    parser.add_argument("--fast", action="store_true", help="Enable Sanic fast mode")
    parser.add_argument("-d", "--dev", action="store_true", help="Enable Sanic development mode")
    parser.add_argument("--single-process", action="store_true", help="Do not use multiprocessing.")
    args = vars(parser.parse_args())

    # Log that the service is starting
    logger.info("Starting services...")

    # Start the event service
    loader = AppLoader(factory=create_event_app)
    event_app = loader.load()
    event_app.prepare(**args)

    if args['debug']:
        event_app.debug = True

    # Start the verification service
    logger.info("Starting verification task...")
    verification_task = asyncio.create_task(create_verification_app())

    # Start both services concurrently
    logger.info("Starting Sanic server...")
    sanic_server = event_app.create_server(host=args['host'], port=args['port'], return_asyncio_server=True)
    sanic_task = asyncio.create_task(sanic_server)
    asyncio.run(asyncio.gather(sanic_task, verification_task))
    logger.info("Services started.")
