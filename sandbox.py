# core_utils/sandbox.py
# This is our new, safe "cage" for testing Forged code.

import subprocess
import sys
import os
import tempfile

# Get the path to the current Python executable
PYTHON_EXECUTABLE = sys.executable

def test_code_in_sandbox(code: str):
    """
    Runs Python code in a separate, isolated subprocess.
    This prevents any errors or malicious code from crashing
    the main ARGUS application.
    
    Returns:
        (bool, str): A tuple of (success, output)
                     If success=True, output is the stdout.
                     If success=False, output is the stderr.
    """
    print(f"--- [Sandbox] Testing new code... ---")
    
    # Create a temporary file to write the code to
    # We use 'with' to ensure it's automatically deleted
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name
        
        # --- Run the file in a new, separate process ---
        # We capture both stdout and stderr
        result = subprocess.run(
            [PYTHON_EXECUTABLE, temp_file_path],
            capture_output=True,
            text=True,
            timeout=10 # Kill the tool if it runs for more than 10s
        )
        
        # --- Check the results ---
        if result.stderr:
            # The tool failed!
            print(f"--- [Sandbox] TEST FAILED ---")
            print(result.stderr)
            return (False, result.stderr)
        else:
            # The tool succeeded!
            print(f"--- [Sandbox] TEST PASSED ---")
            print(result.stdout)
            return (True, result.stdout)

    except subprocess.TimeoutExpired:
        print("--- [Sandbox] TEST FAILED: Code ran for too long (Timeout). ---")
        return (False, "Error: Code execution timed out after 10 seconds.")
    except Exception as e:
        print(f"--- [Sandbox] Error during sandbox setup: {e}")
        return (False, f"Sandbox Error: {e}")
    finally:
        # Clean up the temp file
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)