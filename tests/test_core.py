"""
Tests for APRIL core components
"""

import pytest
from datetime import datetime
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import AgentConfig
from core.session import Session, SessionManager
from tools.shell import ShellTool, ToolResult


class TestAgentConfig:
    """Test AgentConfig class"""
    
    def test_config_defaults(self):
        """Test default configuration values"""
        config = AgentConfig(
            model="test-model",
            api_key="test-key",
            api_base_url="http://test.url"
        )
        
        assert config.model == "test-model"
        assert config.api_key == "test-key"
        assert config.api_base_url == "http://test.url"
        assert config.max_context_length == 128000
        assert config.temperature == 0.7
        assert config.max_iterations == 100
    
    def test_config_validation(self):
        """Test configuration validation"""
        # Valid config
        config = AgentConfig(
            model="test",
            api_key="test",
            api_base_url="http://test"
        )
        assert config.validate() is True
        
        # Invalid: empty model
        config_invalid = AgentConfig(
            model="",
            api_key="test",
            api_base_url="http://test"
        )
        assert config_invalid.validate() is False


class TestSession:
    """Test Session class"""
    
    def test_session_creation(self):
        """Test session creation"""
        session = Session()
        
        assert session.id is not None
        assert len(session.id) == 8  # UUID truncated to 8 chars
        assert session.context == []
        assert isinstance(session.created_at, datetime)
    
    def test_session_add_message(self):
        """Test adding messages to session"""
        session = Session()
        
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")
        
        assert len(session.context) == 2
        assert session.context[0]["role"] == "user"
        assert session.context[0]["content"] == "Hello"
        assert session.context[1]["role"] == "assistant"
    
    def test_session_serialization(self):
        """Test session serialization"""
        session = Session(metadata={"test": "value"})
        session.add_message("user", "Test")
        
        # Test to_dict
        data = session.to_dict()
        assert data["id"] == session.id
        assert len(data["context"]) == 1
        
        # Test to_json
        json_str = session.to_json()
        assert isinstance(json_str, str)
        assert session.id in json_str


class TestSessionManager:
    """Test SessionManager class"""
    
    def test_manager_create_session(self):
        """Test creating sessions"""
        manager = SessionManager()
        
        session1 = manager.create_session()
        session2 = manager.create_session()
        
        assert session1.id != session2.id
        assert len(manager.sessions) == 2
    
    def test_manager_get_session(self):
        """Test retrieving sessions"""
        manager = SessionManager()
        
        session = manager.create_session()
        retrieved = manager.get_session(session.id)
        
        assert retrieved is not None
        assert retrieved.id == session.id
    
    def test_manager_get_nonexistent_session(self):
        """Test retrieving non-existent session"""
        manager = SessionManager()
        
        retrieved = manager.get_session("nonexistent")
        assert retrieved is None


class TestShellTool:
    """Test ShellTool class"""
    
    def test_tool_schema(self):
        """Test tool schema generation"""
        schema = ShellTool.schema()
        
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "shell_execute"
        assert "command" in schema["function"]["parameters"]["properties"]
        assert "command" in schema["function"]["parameters"]["required"]
    
    def test_tool_execute_success(self):
        """Test successful command execution"""
        tool = ShellTool()
        
        result = tool.execute("echo 'Hello APRIL'")
        
        assert result.success is True
        assert "Hello APRIL" in result.output
        assert result.return_code == 0
    
    def test_tool_execute_failure(self):
        """Test failed command execution"""
        tool = ShellTool()
        
        result = tool.execute("nonexistentcmd123")
        
        assert result.success is False
        assert result.return_code != 0 or result.error != ""
    
    def test_tool_result_to_dict(self):
        """Test ToolResult serialization"""
        result = ToolResult(
            success=True,
            output="test output",
            error="",
            return_code=0
        )
        
        data = result.to_dict()
        
        assert data["success"] is True
        assert data["output"] == "test output"
        assert data["return_code"] == 0
    
    def test_tool_result_str(self):
        """Test ToolResult string representation"""
        # Success case
        result_success = ToolResult(success=True, output="output")
        assert str(result_success) == "output"
        
        # Error case
        result_error = ToolResult(success=False, output="", error="failed")
        assert str(result_error) == "Error: failed"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
