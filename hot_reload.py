# core_utils/hot_reload.py

import importlib.util
import sys
from types import ModuleType
import os

TOOLS_DIR = "force_modules"
os.makedirs(TOOLS_DIR, exist_ok=True)

def load_tool_from_code(tool_name: str, code: str) -> ModuleType:
    """
    Saves code to a file, deletes any old cache, 
    and dynamically loads it as a new module.
    """
    
    # Define the file path for the new tool
    module_path = os.path.join(TOOLS_DIR, f"{tool_name}.py")
    
    # Write the new code to the file
    try:
        with open(module_path, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as e:
        print(f"--- [HotReload] Error writing code to file: {e} ---")
        raise
    
    # --- This is the dynamic loading magic ---
    
    # If the module is already loaded, remove it from Python's cache
    if tool_name in sys.modules:
        del sys.modules[tool_name]
        
    try:
        # Create a "spec" for the new module from its file path
        spec = importlib.util.spec_from_file_location(tool_name, module_path)
        if spec is None:
            raise ImportError(f"Could not create spec for module at {module_path}")
            
        # Create a new, empty module object
        module = importlib.util.module_from_spec(spec)
        
        # "Execute" the code inside the new module object
        spec.loader.exec_module(module)
        
        # Add the newly loaded module to the system's list
        sys.modules[tool_name] = module
        
        print(f"--- [HotReload] Successfully loaded/reloaded tool: {tool_name} ---")
        return module
    
    except Exception as e:
        print(f"--- [HotReload] Error loading module: {e} ---")
        raise