from multiprocessing import Process
import os
import signal
import time

def run_script(script):
    os.system(f'python3.11 {script}')

if __name__ == '__main__':

    # Create processes
    event_service = Process(target=run_script, args=('event_service/app.py',))
    verification_service = Process(target=run_script, args=('verification_service/app.py',))

    # Start processes
    event_service.start()
    verification_service.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Kill processes on Ctrl+C
        os.kill(event_service.pid, signal.SIGINT)
        os.kill(verification_service.pid, signal.SIGINT)
