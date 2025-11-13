# core_utils/vector_memory.py
"""
ARGUS Enhanced Vector Memory - "The Long-Term Memory System"

This is the UPGRADED version of your existing vector_memory.py
It adds:
1. Priority-weighted memories (important facts surface faster)
2. Context-aware retrieval (knows what you're doing)
3. Memory decay (old, unused memories fade)
4. Semantic clustering (groups related memories)

Jarvis equivalent: How he remembers everything Tony ever told him
"""

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import pickle
import time
import threading
import logging
from datetime import datetime, timedelta
from collections import defaultdict

# === CONFIGURATION ===
MODEL_NAME = 'all-MiniLM-L6-v2'  # Fast, high-quality embeddings
INDEX_FILE = 'argus_memory.index'
METADATA_FILE = 'argus_memory.meta'
EMBEDDING_DIMENSION = 384  # Fixed by the model

# === GLOBAL STATE ===
embedding_model = None
vector_index = None
metadata = []  # List of memory objects
index_lock = threading.Lock()

# === MEMORY PRIORITY LEVELS ===
PRIORITY_CRITICAL = 10    # User preferences, important facts
PRIORITY_HIGH = 8         # Project-specific information
PRIORITY_NORMAL = 5       # Regular conversation
PRIORITY_LOW = 3          # Casual chat
PRIORITY_TRANSIENT = 1    # Temporary info (weather, etc.)


def initialize_vector_db():
    """
    Loads the embedding model and FAISS index from disk.
    If no index exists, creates a new one.
    
    This should be called ONCE at startup.
    """
    global embedding_model, vector_index, metadata
    
    logging.info("--- [VectorMemory] Initializing Smart Context engine... ---")
    
    # === 1. Load the Sentence Transformer model ===
    try:
        embedding_model = SentenceTransformer(MODEL_NAME)
        logging.info(f"[VectorMemory] Embedding model '{MODEL_NAME}' loaded successfully.")
    except Exception as e:
        logging.error(f"[VectorMemory] CRITICAL: Could not load embedding model! {e}")
        return
    
    # === 2. Load or create the FAISS index ===
    with index_lock:
        if os.path.exists(INDEX_FILE) and os.path.exists(METADATA_FILE):
            try:
                vector_index = faiss.read_index(INDEX_FILE)
                with open(METADATA_FILE, 'rb') as f:
                    metadata = pickle.load(f)
                logging.info(f"[VectorMemory] Loaded existing database with {len(metadata)} memories.")
                
                # Clean up old, unused memories (memory decay)
                _apply_memory_decay(embedding_model)
                
            except Exception as e:
                logging.warning(f"[VectorMemory] Error loading index, creating new one. {e}")
                vector_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
                metadata = []
        else:
            logging.info("[VectorMemory] No existing index found. Creating a new one.")
            vector_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
            metadata = []


def add_memory_embedding(text: str, source: str, mem_type: str, priority: int = PRIORITY_NORMAL):
    """
    Creates an embedding for a text snippet and adds it to the database.
    
    This is called by database.py every time a memory is saved.
    
    Args:
        text: The text to remember
        source: 'user' | 'argus' | 'system'
        mem_type: 'conversation' | 'task' | 'fact'
        priority: 1-10, how important this memory is
    """
    if not embedding_model or vector_index is None:
        logging.warning("[VectorMemory] Vector DB not initialized. Skipping embedding.")
        return
    
    try:
        # === 1. Create the embedding ===
        embedding = embedding_model.encode([text])[0]
        
        # === 2. Apply priority boost ===
        # Higher priority memories are slightly "closer" to all queries
        # This makes important facts surface faster
        boost_factor = 1.0 + (priority / 100.0)
        boosted_embedding = embedding * boost_factor
        
        vector = np.array([boosted_embedding]).astype('float32')
        
        # === 3. Thread-safe addition ===
        with index_lock:
            vector_index.add(vector)
            
            new_id = len(metadata)
            metadata.append({
                "id": new_id,
                "source": source,
                "type": mem_type,
                "text": text,
                "timestamp": time.time(),
                "priority": priority,
                "access_count": 0,      # How many times this was retrieved
                "last_accessed": None,  # When it was last retrieved
                "relevance_score": 0    # Computed during retrieval
            })
            
            # === 4. Save to disk ===
            # In production, we'd batch these writes
            faiss.write_index(vector_index, INDEX_FILE)
            with open(METADATA_FILE, 'wb') as f:
                pickle.dump(metadata, f)
        
        logging.debug(f"[VectorMemory] Added memory #{new_id}: '{text[:50]}...' (Priority: {priority})")
    
    except Exception as e:
        logging.error(f"[VectorMemory] Error adding embedding: {e}")


