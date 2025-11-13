# core_utils/tools_registry.py
from datetime import time
import json
import os
import sys
import threading
from typing import Optional
from core_utils import hot_reload

REGISTRY_FILE = os.path.join("force_modules", "registry.json")
MODULES_DIR = "force_modules"
os.makedirs(MODULES_DIR, exist_ok=True)

_registry_lock = threading.Lock()
_registry = {}  # tool_name -> {"name":..., "code_path":..., "metadata":{...}}

def _load_registry():
    global _registry
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                _registry = json.load(f)
        except Exception:
            _registry = {}

def _save_registry():
    with _registry_lock:
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(_registry, f, indent=2)

def add_tool(tool_name: str, code: str, metadata: Optional[dict] = None) -> bool:
    """
    Persist a tool and load it into the running process (via hot_reload).
    Returns True on success.
    """
    metadata = metadata or {}
    module_path = os.path.join(MODULES_DIR, f"{tool_name}.py")
    try:
        with open(module_path, "w", encoding="utf-8") as mf:
            mf.write(code)
        # Load dynamically
        module = hot_reload.load_tool_from_code(tool_name, code)
        if not hasattr(module, "run"):
            # Clean up: remove file
            os.remove(module_path)
            return False
        # Save to registry
        with _registry_lock:
            _registry[tool_name] = {
                "name": tool_name,
                "code_path": module_path,
                "metadata": metadata
            }
            _save_registry()
        return True
    except Exception as e:
        print(f"[ToolsRegistry] Error adding tool {tool_name}: {e}")
        return False

def remove_tool(tool_name: str) -> bool:
    with _registry_lock:
        info = _registry.get(tool_name)
        if not info:
            return False
        try:
            path = info.get("code_path")
            if path and os.path.exists(path):
                os.remove(path)
            del _registry[tool_name]
            _save_registry()
            if tool_name in sys.modules:
                del sys.modules[tool_name]
            return True
        except Exception:
            return False

def list_tools():
    return list(_registry.keys())

def get_tool_info(tool_name: str):
    return _registry.get(tool_name)

# Run on import
_load_registry()

# Re-load all registered tools into memory (call at startup)
def reload_all_tools():
    for name, info in list(_registry.items()):
        path = info.get("code_path")
        try:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            hot_reload.load_tool_from_code(name, code)
        except Exception as e:
            print(f"[ToolsRegistry] Failed to reload {name}: {e}")

# ADD THESE METHODS TO YOUR EXISTING CLASS

def get_tool_performance_stats(tool_name: str):
    """Track how often and how fast tools run."""
    stats_file = f"{MODULES_DIR}/{tool_name}_stats.json"
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            return json.load(f)
    return {"run_count": 0, "avg_time": 0, "last_run": None}

def log_tool_execution(tool_name: str, execution_time: float, success: bool):
    """Log every tool run for analytics."""
    stats = get_tool_performance_stats(tool_name)
    stats['run_count'] += 1
    stats['last_run'] = time.time()
    
    # Update average time
    if stats['run_count'] == 1:
        stats['avg_time'] = execution_time
    else:
        stats['avg_time'] = (stats['avg_time'] * (stats['run_count'] - 1) + execution_time) / stats['run_count']
    
    stats['last_success'] = success
    
    stats_file = f"{MODULES_DIR}/{tool_name}_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)

def suggest_tool_optimization(tool_name: str):
    """
    If a tool is slow, Jarvis can offer to rewrite it.
    Returns: (should_optimize: bool, reason: str)
    """
    stats = get_tool_performance_stats(tool_name)
    
    if stats['avg_time'] > 5.0:  # Over 5 seconds
        return True, f"This tool averages {stats['avg_time']:.1f}s. I can attempt to optimize it."
    
    if stats.get('last_success') == False:
        return True, "This tool failed last time. I can debug and fix it."
    
    return False, ""
