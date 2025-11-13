# core_utils/autonomous_learning.py
"""
AUTONOMOUS LEARNING SYSTEM
This makes Argus learn new skills WITHOUT human coding.

How it works:
1. User: "Argus, I need you to control my smart lights"
2. Argus: "I don't know how. Let me learn..."
3. Argus: Searches for Philips Hue API documentation
4. Argus: Reads documentation
5. Argus: Writes Python code to control lights
6. Argus: Tests code in sandbox
7. Argus: If successful, adds to own tools
8. Argus: "I learned how! Try: Turn on the lights"

This is EXACTLY how Jarvis works in the movies.
"""

from datetime import time
import logging
from core_utils import web_utils, sandbox, tools_registry, hot_reload
import re
import sys

class AutonomousLearning:
    """
    The self-learning engine that makes Argus truly autonomous.
    """
    
    def __init__(self, argus_core):
        self.argus = argus_core
        self.llm = argus_core.llm_client
        self.learning_attempts = {}  # Track what it's tried to learn
    
    def learn_new_skill(self, task_description: str):
        """
        Main entry point for autonomous learning.
        
        Args:
            task_description: "control Spotify", "send tweets", "control lights", etc.
        
        Returns:
            dict: {success: bool, tool_name: str, explanation: str}
        """
        logging.info(f"[Learning] Attempting to learn: {task_description}")
        
        # Step 1: Search for API documentation
        api_docs = self._find_api_documentation(task_description)
        
        if not api_docs:
            return {
                "success": False,
                "error": "Could not find API documentation for this task"
            }
        
        # Step 2: Generate code from documentation
        code, tool_name = self._generate_code_from_docs(task_description, api_docs)
        
        if not code:
            return {
                "success": False,
                "error": "Failed to generate code"
            }
        
        # Step 3: Test in sandbox
        test_passed, output = sandbox.test_code_in_sandbox(code)
        
        if not test_passed:
            # Try to fix the error
            logging.info(f"[Learning] First attempt failed: {output}")
            code, fixed = self._fix_code_error(code, output, api_docs)
            
            if fixed:
                test_passed, output = sandbox.test_code_in_sandbox(code)
        
        if not test_passed:
            return {
                "success": False,
                "error": f"Code failed tests: {output}",
                "attempted_code": code
            }
        
        # Step 4: Deploy the new tool
        success = tools_registry.add_tool(tool_name, code, metadata={
            "learned_from": task_description,
            "timestamp": time.time(),
            "autonomous": True
        })
        
        if success:
            # Step 5: Register with Argus
            module = sys.modules.get(tool_name)
            if module and hasattr(module, 'run'):
                self.argus.TOOLS[tool_name] = module.run
                
                # Step 6: Update LLM knowledge
                self._update_llm_knowledge(tool_name, task_description)
                
                return {
                    "success": True,
                    "tool_name": tool_name,
                    "explanation": f"I learned how to {task_description}! New tool: {tool_name}"
                }
        
        return {
            "success": False,
            "error": "Failed to register new tool"
        }
    
    def _find_api_documentation(self, task: str):
        """
        Searches the web for API documentation.
        
        Example: "control Spotify" → Finds Spotify API docs
        """
        # Build search query
        search_queries = [
            f"{task} API documentation python",
            f"how to {task} with python",
            f"{task} python library",
            f"{task} API tutorial"
        ]
        
        all_results = []
        for query in search_queries[:2]:  # Only first 2 to avoid rate limits
            results = web_utils.search_web(query, max_results=3)
            all_results.append(results)
        
        # Parse and extract relevant documentation
        combined_docs = "\n\n".join(all_results)
        
        # Look for code examples
        code_examples = re.findall(r'```python\n(.*?)```', combined_docs, re.DOTALL)
        
        return {
            "raw_docs": combined_docs,
            "code_examples": code_examples
        }
    
    def _generate_code_from_docs(self, task: str, api_docs: dict):
        """
        Uses LLM to generate working code from documentation.
        
        This is the KEY to autonomous learning.
        """
        prompt = f"""
You are an autonomous AI learning system. You need to learn how to: {task}

Here is API documentation and examples I found:
{api_docs['raw_docs'][:4000]}  # Truncate to fit context

Your task:
1. Analyze the documentation
2. Write a COMPLETE, WORKING Python function called 'run()'
3. The function should accomplish: {task}
4. Include all necessary imports
5. Handle errors gracefully
6. Return a dict with results

Requirements:
- Must have a 'run()' function (no parameters)
- Must be self-contained (all imports inside)
- Must return dict: {{"success": bool, "result": any}}
- Use only standard libraries or common libraries (requests, etc.)

Example structure:
```python
def run():
    import requests
    try:
        # Your code here
        return {{"success": True, "result": "..."}}
    except Exception as e:
        return {{"success": False, "error": str(e)}}
```

Generate ONLY the Python code, no explanations.
"""
        
        try:
            response = self.llm.chat(
                model='gdisney/mistral-uncensored',
                messages=[{'role': 'user', 'content': prompt}],
                stream=False
            )
            
            code = response['message']['content']
            
            # Clean up code
            code = code.strip()
            if code.startswith('```python'):
                code = code[9:]
            if code.endswith('```'):
                code = code[:-3]
            code = code.strip()
            
            # Generate tool name
            tool_name = f"learned_{task.replace(' ', '_').lower()}"
            
            return code, tool_name
        
        except Exception as e:
            logging.error(f"[Learning] Code generation failed: {e}")
            return None, None
    
    def _fix_code_error(self, code: str, error: str, api_docs: dict):
        """
        Attempts to fix code that failed testing.
        This is CRITICAL for autonomous learning.
        """
        prompt = f"""
You are debugging code that failed.

Original code:
```python
{code}
```

Error encountered:
{error}

API documentation:
{api_docs['raw_docs'][:2000]}

Fix the code to handle this error. Return ONLY the corrected code.
"""
        
        try:
            response = self.llm.chat(
                model='gdisney/mistral-uncensored',
                messages=[{'role': 'user', 'content': prompt}],
                stream=False
            )
            
            fixed_code = response['message']['content'].strip()
            if fixed_code.startswith('```python'):
                fixed_code = fixed_code[9:].strip('```').strip()
            
            return fixed_code, True
        
        except Exception as e:
            logging.error(f"[Learning] Code fix failed: {e}")
            return code, False
    
    def _update_llm_knowledge(self, tool_name: str, task: str):
        """
        Updates the LLM's system prompt to know about the new tool.
        
        This is how Jarvis "remembers" what he learned.
        """
        # In a real system, you'd update the base_system_prompt
        # For now, we just log it
        logging.info(f"[Learning] New skill acquired: {tool_name} for '{task}'")
        
        # Save to a "learned skills" file
        with open('learned_skills.txt', 'a') as f:
            f.write(f"{tool_name}: {task}\n")


