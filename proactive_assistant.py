# core_utils/proactive_assistant.py
"""
ARGUS Proactive Assistant - "The Anticipation Layer"

This module makes Argus proactive, not just reactive.

Features:
1. Morning briefings ("You have 3 tasks due today...")
2. Pattern learning ("You usually start coding at 9 AM")
3. Anticipatory suggestions ("You're viewing a CAD file. Need the material specs?")
4. Smart reminders (escalating based on urgency)
5. Workflow optimization ("You could save time by...")

Inspired by: Jarvis anticipating Tony's needs before he asks
"""

import datetime
import time
import logging
from collections import defaultdict

import requests
from core_utils import memory_utils, vector_memory
import database
def get_weather():
        """
        Gets weather from wttr.in (free, no API key)
        """
        try:
            response = requests.get('https://wttr.in/Silchar?format=3', timeout=5)
            if response.status_code == 200:
                return response.text.strip()  # "Silchar: ☀️  +24°C"
        except:
            pass
        return None

class ProactiveAssistant:
    def __init__(self, argus_core, context_engine):
        """
        Initializes the Proactive Assistant.
        
        Args:
            argus_core: The main ArgusCore instance
            context_engine: The ContextEngine instance
        """
        self.argus = argus_core
        self.context = context_engine
        self.speak = argus_core.speak
        self.send_to_ui = argus_core.send_to_ui if hasattr(argus_core, 'send_to_ui') else None
        
        # === STATE TRACKING ===
        self.last_briefing_date = None
        self.last_pattern_check = time.time()
        self.last_suggestion_time = 0
        
        # === PATTERN LEARNING ===
        # Format: {pattern_key: count}
        # Example: {"coding_Monday_9": 15} means you coded on Mondays at 9 AM 15 times
        self.learned_patterns = self._load_patterns()
        
        # === SUGGESTION HISTORY ===
        # To avoid repeating the same suggestion
        self.suggestion_history = []
        self.max_suggestion_history = 50
        
        logging.info("[ProactiveAssistant] Initialized successfully.")
    
    def _load_patterns(self):
        """
        Loads learned patterns from the database.
        In the future, we'll store these in a dedicated table.
        For now, we use profile settings.
        """
        patterns_json = database.load_profile_setting('learned_patterns', '{}')
        try:
            import json
            return json.loads(patterns_json)
        except:
            return {}
    
    def _save_patterns(self):
        """Saves learned patterns to the database."""
        import json
        database.save_profile_setting('learned_patterns', json.dumps(self.learned_patterns))
    
    def run_proactive_checks(self):
        """
        Main loop function. Call this periodically (e.g., every 5 minutes).
        
        This is where all the "magic" happens:
        - Morning briefings
        - Pattern learning
        - Anticipatory suggestions
        """
        current_time = time.time()
        
        # === 1. MORNING BRIEFING ===
        # Run once per day, between 6-10 AM
        if self._should_give_morning_briefing():
            self.morning_briefing()
        
        # === 2. PATTERN LEARNING ===
        # Check every 15 minutes
        if current_time - self.last_pattern_check > 900:  # 15 minutes
            self._learn_current_pattern()
            self.last_pattern_check = current_time
        
        # === 3. ANTICIPATORY SUGGESTIONS ===
        # Check every 5 minutes, but only if not recently suggested
        if current_time - self.last_suggestion_time > 300:  # 5 minutes
            self._make_anticipatory_suggestions()
    
    def _should_give_morning_briefing(self):
        """
        Returns True if it's morning and we haven't briefed yet today.
        """
        now = datetime.datetime.now()
        today = now.date()
        hour = now.hour
        
        # Only between 6-10 AM
        if not (6 <= hour < 10):
            return False
        
        # Only once per day
        if self.last_briefing_date == today:
            return False
        
        return True
    
    def morning_briefing(self):
        """
        Delivers a comprehensive morning briefing.
        
        This is like how Jarvis greets Tony each morning with status updates.
        """
        now = datetime.datetime.now()
        self.last_briefing_date = now.date()
        
        logging.info("[ProactiveAssistant] Delivering morning briefing...")
        
        briefing_parts = []
        
        # === GREETING ===
        user_name = database.load_profile_setting('name', 'Sir')
        greeting = self._get_time_greeting()
        briefing_parts.append(f"{greeting}, {user_name}.")
        
        # === TASKS DUE TODAY ===
        tasks = memory_utils.get_pending_tasks()
        tasks_today = [t for t in tasks if 
                      datetime.datetime.fromisoformat(t['due_date']).date() == now.date()]
        
        if tasks_today:
            briefing_parts.append(f"You have {len(tasks_today)} task{'s' if len(tasks_today) > 1 else ''} due today.")
            # List the first 3
            for i, task in enumerate(tasks_today[:3]):
                briefing_parts.append(f"Task {i+1}: {task['description']}")
        else:
            briefing_parts.append("No urgent tasks today.")
        
        # === OVERDUE TASKS ===
        overdue = [t for t in tasks if 
                  datetime.datetime.fromisoformat(t['due_date']) < now]
        if overdue:
            briefing_parts.append(f"You have {len(overdue)} overdue task{'s' if len(overdue) > 1 else ''}.")
        
        # === PREDICTED SCHEDULE ===
        # Based on learned patterns
        predicted_activity = self._predict_activity_for_time(now.hour, now.strftime("%A"))
        if predicted_activity:
            briefing_parts.append(f"Based on your patterns, you usually {predicted_activity} around this time.")
        
        weather = get_weather()
        if weather:
            briefing_parts.append(f"Weather: {weather}")
        
        # === SYSTEM STATUS ===
        # Check if any critical system issues
        # (In a full implementation, we'd check disk space, updates, etc.)
        
        # === DELIVER THE BRIEFING ===
        full_briefing = " ".join(briefing_parts)
        self.speak(full_briefing)
        
        if self.send_to_ui:
            self.send_to_ui("morning_briefing", {
                "tasks_today": len(tasks_today),
                "tasks_overdue": len(overdue),
                "predicted_activity": predicted_activity
            })
    
    def _get_time_greeting(self):
        """Returns a time-appropriate greeting."""
        hour = datetime.datetime.now().hour
        if 5 <= hour < 12:
            return "Good morning"
        elif 12 <= hour < 18:
            return "Good afternoon"
        else:
            return "Good evening"
    
    def _learn_current_pattern(self):
        """
        Records the current activity to learn patterns over time.
        
        Example: If you always code on Mondays at 9 AM, this will learn that.
        After 5+ occurrences, it becomes a "habit" that Argus can reference.
        """
        activity, context = self.context.detect_activity()
        
        # Don't learn 'idle'
        if activity == 'idle':
            return
        
        now = datetime.datetime.now()
        day_of_week = now.strftime("%A")  # "Monday", "Tuesday", etc.
        hour = now.hour
        
        # Create a pattern key
        pattern_key = f"{activity}_{day_of_week}_{hour}"
        
        # Increment the count
        self.learned_patterns[pattern_key] = self.learned_patterns.get(pattern_key, 0) + 1
        
        # Save every 10 increments to reduce disk writes
        if self.learned_patterns[pattern_key] % 10 == 0:
            self._save_patterns()
        
        # === CHECK IF THIS IS A NEW HABIT ===
        # If this pattern has occurred 5+ times, inform the user
        if self.learned_patterns[pattern_key] == 5:
            self.speak(f"I've noticed you often {activity} on {day_of_week}s around {hour}:00. I'll remember this.")
            logging.info(f"[ProactiveAssistant] New habit learned: {pattern_key}")
    
    def _predict_activity_for_time(self, hour: int, day: str):
        """
        Predicts what the user will likely do at a given time.
        
        Args:
            hour: Hour of day (0-23)
            day: Day of week ("Monday", etc.)
        
        Returns:
            str: Predicted activity, or None
        """
        # Find all patterns matching this time
        matching_patterns = {}
        for pattern_key, count in self.learned_patterns.items():
            parts = pattern_key.split('_')
            if len(parts) == 3:
                activity, pattern_day, pattern_hour = parts
                if pattern_day == day and int(pattern_hour) == hour:
                    matching_patterns[activity] = count
        
        if not matching_patterns:
            return None
        
        # Return the most frequent activity
        most_common = max(matching_patterns, key=matching_patterns.get)
        return most_common
    
    def _make_anticipatory_suggestions(self):
        """
        Makes smart suggestions based on current context.
        
        This is the core of "Jarvis-like" intelligence.
        
        Examples:
        - You're viewing a CAD file → "Should I search for material specs?"
        - You're debugging code → "Should I search Stack Overflow?"
        - You just saved a project → "Should I commit to Git?"
        """
        activity, context = self.context.detect_activity()
        
        # Don't suggest during gaming or idle
        if activity in ['gaming', 'idle']:
            return
        
        suggestions = []
        
        # === CODING SUGGESTIONS ===
        if activity == 'coding':
            # Unsaved changes
            if context.get('state') == 'editing_unsaved':
                suggestions.append({
                    "text": "You have unsaved changes. Should I remind you to save?",
                    "action": "remind_save",
                    "priority": "low"
                })
            
            # Debugging
            if context.get('state') == 'debugging':
                suggestions.append({
                    "text": "You're debugging. Should I search for this error on Stack Overflow?",
                    "action": "search_stackoverflow",
                    "priority": "medium"
                })
            
            # Long coding session
            if self.context.focus_start_time:
                duration = time.time() - self.context.focus_start_time
                if duration > 5400:  # 1.5 hours
                    suggestions.append({
                        "text": "You've been coding for 90 minutes. Should I suggest a break?",
                        "action": "suggest_break",
                        "priority": "medium"
                    })
        
        # === CAD SUGGESTIONS ===
        elif activity == 'cad':
            # Project file detected
            if context.get('project_file'):
                project_name = context['project_file']
                
                # Check if there's a related Python script
                # (Common workflow: Design in CAD, then write automation script)
                suggestions.append({
                    "text": f"Working on {project_name}. Should I open the related Python script?",
                    "action": "open_related_script",
                    "priority": "low"
                })
            
            # Rendering detected
            if context.get('state') == 'rendering':
                suggestions.append({
                    "text": "Rendering in progress. Should I notify you when complete?",
                    "action": "notify_when_done",
                    "priority": "high"
                })
        
        # === PRODUCTIVITY SUGGESTIONS ===
        elif activity == 'productivity':
            # Writing a document
            if context.get('app_type') == 'word':
                # Check if it's been a while since last save
                # (This would require file monitoring, which we could add)
                pass
        
        # === DELIVER SUGGESTIONS ===
        if suggestions:
            # Only deliver if we haven't suggested recently
            for suggestion in suggestions:
                # Check if we've made this suggestion before
                if suggestion['text'] not in self.suggestion_history:
                    self._deliver_suggestion(suggestion)
                    
                    # Add to history
                    self.suggestion_history.append(suggestion['text'])
                    if len(self.suggestion_history) > self.max_suggestion_history:
                        self.suggestion_history.pop(0)
                    
                    # Only one suggestion at a time
                    break
    
    def _deliver_suggestion(self, suggestion):
        """
        Delivers a suggestion to the user.
        
        Args:
            suggestion: dict with {text, action, priority}
        """
        self.last_suggestion_time = time.time()
        
        logging.info(f"[ProactiveAssistant] Suggesting: {suggestion['text']}")
        
        # For high-priority suggestions, speak them
        if suggestion['priority'] == 'high':
            self.speak(suggestion['text'])
        
        # Always send to UI
        if self.send_to_ui:
            self.send_to_ui("proactive_suggestion", suggestion)

    
    
    def anticipate_next_action(self):
        """
        Based on current activity and learned patterns, predict the next action.
        
        This is called when the user finishes an activity.
        
        Returns:
            str: Predicted next action (or None)
        """
        current_activity = self.context.current_activity
        
        # Analyze transitions
        transitions = self.context.activity_transitions
        
        # Count what usually follows this activity
        next_activities = defaultdict(int)
        for transition in transitions:
            if transition['from'] == current_activity:
                next_activities[transition['to']] += 1
        
        if not next_activities:
            return None
        
        # Return the most common next activity
        most_likely = max(next_activities, key=next_activities.get)
        return most_likely
    
    def suggest_workflow_optimization(self):
        """
        Analyzes the user's workflow and suggests improvements.
        
        Example: "I've noticed you always switch from CAD to File Explorer
                 to find your renders. Should I create a quick-access button?"
        
        This is advanced and would require significant pattern analysis.
        Placeholder for future implementation.
        """
        # TODO: Implement workflow analysis
        pass
    
    def get_learned_patterns_summary(self):
        """
        Returns a human-readable summary of learned patterns.
        Useful for debugging and showing the user what Argus has learned.
        
        Returns:
            list: List of pattern descriptions
        """
        summaries = []
        
        for pattern_key, count in sorted(self.learned_patterns.items(), 
                                         key=lambda x: x[1], reverse=True):
            if count < 5:  # Only show established patterns
                continue
            
            parts = pattern_key.split('_')
            if len(parts) == 3:
                activity, day, hour = parts
                summaries.append(f"You {activity} on {day}s around {hour}:00 ({count} times)")
        
        return summaries[:10]  # Top 10


# === STANDALONE TEST ===
if __name__ == "__main__":
    print("=== ARGUS Proactive Assistant - Standalone Test ===\n")
    
    # Mock objects for testing
    class MockArgus:
        def speak(self, text):
            print(f"[ARGUS SPEAKS] {text}")
        
        def send_to_ui(self, msg_type, data):
            print(f"[UI UPDATE] {msg_type}: {data}")
    
    class MockContext:
        def __init__(self):
            self.current_activity = "coding"
            self.focus_start_time = time.time() - 6000  # 100 minutes ago
            self.activity_transitions = []
        
        def detect_activity(self):
            return "coding", {
                "app_name": "Code.exe",
                "current_file": "test.py",
                "state": "editing_unsaved"
            }
    
    # Initialize
    mock_argus = MockArgus()
    mock_context = MockContext()
    assistant = ProactiveAssistant(mock_argus, mock_context)
    
    print("Testing proactive checks...\n")
    assistant.run_proactive_checks()
    
    print("\n" + "="*50 + "\n")
    print("Learned patterns summary:")
    patterns = assistant.get_learned_patterns_summary()
    if patterns:
        for pattern in patterns:
            print(f"  - {pattern}")
    else:
        print("  (No patterns learned yet)")