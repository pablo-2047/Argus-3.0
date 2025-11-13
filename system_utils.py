# core_utils/system_utils.py
# This is the "Ghost" module for screen awareness and system control.

import logging
import subprocess
import psutil
import pytesseract
from PIL import ImageGrab # Pillow
import os
import platform
import tempfile
import winshell  # <-- NEW
import glob
from core_utils.file_utils import confirm_action
import winreg  # For registry access
import wmi
from datetime import datetime

# --- Tweak: Set Tesseract Path (if needed) ---
# If you installed Tesseract to a non-default location, you'll
# need to set the path here.
# Example for Windows:
# if platform.system() == "Windows":
#     pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def get_active_window():
    """
    Finds the name of the currently active window.
    This is a complex, OS-specific task. This is a simplified version.
    """
    print("--- [Ghost] Getting active window... ---")
    active_window_name = "Unknown"
    
    # This is a cross-platform (but basic) way to get active PIDs
    # A more robust solution uses pygetwindow or OS-specific APIs
    try:
        active_pids = [p.pid for p in psutil.process_iter(['pid', 'name', 'cpu_percent']) if p.info['cpu_percent'] > 0.1]
        if active_pids:
            # We'll just guess the "most active" is the one
            p = psutil.Process(active_pids[0])
            active_window_name = p.name()
    except Exception as e:
        print(f"--- [Ghost] Could not get active window: {e} ---")
        
    return {"active_app": active_window_name}


def get_screen_text():
    """
    Captures the entire screen, saves it as a temporary image,
    and runs Tesseract OCR to extract all visible text.
    """
    print("--- [Ghost] Capturing screen text (OCR)... ---")
    try:
        # 1. Capture the screen
        screenshot = ImageGrab.grab()
        
        # 2. Save to a temporary file
        temp_image_path = os.path.join(tempfile.gettempdir(), "argus_ocr.png")
        screenshot.save(temp_image_path, "PNG")

        # 3. Run Tesseract OCR on the image
        text = pytesseract.image_to_string(temp_image_path)
        
        # 4. Clean up the temp file
        os.remove(temp_image_path)
        
        if not text.strip():
            return "No text could be read from the screen."
            
        # Truncate to avoid massive LLM prompts
        if len(text) > 4000:
            text = text[:4000] + "\n... [Screen text truncated]"
            
        return text

    except FileNotFoundError:
        print("--- [Ghost] OCR Error: Tesseract not found! ---")
        return "OCR Error: Tesseract is not installed or not in your system PATH."
    except Exception as e:
        print(f"--- [Ghost] OCR Error: {e} ---")
        return f"An error occurred during screen capture: {e}"
