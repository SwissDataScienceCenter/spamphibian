from multiprocessing import Process
import os
import signal
import time


def run_script(script):
    os.system(f"python {script}")


if __name__ == "__main__":
    # Create processes
    event_service = Process(target=run_script, args=("event_service/main.py",))
    verification_service = Process(
        target=run_script, args=("verification_service/main.py",)
    )
    retrieval_service = Process(target=run_script, args=("retrieval_service/main.py",))
    classification_service = Process(
        target=run_script, args=("classification_service/main.py",)
    )
    flask_service = Process(target=run_script, args=("models/users/flask_service.py",))
    notification_service = Process(
        target=run_script, args=("notification_service/main.py",)
    )

    # Start processes
    event_service.start()
    verification_service.start()
    retrieval_service.start()
    classification_service.start()
    flask_service.start()
    notification_service.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Kill processes on Ctrl+C
        os.kill(event_service.pid, signal.SIGINT)
        os.kill(verification_service.pid, signal.SIGINT)
        os.kill(retrieval_service.pid, signal.SIGINT)
        os.kill(classification_service.pid, signal.SIGINT)
        os.kill(flask_service.pid, signal.SIGINT)
        os.kill(notification_service.pid, signal.SIGINT)
