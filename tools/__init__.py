"""APRIL Tools"""

from .shell import ShellTool, ToolResult

ALL_TOOLS = {
    "shell_execute": ShellTool()
}

def get_tool_schemas() -> list:
    """Get all tool schemas for OpenAI"""
    return [tool.schema() for tool in ALL_TOOLS.values()]

__all__ = ['ShellTool', 'ToolResult', 'ALL_TOOLS', 'get_tool_schemas']