# === INTEGRATION WITH MAIN ARGUS ===

def handle_unknown_request(argus_core, request: str):
    """
    Called when Argus doesn't know how to do something.
    
    This is the trigger for autonomous learning.
    """
    # Check if this is a task Argus can't do
    if should_attempt_learning(request):
        learner = AutonomousLearning(argus_core)
        
        # Ask user for permission
        argus_core.speak(f"I don't know how to {request}, but I can learn. Should I try?")
        
        # In a real system, wait for user response
        # For now, assume yes
        
        result = learner.learn_new_skill(request)
        
        if result['success']:
            argus_core.speak(result['explanation'])
            return True
        else:
            argus_core.speak(f"I tried to learn, but encountered an issue: {result.get('error', 'Unknown error')}")
            return False
    
    return False

def should_attempt_learning(request: str):
    """
    Determines if a request is something Argus should try to learn.
    
    Returns True for:
    - API integrations ("control Spotify", "send tweets")
    - Web automation ("scrape data from X")
    - System integrations ("control smart lights")
    
    Returns False for:
    - Simple questions ("what is 2+2")
    - General knowledge ("who is the president")
    """
    learning_keywords = [
        'control', 'connect', 'integrate', 'send', 'post', 
        'tweet', 'message', 'automate', 'scrape', 'api'
    ]
    
    return any(keyword in request.lower() for keyword in learning_keywords)


