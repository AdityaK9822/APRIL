"""Test memory system"""

import unittest
import os
import tempfile
import json
import sqlite3
from datetime import datetime

from core.database import MemoryDatabase
from core.memory_extractor import MemoryExtractor
from core.config import AgentConfig


def fake_client(response_json: str):
    """
    Minimal OpenAI-compatible double for extraction tests

    Records every prompt it receives into .calls and always returns
    response_json as the assistant message content.
    """
    from types import SimpleNamespace

    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=response_json))]
    )

    def create(**kwargs):
        client.calls.append(kwargs)
        return response

    client = SimpleNamespace()
    client.calls = []
    client.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
    return client


class TestMemoryDatabase(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        """Create temporary database"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db = MemoryDatabase(self.temp_db.name)
    
    def tearDown(self):
        """Clean up"""
        self.db.close()
        os.unlink(self.temp_db.name)
    
    def test_save_message(self):
        """Test saving message"""
        msg_id = self.db.save_message("test-session", "user", "Hello")
        self.assertIsNotNone(msg_id)
        self.assertGreater(msg_id, 0)
    
    def test_save_memory(self):
        """Test saving memory"""
        mem_id = self.db.save_memory(
            session_id="test",
            memory_type="fact",
            content={"text": "Test fact"},
            confidence=0.9,
            tags=["test"]
        )
        self.assertIsNotNone(mem_id)
    
    def test_get_memories(self):
        """Test retrieving memories"""
        self.db.save_memory("s1", "fact", {"text": "fact1"}, tags=["tag1"])
        self.db.save_memory("s2", "decision", {"text": "dec1"}, tags=["tag2"])
        
        memories = self.db.get_memories(limit=10)
        self.assertEqual(len(memories), 2)
    
    def test_search_memories(self):
        """Test searching memories"""
        self.db.save_memory("s1", "fact", {"text": "User prefers dark theme"})
        
        results = self.db.search_memories("dark theme")
        self.assertGreater(len(results), 0)
    
    def test_save_and_get_session(self):
        """Test session metadata"""
        self.db.save_session("test-session", {"name": "Test", "user": "admin"})
        session = self.db.get_session("test-session")
        
        self.assertIsNotNone(session)
        self.assertEqual(session['metadata']['name'], "Test")
    
    def test_processed_flag(self):
        """Test processed flag functionality"""
        msg_id = self.db.save_message("s1", "user", "Hello")
        
        unprocessed = self.db.get_unprocessed_messages("s1")
        self.assertEqual(len(unprocessed), 1)
        
        self.db.mark_processed([msg_id])
        
        unprocessed = self.db.get_unprocessed_messages("s1")
        self.assertEqual(len(unprocessed), 0)
    
    def test_get_stats(self):
        """Test database statistics"""
        stats = self.db.get_stats()
        
        self.assertIn('total_messages', stats)
        self.assertIn('total_memories', stats)
        self.assertIn('total_sessions', stats)
    
    def test_save_memory_dedup(self):
        """Identical memory content is stored once, wherever re-saved"""
        first = self.db.save_memory("s1", "fact", {"text": "User prefers dark theme"}, tags=["ui"])
        second = self.db.save_memory("s2", "fact", {"text": "User prefers dark theme"}, tags=["ui"])
        
        self.assertEqual(first, second)
        self.assertEqual(len(self.db.get_memories(limit=10)), 1)
    
    def test_dedup_respects_memory_type(self):
        """Same content under different types are distinct memories"""
        fact = self.db.save_memory("s1", "fact", {"text": "Switched to local model"})
        decision = self.db.save_memory("s1", "decision", {"text": "Switched to local model"})
        
        self.assertNotEqual(fact, decision)
        self.assertEqual(len(self.db.get_memories(limit=10)), 2)
    
    def test_dedup_respects_content(self):
        """Different content saves as distinct memories"""
        a = self.db.save_memory("s1", "fact", {"text": "Prefers dark theme"})
        b = self.db.save_memory("s1", "fact", {"text": "Prefers light theme"})
        
        self.assertNotEqual(a, b)


class TestIncrementalExtraction(unittest.TestCase):
    """extract_incremental must target new messages, not re-extract history"""
    
    def setUp(self):
        self.extractor = MemoryExtractor()
    
    def test_extracts_only_new_with_old_as_context(self):
        """New messages are the extraction target; old messages are context"""
        extraction = {"extractions": [
            {"type": "preference", "content": {"text": "User prefers the TUI"},
             "confidence": 0.9, "tags": ["ui"]}
        ]}
        client = fake_client(json.dumps(extraction))
        
        old = [
            {"role": "user", "content": "Hi, I am Alex"},
            {"role": "assistant", "content": "Hello Alex"}
        ]
        new = [{"role": "user", "content": "I prefer the TUI"}]
        
        memories = self.extractor.extract_incremental(old, new, client=client)
        
        self.assertEqual(len(client.calls), 1, "expected exactly one LLM call")
        prompt = client.calls[0]["messages"][0]["content"]
        self.assertIn("I prefer the TUI", prompt)      # new messages are the target
        self.assertIn("Hi, I am Alex", prompt)          # old messages appear as context
        self.assertIn("do NOT extract", prompt)         # old messages marked as context
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["type"], "preference")
    
    def test_skips_llm_when_nothing_new(self):
        """Empty new_messages: no LLM call, empty result"""
        client = fake_client('{"extractions": []}')
        
        memories = self.extractor.extract_incremental(
            [{"role": "user", "content": "old"}], [], client=client
        )
        
        self.assertEqual(memories, [])
        self.assertEqual(client.calls, [], "no LLM call when there is nothing new")


class TestDatabaseMigration(unittest.TestCase):
    """Databases created before content_hash migrate onto dedup cleanly"""
    
    def test_legacy_db_migrates_and_dedups(self):
        """A pre-hash database backfills hashes and dedups instead of re-inserting"""
        handle = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        handle.close()
        conn = sqlite3.connect(handle.name)
        conn.execute("""
            CREATE TABLE memory (
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
        conn.execute(
            "INSERT INTO memory (session_id, memory_type, content, confidence, tags, source_message_ids) "
            "VALUES (?, 'fact', ?, 0.9, '[]', '[]')",
            ("s1", json.dumps({"text": "legacy fact"}))
        )
        conn.commit()
        conn.close()
        
        db = MemoryDatabase(handle.name)
        try:
            duplicate_id = db.save_memory("s1", "fact", {"text": "legacy fact"})
            memories = db.get_memories(limit=10)
            
            self.assertEqual(len(memories), 1, "legacy duplicate must not be re-inserted")
            self.assertEqual(duplicate_id, memories[0]['id'])
            self.assertIsNotNone(memories[0]['content_hash'])
        finally:
            db.close()
            os.unlink(handle.name)


class TestMemoryExtractor(unittest.TestCase):
    """Test memory extraction"""
    
    def test_format_conversation(self):
        """Test conversation formatting"""
        extractor = MemoryExtractor()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        formatted = extractor.format_conversation(messages)
        
        self.assertIn("User: Hello", formatted)
        self.assertIn("Assistant: Hi!", formatted)
    
    def test_validate_extraction(self):
        """Test extraction validation"""
        extractor = MemoryExtractor()
        
        valid = {
            "type": "fact",
            "content": {"text": "test"},
            "confidence": 0.9,
            "tags": ["test"]
        }
        
        self.assertTrue(extractor._validate_extraction(valid))
        
        invalid = {"type": "invalid_type"}
        self.assertFalse(extractor._validate_extraction(invalid))
    
    def test_extract_empty(self):
        """Test extraction with empty messages"""
        extractor = MemoryExtractor()
        memories = extractor.extract([])
        self.assertEqual(memories, [])
    
    def test_extract_fallback(self):
        """Test extraction fallback mode"""
        extractor = MemoryExtractor()
        # Should return empty list when client fails
        messages = [{"role": "user", "content": "test"}]
        memories = extractor.extract(messages, fallback_mode=True)
        # Will be empty because no valid OpenAI client
        self.assertIsInstance(memories, list)


class TestIntegration(unittest.TestCase):
    """Integration test with agent config"""
    
    def test_config_with_memory(self):
        """Test config has memory settings"""
        config = AgentConfig(
            model="gemma4:31b-cloud",
            api_key="test",
            api_base_url="http://localhost:11434/v1"
        )
        
        self.assertTrue(config.memory_enabled)
        self.assertIn("april_memory", config.memory_db_path)
        self.assertIn("gemma4:31b-cloud", config.memory_extraction_model)


if __name__ == '__main__':
    unittest.main()
