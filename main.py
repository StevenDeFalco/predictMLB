#!/usr/bin/python3

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from predict import check_and_predict
from datetime import datetime
from predict import MODELS
import apscheduler  # type: ignore
import subprocess
import signal
import time
import sys

# by default use largest model
selected_model = "mlb3year"


def run_predict_script(selected_model: str) -> None:
    """
    function to run the prediction script (predict.py)

    Args:
        selected_model: string name of the model to use for predictions
    """
    print(f"{datetime.now().strftime('%D - %T')}... \nCalling predict.py\n")
    try:
        process = subprocess.Popen(
            ["python3", "predict.py", selected_model],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                print(output.strip())
        return_code = process.poll()
        if return_code != 0:
            print(f"Error running predict.py. Return code: {return_code}")
    except subprocess.CalledProcessError as e:
        print(f"Error running predict.py: {e}")


def switch_model() -> None:
    """
    function to switch the prediction model
        -> updates global variable 'selected_model'
    """
    global selected_model
    print(f"Available prediction models: \n{', '.join(MODELS)}")
    while True:
        new_model = input("Enter the name of the model to use: ")
        if new_model not in MODELS:
            print("Invalid model. The only supported models are those listed here.")
            continue
        selected_model = new_model
        print(
            f"{datetime.now().strftime('%D - %T')}... \nModel set to {selected_model}\n"
        )
        break


def shutdown() -> None:
    """
    function to shutdown the scheduler and exit the script
    """
    print(f"{datetime.now().strftime('%D - %T')}... \nShutting down scheduler\n")
    try:
        scheduler.shutdown(wait=False)
    except apscheduler.schedulers.SchedulerNotRunningError:
        pass
    except SystemExit:
        pass
    sys.exit(0)


def interrupt_handler(signum, frame) -> None:
    """
    function to handle keyboard interrupt (ctrl+c)
    """
    print(f"{datetime.now().strftime('%D - %T')}... \nKeyboard interrupt detected\n")
    time.sleep(0.25)
    while True:
        print("\nOptions:")
        print("0: Do nothing (return)")
        print("1. Switch prediction model")
        print("2. Shutdown")
        choice = input("Enter choice: ")
        if choice == "0":
            print("\n")
            return
        if choice == "1":
            print("\n")
            switch_model()
            return
        elif choice == "2":
            print("\n")
            shutdown()
            return
        else:
            print("\nInvalid choice. Please try again.")


def print_jobs(scheduler) -> None:
    """simple function to print all scheduled jobs"""
    # Print details of scheduled jobs
    print("Scheduled Jobs:")
    for job in scheduler.get_jobs():
        print(f"Job Name: {job.name}")
        print(f"Next Execution Time: {job.next_run_time}")
        print(f"Trigger: {job.trigger}\n")


scheduler = BackgroundScheduler()
task_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
scheduler.add_job(
    check_and_predict,
    trigger=CronTrigger(
        hour=task_time.hour, minute=task_time.minute, second=task_time.second
    ),
    args=[selected_model],
)
scheduler.start()

signal.signal(signal.SIGINT, interrupt_handler)

print_jobs(scheduler)

# run indefinitely
try:
    while True:
        pass
except (KeyboardInterrupt, SystemExit):
    pass
