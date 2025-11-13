# core_utils/context_engine.py
"""
ARGUS Context Engine 2.0 - The "Awareness Layer"

This module makes Argus aware of:
1. What you're doing (coding, CAD work, gaming, etc.)
2. What specific file/project you're working on
3. How long you've been focused
4. When to suggest breaks or context switches

Inspired by: Jarvis's ability to anticipate Tony Stark's needs
"""

import psutil
import win32gui
import win32process
import datetime
import time
from collections import defaultdict
import re
import logging

class ContextEngine:
    def __init__(self, send_to_ui_func, speak_func):
        """
        Initializes the Context Engine.
        
        Args:
            send_to_ui_func: Function to send data to the Electron UI
            speak_func: Function to make Argus speak
        """
        self.send_to_ui = send_to_ui_func
        self.speak = speak_func
        
        # === APP SIGNATURES (Based on your installed apps) ===
        # This maps activities to the actual .exe names on your system
        self.APP_SIGNATURES = {
            'coding': [
                'Code.exe',              # Visual Studio Code
                'devenv.exe',            # Visual Studio
                'python.exe',
                'pythonw.exe',
                'node.exe',
                'powershell.exe',        # When scripting
                'WindowsTerminal.exe'
            ],
            'cad': [
                'acad.exe',              # AutoCAD 2026
                'Fusion360.exe',
                'SOLIDWORKS.exe',
                'Inventor.exe'
            ],
            'gaming': [
                'GTA5.exe',
                'RDR2.exe',
                'EpicGamesLauncher.exe',
                'RockstarGamesLauncher.exe',
                'Steam.exe',
                'steamwebhelper.exe'
            ],
            'media': [
                'vlc.exe',
                'spotify.exe',
                'chrome.exe',            # YouTube detection via title
                'msedge.exe',
                'firefox.exe'
            ],
            'communication': [
                'Discord.exe',
                'Telegram.exe',
                'WhatsApp.exe',
                'Teams.exe',
                'Slack.exe'
            ],
            'productivity': [
                'WINWORD.EXE',           # Microsoft Word
                'EXCEL.EXE',
                'POWERPNT.EXE',
                'ONENOTE.EXE',
                'Notion.exe',
                'obsidian.exe'
            ]
        }
        
        # === STATE TRACKING ===
        self.current_activity = "idle"
        self.current_focus_app = None
        self.focus_start_time = time.time()
        self.activity_history = defaultdict(int)  # Total time per activity
        self.last_suggestion_time = 0
        self.session_start = time.time()
        
        # === PATTERN LEARNING ===
        self.activity_transitions = []  # List of (from_activity, to_activity, timestamp)
        self.daily_patterns = {}  # hour -> most_common_activity
        
        logging.info("--- [ContextEngine] Initialized successfully ---")
    
    def get_active_window_info(self):
        """
        Gets detailed information about the currently focused window.
        
        Returns:
            dict: {process_name, window_title, pid, exe_path}
            None: If detection fails
        """
        try:
            # Get the foreground window handle
            hwnd = win32gui.GetForegroundWindow()
            
            # Get the process ID that owns this window
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            # Get the window title (e.g., "main.py - Visual Studio Code")
            title = win32gui.GetWindowText(hwnd)
            
            # Get the process object
            process = psutil.Process(pid)
            
            return {
                'process_name': process.name(),
                'window_title': title,
                'pid': pid,
                'exe_path': process.exe()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
            logging.debug(f"[ContextEngine] Could not get window info: {e}")
            return None
    
    def detect_activity(self):
        """
        Main detection logic - the "eyes" of the Context Engine.
        
        Returns:
            tuple: (activity_name: str, context: dict)
            
        Example:
            ('coding', {
                'app_name': 'Code.exe',
                'current_file': 'main.py',
                'state': 'editing',
                'language': 'python'
            })
        """
        window_info = self.get_active_window_info()
        if not window_info:
            return "idle", {}
        
        proc_name = window_info['process_name']
        title = window_info['window_title']
        
        # === ACTIVITY DETECTION ===
        for activity, processes in self.APP_SIGNATURES.items():
            if any(proc.lower() == proc_name.lower() for proc in processes):
                
                context = {
                    'app_name': proc_name,
                    'window_title': title,
                    'pid': window_info['pid']
                }
                
                # === ENHANCED CONTEXT EXTRACTION ===
                
                # --- CODING CONTEXT ---
                if activity == 'coding':
                    # Detect VS Code
                    if 'Visual Studio Code' in title or 'Code.exe' in proc_name:
                        # Extract current file (format: "● main.py - ARGUS - Visual Studio Code")
                        file_match = re.search(r'[●]?\s*(.+?\.(?:py|js|cpp|html|css|json))', title)
                        if file_match:
                            context['current_file'] = file_match.group(1).strip()
                            
                            # Detect language from extension
                            if '.py' in context['current_file']:
                                context['language'] = 'python'
                            elif '.js' in context['current_file']:
                                context['language'] = 'javascript'
                            elif '.cpp' in context['current_file']:
                                context['language'] = 'cpp'
                        
                        # Detect state
                        if '●' in title:  # Unsaved changes (VS Code convention)
                            context['state'] = 'editing_unsaved'
                        else:
                            context['state'] = 'editing'
                    
                    # Detect debugging
                    if 'Debugging' in title or 'Running' in title:
                        context['state'] = 'debugging'
                    
                    # Detect terminal work
                    if 'Terminal' in title or 'PowerShell' in proc_name:
                        context['state'] = 'terminal'
                
                # --- CAD CONTEXT ---
                elif activity == 'cad':
                    # Extract project file name
                    if '.dwg' in title.lower():
                        context['file_type'] = 'autocad'
                        dwg_match = re.search(r'(.+?)\.dwg', title, re.IGNORECASE)
                        if dwg_match:
                            context['project_file'] = dwg_match.group(1).strip()
                    
                    elif '.step' in title.lower() or '.stp' in title.lower():
                        context['file_type'] = 'step'
                    
                    # Detect if rendering
                    if 'render' in title.lower():
                        context['state'] = 'rendering'
                
                # --- GAMING CONTEXT ---
                elif activity == 'gaming':
                    context['suppress_all'] = True  # Don't disturb
                    
                    # Detect specific game
                    if 'GTA' in title:
                        context['game'] = 'GTA V'
                    elif 'Launcher' in proc_name:
                        context['state'] = 'launcher'
                
                # --- MEDIA CONTEXT ---
                elif activity == 'media':
                    # Detect YouTube
                    if 'YouTube' in title:
                        context['media_type'] = 'youtube'
                        # Try to extract video title
                        yt_match = re.search(r'(.+?)\s*-\s*YouTube', title)
                        if yt_match:
                            context['video_title'] = yt_match.group(1).strip()
                    
                    # Detect Netflix/Streaming
                    elif 'Netflix' in title or 'Prime Video' in title or 'Disney+' in title:
                        context['media_type'] = 'streaming'
                    
                    # Detect VLC
                    elif 'vlc.exe' in proc_name.lower():
                        context['media_type'] = 'local_video'
                        # Extract file name if possible
                        if ' - VLC' in title:
                            context['video_file'] = title.replace(' - VLC media player', '').strip()
                
                # --- PRODUCTIVITY CONTEXT ---
                elif activity == 'productivity':
                    if 'WINWORD' in proc_name:
                        context['app_type'] = 'word'
                        doc_match = re.search(r'(.+?)\s*-\s*Word', title)
                        if doc_match:
                            context['document'] = doc_match.group(1).strip()
                    
                    elif 'EXCEL' in proc_name:
                        context['app_type'] = 'excel'
                
                return activity, context
        
        # No known activity detected
        return "idle", {'last_known_app': proc_name}
    
    def update_state(self):
        """
        Main update loop - call this periodically (e.g., every 5 seconds).
        This is the "brain" that tracks changes and makes decisions.
        
        Returns:
            dict: Status information about the update
        """
        activity, context = self.detect_activity()
        current_time = time.time()
        
        # === TRACK ACTIVITY CHANGES ===
        if activity != self.current_activity:
            # Activity switched!
            prev_activity = self.current_activity
            focus_duration = current_time - self.focus_start_time
            
            # Log the transition
            self.activity_transitions.append({
                'from': prev_activity,
                'to': activity,
                'timestamp': datetime.datetime.now(),
                'duration': focus_duration
            })
            
            # Update history
            self.activity_history[prev_activity] += focus_duration
            
            # Reset focus tracking
            self.current_activity = activity
            self.current_focus_app = context.get('app_name')
            self.focus_start_time = current_time
            
            logging.info(f"[ContextEngine] Activity changed: {prev_activity} -> {activity}")
            
            # === TRANSITION SUGGESTIONS (Jarvis-style) ===
            self._handle_activity_transition(prev_activity, activity, context)
        
        else:
            # Same activity, update duration
            focus_duration = current_time - self.focus_start_time
            
            # === LONG FOCUS WARNINGS ===
            # Jarvis cares about Tony's health!
            if focus_duration > 7200:  # 2 hours
                if current_time - self.last_suggestion_time > 1800:  # Every 30 min
                    self._suggest_break(activity, focus_duration)
        
        # === SEND UI UPDATE ===
        self.send_to_ui("context_update", {
            "activity": activity,
            "context": context,
            "focus_duration_seconds": int(current_time - self.focus_start_time),
            "session_duration_seconds": int(current_time - self.session_start)
        })
        
        return {
            "activity": activity,
            "context": context,
            "focus_duration": focus_duration if activity != self.current_activity else current_time - self.focus_start_time
        }
    
    def _handle_activity_transition(self, from_activity, to_activity, context):
        """
        Handles smart suggestions when you switch activities.
        This is where Jarvis-like anticipation happens.
        """
        
        # CAD -> Coding (Common workflow: Design -> Program)
        if from_activity == 'cad' and to_activity == 'coding':
            self.speak("Switching to coding mode, Sir. Should I close AutoCAD to free up system resources?")
        
        # Coding -> Gaming (You deserve a break!)
        elif from_activity == 'coding' and to_activity == 'gaming':
            self.speak("Time for a break, I see. Enjoy, Sir.")
            # Optionally: Set performance mode to 'gaming'
        
        # Idle -> Coding (Morning start)
        elif from_activity == 'idle' and to_activity == 'coding':
            hour = datetime.datetime.now().hour
            if 6 <= hour < 12:
                self.speak("Good morning, Sir. Ready to code.")
        
        # Gaming -> Productivity (Back to work)
        elif from_activity == 'gaming' and to_activity in ['coding', 'cad', 'productivity']:
            self.speak("Welcome back, Sir. Switching to work mode.")
        
        # Media -> Coding (After a break)
        elif from_activity == 'media' and to_activity == 'coding':
            if context.get('current_file'):
                self.speak(f"Resuming work on {context['current_file']}.")
    
    def _suggest_break(self, activity, duration_seconds):
        """
        Suggests a break after prolonged focus.
        Jarvis is protective of Tony's well-being.
        """
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        
        if activity == 'coding':
            self.speak(f"Sir, you've been coding for {hours} hours and {minutes} minutes. I recommend a brief break.")
        elif activity == 'cad':
            self.speak(f"You've been working in AutoCAD for over {hours} hours. Perhaps some rest?")
        
        self.last_suggestion_time = time.time()
    
    def get_ui_theme(self):
        """
        Returns the UI color scheme based on:
        1. Time of day
        2. Current activity
        
        This makes the UI "breathe" with your workflow.
        
        Returns:
            dict: {primary, secondary, accent, mode, should_dim}
        """
        hour = datetime.datetime.now().hour
        activity, _ = self.detect_activity()
        
        # === GAMING MODE (High contrast, dark red) ===
        if activity == 'gaming':
            return {
                "primary": "#c41e3a",      # Dark red (Arc Reactor stress)
                "secondary": "#0a0a0a",
                "accent": "#ff4757",
                "mode": "gaming",
                "should_dim": True,         # Dim UI to not distract
                "particle_count": 50        # Fewer particles
            }
        
        # === TIME-BASED THEMES ===
        
        # Morning (5 AM - 12 PM): Warm, energizing
        if 5 <= hour < 12:
            return {
                "primary": "#D4AF37",      # Gold (Jarvis signature)
                "secondary": "#f5f5dc",    # Beige
                "accent": "#ff9800",       # Amber
                "mode": "morning",
                "should_dim": False,
                "particle_count": 150
            }
        
        # Afternoon (12 PM - 6 PM): Cool, focused
        elif 12 <= hour < 18:
            return {
                "primary": "#3498db",      # Blue
                "secondary": "#2c3e50",    # Dark blue-grey
                "accent": "#5dade2",       # Light blue
                "mode": "afternoon",
                "should_dim": False,
                "particle_count": 120
            }
        
        # Evening (6 PM - 10 PM): Warm, relaxing
        elif 18 <= hour < 22:
            return {
                "primary": "#8e44ad",      # Purple
                "secondary": "#34495e",    # Grey
                "accent": "#bb8fce",       # Light purple
                "mode": "evening",
                "should_dim": False,
                "particle_count": 100
            }
        
        # Night (10 PM - 5 AM): Dark, minimal
        else:
            return {
                "primary": "#D4AF37",      # Gold (always Jarvis)
                "secondary": "#0f1419",    # Near-black
                "accent": "#f39c12",       # Dark gold
                "mode": "night",
                "should_dim": True,
                "particle_count": 80
            }
    
    def get_activity_summary(self):
        """
        Returns a summary of today's activity.
        Useful for end-of-day reports.
        
        Returns:
            dict: {total_coding_minutes, total_cad_minutes, ...}
        """
        summary = {}
        for activity, seconds in self.activity_history.items():
            summary[f"{activity}_minutes"] = int(seconds / 60)
        
        return summary
    
    def should_suppress_notifications(self):
        """
        Returns True if Argus should be silent (e.g., during gaming).
        
        Returns:
            bool: True if in "Do Not Disturb" mode
        """
        activity, context = self.detect_activity()
        
        # Suppress during gaming
        if activity == 'gaming':
            return True
        
        # Suppress during media (unless it's a critical alert)
        if activity == 'media' and context.get('media_type') in ['streaming', 'local_video']:
            return True
        
        return False


# === STANDALONE TEST ===
if __name__ == "__main__":
    # Test the Context Engine independently
    print("=== ARGUS Context Engine 2.0 - Standalone Test ===\n")
    
    def mock_send_to_ui(msg_type, data):
        print(f"[UI] {msg_type}: {data}")
    
    def mock_speak(text):
        print(f"[ARGUS] {text}")
    
    engine = ContextEngine(mock_send_to_ui, mock_speak)
    
    print("Monitoring your activity for 60 seconds...\n")
    
    for i in range(12):  # 12 iterations = 60 seconds
        result = engine.update_state()
        print(f"[{i*5}s] Activity: {result['activity']} | Focus: {result['focus_duration']:.1f}s")
        
        # Get current theme
        theme = engine.get_ui_theme()
        print(f"      Theme: {theme['mode']} (Primary: {theme['primary']})")
        print()
        
        time.sleep(5)
    
    print("\n=== Session Summary ===")
    summary = engine.get_activity_summary()
    for activity, minutes in summary.items():
        print(f"{activity}: {minutes} minutes")