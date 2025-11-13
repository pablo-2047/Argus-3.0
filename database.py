# database.py
import logging
import sqlite3
from cryptography.fernet import Fernet
import os
import datetime
from core_utils import vector_memory
import threading

DB_FILE = "argus.db"
KEY_FILE = "secret.key"

# --- Key and Encryption Management ---
def write_key():
    """Generates a key and saves it into a file."""
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as key_file:
        key_file.write(key)

def load_key():
    """Loads the key from the current directory, generating it if it doesn't exist."""
    if not os.path.exists(KEY_FILE):
        write_key()
    return open(KEY_FILE, "rb").read()

KEY = load_key()
FERNET = Fernet(KEY)

def encrypt_data(data):
    """Encrypts data using the loaded key."""
    if data is None:
        return None
    return FERNET.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data):
    """Decrypts data using the loaded key."""
    if encrypted_data is None:
        return None
    return FERNET.decrypt(encrypted_data.encode()).decode()

# --- Database Connection ---
def create_connection():
    """Create a database connection to a standard SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
    except Exception as e:
        print(f"Database connection error: {e}")
        return None
    return conn

# --- Core Database Functions ---
# In: database.py
# REPLACE your 'save_memory' function with this:

def save_memory(source, content, mem_type='conversation'):
    """Saves an encrypted memory to the database."""
    encrypted_content = encrypt_data(content)
    conn = create_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memories (source, content, type) VALUES (?, ?, ?)",
                (source, encrypted_content, mem_type)
            )
            conn.commit()
            
            # --- NEW: Also save to vector memory ---
            # We only want to index searchable memories (not tasks, etc.)
            if mem_type == 'conversation':
                # Run this in a thread so it doesn't block the chat
                threading.Thread(
                    target=vector_memory.add_memory_embedding, 
                    args=(content, source, mem_type), 
                    daemon=True
                ).start()
            # --- END NEW ---
            
        except Exception as e:
            print(f"Error saving memory: {e}")
        finally:
            conn.close()

def save_profile_setting(key, value):
    """Saves an encrypted profile setting."""
    encrypted_value = encrypt_data(value)
    conn = create_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_profile (key, value) VALUES (?, ?)",
                (key, encrypted_value)
            )
            conn.commit()
        except Exception as e:
            print(f"Error saving profile setting: {e}")
        finally:
            conn.close()

def load_profile_setting(key, default=None):
    """Loads and decrypts a profile setting."""
    conn = create_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_profile WHERE key = ?", (key,))
            result = cursor.fetchone()
            if result:
                return decrypt_data(result[0])
            else:
                return default
        except Exception as e:
            print(f"Error loading profile setting for key '{key}': {e}")
            return default
        finally:
            conn.close()
    return default
# database.py

# ... (keep all the existing functions like save_memory, load_profile_setting, etc.)

def load_recent_memories(source_filter=None, limit=50, type_filter=None):
    """Loads and decrypts a list of the most recent memories."""
    conn = create_connection()
    memories = []
    if conn:
        try:
            cursor = conn.cursor()
            
            # Build the query dynamically
            query = "SELECT content FROM memories"
            conditions = []
            params = []
            
            if source_filter:
                conditions.append("source = ?")
                params.append(source_filter)
            
            if type_filter:
                conditions.append("type = ?")
                params.append(type_filter)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
                
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            results = cursor.fetchall()
            
            for row in results:
                memories.append(decrypt_data(row[0]))
        except Exception as e:
            print(f"Error loading recent memories: {e}")
        finally:
            conn.close()
    return memories

# ... (keep the rest of the file: initialize_database() and if __name__ == '__main__':)

# --- Initialization ---
def initialize_database():
    """Creates tables and populates initial data."""
    conn = create_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );""")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    source TEXT NOT NULL, content TEXT NOT NULL,
                    type TEXT DEFAULT 'conversation'
                );""")
            conn.commit()
            print("Tables checked/created successfully.")
            
            # Populate with default data if empty
            if load_profile_setting('name') is None:
                print("Setting default user profile...")
                save_profile_setting('name', 'Hammad')
                save_profile_setting('timezone', 'Asia/Kolkata')
        except Exception as e:
            print(f"Table creation error: {e}")
        finally:
            conn.close()

if __name__ == '__main__':
    print("Initializing database and encryption key...")
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    if os.path.exists(KEY_FILE):
        os.remove(KEY_FILE)
    
    initialize_database()
    print("Database initialization complete.")

def update_task(task_id: int, updated_data: dict):
    """Updates a task in the database."""
    conn = create_connection()
    if conn:
        try:
            cursor = conn.cursor()
            encrypted_content = encrypt_data(str(updated_data))
            cursor.execute(
                "UPDATE memories SET content = ? WHERE id = ?",
                (encrypted_content, task_id)
            )
            conn.commit()
        except Exception as e:
            logging.error(f"Error updating task: {e}")
        finally:
            conn.close()