def get_installed_apps():
    """
    Scans the Windows Start Menu to get a list of all installed application shortcuts.
    This is the most reliable way to find what the user considers an "app".
    """
    # Paths to the All Users and Current User Start Menu folders
    start_menu_paths = [
        os.path.join(os.environ['PROGRAMDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
        os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs')
    ]
    
    app_list = {} # We'll store "App Name": "File Path"
    
    for path in start_menu_paths:
        # The glob.glob('**/*.lnk', recursive=True) command finds every .lnk file
        # in every subfolder. This is how we scan for all apps.
        try:
            for shortcut_path in glob.glob(os.path.join(path, '**', '*.lnk'), recursive=True):
                # Get the "clean" name of the shortcut, e.g., "Cricket 24"
                app_name = os.path.splitext(os.path.basename(shortcut_path))[0]
                
                # Use winshell to get the *actual* target path (e.g., the .exe)
                with winshell.shortcut(shortcut_path) as shortcut:
                    target_path = shortcut.path
                    
                if app_name and target_path and app_name not in app_list:
                    app_list[app_name] = target_path
                    
        except Exception as e:
            logging.warning(f"[Ghost] Failed to scan Start Menu folder: {path}. Error: {e}")

    return app_list


def launch_application(fuzzy_name: str):
    """
    This is the "smart" launch tool.
    It gets all installed apps, finds the best match for the fuzzy_name,
    and then launches it.
    """
    logging.info(f"--- [Ghost] Received launch request for: '{fuzzy_name}' ---")
    
    try:
        # 1. Scan for all apps
        all_apps = get_installed_apps()
        if not all_apps:
            return "Error: Could not scan for installed applications."
            
        # 2. Find the best match (fuzzy matching)
        lower_fuzzy_name = fuzzy_name.lower()
        best_match = None
        
        for app_name in all_apps.keys():
            if lower_fuzzy_name == app_name.lower():
                best_match = app_name # Found an exact match
                break
            if lower_fuzzy_name in app_name.lower():
                best_match = app_name # Found a partial match
                # We don't break, in case a better (exact) match exists
        
        # 3. Launch the app
        if best_match:
            try:
                target_path = all_apps[best_match]
                # os.startfile is the Windows equivalent of "double-clicking" a file.
                # It will launch the .exe or whatever the shortcut points to.
                os.startfile(target_path)
                return f"Success. Launching {best_match}."
            except Exception as e:
                logging.error(f"[Ghost] Failed to launch '{best_match}' at {target_path}: {e}")
                return f"Error: Found app '{best_match}' but failed to launch it. {e}"
        else:
            return f"Error: Could not find any installed app matching the name '{fuzzy_name}'."
            
    except Exception as e:
        logging.error(f"[Ghost] Critical error in launch_application: {e}")
        return f"Error: {e}"
    
# In: core_utils/system_utils.py (at the bottom)

def execute_command(cmd: str):
    """
    Runs a system shell command. Confirms before destructive operations.
    """
    logging.info(f"--- [Ghost] Executing command: {cmd} ---")
    
    # "Pablo's" safety check
    risky_terms = ["del", "erase", "rm", "shutdown", "format"]
    if any(term in cmd.lower() for term in risky_terms):
        logging.warning(f"--- [Ghost] Risky command detected: {cmd} ---")
        # NOTE: This 'confirm_action' uses the input() in the backend terminal.
        # In the future, we will upgrade this to a UI-based confirmation.
        if not confirm_action("execute", cmd):
            return "Command canceled by user."

    try:
        # Run the command
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = process.communicate(timeout=30) # 30-second timeout
        
        if err:
            logging.error(f"--- [Ghost] Command error: {err} ---")
            return f"Command failed: {err}"
        return f"Command output:\n{out}"
        
    except subprocess.TimeoutExpired:
        logging.error(f"--- [Ghost] Command timed out: {cmd} ---")
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        logging.error(f"--- [Ghost] Command failed: {e} ---")
        return f"[Error] Command failed: {e}"

# ADD THESE TO YOUR EXISTING system_utils.py

    # For hardware monitoring

def get_hardware_status():
    """
    Like Jarvis monitoring the suit's systems.
    Returns: {cpu_temp, gpu_temp, ram_usage, disk_space}
    """
    c = wmi.WMI(namespace="root\\OpenHardwareMonitor")
    data = {}
    
    for sensor in c.Sensor():
        if sensor.SensorType == 'Temperature':
            if 'CPU' in sensor.Name:
                data['cpu_temp'] = sensor.Value
            elif 'GPU' in sensor.Name:
                data['gpu_temp'] = sensor.Value
    
    data['ram_usage'] = psutil.virtual_memory().percent
    data['disk_space'] = psutil.disk_usage('/').percent
    
    return data

def set_system_performance_mode(mode: str):
    """
    Adjusts Windows power plan.
    'performance' | 'balanced' | 'power_saver'
    
    Jarvis equivalent: "Diverting power to repulsors."
    """
    power_plans = {
        'performance': '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c',
        'balanced': '381b4222-f694-41f0-9685-ff5bb260df2e',
        'power_saver': 'a1841308-3541-4fab-bc81-f71556f20b4a'
    }
    
    if mode in power_plans:
        plan_guid = power_plans[mode]
        cmd = f'powercfg /setactive {plan_guid}'
        result = execute_command(cmd)
        return f"System switched to {mode} mode."
    return "Invalid mode."

def monitor_network_traffic():
    """
    Track what's using your bandwidth.
    Useful for detecting background downloads or security issues.
    """
    net_io = psutil.net_io_counters(pernic=True)
    active_connections = psutil.net_connections()
    
    return {
        'total_sent_mb': net_io['Ethernet'].bytes_sent / 1024 / 1024,
        'total_recv_mb': net_io['Ethernet'].bytes_recv / 1024 / 1024,
        'active_connections': len(active_connections)
    }
# core_utils/system_utils.py
"""
ENHANCED SYSTEM UTILITIES - ADDITIONS

Add these functions to your existing system_utils.py file.
These provide deep OS-level control, like Jarvis monitoring the Iron Man suit.

NEW CAPABILITIES:
1. Hardware monitoring (CPU/GPU temps, voltages)
2. Performance mode switching
3. Network traffic monitoring
4. Process resource analysis
5. System health diagnostics
"""



# === REQUIRES: pip install wmi ===
try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False
    logging.warning("[SystemUtils] WMI not available. Hardware monitoring disabled.")


def get_hardware_status():
    """
    Monitors hardware health like Jarvis monitors the suit's systems.
    
    Returns:
        dict: {
            cpu_temp: float,
            gpu_temp: float,
            cpu_usage: float,
            ram_usage: float,
            disk_usage: float,
            battery_percent: float (if laptop),
            power_mode: str
        }
    
    Note: Requires OpenHardwareMonitor or similar to be running for temps.
          On Windows, you can use: https://openhardwaremonitor.org/
    """
    status = {}
    
    # === CPU & RAM (Always available) ===
    status['cpu_usage'] = psutil.cpu_percent(interval=1)
    status['cpu_cores'] = psutil.cpu_count(logical=False)
    status['cpu_threads'] = psutil.cpu_count(logical=True)
    
    mem = psutil.virtual_memory()
    status['ram_usage'] = mem.percent
    status['ram_total_gb'] = mem.total / (1024**3)
    status['ram_available_gb'] = mem.available / (1024**3)
    
    # === DISK ===
    disk = psutil.disk_usage('/')
    status['disk_usage'] = disk.percent
    status['disk_free_gb'] = disk.free / (1024**3)
    
    # === BATTERY (Laptop only) ===
    battery = psutil.sensors_battery()
    if battery:
        status['battery_percent'] = battery.percent
        status['battery_plugged'] = battery.power_plugged
        status['battery_time_left'] = battery.secsleft / 60  # minutes
    
    # === TEMPERATURES (Requires WMI + OpenHardwareMonitor) ===
    if WMI_AVAILABLE:
        try:
            w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            for sensor in w.Sensor():
                if sensor.SensorType == 'Temperature':
                    if 'CPU' in sensor.Name:
                        status['cpu_temp'] = sensor.Value
                    elif 'GPU' in sensor.Name:
                        status['gpu_temp'] = sensor.Value
        except Exception as e:
            logging.debug(f"[SystemUtils] Could not read temps: {e}")
    
    # === NETWORK ===
    net = psutil.net_io_counters()
    status['network_sent_mb'] = net.bytes_sent / (1024**2)
    status['network_recv_mb'] = net.bytes_recv / (1024**2)
    
    return status


def set_system_performance_mode(mode: str):
    """
    Adjusts Windows power plan for performance.
    Jarvis equivalent: "Diverting power to repulsors."
    
    Args:
        mode: 'performance' | 'balanced' | 'power_saver'
    
    Returns:
        str: Status message
    
    Requires: Administrator privileges
    """
    # Windows power plan GUIDs
    power_plans = {
        'performance': '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c',
        'balanced': '381b4222-f694-41f0-9685-ff5bb260df2e',
        'power_saver': 'a1841308-3541-4fab-bc81-f71556f20b4a'
    }
    
    if mode not in power_plans:
        return f"Invalid mode. Choose: {', '.join(power_plans.keys())}"
    
    plan_guid = power_plans[mode]
    
    try:
        # Use powercfg to switch plan
        cmd = f'powercfg /setactive {plan_guid}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info(f"[SystemUtils] Switched to {mode} mode.")
            return f"System switched to {mode} mode."
        else:
            return f"Failed to switch mode: {result.stderr}"
    
    except Exception as e:
        logging.error(f"[SystemUtils] Error switching power mode: {e}")
        return f"Error: {e}"


def monitor_network_traffic(duration_seconds: int = 5):
    """
    Monitors network traffic for a specified duration.
    Useful for detecting bandwidth-heavy processes or security issues.
    
    Args:
        duration_seconds: How long to monitor
    
    Returns:
        dict: {
            total_sent_mb: float,
            total_recv_mb: float,
            active_connections: int,
            top_bandwidth_processes: list
        }
    """
    import time
    
    # Get initial counters
    net_start = psutil.net_io_counters()
    
    # Wait
    time.sleep(duration_seconds)
    
    # Get final counters
    net_end = psutil.net_io_counters()
    
    # Calculate delta
    sent_mb = (net_end.bytes_sent - net_start.bytes_sent) / (1024**2)
    recv_mb = (net_end.bytes_recv - net_start.bytes_recv) / (1024**2)
    
    # Get active connections
    connections = psutil.net_connections(kind='inet')
    active_count = len([c for c in connections if c.status == 'ESTABLISHED'])
    
    # Find top bandwidth processes (requires elevated privileges)
    top_processes = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            if proc.info['connections']:
                top_processes.append({
                    'name': proc.info['name'],
                    'pid': proc.info['pid'],
                    'connections': len(proc.info['connections'])
                })
        
        top_processes.sort(key=lambda x: x['connections'], reverse=True)
    except psutil.AccessDenied:
        logging.warning("[SystemUtils] Access denied for process network info.")
    
    return {
        'total_sent_mb': sent_mb,
        'total_recv_mb': recv_mb,
        'active_connections': active_count,
        'top_bandwidth_processes': top_processes[:5]
    }


def analyze_resource_hoggers():
    """
    Identifies processes consuming excessive resources.
    Jarvis would report: "Sir, Chrome is consuming 4GB of RAM."
    
    Returns:
        dict: {
            cpu_hogs: list,  # Processes using >20% CPU
            ram_hogs: list,  # Processes using >1GB RAM
            disk_hogs: list  # Processes with high disk I/O
        }
    """
    cpu_hogs = []
    ram_hogs = []
    disk_hogs = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            # CPU hogs
            if proc.info['cpu_percent'] > 20:
                cpu_hogs.append({
                    'name': proc.info['name'],
                    'pid': proc.info['pid'],
                    'cpu_percent': proc.info['cpu_percent']
                })
            
            # RAM hogs (over 1GB)
            ram_mb = proc.info['memory_info'].rss / (1024**2)
            if ram_mb > 1024:
                ram_hogs.append({
                    'name': proc.info['name'],
                    'pid': proc.info['pid'],
                    'ram_mb': ram_mb
                })
        
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Sort by resource usage
    cpu_hogs.sort(key=lambda x: x['cpu_percent'], reverse=True)
    ram_hogs.sort(key=lambda x: x['ram_mb'], reverse=True)
    
    return {
        'cpu_hogs': cpu_hogs[:5],  # Top 5
        'ram_hogs': ram_hogs[:5],
        'disk_hogs': disk_hogs  # TODO: Implement disk I/O tracking
    }
def get_disk_io_stats():
    """
    Tracks disk read/write speeds.
    Jarvis equivalent: "Hard drive activity at 45 MB/s"
    """
    disk_io_start = psutil.disk_io_counters()
    time.sleep(1)
    disk_io_end = psutil.disk_io_counters()
    
    read_speed = (disk_io_end.read_bytes - disk_io_start.read_bytes) / 1024 / 1024  # MB/s
    write_speed = (disk_io_end.write_bytes - disk_io_start.write_bytes) / 1024 / 1024
    
    return {
        'read_speed_mbps': round(read_speed, 2),
        'write_speed_mbps': round(write_speed, 2),
        'read_count': disk_io_end.read_count - disk_io_start.read_count,
        'write_count': disk_io_end.write_count - disk_io_start.write_count
    }

def run_system_diagnostics():
    """
    Comprehensive system health check.
    Like Jarvis's "Diagnostics complete" reports.
    
    Returns:
        dict: {
            overall_health: str ('healthy' | 'warning' | 'critical'),
            issues: list,
            recommendations: list
        }
    """
    issues = []
    recommendations = []
    
    # === CHECK 1: Disk Space ===
    disk = psutil.disk_usage('/')
    if disk.percent > 90:
        issues.append("Disk space critical (>90% used)")
        recommendations.append("Clean up temporary files or move data to external storage")
    elif disk.percent > 75:
        issues.append("Disk space low (>75% used)")
    
    # === CHECK 2: RAM Usage ===
    mem = psutil.virtual_memory()
    if mem.percent > 85:
        issues.append("High RAM usage (>85%)")
        recommendations.append("Close unused applications or upgrade RAM")
    
    # === CHECK 3: CPU Temperature (if available) ===
    hardware = get_hardware_status()
    if 'cpu_temp' in hardware and hardware['cpu_temp'] > 80:
        issues.append(f"CPU temperature high ({hardware['cpu_temp']}°C)")
        recommendations.append("Check cooling system and clean dust from fans")
    
    # === CHECK 4: Battery (if laptop) ===
    if 'battery_percent' in hardware:
        if hardware['battery_percent'] < 20 and not hardware['battery_plugged']:
            issues.append("Battery low (<20%)")
            recommendations.append("Connect to power source")
    
    # === CHECK 5: Background Processes ===
    hogs = analyze_resource_hoggers()
    if len(hogs['cpu_hogs']) > 3:
        issues.append(f"{len(hogs['cpu_hogs'])} processes using high CPU")
        recommendations.append("Consider closing unnecessary applications")
    
    # === OVERALL HEALTH ===
    if any('critical' in issue.lower() for issue in issues):
        overall_health = 'critical'
    elif len(issues) > 2:
        overall_health = 'warning'
    else:
        overall_health = 'healthy'
    
    return {
        'overall_health': overall_health,
        'issues': issues,
        'recommendations': recommendations,
        'timestamp': datetime.now().isoformat()
    }


def optimize_for_activity(activity: str):
    """
    Automatically optimizes system settings based on current activity.
    
    Args:
        activity: 'coding' | 'gaming' | 'cad' | 'media'
    
    Returns:
        list: Actions taken
    
    Examples:
        - Gaming: Switch to performance mode, close background apps
        - CAD: Allocate more RAM, switch to performance mode
        - Media: Switch to balanced mode, dim UI
    """
    actions = []
    
    if activity == 'gaming':
        # Performance mode
        result = set_system_performance_mode('performance')
        actions.append(result)
        
        # Close unnecessary background apps (carefully)
        # TODO: Implement safe background app closing
        
        actions.append("Minimized system notifications")
    
    elif activity == 'cad':
        # Performance mode
        result = set_system_performance_mode('performance')
        actions.append(result)
        
        actions.append("Allocated additional resources for CAD rendering")
    
    elif activity == 'coding':
        # Balanced mode (no need for max performance)
        result = set_system_performance_mode('balanced')
        actions.append(result)
    
    elif activity == 'media':
        # Power saver mode
        result = set_system_performance_mode('power_saver')
        actions.append(result)
    
    logging.info(f"[SystemUtils] Optimized for {activity}: {actions}")
    return actions


# === WINDOWS REGISTRY UTILITIES ===

def get_startup_programs():
    """
    Lists all programs that run at Windows startup.
    Useful for system optimization.
    
    Returns:
        list: [{name, path, registry_key}]
    """
    startup_programs = []
    
    # Registry keys where startup programs are stored
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ]
    
    for hkey, key_path in keys:
        try:
            key = winreg.OpenKey(hkey, key_path)
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    startup_programs.append({
                        'name': name,
                        'path': value,
                        'registry_key': key_path
                    })
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except FileNotFoundError:
            continue
    
    return startup_programs


# === STANDALONE TEST ===
if __name__ == "__main__":
    print("=== ARGUS Enhanced System Utils - Test ===\n")
    
    print("1. Hardware Status:")
    hw = get_hardware_status()
    for key, value in hw.items():
        print(f"   {key}: {value}")
    
    print("\n2. Resource Hogs:")
    hogs = analyze_resource_hoggers()
    print(f"   CPU Hogs: {len(hogs['cpu_hogs'])}")
    for proc in hogs['cpu_hogs'][:3]:
        print(f"      - {proc['name']}: {proc['cpu_percent']}%")
    
    print(f"\n   RAM Hogs: {len(hogs['ram_hogs'])}")
    for proc in hogs['ram_hogs'][:3]:
        print(f"      - {proc['name']}: {proc['ram_mb']:.1f} MB")
    
    print("\n3. System Diagnostics:")
    diag = run_system_diagnostics()
    print(f"   Overall Health: {diag['overall_health'].upper()}")
    if diag['issues']:
        print(f"   Issues:")
        for issue in diag['issues']:
            print(f"      - {issue}")
    if diag['recommendations']:
        print(f"   Recommendations:")
        for rec in diag['recommendations']:
            print(f"      - {rec}")
    
    print("\n4. Network Traffic (5 second sample):")
    net = monitor_network_traffic(5)
    print(f"   Sent: {net['total_sent_mb']:.2f} MB")
    print(f"   Received: {net['total_recv_mb']:.2f} MB")
    print(f"   Active Connections: {net['active_connections']}")