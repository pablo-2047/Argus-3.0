# In: core_utils/memory_utils.py
import psutil
import threading
import time
import database
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# This will be set by main.py
send_to_ui = None
speak = None

# --- Task Database Functions ---
# (We'll use the main 'memories' table for now for simplicity)
# A 'task' is just a memory with type='task'

def add_task(description: str, due_date: datetime):
    """Saves a new task to the database."""
    task_data = {
        "description": description,
        "due_date": due_date.isoformat(),
        "status": "pending",
        "reminders_sent": []
    }
    database.save_memory(source='user', content=str(task_data), mem_type='task')
    if speak:
        speak(f"Task added: {description}, due {due_date.strftime('%A, %B %d')}")

def get_pending_tasks():
    """Loads all tasks that aren't marked 'done'."""
    # This is a simple implementation. A real one would use a proper DB query.
    all_tasks = database.load_recent_memories(source_filter='user', limit=100, type_filter='task')
    pending = []
    for task_str in all_tasks:
        try:
            task_data = eval(task_str) # eval() is simple, but use json.loads in production
            if task_data.get('status') == 'pending':
                pending.append(task_data)
        except Exception as e:
            print(f"Error parsing task: {e}")
    return pending

# --- Escalating Reminder Logic ---
def check_tasks():
    """
    This is the core logic. It runs on a schedule (e.g., every hour).
    It checks all pending tasks and decides if a reminder is needed.
    """
    if not speak or not send_to_ui:
        return # Not ready yet

    print(f"--- [Scheduler] Checking tasks at {datetime.now()} ---")
    pending_tasks = get_pending_tasks()
    
    for task in pending_tasks:
        due_date = datetime.fromisoformat(task['due_date'])
        time_left = due_date - datetime.now()
        
        # 1. Task is past due
        if time_left.total_seconds() < 0:
            notify(task, "URGENT: This task is past due!", level='critical')
            continue
            
        # 2. Due in less than 24 hours (Hourly)
        if time_left < timedelta(days=1):
            if 'hourly' not in task['reminders_sent']:
                notify(task, f"Reminder: Due in {time_left.seconds // 3600} hours.", level='high')
                # We would update the task in the DB here
                # task['reminders_sent'].append('hourly') 
                # database.update_task(...)
            continue

        # 3. Due in less than 7 days (Daily)
        if time_left < timedelta(days=7):
            if 'daily' not in task['reminders_sent']:
                notify(task, f"Reminder: Due in {time_left.days} days.", level='medium')
                # task['reminders_sent'].append('daily')
            continue
            
        # 4. Due in less than 3 weeks (Weekly)
        if time_left < timedelta(weeks=3):
            if 'weekly' not in task['reminders_sent']:
                notify(task, f"Heads up: Due in {time_left.days // 7} weeks.", level='low')
                # task['reminders_sent'].append('weekly')
            continue
        if 'hourly' not in task['reminders_sent']:
            # Update database
            task['reminders_sent'].append('hourly')
            database.update_task(task['id'], task)  # NEW function needed


def notify(task, message, level):
    """Sends the notification (implements Tweak #1: Context-Aware)."""
    
    # --- Tweak #1: Context-Aware Logic ---
    is_gaming = False
    is_working = False
    is_idle = False
    
    # (Simple check, can be expanded)
    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() in ['gta5.exe', 'steam.exe']:
            is_gaming = True
            break
        if proc.info['name'].lower() in ['code.exe', 'pycharm64.exe']:
            is_working = True
    
    # (Check for idle would require mouse/keyboard hooks, skipping for now)
    
    if is_gaming and level in ['low', 'medium']:
        print(f"--- [Scheduler] User is gaming. Deferring reminder: {task['description']} ---")
        send_to_ui("status", {"state": f"Reminder deferred (Gaming): {task['description']}"})
        return # Don't bother the user

    if is_working and level in ['low', 'medium']:
        print(f"--- [Scheduler] User is working. Sending silent reminder. ---")
        send_to_ui("speech", {"text": f"[SILENT] {message}"}) # Send to UI only
        return

    # Default: Speak the reminder
    print(f"--- [Scheduler] Speaking reminder: {message} ---")
    speak(message)
    # --- End Tweak #1 ---


# --- Scheduler Thread ---
def start_scheduler_thread():
    """Starts the APScheduler in a separate thread."""
    scheduler = BackgroundScheduler()
    # Check tasks every hour
    scheduler.add_job(check_tasks, 'interval', hours=1)
    # (We can also add the 'Proactive Task Inference' Tweak #2 here)
    # scheduler.add_job(proactive_task_inference, 'interval', minutes=15)
    
    print("--- [Scheduler] Background task checker started. ---")
    scheduler.start()