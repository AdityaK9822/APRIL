"""
APRIL CLI

Command-line interface for interacting with APRIL agent.
"""

import sys
import argparse
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import AgentConfig
from core.agent import AgentRuntime


def run_interactive(agent: AgentRuntime):
    """
    Run interactive REPL

    Args:
        agent: Agent runtime instance
    """
    print("\n" + "="*60)
    print("APRIL - An assistant with a body")
    print("="*60)
    print(f"Session: {agent.session.id}")
    print(f"Tools: {', '.join(agent.tool_map.keys())}")
    print("\nType your message and press Enter.")
    print("Type 'quit' or 'exit' to stop.")
    print("Type 'clear' to start a new session.")
    print("Type 'status' to see session info.")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("apr> ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ['quit', 'exit']:
                print("\nGoodbye!")
                break

            if user_input.lower() == 'clear':
                agent.session = agent.session.__class__()
                print(f"\nNew session: {agent.session.id}")
                continue

            if user_input.lower() == 'status':
                summary = agent.get_context_summary()
                print("\n" + "-"*40)
                print(f"Session ID: {summary['session_id']}")
                print(f"Messages: {summary['message_count']}")
                print(f"Created: {summary['created_at']}")
                print(f"Tools: {', '.join(summary['tools_available'])}")
                print("-"*40 + "\n")
                continue

            # Run agent
            print("\nThinking...\n")
            response = agent.run(user_input)
            print(f"APRIL: {response}\n")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'quit' to exit.")
            continue

        except Exception as e:
            print(f"\nError: {e}\n")
            continue


def run_single(agent: AgentRuntime, message: str) -> str:
    """
    Run a single message through the agent

    Args:
        agent: Agent runtime instance
        message: User message

    Returns:
        Agent response
    """
    return agent.run(message)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="APRIL - An assistant with a body"
    )

    parser.add_argument(
        "message",
        nargs="?",
        help="Single message to send (if omitted, runs interactive)"
    )

    parser.add_argument(
        "-c", "--config",
        default=".env",
        help="Path to config file (default: .env)"
    )

    parser.add_argument(
        "-m", "--model",
        help="Override model from config"
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=100,
        help="Maximum tool call iterations (default: 100)"
    )

    args = parser.parse_args()

    # Load configuration
    try:
        config = AgentConfig.from_env(args.config)

        # Override model if specified
        if args.model:
            config.model = args.model

        config.max_iterations = args.max_iterations

    except Exception as e:
        print(f"Error loading config: {e}")
        print(f"\nMake sure to create a .env file with:")
        print("  OPENAI_API_KEY=your_key")
        print("  OPENAI_API_BASE_URL=http://localhost:11434/v1")
        print("  OPENAI_MODEL=mistral")
        sys.exit(1)

    # Create agent
    agent = AgentRuntime(config)

    # Run
    if args.message:
        # Single message mode
        response = run_single(agent, args.message)
        print(response)
    else:
        # Interactive mode
        run_interactive(agent)


if __name__ == "__main__":
    main()
