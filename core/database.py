"""
APRIL Memory Database

SQLite database for conversation storage and extracted memories.

Optimized with connection pooling and proper error handling.
"""

import sqlite3
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import weakref


class ConnectionPool:
    """
    Thread-safe connection pool for SQLite
    
    Pool of database connections that can be reused across operations.
    Each connection is created with check_same_thread=False to allow
    cross-thread usage.
    """
    
    def __init__(self, db_path: str, pool_size: int = 5):
        """
        Initialize connection pool
        
        Args:
            db_path: Path to SQLite database
            pool_size: Number of connections in pool
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.pool = []
        self.lock = threading.Lock()
        self._in_use = set()
        
        # Pre-create connections
        for _ in range(pool_size):
            conn = self._create_connection()
            self.pool.append(conn)
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn
    
    def acquire(self) -> sqlite3.Connection:
        """
        Acquire a connection from the pool
        
        Returns:
            Database connection
        """
        with self.lock:
            # Find available connection
            for conn in self.pool:
                if id(conn) not in self._in_use:
                    self._in_use.add(id(conn))
                    return conn
            
            # Create new connection if pool not full
            if len(self.pool) < self.pool_size * 2:
                conn = self._create_connection()
                self.pool.append(conn)
                self._in_use.add(id(conn))
                return conn
            
            # Wait for available connection
            raise RuntimeError("Connection pool exhausted")
    
    def release(self, conn: sqlite3.Connection):
        """
        Release a connection back to the pool
        
        Args:
            conn: Connection to release
        """
        with self.lock:
            self._in_use.discard(id(conn))
    
    def execute(self, query: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        """Execute a query with connection from pool"""
        conn = self.acquire()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor
        finally:
            self.release(conn)
    
    def fetchall(self, query: str, params: Optional[tuple] = None) -> List[sqlite3.Row]:
        """Execute query and fetch all results"""
        cursor = self.execute(query, params)
        return cursor.fetchall()
    
    def fetchone(self, query: str, params: Optional[tuple] = None) -> Optional[sqlite3.Row]:
        """Execute query and fetch one result"""
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def close_all(self):
        """Close all connections in the pool"""
        with self.lock:
            for conn in self.pool:
                try:
                    conn.close()
                except:
                    pass
            self.pool.clear()


# Module-level connection pool (singleton-like)
_pool = None
_pool_lock = threading.Lock()


def get_pool(db_path: str) -> ConnectionPool:
    """
    Get or create connection pool for database
    
    Args:
        db_path: Path to database file
        
    Returns:
        ConnectionPool instance
    """
    global _pool
    
    with _pool_lock:
        if _pool is None or _pool.db_path != db_path:
            if _pool:
                _pool.close_all()
            _pool = ConnectionPool(db_path)
        return _pool


class MemoryDatabase:
    """
    SQLite database for APRIL memory system
    
    Thread-safe: Uses connection pooling for concurrent access.
    
    Tables:
        - conversations: Temporary raw message buffer
        - memory: Permanent structured knowledge
        - sessions: Session metadata
    """
    
    def __init__(self, db_path: str = "./data/april_memory.db"):
        """
        Initialize database
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Get connection pool
        self.pool = get_pool(db_path)
        
        # Initialize schema
        self._init_schema()
    
    def _init_schema(self):
        """Create database schema"""
        # Conversations table
        self.pool.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_session 
            ON conversations(session_id)
        """)
        
        self.pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_unprocessed 
            ON conversations(processed) WHERE processed = 0
        """)
        
        # Memory table
        self.pool.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                tags TEXT,
                source_message_ids TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_type 
            ON memory(memory_type)
        """)
        
        self.pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_session 
            ON memory(session_id)
        """)
        
        # Sessions table
        self.pool.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
    
    def save_message(self, session_id: str, role: str, content: str) -> int:
        """Save a message to conversations table"""
        cursor = self.pool.execute("""
            INSERT INTO conversations (session_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
        """, (session_id, role, content, datetime.now().isoformat()))
        return cursor.lastrowid
    
    def get_unprocessed_messages(self, session_id: Optional[str] = None) -> List[Dict]:
        """Get unprocessed messages"""
        if session_id:
            rows = self.pool.fetchall("""
                SELECT * FROM conversations 
                WHERE session_id = ? AND processed = 0
                ORDER BY timestamp ASC
            """, (session_id,))
        else:
            rows = self.pool.fetchall("""
                SELECT * FROM conversations 
                WHERE processed = 0
                ORDER BY timestamp ASC
            """)
        return [dict(row) for row in rows]
    
    def get_messages_by_session(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Get messages for a specific session"""
        rows = self.pool.fetchall("""
            SELECT * FROM conversations 
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, limit))
        return [dict(row) for row in rows]
    
    def mark_processed(self, message_ids: List[int]):
        """Mark messages as processed"""
        if not message_ids:
            return
        placeholders = ','.join('?' * len(message_ids))
        self.pool.execute(f"""
            UPDATE conversations 
            SET processed = 1 
            WHERE id IN ({placeholders})
        """, message_ids)
    
    def delete_processed_messages(self, older_than_hours: int = 60):
        """Delete processed messages older than threshold"""
        self.pool.execute("""
            DELETE FROM conversations 
            WHERE processed = 1 
            AND datetime(created_at) < datetime('now', ?)
        """, (f'-{older_than_hours} hours',))
    
    def save_memory(
        self,
        session_id: str,
        memory_type: str,
        content: Dict,
        confidence: float = 0.5,
        tags: List[str] = None,
        source_message_ids: List[int] = None
    ) -> int:
        """Save extracted memory"""
        cursor = self.pool.execute("""
            INSERT INTO memory 
            (session_id, memory_type, content, confidence, tags, source_message_ids)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session_id, memory_type, json.dumps(content), confidence,
            json.dumps(tags or []), json.dumps(source_message_ids or [])
        ))
        return cursor.lastrowid
    
    def get_memories(
        self,
        session_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """Retrieve memories"""
        query = "SELECT * FROM memory WHERE 1=1"
        params = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        if tags:
            for tag in tags:
                query += " AND tags LIKE ?"
                params.append(f'%\"{tag}\"%')
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self.pool.fetchall(query, params)
        memories = []
        for row in rows:
            memory = dict(row)
            memory['content'] = json.loads(memory['content'])
            memory['tags'] = json.loads(memory['tags'])
            source_ids = memory['source_message_ids']
            memory['source_message_ids'] = json.loads(source_ids) if source_ids else []
            memories.append(memory)
        return memories
    
    def search_memories(self, query_text: str, limit: int = 10) -> List[Dict]:
        """Simple text search in memory content"""
        query = """
            SELECT * FROM memory 
            WHERE content LIKE ? 
            OR tags LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        SearchParam = f'%{query_text}%'
        rows = self.pool.fetchall(query, (SearchParam, SearchParam, limit))
        memories = []
        for row in rows:
            memory = dict(row)
            memory['content'] = json.loads(memory['content'])
            memory['tags'] = json.loads(memory['tags'])
            source_ids = memory['source_message_ids']
            memory['source_message_ids'] = json.loads(source_ids) if source_ids else []
            memories.append(memory)
        return memories
    
    def save_session(self, session_id: str, metadata: Dict = None):
        """Save session metadata"""
        self.pool.execute("""
            INSERT OR REPLACE INTO sessions (id, metadata)
            VALUES (?, ?)
        """, (session_id, json.dumps(metadata or {})))
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session metadata"""
        row = self.pool.fetchone("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if row:
            session = dict(row)
            session['metadata'] = json.loads(session['metadata']) if session['metadata'] else {}
            return session
        return None
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        stats = {}
        stats['total_messages'] = self.pool.fetchone("SELECT COUNT(*) FROM conversations")[0]
        stats['unprocessed_messages'] = self.pool.fetchone(
            "SELECT COUNT(*) FROM conversations WHERE processed = 0")[0]
        stats['total_memories'] = self.pool.fetchone("SELECT COUNT(*) FROM memory")[0]
        stats['total_sessions'] = self.pool.fetchone("SELECT COUNT(*) FROM sessions")[0]
        rows = self.pool.fetchall("""
            SELECT memory_type, COUNT(*) as count FROM memory GROUP BY memory_type
        """)
        stats['memory_by_type'] = {row[0]: row[1] for row in rows}
        return stats
    
    def close(self):
        """Close database connections"""
        self.pool.close_all()


# Cleanup on module exit
import atexit

def cleanup_pool():
    """Clean up connection pool on exit"""
    global _pool
    if _pool:
        _pool.close_all()

atexit.register(cleanup_pool)