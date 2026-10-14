"""Test memory system"""

import unittest
import os
import tempfile
import json
from datetime import datetime

from core.database import MemoryDatabase
from core.memory_extractor import MemoryExtractor
from core.config import AgentConfig


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
