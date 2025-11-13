# In: core_utils/dossier_utils.py

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from core_utils import osint_utils
import re

# This will be set by main.py
argus_core = None 
speak = None
send_to_ui = None

# --- Dossier Manager Class ---
class DossierManager:
    def __init__(self, query, argus_instance, speak_func, ui_func):
        self.query = query
        self.argus_core = argus_instance
        self.speak = speak_func
        self.send_to_ui = ui_func
        self.report = {"query": query, "intel": {}}
        
        # Simple regex to detect query type
        self.is_email = re.match(r"[^@]+@[^@]+\.[^@]+", query)
        self.is_username = re.match(r"^[a-zA-Z0-9_]{3,20}$", query)
        self.is_domain = re.match(r"^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$", query)

    def run_parallel_tools(self):
        """
        Uses a ThreadPool to run all relevant OSINT tools at once.
        This is how we get speed.
        """
        self.speak(f"Compiling dossier for: {self.query}. This may take a moment.")
        self.send_to_ui("status", {"state": "compiling_dossier"})
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            
            # --- FIX: We now add robust error handling ---
            try:
                # Always run Google Dorks
                futures[executor.submit(osint_utils.search_google_dorks, self.query)] = "google_dorks"
                
                # Run tools based on query type
                if self.is_email:
                    futures[executor.submit(osint_utils.check_breaches, self.query)] = "breach_check"
                
                if self.is_username:
                    futures[executor.submit(osint_utils.search_socials, self.query)] = "social_search"
                    
                if self.is_domain:
                    futures[executor.submit(osint_utils.find_domain_intel, self.query)] = "domain_intel"
                
                # "Force-as-a-Tool" Tweak
                if self.is_username and "new-social-site.com" in self.query:
                    self.speak("Unknown target. Attempting to forge a new tool...")
                    forge_prompt = f"a tool to scrape user '{self.query}' from new-social-site.com"
                    futures[executor.submit(self.argus_core.execute_forge, forge_prompt)] = "forge_new_tool"
            
            except Exception as e:
                print(f"--- [Dossier] Error submitting a tool: {e} ---")
                self.report["intel"]["manager_error"] = str(e)


            # Collect all results
            for future in futures:
                tool_name = futures[future]
                try:
                    result = future.result()
                    # We store the result under the tool's name
                    self.report["intel"][tool_name] = result
                except Exception as e:
                    # If one tool fails, we just log its error and continue
                    print(f"--- [Dossier] Tool '{tool_name}' failed: {e} ---")
                    self.report["intel"][tool_name] = {"error": f"Tool failed to run: {e}"}

        self.finish_dossier()

    def finish_dossier(self):
        """
        Synthesizes the final report and speaks it.
        """
        self.speak("Dossier compilation complete.")
        self.send_to_ui("status", {"state": "passively_listening"})
        
        # In the future, we'll send this raw JSON to the LLM for a
        # natural language summary. For now, we just print the data.
        print(json.dumps(self.report, indent=2))
        self.speak(f"I have gathered {len(self.report['intel'])} intelligence packets on {self.query}. Please check the console.")
        
        # Send the full report to the UI for a new panel
        self.send_to_ui("dossier_complete", self.report)


def start_dossier(query: str):
    """
    Public entry point to start a new dossier investigation.
    """
    if not all([argus_core, speak, send_to_ui]):
        print("--- [Dossier] Error: DossierManager not initialized from main.py ---")
        return
        
    # Create an instance of the manager and run it in a new thread
    # so it doesn't block the main application
    manager = DossierManager(query, argus_core, speak, send_to_ui)
    threading.Thread(target=manager.run_parallel_tools, daemon=True).start()