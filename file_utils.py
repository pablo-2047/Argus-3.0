# file_utils.py

import os
import shutil
import logging

def confirm_action(action: str, path: str) -> bool:
    """
    Ask for user confirmation before performing critical actions.
    """
    confirmation = input(f"[ARGUS CONFIRM] Do you want to {action.upper()} this path?\n→ {path}\nType 'yes' to proceed: ")
    if confirmation.strip().lower() == "yes":
        print(f"[ARGUS] Action confirmed: {action} on {path}")
        return True
    else:
        print(f"[ARGUS] Action canceled.")
        return False


def read_file_content(filepath: str) -> str:
    """
    Reads a file from anywhere on the system (text or binary).
    Returns content or error message.
    """
    target_path = os.path.abspath(filepath)
    print(f"--- [FileUtils] Reading file: {target_path}")

    if not os.path.exists(target_path):
        return f"Error: File not found — {target_path}"

    try:
        # Detect binary files by trying utf-8
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Binary fallback
        size = os.path.getsize(target_path)
        return f"[Binary File] {target_path} ({round(size/1024,2)} KB) — cannot display binary data."

    if not content.strip():
        return "[Notice] File is empty."

    if len(content) > 8000:
        content = content[:8000] + "\n... [Truncated for context length]"

    return content


def write_to_file(filepath: str, data: str, overwrite=False) -> str:
    """
    Writes data to a file, with overwrite confirmation if needed.
    """
    target_path = os.path.abspath(filepath)
    print(f"--- [FileUtils] Writing file: {target_path}")

    if os.path.exists(target_path) and not overwrite:
        if not confirm_action("overwrite", target_path):
            return "Operation canceled by user."

    try:
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(data)
        return f"[Success] Data written to: {target_path}"
    except Exception as e:
        return f"[Error] Could not write to file: {e}"


def delete_file(filepath: str) -> str:
    """
    Deletes a file with explicit confirmation.
    """
    target_path = os.path.abspath(filepath)
    if not os.path.exists(target_path):
        return f"Error: File not found — {target_path}"

    if not confirm_action("delete", target_path):
        return "Deletion canceled."

    try:
        os.remove(target_path)
        return f"[Success] File deleted: {target_path}"
    except Exception as e:
        return f"[Error] Deletion failed: {e}"


def move_file(src: str, dest: str) -> str:
    """
    Moves or renames a file after confirmation.
    """
    src_path = os.path.abspath(src)
    dest_path = os.path.abspath(dest)

    if not os.path.exists(src_path):
        return f"Error: Source not found — {src_path}"

    if not confirm_action("move", f"{src_path} → {dest_path}"):
        return "Move canceled."

    try:
        shutil.move(src_path, dest_path)
        return f"[Success] File moved: {src_path} → {dest_path}"
    except Exception as e:
        return f"[Error] Move failed: {e}"


def list_directory(path=".") -> str:
    """
    Lists all files and folders in the specified directory.
    """
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"Error: Directory not found — {target}"

    items = os.listdir(target)
    if not items:
        return "[Notice] Directory is empty."

    return "\n".join(items)


def create_directory(path: str) -> str:
    """
    Creates a directory if it doesn’t exist.
    """
    target = os.path.abspath(path)
    if os.path.exists(target):
        return f"[Notice] Directory already exists: {target}"

    try:
        os.makedirs(target)
        return f"[Success] Created directory: {target}"
    except Exception as e:
        return f"[Error] Failed to create directory: {e}"


# --- Test run ---
if __name__ == "__main__":
    print("[Testing file_utils.py]")
    print(list_directory("."))
    print(read_file_content("main.py"))
