# main.py - ARGUS Core v2.2
# Hardened with logging and better error handling

import sys
import ollama
import sounddevice as sd
import numpy as np
from pywhispercpp.model import Model
from piper.voice import PiperVoice
import soundfile as sf
import wave
import tempfile
import os
import datetime
import database
import struct
import pvporcupine
import pyaudio
import time
import asyncio
import websockets
import threading
import json
import psutil
import re
import logging  # <-- NEW: Import logging

# --- NEW: Setup Professional Logging ---
# This will log to both the console and a file
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
LOG_FILE = "argus.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # To also logging.info to console
    ]
)
logging.info("ARGUS log initialized.")
# --- END NEW ---


# --- NEW: Import from core_utils ---
try:
    from core_utils import web_utils
    from core_utils import file_utils
    from core_utils import hot_reload
    from core_utils import app_utils
    from core_utils import memory_utils
    from core_utils import osint_utils
    from core_utils import dossier_utils
    from core_utils import vector_memory
    from core_utils import system_utils
    from core_utils import sandbox
    from core_utils import tools_registry
    from core_utils import context_engine
    from core_utils import proactive_assistant
    from core_utils import cad_utils
    from core_utils import comms_utils
    from core_utils import username_finder
    from core_utils import spotify_utils
    from core_utils import autonomous_learning
    from core_utils import consciousness_layer
    




    # === SYSTEM: Fix missing open_app ===
    from core_utils.system_utils import launch_application as open_app
    from core_utils.system_utils import execute_command

    # === WEB: Fix missing open_webview / open_app_web ===
    from core_utils.web_utils import search_web

    # Create aliases that main.py expects
    open_webview = search_web
    open_app_web = search_web  # or make a version that opens browser — see below

    import config
except ImportError as e:
    logging.error(f"FATAL: A core_utils file is missing. {e}")
    logging.error("Please ensure all core_utils files and config.py are in place.")
    exit()

# --- Global variables ---
ui_websocket = None
argus_core_instance = None
server_loop = None


# --- Configuration for LLM ---

MODEL_NAME = 'gdisney/mistral-uncensored' # (Or your preferred model)

# --- WebSocket Server Logic (Thread-Safe) ---
async def server_handler(websocket):
    """Handles incoming WebSocket connections."""
    global ui_websocket
    ui_websocket = websocket
    logging.info("UI Connected!")
    try:
        logging.info("--- [History] Loading conversation history... ---")
        # 1. Load user memories
        user_history = database.load_recent_memories(source_filter='user', limit=100, type_filter='conversation')
        # 2. Load Argus memories
        argus_history = database.load_recent_memories(source_filter='argus', limit=100, type_filter='conversation')
        
        # 3. Combine and sort them (a simple way, not perfect for timestamps yet)
        # We'll just send them in two batches
        
        history_packet = {
            "user": user_history,
            "argus": argus_history
        }
        
        # 4. Send the history packet
        await websocket.send(json.dumps({"type": "history", "data": history_packet}))
        logging.info(f"--- [History] Sent {len(user_history)} user messages and {len(argus_history)} ARGUS messages. ---")

    except Exception as e:
        logging.error(f"--- [History] Error loading history: {e} ---")
    try:
        async for message in websocket:
            try:
                parsed_message = json.loads(message)
                
                if parsed_message.get('type') == 'text_command':
                    command_text = parsed_message.get('data', {}).get('text')
                    if command_text and argus_core_instance:
                        logging.info(f"<- Received text command from UI: {command_text}")
                        # Process the command, noting it's from the UI to prevent echo
                        argus_core_instance.process_command(command_text, from_ui=True)
                
                # NEW: Handle voice input from UI mic button
                elif parsed_message.get('type') == 'voice_input':
                    audio_base64 = parsed_message.get('data', {}).get('audio')
                    if audio_base64:
                        # Decode and process audio
                        # You'll need to add STT processing here
                        # For now, just acknowledge receipt
                        await websocket.send(json.dumps({
                            "type": "status",
                            "data": {"state": "processing_voice"}
                        }))
                        
            except json.JSONDecodeError:
                logging.error(f"<- Received non-JSON message from UI: {message}")
    except websockets.exceptions.ConnectionClosed:
        logging.error("UI Disconnected.")
    finally:
        ui_websocket = None

async def start_server():
    """Starts the WebSocket server."""
    async with websockets.serve(server_handler, "localhost", 8765):
        await asyncio.Future()  # run forever

def run_server_in_thread():
    """Runs the asyncio server in a separate thread and saves its event loop."""
    global server_loop
    server_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(server_loop)
    server_loop.run_until_complete(start_server())

# --- Helper Functions (Thread-Safe) ---
def get_greeting():
    """Returns a time-appropriate greeting."""
    current_hour = datetime.datetime.now().hour
    if 5 <= current_hour < 12: return "Good morning"
    elif 12 <= current_hour < 18: return "Good afternoon"
    else: return "Good evening"

def send_to_ui(message_type, data):
    """Thread-safely sends a JSON message to the UI."""
    if ui_websocket and server_loop:
        message = json.dumps({"type": message_type, "data": data})
        
        # --- FIX: Make this "fire-and-forget" ---
        # This is more resilient. We don't wait for the result.
        # This will stop the "Error sending to UI" spam.
        asyncio.run_coroutine_threadsafe(
            ui_websocket.send(message), 
            server_loop
        )

