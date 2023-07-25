from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
from datetime import datetime
from predict import MODELS
import subprocess
import signal
import sys

selected_model = "mlb3year"


def run_predict_script(selected_model):
    """
    function to run the prediction script (predict.py)
    """
    print(f"{datetime.now().strftime('%D - %T')}... Calling predict.py")
    try:
        subprocess.run(["python3", "../predict.py", selected_model], check=True)
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
        print(f"{datetime.now().strftime('%D - %T')}... Model set to {selected_model}")
        break


def shutdown():
    """
    function to shutdown the scheduler and exit the script
    """
    print(f"{datetime.now().strftime('%D - %T')}... Shutting down scheduler")
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
    print(f"\n{datetime.now().strftime('%D - %T')}... Keyboard interrupt detected")
    while True:
        print("\nOptions:")
        print("1. Switch prediction model")
        print("2. Shutdown")
        choice = input("Enter choice: ")
        if choice == "1":
            switch_model()
            return
        elif choice == "2":
            shutdown()
            return
        else:
            print("Invalid choice. Please try again.")


scheduler = BackgroundScheduler()
task_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
scheduler.add_job(
    run_predict_script,
    trigger=CronTrigger(hour=task_time.hour, minute=task_time.minute),
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
