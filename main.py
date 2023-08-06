from apscheduler.events import EVENT_SCHEDULER_STARTED, EVENT_JOB_EXECUTED  # type: ignore
from apscheduler.schedulers.blocking import BlockingScheduler # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from predict import check_and_predict
from dotenv import load_dotenv  # type: ignore
from datetime import datetime
import time
import pytz  # type: ignore
import os

# use model defined in .env or by default 'mlb3year'
selected_model = "mlb3year"
cwd = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(cwd, ".env")
load_dotenv(env_file_path)
ret = os.getenv("SELECTED_MODEL")
selected_model = ret if ret is not None else selected_model

eastern = pytz.timezone("America/New_York")


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


scheduler = BlockingScheduler()
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

# start the scheduler
scheduler.start()