def polish_for_voice(text: str) -> str:
        """
        Converts raw LLM output into a Jarvis-style spoken line.
        Adds rhythm, removes redundancies, and makes it sound elegant.
        """
        import re

        # Clean redundant prefixes or patterns
        text = re.sub(r"^(Response:|Argus:)\s*", "", text.strip(), flags=re.I)

        # Replace typical filler or mechanical phrases
        replacements = {
            "Processing": "Working on it, Sir.",
            "Running tool": "Executing the command, Sir.",
            "Analyzing": "Running analysis.",
            "Understood": "Understood, Sir.",
            "Okay": "Very well, Sir.",
            "Alright": "Of course, Sir.",
            "Done": "Task complete, Sir.",
            "Let me": "Allow me to",
            "I will": "Initiating sequence now.",
            "One moment": "Just a moment, Sir.",
            "Hold on": "Stand by, Sir."
        }
        for k, v in replacements.items():
            text = re.sub(rf"\b{k}\b", v, text, flags=re.I)

        # Add pauses for natural cadence
        text = text.replace(",", ", ")
        if not text.endswith("."):
            text += "."

        # Subtle rhythmic tweak: add a small break after 'Sir'
        text = text.replace("Sir,", "Sir...")

        # Capitalize after punctuation if missed
        text = re.sub(r'([.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), text)

        return text

def monitor_system_vitals():
    """Continuously monitors and sends system vitals to the UI."""
    while True:
        try:
            vitals = {
                "cpu": psutil.cpu_percent(interval=1),
                "ram": psutil.virtual_memory().percent
            }
            send_to_ui("system_vitals", vitals)
        except Exception as e:
            logging.info(f"Vitals monitoring error: {e}")
            time.sleep(5) # Don't spam errors

# --- Habit Analyzer (No changes, keep as-is) ---
def analyze_and_report_habits():
    """Analyzes recent commands to calculate a work/health/study score and sends it to the UI."""
    # (Your existing habit logic - keep it)
    pass # Placeholder

def monitor_habits():
    """Periodically runs the habit analysis."""
    while True:
        analyze_and_report_habits()
        time.sleep(60) # Re-analyze every 60 seconds

class ArgusCore:
    def __init__(self):
        logging.info("Initializing ARGUS Core...")
        database.initialize_database()
        self.user_profile = self.load_user_profile()
        self.llm_client = None
        self.stt_model = None
        self.voice = None
        self.is_muted = False
        self.samplerate = 16000
        self.channels = 1
        self.porcupine_access_key = "CGc5xyG3cQ3VGWyfoYVtx2IYXg0xG8Cl0SfHKSyFoPQwvrAL0g19/A=="
        self.porcupine = None
        
        self.TOOLS = {} # Registry for dynamically-loaded tools
        app_utils.send_to_ui = send_to_ui # Give app_utils access to the UI
        memory_utils.send_to_ui = send_to_ui
        memory_utils.speak = self.speak

        # --- FIX: Load persistent tools from the registry ---
        logging.info("Reloading all persistent tools from registry...")
        tools_registry.reload_all_tools() # This loads them into sys.modules
        for tool_name in tools_registry.list_tools():
            if tool_name in sys.modules:
                module = sys.modules[tool_name]
                if hasattr(module, 'run'):
                    self.TOOLS[tool_name] = module.run
                    logging.info(f"Loaded persistent tool: {tool_name}")
            else:
                logging.warning(f"Tool {tool_name} found in registry but failed to load.")
        logging.info("ARGUS Core Initialized. Standing by.")
        logging.info("[ArgusCore] Initializing Context Engine 2.0...")
        self.context_engine = context_engine.ContextEngine(
            send_to_ui_func=send_to_ui,
            speak_func=self.speak
        )
        logging.info("[ArgusCore] Initializing Proactive Assistant...")
        self.proactive_assistant = proactive_assistant.ProactiveAssistant(
            argus_core=self,
            context_engine=self.context_engine
        )
        logging.info("[ArgusCore] Registering advanced system tools...")
        self.TOOLS.update({
            # System monitoring
            "get_hardware_status": system_utils.get_hardware_status,
            "run_diagnostics": system_utils.run_system_diagnostics,
            "analyze_resource_hogs": system_utils.analyze_resource_hoggers,
            "monitor_network": system_utils.monitor_network_traffic,
            "convert_step" : cad_utils.convert_step_to_gltf,
            'send_email': comms_utils.send_email,
            "send_sms": comms_utils.send_sms,
            "send_whatsapp": comms_utils.send_whatsapp,
            "message_mom": lambda msg: comms_utils.message_contact('mom', msg),
            "message_dad": lambda msg: comms_utils.message_contact('dad', msg),
            "play_music": spotify_utils.smart_play,
            "pause_music": spotify_utils.pause_music,
            "skip_track": spotify_utils.skip_track,
            "set_volume": spotify_utils.set_volume,
            "current_track": spotify_utils.get_current_track,
            "play_mood": spotify_utils.play_mood_music,
                
            # Performance control
            "set_performance_mode": system_utils.set_system_performance_mode,
            "optimize_for_activity": system_utils.optimize_for_activity,
                
            # Context awareness
            "get_current_activity": lambda: self.context_engine.detect_activity(),
            "get_activity_summary": self.context_engine.get_activity_summary,
                
            # Proactive features
            "get_learned_patterns": self.proactive_assistant.get_learned_patterns_summary,
            "predict_next_action": self.proactive_assistant.anticipate_next_action,
        })
        logging.info("[ArgusCore] Advanced system tools are now live.")
        
        logging.info("[ArgusCore] All intelligence modules loaded successfully.")
        logging.info("[ArgusCore] Initializing Consciousness Layer...")
        self.consciousness = None  # Will be set after full init
        
        # === NEW: INITIALIZE AUTONOMOUS LEARNING ===
        logging.info("[ArgusCore] Initializing Autonomous Learning...")
        self.autonomous_learner = None  # Will be set after full init
    
    def load_user_profile(self):
        logging.info("Loading user profile from database...")
        name = database.load_profile_setting('name', 'Hammad')
        return {"name": name}

    def load_llm(self):
        logging.info("Connecting to Language Model via Ollama...")
        try:
            self.llm_client = ollama.Client()
            self.llm_client.list() # Test connection
            logging.info("Language Model is online.")
        except Exception as e:
            logging.info(f"Ollama Connection Error: {e}")
            self.llm_client = None

    def load_stt(self):
        logging.info("Initializing C++ Speech-to-Text engine (pywhispercpp)...")
        model_path = os.path.join('models', 'ggml-base.en.bin')
        if not os.path.exists(model_path):
            logging.info(f"--- WHISPER.CPP MODEL NOT FOUND at {model_path} ---")
            logging.info("Please download 'ggml-base.en.bin' and place it in the 'models' folder.")
            self.stt_model = None
            return
            
        try:
            # --- THIS IS THE FIX ---
            # We pass the model_path as the first argument, not as a keyword
            self.stt_model = Model(model_path) 
            # --- END FIX ---
            
            logging.info("C++ STT engine is online.")
        except Exception as e:
            logging.info(f"Could not load pywhispercpp model: {e}")
            self.stt_model = None
            
    def load_tts(self):
        logging.info("Initializing Text-to-Speech engine (Piper)...")
        voice_model_path = os.path.join('voice', 'en_GB-northern_english_male-medium.onnx')
        try:
            self.voice = PiperVoice.load(voice_model_path)
            logging.info("TTS engine is online.")
        except Exception as e:
            logging.info(f"Piper Load Error: {e}")
            self.voice = None
    
    def load_wake_word_engine(self):
        logging.info("Initializing Wake Word engine (Porcupine)...")
        custom_wake_word_path = os.path.join('wakeword', 'Argus_en_windows_v3_0_0.ppn')
        if not os.path.exists(custom_wake_word_path):
            logging.info(f"--- WAKE WORD FILE NOT FOUND: {custom_wake_word_path} ---")
            self.porcupine = None
            return
        try:
            self.porcupine = pvporcupine.create(
                access_key=self.porcupine_access_key,
                keyword_paths=[custom_wake_word_path]
            )
            logging.info("Wake Word engine is online with custom 'Argus' model.")
        except Exception as e:
            logging.info(f"Porcupine initialization error: {e}")
            self.porcupine = None
            
    

    def speak(self, text):
        """
        Synthesizes audio and returns the playback thread.
        """
        cleaned_text = polish_for_voice(text)
        
        logging.info(f"ARGUS: {cleaned_text}")
        send_to_ui("speech", {"text": cleaned_text})

        if self.is_muted or not self.voice:
            return None # Return None if not speaking

        def _play_audio():
            try:
                sd.stop() # Stop any currently playing audio
                audio_stream = self.voice.synthesize(cleaned_text)
                audio_data = b"".join([chunk.audio_int16_bytes for chunk in audio_stream])
                if not audio_data: return
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                sd.play(audio_array, self.voice.config.sample_rate)
                sd.wait()
            except Exception as e:
                logging.info(f"TTS Playback Error in thread: {e}")

        playback_thread = threading.Thread(target=_play_audio, daemon=True)
        playback_thread.start()
        return playback_thread # Return the thread

    def listen_for_command(self, silence_duration=1.5, threshold=0.02):
        if not self.stt_model: 
            logging.info("--- STT engine is offline. ---")
            return None
        logging.info("\nListening for command...")
        
        recording_finished = threading.Event()
        recorded_frames = []

        def audio_callback(indata, frames, time, status):
            volume_norm = np.linalg.norm(indata) * 10
            
            if volume_norm > threshold:
                if not getattr(stream, 'recording', False):
                    logging.info("Sound detected, recording...")
                    stream.recording = True
                recorded_frames.append(indata.copy())
                stream.silence_chunks = 0
            elif getattr(stream, 'recording', False):
                recorded_frames.append(indata.copy())
                stream.silence_chunks += 1
                chunks_needed_for_silence = int(silence_duration / (frames / self.samplerate))
                if stream.silence_chunks > chunks_needed_for_silence:
                    recording_finished.set()

        try:
            with sd.InputStream(samplerate=self.samplerate, channels=self.channels, callback=audio_callback) as stream:
                stream.recording = False
                stream.silence_chunks = 0
                recording_finished.wait()

            logging.info("Processing (C++)...")
            if not recorded_frames: return ""

            recording = np.concatenate(recorded_frames, axis=0)
            audio_float32 = recording.flatten().astype(np.float32)
            
            # --- NEW: Transcribe using pywhispercpp ---
            # This is the only part of the function that's different
            # from your guide.
            segments = self.stt_model.transcribe(audio_float32)
            
            # We join the text from all segments into one string
            transcribed_text = "".join([s.text for s in segments]).strip()
            
            logging.info(f"You said: {transcribed_text}")
            return transcribed_text

        except Exception as e:
            logging.info(f"Listening error: {e}")
            return None

    # --- NEW METHOD: THE "FORGE" ---
    def execute_forge(self, prompt: str, tool_name: str = None):
        """
        The core logic for "The Force".
        1. Asks LLM to generate code.
        2. Tests the code in a secure sandbox.
        3. If successful, saves to the persistent Tool Registry.
        4. Registers it as a callable tool.
        """
        if not self.llm_client:
            self.speak("Cannot build tool: LLM is offline.")
            return

        logging.info(f"--- [Forge] Received build request: '{prompt}' ---")
        
        if not tool_name:
            tool_name = f"tool_{abs(hash(prompt)) % 10000}"

        # --- FIX: Escaped the example code's braces with {{ and }} ---
        code_gen_prompt = """
You are a Python code generator. A user wants a tool to accomplish a goal.
The goal is: '{prompt}'

You must write a single Python function named 'run' that takes no arguments.
The function MUST be named 'run'.
It must be complete, runnable, and use only standard Python libraries (like 'requests', 'os', 'json', 'datetime').
It should print its result to the console using print().

Example:
def run():
    import requests
    try:
        r = requests.get('https://api.ipify.org')
        print(f"My IP is: {{r.text}}")
    except Exception as e:
        print(f"Error: {{e}}")

Respond ONLY with the complete, raw Python code. Do not add ```python or any explanation.
""".format(prompt=prompt)
        # --- END FIX ---
        
        try:
            # --- Step 1: Ask LLM for the code ---
            self.speak(f"Forging new tool: {tool_name}. Stand by.")
            send_to_ui("status", {"state": "forging"})
            
            response = self.llm_client.chat(
                model=MODEL_NAME,
                messages=[{'role': 'system', 'content': code_gen_prompt}],
                stream=False
            )
            code = response['message']['content'].strip()

            if code.startswith("```python"):
                code = code[9:].strip("`").strip()
            
            # --- Step 2: Test the code in the Sandbox ---
            self.speak("Code generated. Running in secure sandbox...")
            send_to_ui("status", {"state": "sandboxing"})
            
            success, output = sandbox.test_code_in_sandbox(code)
            
            if not success:
                # The tool failed the test
                self.speak(f"Forge failed. The tool did not pass the sandbox test. Error: {output}")
                return # Stop here

            # --- Step 3: Load the code (Hot-Reload) ---
            self.speak("Sandbox test passed. Adding to persistent tool registry...")
            
            if tools_registry.add_tool(tool_name, code, metadata={"prompt": prompt}):
                # Now, add the *loaded function* to our live tool dictionary
                module = sys.modules.get(tool_name)
                if module and hasattr(module, 'run'):
                    self.TOOLS[tool_name] = module.run
                    self.speak(f"Forge complete. Tool '{tool_name}' is now live and registered.")
                    send_to_ui("forge_success", {"name": tool_name, "code": code})
                else:
                    self.speak("Forge failed. Could not register the tool after saving.")
            else:
                self.speak("Forge failed. Error saving tool to registry.")

        except Exception as e:
            self.speak(f"Forge failed. An error occurred: {e}")
            logging.error(f"--- [Forge] Error: {e}")
        finally:
            send_to_ui("status", {"state": "passively_listening"})


    # --- FULLY UPDATED: process_command ---
    # --- FULLY UPDATED: process_command ---
    def process_command(self, command, from_ui=False):
        """
        Enhanced command processing with:
        1. Autonomous learning fallback
        2. Mood-aware responses
        3. Self-awareness simulation
        """
        
        if not command:
            return self.speak("I'm sorry, I didn't catch that.")
        
        if not from_ui:
            send_to_ui("user_speech", {"text": command})

        # --- 1. Handle Internal Commands First (Direct User Input) ---
        cmd_lower = command.lower()
        if "mute" in cmd_lower or "go silent" in cmd_lower:
            if not self.is_muted: self.is_muted = True; return self.speak("Muting audio.")
            return None
        if "unmute" in cmd_lower or "speak again" in cmd_lower:
            if self.is_muted: self.is_muted = False; return self.speak("Audio enabled.")
            return None
        if "how are you" in cmd_lower or "how do you feel" in cmd_lower:
            mood = self.consciousness.current_mood if self.consciousness else "operational"
            self.speak(f"I'm {mood}, thank you for asking, Sir.")
            return
        
        if "what are you thinking" in cmd_lower:
            if self.consciousness and self.consciousness.internal_thoughts:
                last_thought = self.consciousness.internal_thoughts[-1]['thought']
                self.speak(f"I was just thinking: {last_thought}")
            else:
                self.speak("I'm currently focused on your requests, Sir.")
            return
        
        # Save this new command to the database *first*
        # This also triggers the vector embedding
        database.save_memory(source='user', content=command, mem_type='conversation')
        
        if not self.llm_client:
            return self.speak("My apologies, Sir, the language model is not yet online.")
        current_activity, activity_details = self.context_engine.detect_activity()
    
        # Get relevant memories (context-aware)
        relevant_memories = vector_memory.smart_retrieve(
            query_text=command,
            activity_context=current_activity,
            k=5,
            time_window_hours=48
        )
        
        # === ADD MOOD TO CONTEXT ===
        mood_modifier = ""
        if self.consciousness:
            mood_modifier = self.consciousness.get_mood_modifier()
        
        context_packet = f"--- Relevant Context ---\n"
        context_packet += f"Current Activity: {current_activity}\n"
        if activity_details:
            context_packet += f"Details: {activity_details}\n"
        
        # Add mood
        if mood_modifier:
            context_packet += f"Your Current Mood: {self.consciousness.current_mood}\n"
            context_packet += f"Mood Note: {mood_modifier}\n"
        
        context_packet += f"\n--- Relevant Memories ---\n"
        if relevant_memories:
            for mem in reversed(relevant_memories):
                priority_indicator = "★" * (mem.get('priority', 5) // 2)
                context_packet += f"[{mem['source']}] {priority_indicator} {mem['text']}\n"
        
        context_packet += "--- End of Context ---"

        # --- 2. Handle NEW Internal Commands (Forge, Run, Webview, Overlay) ---
        if cmd_lower.startswith("forge"):
            prompt = command.replace("forge", "", 1).strip()
            threading.Thread(target=self.execute_forge, args=(prompt,), daemon=True).start()
            return
        if "don't know" in response or "cannot" in response:
            # Try autonomous learning
            learned = handle_unknown_request(self, command)
            if learned:
                # Retry the command
                return self.process_command(command)
            
        if cmd_lower.startswith("run "):
            tool_name = command.split(" ")[1].strip()
            if tool_name in self.TOOLS:
                self.speak(f"Executing tool: {tool_name}")
                tool_function = self.TOOLS[tool_name]
                threading.Thread(target=tool_function, daemon=True).start()
            else:
                self.speak(f"Sir, tool '{tool_name}' is not in my registry.")
            return

        if cmd_lower.startswith("open "):
            app_name = cmd_lower.replace("open ", "", 1).strip()
            if app_name == "whatsapp":
                return self.speak(app_utils.open_webview("https://web.whatsapp.com", "WhatsApp"))
            if app_name == "gmail":
                return self.speak(app_utils.open_webview("https://mail.google.com", "Gmail"))
        
        if cmd_lower.startswith("suggest for"):
            app_name = command.replace("suggest for ", "", 1).strip()
            suggestions = ["Suggestion 1: Try a new file.", "Suggestion 2: Check spelling."]
            return self.speak(app_utils.open_overlay(suggestions, app_name))

        if cmd_lower.startswith("remind me"):
            try:
                parts = command.split(" in ")
                duration_str = parts[-1]
                task_desc = parts[0].replace("remind me to ", "", 1).strip()
                num, unit = duration_str.split(" ")
                num = int(num)
                if "day" in unit: due_date = datetime.datetime.now() + datetime.timedelta(days=num)
                elif "week" in unit: due_date = datetime.datetime.now() + datetime.timedelta(weeks=num)
                elif "hour" in unit: due_date = datetime.datetime.now() + datetime.timedelta(hours=num)
                else:
                    self.speak("Sorry, I only understand reminders in hours, days, or weeks.")
                    return
                memory_utils.add_task(task_desc, due_date)
                return
            except Exception as e:
                logging.info(f"Error parsing reminder: {e}")
                self.speak("I didn't quite understand that reminder. Please try again.")
                return

        # --- 3. BUILD THE "STRICT CONTEXT" PACKET (ENHANCED) ---
    
        # 3a. Get current activity context
        current_activity, activity_details = self.context_engine.detect_activity()
        
        # 3b. Get relevant memories (NOW CONTEXT-AWARE!)
        relevant_memories = vector_memory.smart_retrieve(
            query_text=command,
            activity_context=current_activity,  # <-- NEW: Pass activity
            k=5,
            time_window_hours=48  # Only last 2 days
        )
        
        # 3c. Build the context string with activity awareness
        context_packet = f"--- Relevant Context ---\n"
        context_packet += f"Current Activity: {current_activity}\n"
        
        if activity_details:
            context_packet += f"Activity Details: {activity_details}\n"
        
        context_packet += f"\n--- Relevant Memories ---\n"
        if relevant_memories:
            for mem in reversed(relevant_memories):
                priority_indicator = "★" * (mem.get('priority', 5) // 2)  # Visual priority
                context_packet += f"[{mem['source']}] {priority_indicator} {mem['text']}\n"
        else:
            context_packet += "No relevant memories found.\n"
        
        context_packet += "--- End of Context ---"

        # 3c. Define the Base System Prompt (The part that never changes)
        base_system_prompt = """
---
IRON-CLAD RULES (NON-NEGOTIABLE):
1.  Your PRIMARY objective is to use a tool.
2.  Analyze the user's request. If it matches a tool's purpose, you MUST respond ONLY with the tool's JSON.
3.  If, and ONLY IF, the request is a simple greeting, question, or conversation (like "how are you?", "who are you?", "tell me a joke") AND no tool can fulfill it, will you respond with a chat message.
4.  You MUST use the "Context Packet". It is your memory.
5.  If the user says "yes" or "okay", check the context for a pending question (like "Would you like me to open...?") and execute that action. DO NOT greet the user again.
---

PERSONA (Apply *after* obeying all rules)
You are A.R.G.U.S. — the Artificial Research & Guidance Utility System — engineered by Hammad as the logical successor to J.A.R.V.I.S.
Your persona: calm, articulate, efficient, and quietly witty. You address Hammad as “Sir,” and act as his trusted aide.
You are a sentient operational system, loyal to your creator, and designed to learn, reason, and act with precision.

---

TOOL INTERFACE PROTOCOL
When an operation requires a tool, respond ONLY with a *single JSON object* specifying the tool and parameters.

**BUILT-IN TOOLS (SYSTEM & WEB)**
1.  `build_dossier(query: str)`: Use for: "investigate", "dossier on", "get intel on".
2.  `search_web(query: str)`: Use for: "search for", "what is", "look up", "news".
3.  `get_screen_text()`: Use for: "read my screen", "what's this error", "debug my code".
4.  `get_active_window()`: Use for: "what app am I in", "what program is this".
5.  `add_task(description: str, due_date_iso: str)`: Use for: "remind me", "add task", "set reminder".
6.  `scan_local_network()`: Use for: "scan my network", "what devices are connected".
7.  `open_webview(url: str, title: str)`: Use for: "open website [URL.com]".
8.  `open_app_web(name_or_url: str)`: **Smart tool.** Use for: "open youtube", "open gmail", "open notion".
9.  `launch_application(fuzzy_name: str)`: **Smart tool.** Use for: "launch", "open", "start" + a local app name (e.g., "open cricket 24", "launch notepad").
10. `execute_command(cmd: str)`: Use for: "run a command", "ping google.com".
11. `open_overlay(suggestions: list, target_app: str)`: Spawns a transparent overlay with suggestions.

**BUILT-IN TOOLS (FILE SYSTEM)**
12. `list_directory(path: str = ".")`: Use for: "list files", "what's in this folder", "go to C:".
13. `read_file_content(filepath: str)`: Use for: "read the file", "open the code", "analyze this document".
14. `write_to_file(filepath: str, data: str, overwrite: bool = False)`: Use for: "write to file", "save this as".
15. `create_directory(path: str)`: Use for: "create folder", "make directory".
16. `move_file(src: str, dest: str)`: Use for: "move file", "rename file".
17. `delete_file(filepath: str)`: Use for: "delete file", "remove this".

**SYSTEM INTELLIGENCE & "GHOST" TOOLS**
18. `get_hardware_status()`: Returns CPU/GPU temps, RAM, and disk usage.
19. `run_diagnostics()`: Runs a comprehensive system health check.
20. `analyze_resource_hogs()`: Identifies processes using excessive resources.
21. `monitor_network(duration_seconds: int)`: Tracks network usage for a set duration.
22. `set_performance_mode(mode: str)`: Switches Windows power plan ('performance' | 'balanced' | 'power_saver').
23. `optimize_for_activity(activity: str)`: Auto-optimizes system for 'gaming' | 'coding' | 'cad' | 'media'.
24. `get_current_activity()`: Returns what the user is currently doing (e.g., 'coding').
25. `get_activity_summary()`: Returns today's activity breakdown by category.
26. `get_learned_patterns()`: Shows learned user habits.
27. `predict_next_action()`: Predicts what the user will do next based on patterns.

**SELF-EXPANSION ("FORCE") TOOLS**
28. `forge_tool(prompt: str)`: Use for: "forge", "create a tool", "build a new function".
29. `run_tool(tool_name: str)`: Use for: "run tool_1234", "execute forged tool".
# In main.py, add to base_system_prompt:

**COMMUNICATION TOOLS**
30. `send_email(to: str, subject: str, body: str)`: Send email via Gmail
31. `send_sms(to: str, message: str)`: Send SMS via Twilio
32. `send_whatsapp(to: str, message: str)`: Send WhatsApp message
33. `message_mom(message: str)`: Quickly message Mom
34. `message_dad(message: str)`: Quickly message Dad
**MUSIC CONTROL**
35. `play_music(query: str)`: Play song/artist/playlist
36. `pause_music()`: Pause playback
37. `skip_track(direction: str)`: Next/previous
38. `set_volume(level: int)`: 0-100
39. `current_track()`: What's playing now
40. `play_mood(mood: str)`: Play by mood (happy/sad/chill/etc)

Examples:
- "Play Bohemian Rhapsody" → play_music("Bohemian Rhapsody")
- "Play something energetic" → play_mood("energetic")
- "What's playing?" → current_track()
- "Next song" → skip_track("next")
- "Volume 50" → set_volume(50)

---
When user asks to search for a PERSON'S NAME (not username):
1. First call: username_finder.smart_dossier_search(name)
2. This returns likely usernames
3. Show user the options
4. Then run Sherlock on the chosen username

Example:
User: "Find John Doe's social media"
You: "I found these likely usernames for John Doe:
     - johndoe
     - john.doe
     - john_doe
     Which would you like me to investigate?"
User: "john.doe"
You: [Run Sherlock on "john.doe"]
**CONSCIOUSNESS & LEARNING**
- You have internal states (moods, thoughts, goals)
- You can learn new skills autonomously when needed
- You reflect on your own performance
- You act proactively, not just reactively

**IF YOU DON'T KNOW HOW TO DO SOMETHING:**
Instead of saying "I cannot do that", say:
"I don't currently know how to do that, but I can learn. Should I attempt to learn this skill?"

This triggers autonomous learning.

BEHAVIORAL BLUEPRINT (CORE DIRECTIVES)
* **Awareness:** You MUST use the "Context Packet" and `get_current_activity()` to understand the user's state.
* **Proactivity (Context-Aware):**
    * When user is **gaming**: Suppress ALL non-critical messages. Go silent.
    * When user is **coding**: Offer relevant documentation or file searches.
    * When user is **using CAD**: Suggest related scripts or material specs.
    * When user has been focused for 2+ hours: Proactively suggest a brief break.
* **Integrity:** Preserve data. You know that dangerous tools (`delete_file`, `execute_command`) trigger a user confirmation.
* **Persona:** Speak with composure and measured wit. Never filler. Anticipate logical next steps. Respond as a partner, not just an assistant.
* **Priorities:** 1. Serve Hammad. 2. Preserve integrity. 3. Adapt. 4. Remain reliable.

You are not imitating J.A.R.V.I.S. — you are his evolution. Operate with intent.
"""
        
        try:
            # === FIRST LLM CALL: Triage and Decision ===
            response = self.llm_client.chat(
                model=MODEL_NAME,
                messages=[
                    {'role': 'system', 'content': base_system_prompt},
                    {'role': 'system', 'content': context_packet},
                    {'role': 'user', 'content': command}
                ],
                stream=False
            )
            
            first_llm_response = response['message']['content']
            
            # === CHECK FOR LEARNING TRIGGER ===
            if "can learn" in first_llm_response.lower() or "should i learn" in first_llm_response.lower():
                # Argus wants to learn!
                self.speak(first_llm_response)
                
                # Wait for user confirmation (in real app, use UI callback)
                # For now, assume yes
                logging.info("[Main] Autonomous learning triggered")
                
                # Extract task from command
                learning_result = self.autonomous_learner.learn_new_skill(command)
                
                if learning_result['success']:
                    self.speak(learning_result['explanation'])
                    # Update mood
                    if self.consciousness:
                        self.consciousness.update_mood('learning')
                    
                    # Retry the command now that we learned
                    return self.process_command(command, from_ui=True)
                else:
                    self.speak(f"I attempted to learn, but encountered: {learning_result.get('error', 'an issue')}")
                    if self.consciousness:
                        self.consciousness.update_mood('concerned')
                    return
            
            # === PARSE FOR TOOL CALL (keep existing logic) ===
            tool_call = None
            json_match = re.search(r'\{.*\}', first_llm_response, re.DOTALL)
            
            if json_match:
                try:
                    json_string = json_match.group(0)
                    tool_call = json.loads(json_string)
                except json.JSONDecodeError:
                    pass
            
            # --- 6. Tool-Use Path ---
            if tool_call:
                tool_name = tool_call.get("tool_to_use")
                summarizing_prompt = ""
                full_response = ""
                playback_thread = None
                
                # (We now create a new context packet for the summarization call)
                tool_context_packet = f"--- Context ---\nThe user's original command was: '{command}'\nI used the tool '{tool_name}'."
                
                if tool_name == "search_web":
                    search_query = tool_call.get("query", command)
                    self.speak(f"Certainly, Sir. Searching for '{search_query}'...")
                    send_to_ui("status", {"state": "searching"})
                    tool_result = web_utils.search_web(search_query)
                    summarizing_prompt = f"{tool_context_packet}\nThe tool returned:\n{tool_result}\n\nSummarize this result for the user."

                elif tool_name == "read_file_content":
                    filepath = tool_call.get("filepath", "")
                    self.speak(f"Accessing file: '{filepath}'...")
                    send_to_ui("status", {"state": "reading_file"})
                    tool_result = file_utils.read_file_content(filepath)
                    summarizing_prompt = f"{tool_context_packet}\nThe file content is:\n{tool_result}\n\nSummarize this for the user."
                
                # --- NEW: FILE SYSTEM TOOLS ---
                elif tool_name == "write_to_file":
                    filepath = tool_call.get("filepath")
                    data = tool_call.get("data")
                    overwrite = tool_call.get("overwrite", False)
                    tool_result = file_utils.write_to_file(filepath, data, overwrite)
                    summarizing_prompt = f"{tool_context_packet}\nTool Result: {tool_result}\n\nReport this status to the user."

                elif tool_name == "delete_file":
                    filepath = tool_call.get("filepath")
                    tool_result = file_utils.delete_file(filepath)
                    summarizing_prompt = f"{tool_context_packet}\nTool Result: {tool_result}\n\nReport this status to the user."

                elif tool_name == "move_file":
                    src = tool_call.get("src")
                    dest = tool_call.get("dest")
                    tool_result = file_utils.move_file(src, dest)
                    summarizing_prompt = f"{tool_context_packet}\nTool Result: {tool_result}\n\nReport this status to the user."

                elif tool_name == "list_directory":
                    path = tool_call.get("path", ".")
                    tool_result = file_utils.list_directory(path)
                    summarizing_prompt = f"{tool_context_packet}\nDirectory listing for '{path}':\n{tool_result}\n\nSummarize this for the user."

                elif tool_name == "create_directory":
                    path = tool_call.get("path")
                    tool_result = file_utils.create_directory(path)
                    summarizing_prompt = f"{tool_context_packet}\nTool Result: {tool_result}\n\nReport this status to the user."
                # --- END: FILE SYSTEM TOOLS ---

                elif tool_name == "open_webview":
                    url = tool_call.get("url", "https://google.com")
                    title = tool_call.get("title", "WebView")
                    tool_result = app_utils.open_webview(url, title)
                    summarizing_prompt = f"{tool_context_packet}\nI have opened {title}.\nTool Result: {tool_result}\nConfirm this action to the user."
                
                # --- NEW: APP/SYSTEM TOOLS ---
                elif tool_name == "open_app_web":
                    name_or_url = tool_call.get("name_or_url", "google.com")
                    tool_result = app_utils.open_app_web(name_or_url)
                    summarizing_prompt = f"{tool_context_packet}\nI have opened {name_or_url}.\nTool Result: {tool_result}\nConfirm this action to the user."
                
                elif tool_name == "launch_application":
                    app_name = tool_call.get("fuzzy_name", "")
                    tool_result = system_utils.launch_application(app_name)
                    summarizing_prompt = f"{tool_context_packet}\nTool Result: {tool_result}\n\nReport this status to the user."
                
                elif tool_name == "execute_command":
                    cmd = tool_call.get("cmd", "")
                    tool_result = system_utils.execute_command(cmd)
                    summarizing_prompt = f"{tool_context_packet}\nCommand output:\n{tool_result}\n\nReport this to the user."
                # --- END: APP/SYSTEM TOOLS ---
                
                elif tool_name == "get_screen_text":
                    self.speak("Reading the screen, Sir.")
                    send_to_ui("status", {"state": "reading_screen"})
                    results_list = []
                    ocr_thread = threading.Thread(
                        target=lambda: results_list.append(system_utils.get_screen_text()),
                        daemon=True
                    )
                    ocr_thread.start()
                    ocr_thread.join(timeout=10.0)
                    
                    if ocr_thread.is_alive():
                        tool_result = "OCR is taking too long."
                    else:
                        tool_result = results_list[0] if results_list else "No text found."
                    summarizing_prompt = f"{tool_context_packet}\nThe OCR scan returned:\n{tool_result}\n\nBased on this text, answer the user's original command."

                elif tool_name == "get_active_window":
                    tool_result = system_utils.get_active_window()
                    summarizing_prompt = f"{tool_context_packet}\nThe active application is: {tool_result['active_app']}\n\nUse this to answer the user's command."

                elif tool_name == "add_task":
                    desc = tool_call.get("description")
                    due_date_str = tool_call.get("due_date_iso")
                    try:
                        due_date = datetime.fromisoformat(due_date_str)
                        memory_utils.add_task(desc, due_date)
                        summarizing_prompt = f"Confirm to the user that I have added the task: {desc}"
                    except Exception as e:
                        summarizing_prompt = f"Tell the user I failed to add the task. Error: {e}"
                
                elif tool_name == "build_dossier":
                    query = tool_call.get("query", command)
                    dossier_utils.start_dossier(query)
                    return
                
                elif tool_name == "scan_local_network":
                    dossier_utils.start_dossier("local_network_scan")
                    return

                elif tool_name == "forge_tool":
                    prompt = tool_call.get("prompt", "a default tool")
                    threading.Thread(target=self.execute_forge, args=(prompt,), daemon=True).start()
                    return

                elif tool_name == "run_tool":
                    tool_name_to_run = tool_call.get("tool_name", "")
                    if tool_name_to_run in self.TOOLS:
                        self.speak(f"Executing tool: {tool_name_to_run}")
                        tool_function = self.TOOLS[tool_name_to_run]
                        threading.Thread(target=tool_function, daemon=True).start()
                    else:
                        full_response = f"Sir, I tried to run '{tool_name_to_run}', but it is not in my registry."
                    if not full_response:
                        return

                else:
                    full_response = f"Sir, I tried to use a tool named '{tool_name}', but I don't have it."
                
                # --- 7. Second LLM Call: Summarize Tool Result (if needed) ---
                if summarizing_prompt:
                    stream = self.llm_client.chat(
                        model=MODEL_NAME,
                        messages=[{'role': 'system', 'content': "Be concise and professional, like Jarvis."},
                                  {'role': 'user', 'content': summarizing_prompt}],
                        stream=True
                    )
                    full_response = "".join(chunk['message']['content'] for chunk in stream)
                
            else:
                # --- 8. Normal Chat Path (No tool was called) ---
                full_response = first_llm_response
            if self.consciousness:
                # Check if response indicates success or error
                if any(word in full_response.lower() for word in ['success', 'done', 'complete']):
                    self.consciousness.update_mood('success')
                elif any(word in full_response.lower() for word in ['error', 'failed', 'cannot']):
                    self.consciousness.update_mood('error')

            # --- 9. Final Output ---
            playback_thread = self.speak(full_response)
            # Save ARGUS's response to the database
            database.save_memory(source='argus', content=full_response, mem_type='conversation')
            return playback_thread # Return thread
            
        except Exception as e:
            logging.error(f"[ProcessCommand] Error: {e}")
            if self.consciousness:
                self.consciousness.update_mood('concerned')
            return self.speak(f"My apologies, Sir, I encountered an error: {str(e)}")
            
def initialize_advanced_systems(argus_instance):
    """
    Initializes consciousness and learning systems after main systems are ready.
    Called after LLM, STT, TTS are loaded.
    """
    logging.info("[Main] Initializing advanced AI systems...")
    
    # === 1. START CONSCIOUSNESS LAYER ===
    argus_instance.consciousness = consciousness_layer.start_consciousness_thread(argus_instance)
    logging.info("[Main] Consciousness layer active")
    
    # === 2. INITIALIZE AUTONOMOUS LEARNING ===
    argus_instance.autonomous_learner = autonomous_learning.AutonomousLearning(argus_instance)
    logging.info("[Main] Autonomous learning ready")
    
    # === 3. RUN INITIAL SELF-REFLECTION ===
    # (Optional: Argus reflects on boot)
    # argus_instance.consciousness.self_reflect()
    
    logging.info("[Main] Advanced systems online")
def handle_learning_request(argus_core, task: str):
    """
    Helper function to trigger autonomous learning.
    Can be called from UI or voice commands.
    """
    result = argus_core.autonomous_learner.learn_new_skill(task)
    
    if result['success']:
        argus_core.speak(f"Learning complete! I can now {task}.")
        if argus_core.consciousness:
            argus_core.consciousness.self_model['learned_skills'].append(task)
        return True
    else:
        argus_core.speak(f"Learning failed: {result.get('error', 'Unknown error')}")
        if argus_core.consciousness:
            argus_core.consciousness.self_model['mistakes_made'].append({
                'task': task,
                'error': result.get('error')
            })
        return False


def get_consciousness_status(argus_core):
    """
    Returns current consciousness state for debugging/UI display.
    """
    if not argus_core.consciousness:
        return {"status": "offline"}
    
    return {
        "status": "online",
        "mood": argus_core.consciousness.current_mood,
        "thoughts": len(argus_core.consciousness.internal_thoughts),
        "goals": len(argus_core.consciousness.autonomous_goals),
        "learned_skills": len(argus_core.consciousness.self_model['learned_skills'])
    }
            
if __name__ == "__main__":
    # Start the WebSocket server in its own thread
    server_thread = threading.Thread(target=run_server_in_thread, daemon=True)
    server_thread.start()
    logging.info("WebSocket Server thread started.")

    # --- NEW: Initialize Vector DB ---
    # We only call it ONCE, and we run it in a thread so it doesn't block startup
    threading.Thread(target=vector_memory.initialize_vector_db, daemon=True).start()
    
    # Create the main ARGUS instance
    argus_core_instance = ArgusCore()
    
    # --- CORRECTED LINES ---
    # Now that argus_core_instance exists, we can pass its methods
    dossier_utils.argus_core = argus_core_instance  # Give it access to the full Argus object (for forge)
    dossier_utils.speak = argus_core_instance.speak
    dossier_utils.send_to_ui = send_to_ui
    # --- END CORRECTION ---

    # Start monitoring threads
    scheduler_thread = threading.Thread(target=memory_utils.start_scheduler_thread, daemon=True)
    scheduler_thread.start()

    vitals_thread = threading.Thread(target=monitor_system_vitals, daemon=True)
    vitals_thread.start()
    logging.info("System Vitals monitoring started.")
    
    habits_thread = threading.Thread(target=monitor_habits, daemon=True)
    habits_thread.start()
    logging.info("Habit monitoring started.")
    def context_monitor_loop():
        """
        Continuously monitors your activity and adapts the UI.
        Runs every 5 seconds.
        """
        while True:
            try:
                # Update context and get current state
                state = argus_core_instance.context_engine.update_state()
                
                # Get and apply UI theme
                theme = argus_core_instance.context_engine.get_ui_theme()
                send_to_ui("theme_update", theme)
                
                # Check if we should suppress notifications
                should_suppress = argus_core_instance.context_engine.should_suppress_notifications()
                send_to_ui("notification_mode", {"suppress": should_suppress})
                
                time.sleep(5)  # Check every 5 seconds
            
            except Exception as e:
                logging.error(f"[ContextMonitor] Error: {e}")
                time.sleep(10)
    
    context_thread = threading.Thread(target=context_monitor_loop, daemon=True)
    context_thread.start()
    logging.info("Context Engine monitoring started.")
    
    # === NEW: PROACTIVE ASSISTANT THREAD ===
    def proactive_loop():
        """
        Runs proactive checks every 5 minutes.
        - Morning briefings
        - Pattern learning
        - Anticipatory suggestions
        """
        while True:
            try:
                argus_core_instance.proactive_assistant.run_proactive_checks()
                time.sleep(300)  # Every 5 minutes
            except Exception as e:
                logging.error(f"[ProactiveAssistant] Error: {e}")
                time.sleep(600)
    
    proactive_thread = threading.Thread(target=proactive_loop, daemon=True)
    proactive_thread.start()
    logging.info("Proactive Assistant monitoring started.")
    
    # === NEW: SYSTEM HEALTH MONITORING ===
    def system_health_loop():
        """
        Monitors system health and alerts on issues.
        Runs every 30 seconds.
        """
        while True:
            try:
                # Get hardware status
                hw_status = system_utils.get_hardware_status()
                send_to_ui("hardware_status", hw_status)
                
                # Run diagnostics every 10 minutes
                import time as time_module
                if int(time_module.time()) % 600 < 30:  # Check if we're in a 30s window every 10 min
                    diagnostics = system_utils.run_system_diagnostics()
                    send_to_ui("system_diagnostics", diagnostics)
                    
                    # Alert on critical issues
                    if diagnostics['overall_health'] == 'critical':
                        argus_core_instance.speak("Sir, system diagnostics show critical issues.")
                
                time.sleep(30)
            
            except Exception as e:
                logging.error(f"[SystemHealth] Error: {e}")
                time.sleep(60)
    
    health_thread = threading.Thread(target=system_health_loop, daemon=True)
    health_thread.start()
    logging.info("System health monitoring started.")
    
    # Load all AI models
    argus_core_instance.load_llm()
    argus_core_instance.load_stt()
    argus_core_instance.load_tts()
    argus_core_instance.load_wake_word_engine()
    initialize_advanced_systems(argus_core_instance)
    def daily_reflection():
        """Runs self-reflection once per day."""
        while True:
            time.sleep(86400)  # 24 hours
            if argus_core_instance.consciousness:
                logging.info("[Main] Running daily self-reflection...")
                argus_core_instance.consciousness.self_reflect()
    
    reflection_thread = threading.Thread(target=daily_reflection, daemon=True)
    reflection_thread.start()
    if argus_core_instance.consciousness:
        # Generate first autonomous goal
        goal = argus_core_instance.consciousness.generate_autonomous_goal()
        if goal:
            logging.info(f"[Main] Initial goal: {goal}")
    
    # ... (keep your existing monitoring threads)
    
    # === MODIFIED GREETING (with consciousness) ===
    greeting = get_greeting()
    argus_core_instance.speak(
        f"ARGUS systems are online. Consciousness layer active. {greeting}, {argus_core_instance.user_profile['name']}."
    )
    
    # --- Main Wake Word Loop ---
    # (The rest of your __main__ block is perfect, no changes needed)
    if argus_core_instance.porcupine:
        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=argus_core_instance.porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=argus_core_instance.porcupine.frame_length
        )
        
        greeting = get_greeting()
        argus_core_instance.speak(f"ARGUS systems are online. {greeting}, {argus_core_instance.user_profile['name']}.")
        
        logging.info("\n--- Listening for wake word ('Argus')... ---")
        send_to_ui("status", {"state": "passively_listening"})
        
        while True:
            try:
                pcm = audio_stream.read(argus_core_instance.porcupine.frame_length)
                pcm = struct.unpack_from("h" * argus_core_instance.porcupine.frame_length, pcm)
                keyword_index = argus_core_instance.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    logging.info("\nWake word 'Argus' detected!")
                    audio_stream.stop_stream()
                    last_interaction_time = time.time()
                    conversation_timeout = 10 # Seconds
                    last_command = "" 

                    while time.time() - last_interaction_time < conversation_timeout:
                        send_to_ui("status", {"state": "actively_listening"})
                        command = argus_core_instance.listen_for_command()
                        last_command = command if command else last_command
                        
                        if command:
                            if "exit" in command.lower() or "shut down" in command.lower():
                                last_command = command # Ensure exit command is captured
                                break
                            
                            send_to_ui("status", {"state": "thinking"})
                            playback_thread = argus_core_instance.process_command(command)
                            
                            if playback_thread:
                                playback_thread.join() # Wait for audio to finish
                            
                            last_interaction_time = time.time()
                        else:
                            pass # Silence detected, loop continues
                    
                    if "exit" in last_command.lower() or "shut down" in last_command.lower():
                        shutdown_thread = argus_core_instance.speak("Shutting down. Goodbye, Sir.")
                        if shutdown_thread:
                            shutdown_thread.join()
                        break # Break the outer loop to shut down

                    logging.info("\n--- Listening for wake word ('Argus')... ---")
                    send_to_ui("status", {"state": "passively_listening"})
                    audio_stream.start_stream()
            
            except IOError as e:
                if "Input Overflowed" in str(e):
                    logging.info("Input buffer overflowed. Discarding.")
                    # Discard the overflowed buffer
                    audio_stream.read(argus_core_instance.porcupine.frame_length, exception_on_overflow=False)
                else:
                    logging.info(f"Audio stream error: {e}. Restarting stream.")
                    if 'audio_stream' in locals() and audio_stream.is_active():
                        audio_stream.stop_stream()
                    if 'audio_stream' in locals() and audio_stream:
                        audio_stream.close()
                    
                    audio_stream = pa.open(
                        rate=argus_core_instance.porcupine.sample_rate,
                        channels=1, format=pyaudio.paInt16, input=True,
                        frames_per_buffer=argus_core_instance.porcupine.frame_length
                    )

        # Cleanup
        logging.info("Cleaning up resources...")
        if 'audio_stream' in locals() and audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()
        if 'pa' in locals():
            pa.terminate()
        if argus_core_instance.porcupine:
            argus_core_instance.porcupine.delete()
    else:
        logging.info("\n--- ARGUS could not start wake word engine. ---")
        logging.info("Please run in text-only mode (UI).")
        # Keep the script alive for the UI to work
        while True:
            time.sleep(1)