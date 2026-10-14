"""
APRIL Shell Tool

Provides shell command execution capability for the agent.
"""

from dataclasses import dataclass
import subprocess
import shlex


@dataclass
class ToolResult:
    """
    Tool execution result

    Attributes:
        success: Whether execution succeeded
        output: Standard output
        error: Standard error
        return_code: Process return code
    """

    success: bool
    output: str
    error: str = ""
    return_code: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'return_code': self.return_code
        }

    def __str__(self) -> str:
        """String representation"""
        if self.success:
            return self.output
        else:
            return f"Error: {self.error}"


class ShellTool:
    """
    Execute shell commands

    Provides a safe interface to execute shell commands on the host system.

    Example:
        >>> tool = ShellTool()
        >>> result = tool.execute("ls -la")
        >>> print(result.output)
    """

    name = "shell_execute"
    description = "Execute a shell command on the host system"

    @staticmethod
    def schema() -> dict:
        """
        Get OpenAI function schema for this tool

        Returns:
            JSON schema for the tool
        """
        return {
            "type": "function",
            "function": {
                "name": "shell_execute",
                "description": "Execute a shell command on the host system. Use this for file operations, system commands, and other shell tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute (e.g., 'ls -la', 'cat file.txt', 'mkdir newdir')"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default: 30)",
                            "default": 30
                        }
                    },
                    "required": ["command"]
                }
            }
        }

    def execute(self, command: str, timeout: int = 30) -> ToolResult:
        """
        Execute a shell command

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds

        Returns:
            ToolResult with execution results

        Example:
            >>> tool = ShellTool()
            >>> result = tool.execute("echo hello")
            >>> assert result.success
            >>> assert "hello" in result.output
        """
        try:
            # Execute command
            result = subprocess.run(
                command,
                shell=True,  # Allow shell syntax
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                return_code=result.returncode
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds",
                return_code=-1
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Execution failed: {str(e)}",
                return_code=-1
            )


# Example usage and testing
if __name__ == "__main__":
    # Test basic execution
    tool = ShellTool()

    # Test: ls command
    result = tool.execute("ls")
    print(f"ls: success={result.success}")
    print(f"output:\n{result.output[:200]}")

    # Test: echo command
    result = tool.execute("echo 'Hello APRIL'")
    print(f"echo: {result.output.strip()}")

    # Test: invalid command
    result = tool.execute("nonexistentcmd123")
    print(f"invalid: success={result.success}, error={result.error}")

    # Test schema
    print(f"\nSchema:\n{tool.schema()}")