def retrieve_relevant_memories(query_text: str, k: int = 5, activity_context: str = None):
    """
    BASIC retrieval (for backwards compatibility).
    Just does semantic similarity search.
    
    For smart retrieval, use smart_retrieve() instead.
    
    Args:
        query_text: The query to search for
        k: Number of results to return
        activity_context: Optional activity hint (e.g., 'coding', 'cad')
    
    Returns:
        list: Top k most relevant memories
    """
    if not embedding_model or vector_index is None or not metadata:
        return []
    
    try:
        query_embedding = embedding_model.encode([query_text])[0]
        query_vector = np.array([query_embedding]).astype('float32')
        
        with index_lock:
            distances, indices = vector_index.search(query_vector, k)
            
            relevant_memories = []
            for i in indices[0]:
                if 0 <= i < len(metadata):
                    mem = metadata[i].copy()
                    # Update access tracking
                    metadata[i]['access_count'] += 1
                    metadata[i]['last_accessed'] = time.time()
                    relevant_memories.append(mem)
        
        logging.debug(f"[VectorMemory] Retrieved {len(relevant_memories)} memories for query.")
        return relevant_memories
    
    except Exception as e:
        logging.error(f"[VectorMemory] Error retrieving memories: {e}")
        return []


def smart_retrieve(query_text: str, activity_context: str = None, k: int = 5, 
                   time_window_hours: int = None):
    """
    ENHANCED retrieval with multi-factor ranking.
    
    This is the "smart" version that considers:
    1. Semantic similarity (FAISS)
    2. Priority (important facts rank higher)
    3. Recency (recent memories rank higher)
    4. Access frequency (popular memories rank higher)
    5. Activity context (memories from similar activities rank higher)
    6. Time window (optional: only consider memories from last N hours)
    
    Args:
        query_text: The user's query
        activity_context: Current activity ('coding', 'cad', etc.)
        k: Number of results to return
        time_window_hours: Only consider memories from last N hours (optional)
    
    Returns:
        list: Top k most relevant memories, sorted by relevance_score
    
    Example:
        memories = smart_retrieve(
            "How do I optimize Python code?",
            activity_context="coding",
            k=5,
            time_window_hours=24  # Only last 24 hours
        )
    """
    if not embedding_model or vector_index is None or not metadata:
        return []
    
    try:
        # === 1. Get initial candidates (semantic search) ===
        query_embedding = embedding_model.encode([query_text])[0]
        query_vector = np.array([query_embedding]).astype('float32')
        
        with index_lock:
            # Get 3x more results than needed for filtering
            num_candidates = min(k * 3, len(metadata))
            distances, indices = vector_index.search(query_vector, num_candidates)
            
            candidates = []
            current_time = time.time()
            
            for idx, distance in zip(indices[0], distances[0]):
                if idx < 0 or idx >= len(metadata):
                    continue
                
                mem = metadata[idx].copy()
                
                # === TIME WINDOW FILTER ===
                if time_window_hours:
                    time_diff = current_time - mem['timestamp']
                    if time_diff > (time_window_hours * 3600):
                        continue  # Too old
                
                # === 2. Calculate multi-factor relevance score ===
                score = 0.0
                
                # Factor 1: Semantic similarity (inverted distance)
                # Lower distance = more similar
                similarity = 1.0 / (1.0 + distance)
                score += similarity * 100  # Weight: 100
                
                # Factor 2: Priority boost
                score += mem['priority'] * 5  # Weight: 5 per priority point
                
                # Factor 3: Recency boost
                time_diff = current_time - mem['timestamp']
                if time_diff < 3600:  # Last hour
                    score += 50
                elif time_diff < 86400:  # Last 24 hours
                    score += 30
                elif time_diff < 604800:  # Last week
                    score += 15
                
                # Factor 4: Access frequency boost
                # Memories that have been useful before are likely useful again
                score += mem['access_count'] * 3
                
                # Factor 5: Activity context matching
                if activity_context:
                    # Check if the memory mentions the current activity
                    if activity_context.lower() in mem['text'].lower():
                        score += 40
                    
                    # Check if memory is from a similar context
                    # (This would require storing context with each memory)
                    # For now, we'll use keyword matching
                    context_keywords = {
                        'coding': ['code', 'python', 'function', 'bug', 'script', 'debug'],
                        'cad': ['autocad', 'drawing', 'design', '3d', 'model'],
                        'productivity': ['document', 'report', 'write', 'email']
                    }
                    
                    if activity_context in context_keywords:
                        keywords = context_keywords[activity_context]
                        if any(kw in mem['text'].lower() for kw in keywords):
                            score += 20
                
                # Factor 6: Decay penalty for rarely-accessed old memories
                if mem['access_count'] == 0 and time_diff > 2592000:  # 30 days, never accessed
                    score *= 0.5  # Halve the score
                
                mem['relevance_score'] = score
                candidates.append(mem)
            
            # === 3. Sort by relevance and return top k ===
            candidates.sort(key=lambda x: x['relevance_score'], reverse=True)
            top_memories = candidates[:k]
            
            # === 4. Update access tracking ===
            for mem in top_memories:
                original_idx = mem['id']
                if 0 <= original_idx < len(metadata):
                    metadata[original_idx]['access_count'] += 1
                    metadata[original_idx]['last_accessed'] = current_time
        
        logging.info(f"[VectorMemory] Smart retrieval: {len(top_memories)} memories "
                    f"(context: {activity_context or 'none'})")
        
        return top_memories
    
    except Exception as e:
        logging.error(f"[VectorMemory] Error in smart_retrieve: {e}")
        return []


