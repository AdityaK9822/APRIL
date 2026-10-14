"""
APRIL Session Management

Handles conversation sessions and ephemeral memory.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import uuid
import json

from .database import MemoryDatabase


@dataclass
class Session:
    """
    Single conversation session

    Attributes:
        id: Unique session identifier
        context: Conversation history (list of messages)
        metadata: Additional session metadata
        created_at: Session creation timestamp
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    context: List[dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    db: Optional[MemoryDatabase] = None

    def add_message(self, role: str, content: str, **kwargs):
        """
        Add message to conversation context

        Args:
            role: Message role (user, assistant, system, tool)
            content: Message content
            **kwargs: Additional message fields
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.context.append(message)

    def get_relevant_memories(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Get relevant memories from database
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of memories
        """
        if self.db:
            return self.db.search_memories(query, limit)
        return []

    def get_context(self) -> List[dict]:
        """
        Get conversation context

        Returns:
            List of messages
        """
        return self.context

    def clear(self):
        """Clear session context"""
        self.context = []

    def to_dict(self) -> dict:
        """
        Serialize session to dictionary

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "context": self.context,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }

    def to_json(self) -> str:
        """
        Serialize session to JSON

        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        """
        Deserialize session from dictionary

        Args:
            data: Dictionary representation

        Returns:
            Session instance
        """
        return cls(
            id=data.get('id', str(uuid.uuid4())[:8]),
            context=data.get('context', []),
            metadata=data.get('metadata', {}),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now()
        )

    def __len__(self) -> int:
        """Get number of messages in context"""
        return len(self.context)

    def __repr__(self) -> str:
        """String representation"""
        return f"Session(id={self.id}, messages={len(self)})"


class SessionManager:
    """
    Manage multiple sessions

    Provides session lifecycle management:
    - Create new sessions
    - Retrieve sessions by ID
    - Delete sessions
    - List all sessions
    """

    def __init__(self, db: Optional[MemoryDatabase] = None):
        """Initialize session manager
        
        Args:
            db: MemoryDatabase instance for persistence
        """
        self.sessions: Dict[str, Session] = {}
        self.db = db

    def create_session(self, metadata: Optional[Dict] = None) -> Session:
        """
        Create new session

        Args:
            metadata: Optional session metadata

        Returns:
            New Session instance
        """
        session = Session(db=self.db, metadata=metadata or {})
        self.sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID

        Args:
            session_id: Session identifier

        Returns:
            Session instance or None if not found
        """
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session by ID

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[Session]:
        """
        List all sessions

        Returns:
            List of Session instances
        """
        return list(self.sessions.values())

    def clear_all(self):
        """Delete all sessions"""
        self.sessions.clear()

    def __len__(self) -> int:
        """Get number of sessions"""
        return len(self.sessions)

    def __repr__(self) -> str:
        """String representation"""
        return f"SessionManager(sessions={len(self)})"


# Example usage and testing
if __name__ == "__main__":
    # Test session creation
    session = Session()
    session.add_message("user", "Hello")
    session.add_message("assistant", "Hi there!")

    print(f"Session: {session}")
    print(f"Context: {session.get_context()}")
    print(f"JSON: {session.to_json()}")
