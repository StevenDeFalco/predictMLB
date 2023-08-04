from apscheduler.events import EVENT_SCHEDULER_STARTED, EVENT_JOB_EXECUTED  # type: ignore
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from predict import check_and_predict
from dotenv import load_dotenv
from datetime import datetime
import subprocess
import time
import pytz
import os

# use model defined in .env or by default 'mlb3year'
selected_model = "mlb3year"
load_dotenv()
ret = os.getenv("SELECTED_MODEL")
selected_model = ret if ret is not None else selected_model

eastern = pytz.timezone("America/New_York")


def run_predict_script(selected_model: str) -> None:
    """
    function to run the prediction script (predict.py)

    Args:
        selected_model: string name of the model to use for predictions
    """
    print(f"{datetime.now().strftime('%D - %I:%M:%S %p')}... \nCalling predict.py\n")
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


def print_next_job(event) -> None:
    """function to print details about next scheduled job"""
    time.sleep(1)
    next_job = scheduler.get_jobs()[0] if scheduler.get_jobs()[0] else None
    if next_job is not None:
        print(
            f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... Next Scheduled Job"
        )
        print(f"Job Name: {next_job.name}")
        run_time = next_job.next_run_time
        et_time = run_time.astimezone(eastern)
        formatted_time = et_time.strftime("%I:%M %p")
        print(f"Next Execution Time: {formatted_time} ET")
        time.sleep(1)
    return


scheduler = BackgroundScheduler()
scheduler.add_listener(print_next_job, EVENT_SCHEDULER_STARTED)
scheduler.add_listener(print_next_job, EVENT_JOB_EXECUTED)

task_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
scheduler.add_job(
    check_and_predict,
    trigger=CronTrigger(
        hour=task_time.hour, minute=task_time.minute, second=task_time.second
    ),
    args=[selected_model],
)

time.sleep(1)
scheduler.start()

# run indefinitely
try:
    while True:
        pass
except (KeyboardInterrupt, SystemExit):
    pass