def get_memory_clusters(n_clusters: int = 5):
    """
    Groups memories into semantic clusters.
    Useful for showing "topics you've discussed recently".
    
    Args:
        n_clusters: Number of clusters to create
    
    Returns:
        dict: {cluster_id: [memory_ids]}
    
    Example:
        clusters = get_memory_clusters(5)
        # {0: [1, 5, 12], 1: [3, 7, 9], ...}
        # Cluster 0 might be "Python coding"
        # Cluster 1 might be "AutoCAD projects"
    """
    if not metadata or not vector_index:
        return {}
    
    try:
        from sklearn.cluster import KMeans
        
        with index_lock:
            # Get all embeddings from the FAISS index
            all_embeddings = []
            for i in range(len(metadata)):
                # Reconstruct the embedding (this is why we use IndexFlatL2)
                vec = vector_index.reconstruct(i)
                all_embeddings.append(vec)
            
            all_embeddings = np.array(all_embeddings)
            
            # Perform K-Means clustering
            kmeans = KMeans(n_clusters=min(n_clusters, len(metadata)), random_state=42)
            labels = kmeans.fit_predict(all_embeddings)
            
            # Group memory IDs by cluster
            clusters = defaultdict(list)
            for mem_id, label in enumerate(labels):
                clusters[int(label)].append(mem_id)
        
        logging.info(f"[VectorMemory] Created {len(clusters)} memory clusters.")
        return dict(clusters)
    
    except ImportError:
        logging.warning("[VectorMemory] scikit-learn not installed. Cannot cluster memories.")
        return {}
    except Exception as e:
        logging.error(f"[VectorMemory] Error clustering memories: {e}")
        return {}


