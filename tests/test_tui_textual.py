"""Tests for Textual TUI implementation"""

import unittest
from core.textual_tui import APRILApp, ConsoleRenderer


class TestAPRILApp(unittest.TestCase):
    """Tests for APRILApp class"""
    
    def test_import(self):
        """Test APRILApp imports correctly"""
        self.assertIsNotNone(APRILApp)
    
    def test_has_compose(self):
        """Test APRILApp has compose method"""
        self.assertTrue(hasattr(APRILApp, 'compose'))
    
    def test_has_bindings(self):
        """Test APRILApp has key bindings"""
        self.assertTrue(hasattr(APRILApp, 'BINDINGS'))
        bindings = APRILApp.BINDINGS
        self.assertIn('quit', [b[1] for b in bindings])
    
    def test_init_no_agent(self):
        """Test APRILApp initialization without agent"""
        app = APRILApp()
        self.assertIsNotNone(app)
        self.assertIsNone(app.agent)
        self.assertIsNone(app.db)
    
    def test_init_with_agent(self):
        """Test APRILApp initialization with agent"""
        from core import AgentConfig, AgentRuntime
        config = AgentConfig.from_env()
        agent = AgentRuntime(config)
        db = agent.db
        
        app = APRILApp(agent=agent, db=db)
        self.assertEqual(app.agent, agent)
        self.assertEqual(app.db, db)


class TestConsoleRenderer(unittest.TestCase):
    """Tests for ConsoleRenderer class"""
    
    def test_import(self):
        """Test ConsoleRenderer imports correctly"""
        self.assertIsNotNone(ConsoleRenderer)
    
    def test_has_print_header(self):
        """Test ConsoleRenderer has print_header method"""
        cr = ConsoleRenderer()
        self.assertTrue(hasattr(cr, 'print_header'))
    
    def test_has_print_message(self):
        """Test ConsoleRenderer has print_message method"""
        cr = ConsoleRenderer()
        self.assertTrue(hasattr(cr, 'print_message'))
    
    def test_init(self):
        """Test ConsoleRenderer initialization"""
        cr = ConsoleRenderer()
        self.assertIsNotNone(cr)
        self.assertFalse(cr.running)
    
    def test_messages_list(self):
        """Test ConsoleRenderer has messages list"""
        cr = ConsoleRenderer()
        self.assertIsInstance(cr.messages, list)


if __name__ == '__main__':
    unittest.main()
