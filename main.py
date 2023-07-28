#!/usr/bin/python3

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from datetime import datetime, timedelta
from predict import check_and_predict
from predict import MODELS
import apscheduler  # type: ignore
import subprocess
import signal
import time
import sys

selected_model = "mlb3year"


def run_predict_script(selected_model):
    """
    function to run the prediction script (predict.py)
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


def switch_model():
    """
    function to switch the prediction model
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


def shutdown():
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


def interrupt_handler(signum, frame):
    """
    function to handle keyboard interrupt (ctrl+c)
    """
    print(f"{datetime.now().strftime('%D - %T')}... \nKeyboard interrupt detected\n")
    time.sleep(0.5)
    while True:
        print("\nOptions:")
        print("0: Do nothing (return)")
        print("1. Switch prediction model")
        print("2. Shutdown")
        choice = input("Enter choice: ")
        if choice == "0":
            return
        if choice == "1":
            switch_model()
            return
        elif choice == "2":
            shutdown()
            return
        else:
            print("Invalid choice. Please try again.")


scheduler = BackgroundScheduler()
# task_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
task_time = datetime.now().replace(second=(datetime.now().second + 3))
scheduler.add_job(
    #run_predict_script,
    check_and_predict,
    trigger=CronTrigger(
        hour=task_time.hour, minute=task_time.minute, second=task_time.second
    ),
    args=[selected_model],
)
scheduler.start()

signal.signal(signal.SIGINT, interrupt_handler)

# Print details of scheduled jobs
print("Scheduled Jobs:")
for job in scheduler.get_jobs():
    print(f"Job Name: {job.name}")
    print(f"Next Execution Time: {job.next_run_time}")
    print(f"Trigger: {job.trigger}\n")

# run indefinitely
try:
    while True:
        pass
except (KeyboardInterrupt, SystemExit):
    pass