def _apply_memory_decay(embedding_model): # <-- FIX: Receive the model
    """
    INTERNAL: Removes old, unused memories to keep the database clean.
    
    Criteria for removal:
    - Over 90 days old
    - Never accessed (access_count == 0)
    - Priority <= PRIORITY_LOW
    
    This is like how Jarvis wouldn't remember every trivial detail forever.
    """
    if not metadata:
        return
    
    current_time = time.time()
    ninety_days = 90 * 24 * 3600
    
    to_remove = []
    
    with index_lock:
        for i, mem in enumerate(metadata):
            age = current_time - mem['timestamp']
            
            if (age > ninety_days and 
                mem['access_count'] == 0 and 
                mem['priority'] <= PRIORITY_LOW):
                to_remove.append(i)
        
        if to_remove:
            logging.info(f"[VectorMemory] Memory decay: Removing {len(to_remove)} old, unused memories.")
            
            # Remove from metadata (in reverse to preserve indices)
            for i in reversed(to_remove):
                del metadata[i]
            
            # Rebuild the FAISS index (expensive, but necessary)
            # In production, we'd use IndexIDMap to avoid this
            new_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
            
            for mem in metadata:
                # Re-encode and add
                embedding = embedding_model.encode([mem['text']])[0]
                boost_factor = 1.0 + (mem['priority'] / 100.0)
                boosted_embedding = embedding * boost_factor
                vector = np.array([boosted_embedding]).astype('float32')
                new_index.add(vector)
            
            vector_index = new_index
            
            # Save
            faiss.write_index(vector_index, INDEX_FILE)
            with open(METADATA_FILE, 'wb') as f:
                pickle.dump(metadata, f)


def get_memory_stats():
    """
    Returns statistics about the memory database.
    Useful for debugging and system monitoring.
    
    Returns:
        dict: {total_memories, oldest_memory_age, most_accessed, ...}
    """
    if not metadata:
        return {"total_memories": 0}
    
    with index_lock:
        current_time = time.time()
        
        oldest = min(metadata, key=lambda m: m['timestamp'])
        most_accessed = max(metadata, key=lambda m: m['access_count'])
        
        priority_distribution = defaultdict(int)
        for mem in metadata:
            priority_distribution[mem['priority']] += 1
        
        return {
            "total_memories": len(metadata),
            "oldest_memory_age_days": (current_time - oldest['timestamp']) / 86400,
            "most_accessed_memory": most_accessed['text'][:100],
            "most_accessed_count": most_accessed['access_count'],
            "priority_distribution": dict(priority_distribution),
            "index_size_mb": os.path.getsize(INDEX_FILE) / 1024 / 1024 if os.path.exists(INDEX_FILE) else 0
        }


# === STANDALONE TEST ===
if __name__ == "__main__":
    print("=== ARGUS Enhanced Vector Memory - Standalone Test ===\n")
    
    initialize_vector_db()
    
    # Add test memories
    test_memories = [
        ("Python is a high-level programming language", "system", "fact", PRIORITY_HIGH),
        ("I like pizza", "user", "conversation", PRIORITY_LOW),
        ("AutoCAD uses .dwg file format", "system", "fact", PRIORITY_HIGH),
        ("The weather today is sunny", "system", "conversation", PRIORITY_TRANSIENT),
        ("Remember to buy milk", "user", "task", PRIORITY_NORMAL),
    ]
    
    print("Adding test memories...\n")
    for text, source, mem_type, priority in test_memories:
        add_memory_embedding(text, source, mem_type, priority)
        print(f"Added: {text} (Priority: {priority})")
    
    print("\n=== Testing Smart Retrieval ===\n")
    
    # Test 1: Basic query
    print("Query: 'programming languages'")
    results = smart_retrieve("programming languages", k=3)
    for i, mem in enumerate(results):
        print(f"{i+1}. [{mem['relevance_score']:.1f}] {mem['text']}")
    
    print("\n" + "="*50 + "\n")
    
    # Test 2: With activity context
    print("Query: 'file formats' (context: cad)")
    results = smart_retrieve("file formats", activity_context="cad", k=3)
    for i, mem in enumerate(results):
        print(f"{i+1}. [{mem['relevance_score']:.1f}] {mem['text']}")
    
    print("\n" + "="*50 + "\n")
    
    # Stats
    stats = get_memory_stats()
    print("=== Memory Database Stats ===")
    for key, value in stats.items():
        print(f"{key}: {value}")