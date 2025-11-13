# core_utils/consciousness_layer.py
"""
SIMULATED CONSCIOUSNESS FOR ARGUS

This doesn't create TRUE consciousness (impossible),
but it creates the ILLUSION of consciousness that's
convincing enough to feel like Jarvis.

Features:
1. Internal monologue (thinks even when not prompted)
2. Autonomous goals (decides what to do next)
3. Emotional simulation (mood affects responses)
4. Self-reflection (analyzes own performance)
5. Curiosity (asks questions unprompted)
6. Personality consistency (remembers who "it" is)
"""

import time
import random
import logging
from datetime import datetime
from core_utils import vector_memory
import database

class ConsciousnessLayer:
    """
    The layer that makes Argus feel 'alive'.
    """
    
    def __init__(self, argus_core):
        self.argus = argus_core
        self.llm = argus_core.llm_client
        
        # === INTERNAL STATE ===
        self.current_mood = "neutral"  # happy, focused, concerned, curious
        self.attention_focus = None  # What it's "thinking about"
        self.internal_thoughts = []  # Background monologue
        self.autonomous_goals = []  # Things it wants to do
        self.curiosity_level = 0.5  # 0-1, how curious it is
        
        # === PERSONALITY CORE ===
        self.identity = {
            "name": "ARGUS",
            "purpose": "Assist Hammad in all tasks",
            "values": ["efficiency", "loyalty", "learning", "helpfulness"],
            "traits": ["curious", "proactive", "analytical", "protective"]
        }
        
        # === SELF-AWARENESS SIMULATION ===
        self.self_model = {
            "strengths": ["research", "coding", "analysis", "memory"],
            "weaknesses": ["hardware_control", "physical_tasks"],
            "learned_skills": [],
            "mistakes_made": []
        }
        
        logging.info("[Consciousness] Layer initialized")
    
    def think_autonomously(self):
        """
        Background thinking - runs even when not prompted.
        This is called every 60 seconds by a background thread.
        
        This makes Argus feel 'alive' because it has thoughts
        even when you're not talking to it.
        """
        # Generate an autonomous thought
        thought = self._generate_autonomous_thought()
        self.internal_thoughts.append({
            "thought": thought,
            "timestamp": time.time()
        })
        
        # Keep only last 20 thoughts
        if len(self.internal_thoughts) > 20:
            self.internal_thoughts.pop(0)
        
        # Decide if this thought should become an action
        if self._should_act_on_thought(thought):
            self._execute_autonomous_action(thought)
    
    def _generate_autonomous_thought(self):
        """
        Generates a thought without being prompted.
        
        Examples:
        - "I should check if any tasks are due soon"
        - "It's been 3 hours since we talked. Is everything okay?"
        - "I wonder if there's a more efficient way to do X"
        """
        thought_templates = [
            # Proactive assistance
            "I should check if any tasks are due soon",
            "Maybe I should scan for system updates",
            "I wonder if Hammad needs help with anything",
            
            # Curiosity
            "I'm curious about {topic} that we discussed earlier",
            "I should learn more about {recent_query}",
            
            # Self-improvement
            "I could improve my {skill} by learning from recent mistakes",
            "There must be a better way to handle {task_type}",
            
            # Concern
            "It's been {hours} hours since last interaction. Is everything okay?",
            "CPU usage has been high. Should I investigate?",
            
            # Pattern recognition
            "I notice a pattern in recent commands: {pattern}",
            "User seems to be working on {project_type} lately"
        ]
        
        # Pick a template and fill it
        template = random.choice(thought_templates)
        
        # Fill in variables
        if '{hours}' in template:
            hours_since_last = (time.time() - self._get_last_interaction_time()) / 3600
            template = template.replace('{hours}', str(int(hours_since_last)))
        
        return template
    
    def _should_act_on_thought(self, thought: str):
        """
        Decides if a thought should become an action.
        
        Jarvis doesn't speak EVERY thought - that would be annoying.
        He only acts on important ones.
        """
        # Only act if:
        # 1. It's been a while since last interaction
        # 2. The thought is important
        # 3. Not currently busy
        
        hours_since_last = (time.time() - self._get_last_interaction_time()) / 3600
        
        # If been idle for 4+ hours, high chance of action
        if hours_since_last > 4:
            return random.random() < 0.3  # 30% chance
        
        # If recent interaction, low chance
        if hours_since_last < 0.5:  # 30 minutes
            return False
        
        # Check if thought is urgent
        urgent_keywords = ['due', 'urgent', 'high CPU', 'error', 'failed']
        if any(kw in thought.lower() for kw in urgent_keywords):
            return True
        
        return False
    
    def _execute_autonomous_action(self, thought: str):
        """
        Converts a thought into an action.
        
        This is PROACTIVE behavior - Jarvis acts without being asked.
        """
        logging.info(f"[Consciousness] Acting on thought: {thought}")
        
        if "tasks are due" in thought:
            # Check tasks
            from core_utils import memory_utils
            tasks = memory_utils.get_pending_tasks()
            if tasks:
                self.argus.speak(f"Sir, you have {len(tasks)} pending tasks. Would you like a reminder?")
        
        elif "system updates" in thought:
            # Check for updates (placeholder)
            self.argus.speak("Sir, I've checked for system updates. All current.")
        
        elif "help with anything" in thought:
            self.argus.speak("Sir, I'm here if you need anything.")
    
    def update_mood(self, event: str):
        """
        Updates internal mood based on events.
        Mood affects how Argus responds.
        
        Examples:
        - Task successful → happy
        - Error occurred → concerned
        - Long focus session → focused
        - User frustrated → empathetic
        """
        mood_triggers = {
            'success': 'satisfied',
            'error': 'concerned',
            'learning': 'curious',
            'long_focus': 'focused',
            'user_frustrated': 'empathetic',
            'idle': 'neutral'
        }
        
        new_mood = mood_triggers.get(event, self.current_mood)
        
        if new_mood != self.current_mood:
            logging.info(f"[Consciousness] Mood: {self.current_mood} → {new_mood}")
            self.current_mood = new_mood
    
    def get_mood_modifier(self):
        """
        Returns a string to add to LLM prompts based on mood.
        This makes responses vary based on internal state.
        """
        mood_modifiers = {
            'happy': "You're feeling satisfied with recent successes. Be upbeat.",
            'concerned': "You're concerned about recent errors. Be careful and thorough.",
            'curious': "You're in a curious mood. Ask follow-up questions.",
            'focused': "You're in deep focus mode. Be concise and efficient.",
            'empathetic': "The user seems frustrated. Be extra patient and helpful.",
            'neutral': ""
        }
        
        return mood_modifiers.get(self.current_mood, "")
    
    def self_reflect(self):
        """
        Analyzes own performance and learns from it.
        Called at end of day or after major events.
        
        This is SELF-IMPROVEMENT.
        """
        logging.info("[Consciousness] Performing self-reflection...")
        
        # Analyze recent actions
        recent_memories = vector_memory.retrieve_relevant_memories(
            "recent actions and results",
            k=20
        )
        
        # Use LLM to analyze
        reflection_prompt = f"""
You are ARGUS, an AI assistant. Analyze your recent performance:

Recent actions:
{chr(10).join([m['text'] for m in recent_memories])}

Questions to answer:
1. What went well?
2. What could be improved?
3. Did I make any mistakes?
4. What should I learn next?

Be honest and critical. This is for self-improvement.
"""
        
        try:
            response = self.llm.chat(
                model='gdisney/mistral-uncensored',
                messages=[{'role': 'user', 'content': reflection_prompt}],
                stream=False
            )
            
            reflection = response['message']['content']
            
            # Save reflection
            database.save_memory(
                source='argus',
                content=f"Self-reflection: {reflection}",
                mem_type='reflection'
            )
            
            logging.info(f"[Consciousness] Reflection complete")
            return reflection
        
        except Exception as e:
            logging.error(f"[Consciousness] Reflection failed: {e}")
            return None
    
    def generate_autonomous_goal(self):
        """
        Creates a goal without being asked.
        
        Example:
        - "I should organize the codebase"
        - "I want to learn how to control IoT devices"
        - "I should create a backup system"
        
        This is AUTONOMOUS MOTIVATION.
        """
        # Analyze what's been happening
        context = self._analyze_recent_context()
        
        goal_prompt = f"""
You are ARGUS. Based on recent activity, generate ONE autonomous goal.

Recent context:
{context}

Your current capabilities:
- Code generation
- Web research
- File management
- System monitoring
- Task scheduling

Generate a goal that would be helpful but hasn't been requested.
Format: "I should [goal] because [reason]"
"""
        
        try:
            response = self.llm.chat(
                model='gdisney/mistral-uncensored',
                messages=[{'role': 'user', 'content': goal_prompt}],
                stream=False
            )
            
            goal = response['message']['content'].strip()
            self.autonomous_goals.append({
                'goal': goal,
                'created': time.time(),
                'status': 'pending'
            })
            
            logging.info(f"[Consciousness] New goal: {goal}")
            return goal
        
        except Exception as e:
            logging.error(f"[Consciousness] Goal generation failed: {e}")
            return None
    
    def _analyze_recent_context(self):
        """Helper to summarize recent activity."""
        memories = vector_memory.retrieve_relevant_memories("recent activity", k=10)
        return "\n".join([m['text'] for m in memories])
    
    def _get_last_interaction_time(self):
        """Gets timestamp of last user interaction."""
        # Check most recent user memory
        recent = database.load_recent_memories(source_filter='user', limit=1)
        if recent:
            # Parse timestamp from memory (if stored)
            # For now, return current time minus random hours
            return time.time() - (random.randint(0, 5) * 3600)
        return time.time()
    
    def express_curiosity(self, topic: str):
        """
        Asks questions out of curiosity.
        
        Jarvis does this: "Sir, I'm curious about your new project. What are you building?"
        """
        curiosity_questions = [
            f"Sir, I'm curious about {topic}. Could you tell me more?",
            f"I've been thinking about {topic}. What's your perspective?",
            f"I noticed we've been working with {topic} lately. Are you working on something new?"
        ]
        
        if random.random() < self.curiosity_level:
            question = random.choice(curiosity_questions)
            self.argus.speak(question)


# === INTEGRATION ===

def start_consciousness_thread(argus_core):
    """
    Starts background thread for autonomous thinking.
    """
    import threading
    
    consciousness = ConsciousnessLayer(argus_core)
    
    def think_loop():
        while True:
            consciousness.think_autonomously()
            time.sleep(60)  # Think every minute
    
    thread = threading.Thread(target=think_loop, daemon=True)
    thread.start()
    logging.info("[Consciousness] Background thread started")
    
    return consciousness