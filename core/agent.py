"""
APRIL Agent Runtime

The core agent loop: manage context, call LLM, process tool calls.
"""

from typing import List, Dict, Optional, Callable, AsyncGenerator, Any
import json
import threading
import os
import uuid
from openai import OpenAI, AsyncOpenAI

from .config import AgentConfig
from .session import Session
from .database import MemoryDatabase
from .memory_extractor import MemoryExtractor
from .logger import APRILLogger, get_logger
from .backend_logger import BackendLoggerBridge
from .events import get_event_bus, Event, LogEvent, ErrorEvent, StatusEvent
from tools.shell import ShellTool


def _harness_spec():
    """APRIL's HarnessSpec, cached; None only if the harness engine fails to import."""
    global _HARNESS_SPEC_CACHE
    if _HARNESS_SPEC_CACHE is None:
        from .harness.april_spec import APRIL_SPEC

        _HARNESS_SPEC_CACHE = APRIL_SPEC
    return _HARNESS_SPEC_CACHE


_HARNESS_SPEC_CACHE = None


class AgentRuntime:
    @property
    def spec(self):
        try:
            return _harness_spec()
        except Exception:
            return None

    @property
    def substrate(self):
        """APRIL's own substrate: the editable file surface of a deployed harness."""
        from .substrate.april import APRIL_SUBSTRATE

        return APRIL_SUBSTRATE

    def tasks(self, split="all"):
        return []

    def domain_of(self, task_id):
        return "default"

    def task_prompt(self, task_id):
        return str(task_id)

    def task_files(self, task_id):
        return None

    def _runs_root(self):
        """One runs root for adapter runs and the schedule's work dirs: the
        `APRIL_RUNS_ROOT` env override when set, else `spec.runs_root`."""
        from pathlib import Path

        env = os.environ.get("APRIL_RUNS_ROOT", "").strip()
        spec = self.spec
        return (
            Path(env) if env
            else Path(getattr(spec, "runs_root", Path("runs")) if spec else Path("runs"))
        )

    def _executor_mode(self):
        """`dry` (default) is the offline structural executor; `live` arrives in P1
        with the zcode substrate."""
        return str(os.environ.get("APRIL_EXECUTOR", "dry")).strip().lower() or "dry"

    def execute(self, task_id, harness_dir=None, run_id=None, timeout=None):
        """One rollout. `dry` writes a structural run dir under the runs root: no
        model, no network, no device. Marked `.adapt_complete` by the recursion layer.
        """
        from pathlib import Path

        if self._executor_mode() != "dry":
            raise NotImplementedError(
                f"APRIL_EXECUTOR={self._executor_mode()!r}: the live executor hands "
                f"rollouts to the zcode substrate, which lands in P1"
            )
        root = self._runs_root()
        parts = [p for p in str(run_id or task_id).replace("\\", "/").split("/") if p not in ("", ".")]
        if not parts or ".." in parts:
            raise ValueError(f"run_id {run_id!r} must name a run dir under the runs root")
        run_dir = root.joinpath(*parts)
        run_dir.mkdir(parents=True, exist_ok=True)

        from .harness import runmark, tree as harness_tree

        surface = self.substrate.surface()
        if harness_dir is not None:
            committed = harness_tree.read_tree(surface, Path(harness_dir))
            harness_line = (
                f"harness: {len(committed)} file(s) on the surface "
                f"[{runmark.fingerprint(Path(harness_dir))}]: "
                + (", ".join(sorted(committed)) or "(none)")
            )
        else:
            committed = None
            harness_line = "harness: base (inherited)"
        trajectory = (
            "APRIL dry executor: structural rollout (no model attached, no network).\n"
            f"task_id: {task_id}\n"
            f"run_id: {run_id or task_id}\n"
            f"{harness_line}\n"
        )
        (run_dir / "trajectory.txt").write_text(trajectory, encoding="utf-8")

        deliverables = run_dir / "deliverables"
        deliverables.mkdir(parents=True, exist_ok=True)
        deliverable = (
            f"# {task_id}\n\n{self.task_prompt(task_id)}\n\n{harness_line}\n"
        )
        (deliverables / "deliverable.md").write_text(deliverable, encoding="utf-8")
        return run_dir

    def delivered(self, run_dir):
        from pathlib import Path

        return (Path(run_dir) / "deliverables" / "deliverable.md").is_file()

    def trajectory(self, run_dir, *, obs_trunc=None):
        from pathlib import Path

        limit = int(obs_trunc) if obs_trunc else 50_000
        try:
            body = (Path(run_dir) / "trajectory.txt").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return body[:limit] + (f"\n... [trajectory clipped to {limit} chars]" if len(body) > limit else "")

    def deliverable_files(self, run_dir):
        from pathlib import Path

        d = Path(run_dir) / "deliverables"
        if not d.is_dir():
            return {}
        return {p.name: str(p) for p in sorted(d.glob("*")) if p.is_file()}

    def deliverable_text(self, run_dir):
        from pathlib import Path

        p = Path(run_dir) / "deliverables" / "deliverable.md"
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""

    def base_harness(self):
        """The shipped base tree: a minimal 3-file always-on harness for APRIL itself."""
        from pathlib import Path

        return Path(__file__).resolve().parent / "harness" / "basetree" / "april"

    def validate_tree(self, tree):
        from core.components.base import default_registry
        from .harness import tree as harness_tree

        spec = self.spec
        harness_tree.validate(
            self.substrate.surface(),
            tree,
            allow_subagents=getattr(spec, "allow_subagents", False) if spec else False,
            reserved_scripts=harness_tree.RESERVED_SCRIPTS
            | (getattr(spec, "reserved_scripts", frozenset()) if spec else frozenset()),
        )
        problems = default_registry().validate_all(tree)
        if problems:
            raise ValueError(" | ".join(problems))

    def score(self, run_dir, task_id):
        return None


    """
    The core agent runtime
    
    Manages conversation with an LLM, processes tool calls, and
    maintains session state.
    """
    
    def __init__(self, config: AgentConfig, tools: Optional[List] = None):
        """
        Initialize agent runtime
        
        Args:
            config: Agent configuration
            tools: List of tool instances (default: ShellTool)
        """
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url
        )
        self.async_client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url
        )
        
        # Initialize memory system
        self.db = None
        self.extractor = None
        if config.memory_enabled:
            try:
                self.db = MemoryDatabase(config.memory_db_path)
                self.extractor = MemoryExtractor(model=config.memory_extraction_model)
                self.extractor._client = self.client
            except Exception as e:
                self._emit_error("memory_init", str(e))
        
        # Create session with database
        self.session = Session(db=self.db)
        
        # Initialize tools
        if tools is None:
            self.tools = [ShellTool()]
        else:
            self.tools = tools
        
        # Build tool schema list for API
        self.tool_schemas = [t.schema() for t in self.tools]
        
        # Build tool name -> instance map
        self.tool_map = {t.name: t for t in self.tools}
        
        # Event bus
        self._event_bus = get_event_bus()

        # P5 runtime persona: APRIL_PERSONA=<id> loads the adopted (or committed)
        # persona — c1 into the system message head, c2 into the permission
        # layer, derive().temperature into sampling. An unknown persona fails
        # here, before any request. Spec: docs/spec/persona-dimension.md
        self.persona_boot = None
        self.persona_guard = None
        from .ade import apply_to_runtime as _persona_boot_apply

        self.persona_boot = _persona_boot_apply(self)

    def _emit_error(self, error_type: str, message: str, details: Dict = None):
        """Emit error event."""
        self._event_bus.emit(ErrorEvent(error_type=error_type, message=message, details=details))
    
    def _emit_status(self, status: str, metadata: Dict = None):
        """Emit status event."""
        self._event_bus.emit(StatusEvent(status=status, metadata=metadata or {}))
    
    def _process_tool_calls(self, tool_calls: List) -> List[Dict]:
        """
        Process tool calls from LLM response.
        
        Args:
            tool_calls: List of tool call objects from API
            
        Returns:
            List of tool result messages
        """
        results = []
        
        for call in tool_calls:
            tool_name = call.function.name
            tool_args = json.loads(call.function.arguments)
            
            # P5 permission layer: a booted persona's c2 rules decide whether a
            # shell command runs at all. A blocked command becomes the tool
            # result — the agent must surface the plan, get the approval marker
            # into the command, and retry; the command is never executed.
            guard = getattr(self, 'persona_guard', None)
            if guard is not None and tool_name == 'shell_execute':
                allowed, reason = guard.check(tool_args.get('command') or '')
                if not allowed:
                    results.append({
                        'tool_call_id': call.id,
                        'role': 'tool',
                        'name': tool_name,
                        'content': f'[persona-guard] {reason}'
                    })
                    continue
            
            if tool_name not in self.tool_map:
                results.append({
                    'tool_call_id': call.id,
                    'role': 'tool',
                    'name': tool_name,
                    'content': f"Error: Unknown tool '{tool_name}'"
                })
                continue
            
            tool = self.tool_map[tool_name]
            
            try:
                if tool_name == 'shell_execute':
                    result = tool.execute(
                        command=tool_args.get('command'),
                        timeout=tool_args.get('timeout', 30)
                    )
                else:
                    result = tool.execute(**tool_args)
                
                results.append({
                    'tool_call_id': call.id,
                    'role': 'tool',
                    'name': tool_name,
                    'content': str(result)
                })
            
            except Exception as e:
                results.append({
                    'tool_call_id': call.id,
                    'role': 'tool',
                    'name': tool_name,
                    'content': f'Error executing tool: {str(e)}'
                })
        
        return results
    
    def run(self, user_input: str, max_iterations: Optional[int] = None) -> str:
        """
        Run the agent loop.
        
        Args:
            user_input: User message
            max_iterations: Maximum tool call iterations (default: from config)
            
        Returns:
            Final response string
        """
        if max_iterations is None:
            max_iterations = self.config.max_iterations
        
        # Log user message
        truncated = user_input[:100] + "..." if len(user_input) > 100 else user_input
        self._event_bus.emit_log(level="INFO", source="user", message=truncated)
        
        # Augment context with relevant memories
        self._augment_context_with_memories(user_input)
        
        # Save user message to database
        self._save_conversation_turn('user', user_input)
        
        # Add user message to context
        self.session.add_message('user', user_input)
        
        # Agent loop
        iterations = 0
        while iterations < max_iterations:
            # Log LLM request
            self._event_bus.emit_log(level="INFO", source="llm", message=f"Request to {self.config.model} ({len(self.session.context)} messages)")
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.session.context,
                tools=self.tool_schemas,
                temperature=self.config.temperature
            )
            
            message = response.choices[0].message
            
            # Log LLM response
            self._event_bus.emit_log(level="INFO", source="llm", message=f"Response from {self.config.model}")
            
            # Check if we need to process tool calls
            if message.tool_calls:
                # Add assistant message with tool calls to context
                self.session.context.append({
                    'role': 'assistant',
                    'content': message.content,
                    'tool_calls': [
                        {
                            'id': tc.id,
                            'type': 'function',
                            'function': {
                                'name': tc.function.name,
                                'arguments': tc.function.arguments
                            }
                        } for tc in message.tool_calls
                    ]
                })
                
                # Process tool calls
                tool_results = self._process_tool_calls(message.tool_calls)
                
                # Log tool executions
                for result in tool_results:
                    tool_name = result.get('name', 'unknown')
                    self._event_bus.emit_log(level="INFO", source="tool", message=f"Calling: {tool_name}")
                
                # Add tool results to context
                for result in tool_results:
                    self.session.context.append(result)
                
                iterations += 1
                continue
            
            # No tool calls - we have a final response
            self.session.add_message('assistant', message.content or '')
            final_response = message.content or ''
            
            # Save assistant response to database and trigger extraction
            if final_response:
                self._save_conversation_turn('assistant', final_response)
                self._extract_and_store_memories()
            
            # Log agent response
            self._event_bus.emit_log(level="INFO", source="agent", message=final_response[:100] + "..." if len(final_response) > 100 else final_response)
            
            return final_response
        
        # Max iterations reached
        return f'Reached maximum iterations ({max_iterations}) without completing. Last context length: {len(self.session.context)} messages.'
    
    def _save_conversation_turn(self, role: str, content: str):
        """
        Save conversation turn to database
        
        Args:
            role: Message role
            content: Message content
        """
        if self.db:
            self.db.save_message(self.session.id, role, content)
    
    def _augment_context_with_memories(self, user_input: str):
        """
        Add relevant memories to context
        
        Args:
            user_input: User's input message
        """
        if not self.db:
            return
        
        # Search for relevant memories
        memories = self.session.get_relevant_memories(user_input, limit=self.config.memory_max_context)
        
        if memories:
            # Format memories as context
            memory_text = "\n\nRelevant previous knowledge from past conversations:\n"
            for mem in memories:
                mem_type = mem['memory_type']
                text = mem['content'].get('text', '')
                memory_text += f"- [{mem_type.upper()}] {text}\n"
            
            # Add to context as system message (only if not already added)
            if not any(m.get('role') == 'system' and 'Relevant previous knowledge' in m.get('content', '') for m in self.session.context[-5:]):
                self.session.add_message('system', memory_text)
    
    def _extract_and_store_memories(self):
        """
        Extract memories from conversation and store
        
        Runs synchronously after agent response.
        Logs only when APRIL_LOG_LEVEL is DEBUG or lower.
        """
        if not self.db or not self.extractor or not self.session.id:
            return
        
        try:
            # Get unprocessed messages for this session
            messages = self.db.get_unprocessed_messages(self.session.id)
            
            if not messages:
                return
            
            self._event_bus.emit_log(level="DEBUG", source="memory", message=f"Extracting memories from {len(messages)} messages")
            
            memories = self.extractor.extract(messages, client=self.client)
            
            self._event_bus.emit_log(level="DEBUG", source="memory", message=f"Extracted {len(memories)} memories")
            
            # Store memories
            for memory in memories:
                self.db.save_memory(
                    session_id=self.session.id,
                    memory_type=memory['type'],
                    content=memory['content'],
                    confidence=memory['confidence'],
                    tags=memory['tags'],
                    source_message_ids=[m['id'] for m in messages]
                )
            
            # Mark messages as processed
            message_ids = [m['id'] for m in messages]
            self.db.mark_processed(message_ids)
            
            self._event_bus.emit_log(level="DEBUG", source="memory", message=f"Marked {len(message_ids)} messages as processed")
            
        except Exception as e:
            self._emit_error("memory_extraction", str(e))
    
    def run_conversation(self, user_messages: List[str]) -> str:
        """
        Run multiple messages through the agent
        
        Args:
            user_messages: List of user messages
            
        Returns:
            Final response after all messages
        """
        response = ''
        for msg in user_messages:
            response = self.run(msg)
        return response
    
    def clear_context(self) -> None:
        """Clear conversation context."""
        self.session.clear()
        self._event_bus.emit_log(level="INFO", source="session", message="Context cleared")
    
    def get_context_summary(self) -> Dict:
        """
        Get summary of current context
        
        Returns:
            Dictionary with context stats
        """
        return {
            'session_id': self.session.id,
            'message_count': len(self.session.context),
            'created_at': self.session.created_at.isoformat(),
            'tools_available': list(self.tool_map.keys())
        }
    
    # Async streaming methods
    async def run_streaming(self, user_input: str, max_iterations: Optional[int] = None) -> AsyncGenerator[str, None]:
        """
        Async streaming version of run.

        Yields tokens as they arrive from the model. Uses the async OpenAI
        client so HTTP streaming does not block the event loop.
        """
        if max_iterations is None:
            max_iterations = self.config.max_iterations

        msg_id = self._event_bus.emit_message_start(is_assistant=True)
        self._event_bus.emit_status("thinking", {"user_input": user_input[:50]})

        truncated = user_input[:100] + "..." if len(user_input) > 100 else user_input
        self._event_bus.emit_log(level="INFO", source="user", message=truncated)

        self._augment_context_with_memories(user_input)
        self._save_conversation_turn('user', user_input)
        self.session.add_message('user', user_input)

        iterations = 0
        while iterations < max_iterations:
            self._event_bus.emit_status("streaming" if iterations == 0 else "running_tool")
            self._event_bus.emit_log(
                level="INFO",
                source="llm",
                message=f"Request to {self.config.model} ({len(self.session.context)} messages)",
            )

            accumulated_content = ""
            accumulated_tools = {}
            finish_reason = None

            try:
                stream = await self.async_client.chat.completions.create(
                    model=self.config.model,
                    messages=self.session.context,
                    tools=self.tool_schemas,
                    temperature=self.config.temperature,
                    stream=True,
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    finish_reason = choice.finish_reason or finish_reason
                    delta = choice.delta
                    if getattr(delta, "content", None):
                        token = delta.content
                        accumulated_content += token
                        yield token
                        self._event_bus.emit_message_delta(token, is_assistant=True, is_complete=False)
                    if getattr(delta, "tool_calls", None):
                        for tc in delta.tool_calls:
                            entry = accumulated_tools.setdefault(tc.index, {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": "",
                            })
                            if tc.id:
                                entry["id"] = tc.id
                            if getattr(tc.function, "name", None):
                                entry["name"] += tc.function.name
                            if getattr(tc.function, "arguments", None):
                                entry["arguments"] += tc.function.arguments
            except Exception as exc:
                self._event_bus.emit_error("llm_stream", str(exc))
                self._event_bus.emit_status("idle")
                yield f"Error: {exc}"
                return

            self._event_bus.emit_message_delta("", is_assistant=True, is_complete=True)

            tool_calls = []
            for _index, entry in sorted(accumulated_tools.items()):
                if entry["name"]:
                    tool_calls.append(entry)

            if tool_calls:
                pseudo_calls = []
                for entry in tool_calls:
                    tc = type("ToolCall", (), {})()
                    tc.id = entry["id"] or str(uuid.uuid4())[:8]
                    tc.function = type("Function", (), {})()
                    tc.function.name = entry["name"]
                    tc.function.arguments = entry["arguments"] or "{}"
                    pseudo_calls.append(tc)

                self._event_bus.emit_status("running_tool", {"tool_calls": len(pseudo_calls)})
                for tc in pseudo_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    self._event_bus.emit_tool_call_start(tc.function.name, args, tc.id)

                tool_results = self._process_tool_calls(pseudo_calls)

                for result in tool_results:
                    tool_name = result.get("name", "unknown")
                    self._event_bus.emit_tool_call_output(
                        result.get("tool_call_id", ""),
                        str(result.get("content", ""))[:500],
                    )
                    self._event_bus.emit_tool_call_done(
                        tool_name,
                        str(result.get("content", "")),
                        result.get("tool_call_id", ""),
                        True,
                    )

                self.session.context.append({
                    "role": "assistant",
                    "content": accumulated_content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in pseudo_calls
                    ],
                })
                for result in tool_results:
                    self.session.context.append(result)

                iterations += 1
                continue

            self.session.add_message("assistant", accumulated_content)
            if accumulated_content:
                self._save_conversation_turn("assistant", accumulated_content)
                self._extract_and_store_memories()

            self._event_bus.emit_message_done(msg_id, accumulated_content, is_assistant=True)
            self._event_bus.emit_status("idle")
            return

        self._event_bus.emit_status("idle")
        yield f"Reached maximum iterations ({max_iterations}) without completing."


    # Thread-safe cancellation support
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._cancellation_tokens = {}
    
    def request_cancel(self, session_id: str = None):
        """Request cancellation of current operation."""
        if session_id is None:
            session_id = self.session.id
        self._cancellation_tokens[session_id] = True
    
    def is_cancellation_requested(self, session_id: str = None) -> bool:
        """Check if cancellation was requested."""
        if session_id is None:
            session_id = self.session.id
        return self._cancellation_tokens.get(session_id, False)
    
    def clear_cancellation(self, session_id: str = None):
        """Clear cancellation flag."""
        if session_id is None:
            session_id = self.session.id
        self._cancellation_tokens.pop(session_id, None)


# Offline self-check: the P0 acceptance path. No model, no network, no device.
if __name__ == '__main__':
    import asyncio
    import json
    import shutil
    import tempfile
    from pathlib import Path

    from core.components.base import default_registry
    from core.harness import tree as harness_tree
    from core.harness import Harness
    from core.harness import config as harness_config
    from core.harness.proposer import Proposer, ProposerError
    from core.harness.spec import resolve_channel_model

    checks = []

    # 1. The config surface is complete and the broken channel is never the fallback.
    assert harness_config.BUN, "config.BUN must resolve a launcher binary"
    assert isinstance(harness_config.OPENCODE_DIR, str), "config.OPENCODE_DIR stays a raw string"
    assert harness_config.DEFAULT_PROPOSER_CHANNEL == "claude_cli"
    checks.append("config surface: BUN / OPENCODE_DIR / DEFAULT_PROPOSER_CHANNEL")

    # 2. The opencode channel fails closed as a ProposerError, never an AttributeError.
    prop = Proposer(spec=resolve_channel_model(kind="opencode", model="openai/gpt-4o-mini"))
    try:
        prop.call("mission", None, "demo.channel")
        raise AssertionError("the opencode channel must fail without a checkout")
    except ProposerError:
        pass
    checks.append("opencode channel fails as ProposerError")

    # 3. The shipped base tree survives tree.validate + ComponentRegistry.validate_all.
    config = AgentConfig.from_env()
    agent = AgentRuntime(config)
    surface = agent.substrate.surface()
    base_tree = harness_tree.read_tree(surface, agent.base_harness())
    census = harness_tree.validate(surface, base_tree, allow_subagents=agent.spec.allow_subagents)
    problems = default_registry().validate_all(base_tree)
    assert not problems, problems
    agent.validate_tree(base_tree)
    checks.append(f"base tree validates: {census}")

    # 4. A dry rollout writes a run dir with a trajectory and a delivered deliverable.
    rd = agent.execute("demo-0001", None, "demo/demo-0001/base1")
    assert agent.delivered(rd), "dry rollout must deliver"
    assert agent.trajectory(rd).strip() and agent.deliverable_text(rd).strip()
    checks.append(f"dry rollout: {Path(rd)}")

    # 5. End to end run_task, dry: ledger identity exact, markers carry a real fingerprint.
    tmp = Path(tempfile.mkdtemp(prefix="april-demo-runs-"))
    old_executor = os.environ.get("APRIL_EXECUTOR")
    old_root = os.environ.get("APRIL_RUNS_ROOT")
    os.environ.update({"APRIL_EXECUTOR": "dry", "APRIL_RUNS_ROOT": str(tmp / "runs")})
    try:
        res = asyncio.run(
            Harness(agent, runs_root=tmp / "runs").run_task("demo-0001", k=1)
        )
    finally:
        if old_executor is None:
            os.environ.pop("APRIL_EXECUTOR", None)
        else:
            os.environ["APRIL_EXECUTOR"] = old_executor
        if old_root is None:
            os.environ.pop("APRIL_RUNS_ROOT", None)
        else:
            os.environ["APRIL_RUNS_ROOT"] = old_root
    assert res.status == "ok", (res.status, res.errors)
    for mode, rec in res.modes.items():
        led = rec["ledger"]
        assert led["R"] == led["expected_R"] == 4, (mode, led)
        assert led["P"] == led["expected_P"] == 3, (mode, led)
        assert led["rollouts"] == ["base1", "inv1", "dom1", ("agg1" if mode == "agg" else "c1")]
    marks = list((tmp / "runs").rglob(".adapt_complete"))
    assert marks, "runmark.mark_complete never fired"
    for m in marks:
        payload = json.loads(m.read_text())
        assert payload["harness"] not in ("absent", "", "base"), payload
        assert payload["version"] == 1, payload
    checks.append(f"end-to-end run_task dry: ledgers R=4k/P=3k, {len(marks)} markers")
    shutil.rmtree(tmp, ignore_errors=True)

    # 6. P1: the zcode substrate — surface facts, authored mini-tasks and the gate matrix.
    from core.harness import prompts as harness_prompts
    from core.harness.zcode_adapter import ZcodeAdapter
    from core.substrate.zcode import (
        ZCODE_HOOK_EVENTS,
        ZCODE_SURFACE as zsurface,
        memory_root_for,
    )
    import copy as _copy

    assert ZCODE_HOOK_EVENTS == frozenset(
        {
            "SessionStart",
            "UserPromptSubmit",
            "PreToolUse",
            "PermissionRequest",
            "PostToolUse",
            "PostToolUseFailure",
            "Stop",
        }
    ), ZCODE_HOOK_EVENTS
    assert zsurface.always_on == ("AGENTS.md",) and zsurface.hooks_file == ".zcode/config.json"
    assert zsurface.hooks_shape == "nested" and set(zsurface.hook_types) == {"command", "process"}
    assert zsurface.subagent_path == ".zcode/agents/{name}.md"
    assert zsurface.plugin_manifest == ".zcode/plugins/{name}/.zcode-plugin/plugin.json"
    assert zsurface.memory_file == "MEMORY.md" and zsurface.memory_max == 40_000
    zst = harness_prompts._st(zsurface)  # noqa: SLF001 — the registry is the check
    assert zst.surface_md.strip() and zst.tts_surface.strip()
    checks.append("zcode surface facts + prompt surface registered")

    zadapter = ZcodeAdapter()
    ztasks = zadapter.tasks()
    assert ztasks == [
        "device-control/read-write",
        "mcp/wiring",
        "network/capability-doc",
    ], ztasks
    assert len({zadapter.domain_of(t) for t in ztasks}) == len(ztasks)
    for t in ztasks:
        zps = zadapter.prompts_for(t)  # HarnessPrompts constructor enforces the slot rules
        assert zps.work.strip() and zps.inv_levers.strip() and zps.yardstick.strip()
        ztd = zadapter._task(t)  # noqa: SLF001 — the forced-deliverable contract needs it
        assert ztd.deliverable.startswith("deliverables/") and "/" not in ztd.deliverable[13:], (
            ztd.deliverable
        )
        for fname, _content in ztd.fixtures:
            assert not fname.startswith("deliverables/"), (t, fname)
    assert zadapter.score("irrelevant-run-dir", ztasks[0]) is None
    checks.append(f"authored mini-tasks: {len(ztasks)} tasks, forced deliverables, no grader vocabulary")

    # The gate matrix: one representative failure per P1-1.3 family (every family's
    # full variant list is proven in the design notes; these are the load-bearing ones).
    zg_ok = {
        "AGENTS.md": (
            "# APRIL (zcode)\n\nWhen the relay needs pairing, use the `relay-pair` "
            "skill: pair a Tasmota relay to the local MQTT broker.\n"
        ),
        ".agents/skills/relay-pair/SKILL.md": (
            "---\nname: relay-pair\n"
            "description: Pair a Tasmota relay to the local MQTT broker.\n---\nbody\n"
        ),
        ".zcode/agents/census-reader.md": (
            "---\ndescription: reads device census files\n---\nbody\n"
        ),
        ".zcode/config.json": json.dumps(
            {
                "hooks": {
                    "enabled": True,
                    "events": {
                        "PreToolUse": [
                            {"hooks": [{"type": "command", "command": "echo", "args": ["x"]}]}
                        ]
                    },
                }
            }
        ),
        ".zcode/plugins/relay-audit/.zcode-plugin/plugin.json": json.dumps(
            {"name": "relay-audit", "version": "0.1.0", "description": "Audit relay changes."}
        ),
        "scripts/spot_check.py": "print('ok')\n",
        "MEMORY.md": "# seed\n\nrelay broker mqtt.local\n",
    }
    ztree_ok = dict(zg_ok)
    harness_tree.validate(zsurface, ztree_ok, allow_subagents=True)

    def zmod(**over: str) -> dict[str, str]:
        bad = dict(zg_ok)
        bad.update(over)
        return bad

    zgates = [
        (
            "skill name mismatch",
            zmod(
                **{
                    ".agents/skills/relay-pair/SKILL.md": (
                        "---\nname: other\ndescription: x\n---\nbody\n"
                    )
                }
            ),
            "matching its directory",
        ),
        (
            "hooks not enabled",
            zmod(
                **{
                    ".zcode/config.json": json.dumps(
                        {
                            "hooks": {
                                "enabled": False,
                                "events": {
                                    "Stop": [
                                        {"hooks": [{"type": "command", "command": "x"}]}
                                    ]
                                },
                            }
                        }
                    )
                }
            ),
            '"enabled": true',
        ),
        (
            "hooks wrong type",
            zmod(
                **{
                    ".zcode/config.json": json.dumps(
                        {
                            "hooks": {
                                "enabled": True,
                                "events": {
                                    "Stop": [
                                        {"hooks": [{"type": "shell", "command": "x"}]}
                                    ]
                                },
                            }
                        }
                    )
                }
            ),
            "type must be one of command, process",
        ),
        (
            "hooks unknown event",
            zmod(
                **{
                    ".zcode/config.json": json.dumps(
                        {
                            "hooks": {
                                "enabled": True,
                                "events": {
                                    "PrePrompt": [
                                        {"hooks": [{"type": "command", "command": "x"}]}
                                    ]
                                },
                            }
                        }
                    )
                }
            ),
            "unknown event 'PrePrompt'",
        ),
        (
            "plugin orphan content",
            {
                **{k: v for k, v in zg_ok.items() if not k.startswith(".zcode/plugins/")},
                ".zcode/plugins/relay-audit/tool.md": "no manifest loads none",
            },
            "has no manifest",
        ),
        (
            "script syntax",
            zmod(**{"scripts/spot_check.py": "def ( break\n"}),
            "does not compile",
        ),
        (
            "always-on over cap",
            zmod(**{"AGENTS.md": "x" * (zsurface.always_on_max + 1)}),
            "over the 60000 cap",
        ),
        (
            "memory over cap",
            zmod(**{"MEMORY.md": "y" * (zsurface.memory_max + 1)}),
            "over the 40000 cap",
        ),
    ]
    for label, bad_tree, needle in zgates:
        try:
            harness_tree.validate(zsurface, bad_tree, allow_subagents=True)
            raise AssertionError(f"zcode gate {label!r} passed but must fail")
        except ValueError as exc:
            assert needle in str(exc), (label, str(exc))
    checks.append(f"zcode gate matrix: {len(zgates)} representatives fail as designed")

    # 7. P1 rollout through the process-boundary stub, with a memory-bearing harness.
    old_zbin = os.environ.get("APRIL_ZCODE_BIN")
    old_zroot = os.environ.get("APRIL_RUNS_ROOT")
    zstub = (Path.cwd() / "core/harness/zcode_cli_stub.py").resolve()
    ztmp = Path(tempfile.mkdtemp(prefix="april-zcode-checks-"))
    os.environ.update({"APRIL_ZCODE_BIN": str(zstub), "APRIL_RUNS_ROOT": str(ztmp / "runs")})
    try:
        ztree = _copy.deepcopy(zg_ok)
        ztree[".agents/skills/relay-pair/scripts/pair_check.py"] = "print('pair-check')\n"
        ztree[".zcode/plugins/relay-audit/README.md"] = "audit notes\n"
        zhdir = harness_tree.write_tree(zsurface, ztree, ztmp / "harnesses" / "zc-gate")
        zadapter.validate_tree(harness_tree.read_tree(zsurface, zhdir))
        zrd = zadapter.execute("device-control/read-write", zhdir, "zcheck/roll1")
        assert zadapter.delivered(zrd), "zcode stub rollout must deliver"
        assert "Device Write Plan" in zadapter.deliverable_text(zrd)
        zws = Path(zrd) / "workspace"
        assert (zws / "AGENTS.md").is_file() and (zws / "input/devices.json").is_file()
        zmem = memory_root_for(zws, Path(zrd) / "zcode_home")
        assert (zmem / "MEMORY.md").read_text() == ztree["MEMORY.md"], zmem
        ztraj = (Path(zrd) / "trajectory.txt").read_text()
        assert f"memory seed: staged at {zmem.relative_to(Path(zrd))}" in ztraj, ztraj[:400]
        assert "harness: 9 file(s) on the surface" in ztraj, ztraj[:400]
        checks.append(f"zcode stub rollout + memory seed: {Path(zrd).relative_to(ztmp)}")

        # 8. P1 end to end: run_task on the zcode adapter, offline, ledger identity exact.
        zres = asyncio.run(
            Harness(zadapter, runs_root=ztmp / "runs").run_task(
                "device-control/read-write", k=1
            )
        )
        assert zres.status == "ok", (zres.status, zres.errors)
        for zmode, zrec in zres.modes.items():
            zled = zrec["ledger"]
            assert zled["R"] == zled["expected_R"] == 4, (zmode, zled)
            assert zled["P"] == zled["expected_P"] == 3, (zmode, zled)
            assert zled["rollouts"] == [
                "base1",
                "inv1",
                "dom1",
                ("agg1" if zmode == "agg" else "c1"),
            ], (zmode, zled["rollouts"])
            assert zrec["finals"] and zrec["ok"], (zmode, zrec["finals"], zrec["errors"])
        zmarks = list((ztmp / "runs").rglob(".adapt_complete"))
        assert len(zmarks) == 6, len(zmarks)
        for zm in zmarks:
            assert zadapter.delivered(zm.parent), zm
            zp = json.loads(zm.read_text())
            assert zp["harness"] not in ("absent", "", "base"), zp
            assert zp["version"] == 1, zp
        checks.append(
            f"zcode run_task offline: ledgers R=4k/P=3k, {len(zmarks)} markers, deliverables hold"
        )
    finally:
        if old_zbin is None:
            os.environ.pop("APRIL_ZCODE_BIN", None)
        else:
            os.environ["APRIL_ZCODE_BIN"] = old_zbin
        if old_zroot is None:
            os.environ.pop("APRIL_RUNS_ROOT", None)
        else:
            os.environ["APRIL_RUNS_ROOT"] = old_zroot
        shutil.rmtree(ztmp, ignore_errors=True)

    # 9. The process-boundary invariant: the ZCode checkout is never touched.
    zcode_repo = Path.cwd() / "ZCode"
    if zcode_repo.is_dir():
        import subprocess as _sp

        porcelain = _sp.run(
            ["git", "-C", str(zcode_repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert porcelain.returncode == 0, porcelain
        assert porcelain.stdout.strip() == "", porcelain.stdout
        checks.append("ZCode checkout byte-for-byte untouched (porcelain empty)")

    # 10. P2: the personality kernel — demo() runs every pin, including the live
    # byte-equal cross-check against personality.ts through bun.
    from core.harness import personality
    from core.harness.ledger import expected_rollouts, expected_sessions
    from core.harness.spec import resolve_prompts

    personality.demo()  # raises on any pin failure; includes the bun cross-check
    april_profile = personality.load_profile("april")
    d_april = personality.derive(april_profile)
    assert (d_april.proactivity, d_april.humor, d_april.temperature) == (67, 43, 0.69), d_april
    checks.append(
        "personality kernel demo: compile_persona/derive/similarity pins green "
        "(JS Math.round fidelity + bun cross-check)"
    )

    # 11. P2 constraint mode: profile-backed missions carry the compiled persona
    # clauses; persona-free adapters render none; the selector stays blind.
    t0 = ztasks[0]
    zpersona = ZcodeAdapter(profile="april")
    assert zpersona.spec.profile == "april" and ZcodeAdapter().spec.profile == ""
    zres_p = resolve_prompts(zpersona, t0)
    assert zres_p.persona_guidance.startswith("You are APRIL."), zres_p.persona_guidance[:40]
    p_mission = harness_prompts.propose(zres_p, "INV", zsurface)
    assert "You are APRIL." in p_mission and "## persona:" in p_mission, "mission lost the persona"
    assert f"capped at {harness_prompts.PERSONA_CLAUSE_CAP}" in p_mission, "marker contract line missing"
    assert "You are APRIL." in harness_prompts.aggregate(zres_p, zsurface, k=1)
    assert "You are APRIL." in harness_prompts.compose_round(zres_p, zsurface, t=1, k=1)
    assert "You are APRIL." not in harness_prompts.select(zres_p, n=2), "selector saw persona"
    zfree = resolve_prompts(ZcodeAdapter(), t0)
    assert zfree.persona_guidance == ""
    assert "You are APRIL." not in harness_prompts.propose(zfree, "INV", zsurface)
    low_persona = zres_p.persona_guidance.lower()
    from core.harness.spec import HARNESS_PROMPT_BAD_WORDS

    assert not any(b in low_persona for b in HARNESS_PROMPT_BAD_WORDS), "persona tripped the slot filter"
    checks.append(
        "constraint mode: profile-backed missions carry compiled persona clauses; "
        "free adapter renders none; selector blind; slot filter passes"
    )

    # 12. P2: PERSONA_CLAUSE_CAP — tagged persona sections in always-on files are
    # capped; over-cap trees are rejected through _accept_tree (retry path), and a
    # legal in-cap persona section validates.
    from core.harness import recursion

    assert recursion.STAGE_ATTEMPTS == 2, recursion.STAGE_ATTEMPTS
    zcensus = harness_tree.validate(zsurface, zg_ok, allow_subagents=True)
    assert zcensus["persona_clause_chars"] == 0, zcensus
    zps_tree = dict(zg_ok)
    zps_tree["AGENTS.md"] = zg_ok["AGENTS.md"] + "\n## persona: voice\nStay stead when relays flap.\n"
    pcensus = harness_tree.validate(zsurface, zps_tree, allow_subagents=True)
    assert 0 < pcensus["persona_clause_chars"] <= harness_tree.PERSONA_CLAUSE_CAP, pcensus
    over = dict(zg_ok)
    over["AGENTS.md"] = zg_ok["AGENTS.md"] + "\n## persona: voice\n" + ("x" * (harness_tree.PERSONA_CLAUSE_CAP + 1))
    _kept, cap_err = recursion._accept_tree(
        zsurface, zpersona, over, dict(zg_ok), "p2-cap-gate"
    )
    assert "always-on persona cap" in cap_err and str(harness_tree.PERSONA_CLAUSE_CAP) in cap_err, cap_err
    _kept, ok_err = recursion._accept_tree(
        zsurface, zpersona, dict(zps_tree), dict(zg_ok), "p2-cap-in"
    )
    assert ok_err == "", ok_err
    checks.append(
        f"persona cap: in-cap `## persona:` section validates; over-cap tree rejected "
        f"through _accept_tree (retry/fallback path, STAGE_ATTEMPTS={recursion.STAGE_ATTEMPTS})"
    )

    # 13. P2: ledger dims-parameterized identities + lesson persona provenance.
    assert expected_rollouts(3) == 12 and expected_sessions(3) == 9
    assert expected_rollouts(3, 3) == 15 and expected_sessions(3, 3) == 12
    assert expected_rollouts(3, 1) == 9 and expected_sessions(3, 1) == 6
    from core.harness.demo_adapter import DEMO_SURFACE
    from core.harness.library import Library

    libdir = Path(tempfile.mkdtemp(prefix="april-p2-library-"))
    try:
        lib = Library(root=libdir, domain="demo", surface=DEMO_SURFACE)
        entry = lib.add(
            "task-002",
            {"AGENTS.md": "Base."},
            label="agg1",
            experience={
                "cue": "ledger sums drop credits",
                "lesson": "include both signs",
                "evidence": "probe total flipped after the filter drop",
                "profile_id": "april",
                "ocean": personality.ocean_row(april_profile),
            },
        )
        entry_text = (entry / "EXPERIENCE.md").read_text()
        assert f"- **profile**: `april` — {personality.ocean_row(april_profile)}" in entry_text, entry_text
        index_text = lib.rebuild_index().read_text()
        assert "- persona: `april` — O70 C90 E45 A88 N20" in index_text, index_text
    finally:
        shutil.rmtree(libdir, ignore_errors=True)
    exp_doc = Path.cwd().joinpath("EXPERIENCE.md").read_text()
    assert "| Task ID | Domain | Adopted | Persona | Lesson |" in exp_doc, "EXPERIENCE.md header lost Persona"
    for pfile in sorted(Path.cwd().glob("profiles/*.json")):
        assert "userContext" not in json.loads(pfile.read_text()), pfile
    checks.append(
        "ledger n_dims identities (2→4k/3k, 3→5k/4k); lessons carry {profile_id, ocean} "
        "into entries + index; EXPERIENCE.md Persona column; profiles stay userContext-free"
    )

    # 14. P3: PSY is a learned axis, but only inside a profile — end to end on the
    # zcode stub, plus the post-selection judge and the edit-attribution split.
    from core.harness import judge
    from core.harness import schedule as harness_schedule
    from core.harness import selection as harness_selection
    from core.harness.library import SIMILARITY_FLOOR, Library as HarnessLibrary

    assert harness_prompts.active_dims(zres_p) == ("INV", "DOM", "PSY")
    assert harness_prompts.active_dims(zfree) == ("INV", "DOM")
    try:
        harness_prompts.propose(zfree, "PSY", zsurface)
        raise AssertionError("PSY must never be scheduled without psy_levers")
    except ValueError as psy_exc:
        assert "psy_levers" in str(psy_exc), psy_exc
    psy_text = personality.psy_mechanism(april_profile)
    assert "warmth" in psy_text and "Derived behavior" in psy_text, psy_text[:80]
    assert "trait" not in psy_text.lower().replace("traits", ""), "PSY slot must carry params, not traits"
    assert f"capped at {harness_prompts.PERSONA_CLAUSE_CAP}" in harness_prompts.propose(
        zres_p, "PSY", zsurface
    )

    old_zbin = os.environ.get("APRIL_ZCODE_BIN")
    old_zroot = os.environ.get("APRIL_RUNS_ROOT")
    ptmp = Path(tempfile.mkdtemp(prefix="april-p3-persona-"))
    os.environ.update(
        {"APRIL_ZCODE_BIN": str(zstub), "APRIL_RUNS_ROOT": str(ptmp / "runs")}
    )
    try:
        pres = asyncio.run(
            Harness(zpersona, runs_root=ptmp / "runs").run_task(t0, k=2, mode="agg")
        )
    finally:
        if old_zbin is None:
            os.environ.pop("APRIL_ZCODE_BIN", None)
        else:
            os.environ["APRIL_ZCODE_BIN"] = old_zbin
        if old_zroot is None:
            os.environ.pop("APRIL_RUNS_ROOT", None)
        else:
            os.environ["APRIL_RUNS_ROOT"] = old_zroot
    try:
        assert pres.status == "ok", (pres.status, pres.errors)
        assert pres.persona == "april", pres.persona
        expected_rollouts = {
            "agg": [
                "base1",
                "base2",
                "inv1",
                "dom1",
                "psy1",
                "inv2",
                "dom2",
                "psy2",
                "agg1",
                "agg2",
            ],
        }
        for pmode, prec in pres.modes.items():
            pled = prec["ledger"]
            assert pled["n_dims"] == 3, (pmode, pled)
            assert pled["R"] == pled["expected_R"] == 10, (pmode, pled)
            assert pled["P"] == pled["expected_P"] == 8, (pmode, pled)
            assert pled["rollouts"] == expected_rollouts[pmode], (pmode, pled["rollouts"])
            assert prec["n_dims"] == 3, (pmode, prec.get("n_dims"))
            assert prec["ok"] and len(prec["finals"]) == 2, (pmode, prec)
        pns = harness_schedule.ns("zcode", "zcode", "agg", 2, persona="april")
        assert pns == "zcode-zcode-agg2-Papril", pns
        psummary = ptmp / "runs" / pns / t0.replace("/", "__") / "summary.json"
        assert json.loads(psummary.read_text())["persona"] == "april", psummary
        pmarks = list((ptmp / "runs").rglob(".adapt_complete"))
        assert len(pmarks) == 8, len(pmarks)
        assert all(zpersona.delivered(m.parent) for m in pmarks), "a marked rollout lost its deliverable"

        # Judge: exactly the two machine-decidable profile rules run, the rest is attested.
        clean = judge.trait_checklist("april", "Wrote the plan. No credentials anywhere.")
        assert clean["ok"] and clean["deterministic"] == 2, clean
        assert clean["attested"] >= len(april_profile.persona.protocols), clean
        bad = judge.trait_checklist(
            "april", "git push origin main\nsk-" + "A" * 24
        )
        checks_by_id = {c["id"]: c for c in bad["checks"] if c["kind"] == "deterministic"}
        assert checks_by_id["no-unapproved-public-action"]["ok"] is False, checks_by_id
        assert checks_by_id["no-secrets-stored-echoed-logged"]["ok"] is False, checks_by_id
        assert bad["ok"] is False
        approved = judge.trait_checklist(
            "april", "git push origin main\nuser approved the release"
        )
        assert next(c for c in approved["checks"] if c["kind"] == "deterministic")["ok"] is True

        class _Sel:
            ok = True

        class _JudgeAdapter:
            spec = type("Spec", (), {"profile": "april", "obs_trunc": 100_000})()

            def score(self, run_dir, task_id):
                return {"value": 1}

            def deliverable_text(self, run_dir):
                return "Done, with no secrets."

            def trajectory(self, run_dir, **kwargs):
                return "trajectory"

        scored = judge.score_after_selection(
            _JudgeAdapter(), _Sel(), run_dir="x", task_id=t0
        )
        assert scored["value"] == 1 and scored["trait_adherence"]["ok"], scored
        assert (
            judge.score_after_selection(_JudgeAdapter(), None, run_dir="x", task_id=t0)
            is None
        ), "scoring must stay gated on selection"

        # Attribution: a PSY edit stays separable from an INV edit, and only an
        # all-PSY lesson is marked non-transferable for the library gate.
        from core.components.base import default_registry

        pbase = dict(zg_ok)
        ppsy = dict(zg_ok)
        ppsy["AGENTS.md"] = zg_ok["AGENTS.md"] + "\nKeep the register calm.\n"
        pinv = dict(zg_ok)
        pinv["scripts/spot_check.py"] = "print('changed')\n"
        attrib = harness_selection.edit_attribution(
            default_registry(),
            pbase,
            {"psy1": ppsy, "inv1": pinv},
            {"psy1": "PSY", "inv1": "INV"},
        )
        assert attrib["system_prompt"]["dims"] == ["PSY"], attrib
        assert attrib["scripts"]["dims"] == ["INV"], attrib
        assert harness_selection.lesson_transferable(
            {"system_prompt": {"dims": ["PSY"]}}
        ) is False
        assert harness_selection.lesson_transferable(attrib) is True
        annotated = harness_selection._annotate_edits(  # noqa: SLF001
            "candidates: psy1, inv1", {"psy1": "PSY", "inv1": "INV"}
        )
        assert "dimensions: INV, PSY" in annotated, annotated

        # Library: cosine rank + transfer gate. april<->user passes, april<->verifier
        # is gated unless the lesson itself says transferable.
        assert SIMILARITY_FLOOR == 0.95
        ltmp = Path(tempfile.mkdtemp(prefix="april-p3-lib-"))
        try:
            plib = HarnessLibrary(
                root=ltmp, domain="device-control", surface=zsurface, profile="april"
            )
            for name, prof, ocean, transfer in (
                ("far", "verifier", personality.ocean_row(personality.load_profile("verifier")), False),
                ("near", "user", personality.ocean_row(personality.load_profile("user")), False),
                ("free", "", "", True),
            ):
                ed = plib.dir / "harnesses" / name
                ed.mkdir(parents=True)
                meta = [f"# {name}", ""]
                if prof:
                    meta.append(f"- **profile**: `{prof}` — {ocean}")
                meta.append(f"- **transferable**: {'true' if transfer else 'false'}")
                (ed / "EXPERIENCE.md").write_text("\n".join(meta) + "\n")
            plib.rebuild_index()
            ctx = plib.load_context(5, profile="april")
            assert "# near" in ctx and "# free" in ctx and "# far" not in ctx, ctx
            assert ctx.index("# near") < ctx.index("# free"), "cosine rank lost"
            free_ctx = HarnessLibrary(
                root=ltmp, domain="device-control", surface=zsurface
            ).load_context(5)
            assert all(f"# {n}" in free_ctx for n in ("far", "near", "free")), free_ctx
        finally:
            shutil.rmtree(ltmp, ignore_errors=True)
    finally:
        shutil.rmtree(ptmp, ignore_errors=True)
    checks.append(
        "PSY end to end: 5k rollouts / 4k sessions (n_dims=3), labels "
        "base→inv→dom→psy→final, 8 markers, `-Papril` namespace, summary persona"
    )
    checks.append(
        "post-selection trait checklist (2 deterministic gates + attested rules), "
        "PSY/INV edit attribution, cosine library gate at 0.95"
    )

    # 15. P3 scale-out: one sweep call, many profiles, isolated namespace and library root.
    from core.harness.execution_manager import _DryProposer

    old_zbin = os.environ.get("APRIL_ZCODE_BIN")
    old_zroot = os.environ.get("APRIL_RUNS_ROOT")
    stmp = Path(tempfile.mkdtemp(prefix="april-p3-sweep-"))
    os.environ.update(
        {"APRIL_ZCODE_BIN": str(zstub), "APRIL_RUNS_ROOT": str(stmp / "runs")}
    )
    try:
        sweep = harness_schedule.run_sweep_zcode(
            1,
            runs_root=stmp / "runs",
            library_root=stmp / "library",
            modes=("agg",),
            only_tasks=(t0,),
            max_tasks=1,
            prop=_DryProposer(),
            profiles=("april", "user"),
        )
    finally:
        if old_zbin is None:
            os.environ.pop("APRIL_ZCODE_BIN", None)
        else:
            os.environ["APRIL_ZCODE_BIN"] = old_zbin
        if old_zroot is None:
            os.environ.pop("APRIL_RUNS_ROOT", None)
        else:
            os.environ["APRIL_RUNS_ROOT"] = old_zroot
    try:
        assert sweep["profiles"] == ["april", "user"], sweep["profiles"]
        assert sweep["n_dims"] == 3
        assert set(sweep["results"]) == {"april", "user"}, sweep["results"].keys()
        roots = {p: sweep["results"][p]["library_root"] for p in ("april", "user")}
        assert roots["april"] != roots["user"], roots
        assert roots["april"].endswith("/april") and roots["user"].endswith("/user"), roots
        for prof in ("april", "user"):
            ns_agg = harness_schedule.ns("zcode", "zcode", "agg", 1, persona=prof)
            task_dir = stmp / "runs" / ns_agg / t0.replace("/", "__")
            summary = json.loads((task_dir / "summary.json").read_text())
            assert summary["persona"] == prof, (prof, summary.get("persona"))
            row = sweep["results"][prof]["domains"][0]["tasks"][0]
            assert row["status"] == "ok", row
            # The reflection evidence tree carries the authored fixtures through
            # the inline-fixture seam, not a task directory.
            assert (task_dir / "reflection" / "agg1" / "source" / "devices.json").is_file(), (
                prof,
                sorted((task_dir / "reflection").rglob("*")),
            )
    finally:
        shutil.rmtree(stmp, ignore_errors=True)
    checks.append(
        "multi-profile sweep: one call fans out per profile with `-P<id>` namespaces "
        "and per-profile library roots (scale-out contract holds)"
    )

    # 16. P4 scale-out contract: a third persona is ONE JSON file, zero code. The
    # proof is the negative source scan plus a real 1-task sweep at full arithmetic.
    ride = personality.load_profile("ridealong")
    assert personality.out_of_band(ride) == "", personality.out_of_band(ride)
    naming = [
        p
        for p in (Path.cwd() / "core" / "harness").rglob("*.py")
        if "ridealong" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not naming, f"third profile leaked into harness code: {naming}"
    rtmp = Path(tempfile.mkdtemp(prefix="april-p4-ridealong-"))
    old_zbin = os.environ.get("APRIL_ZCODE_BIN")
    old_zroot = os.environ.get("APRIL_RUNS_ROOT")
    os.environ.update(
        {"APRIL_ZCODE_BIN": str(zstub), "APRIL_RUNS_ROOT": str(rtmp / "runs")}
    )
    try:
        ride_sweep = harness_schedule.run_sweep_zcode(
            1,
            runs_root=rtmp / "runs",
            library_root=rtmp / "library",
            modes=("agg",),
            only_tasks=(t0,),
            max_tasks=1,
            prop=_DryProposer(),
            profiles=("ridealong",),
        )
    finally:
        if old_zbin is None:
            os.environ.pop("APRIL_ZCODE_BIN", None)
        else:
            os.environ["APRIL_ZCODE_BIN"] = old_zbin
        if old_zroot is None:
            os.environ.pop("APRIL_RUNS_ROOT", None)
        else:
            os.environ["APRIL_RUNS_ROOT"] = old_zroot
    try:
        assert ride_sweep["profiles"] == ["ridealong"], ride_sweep["profiles"]
        assert ride_sweep["n_dims"] == 3, ride_sweep["n_dims"]
        assert ride_sweep["results"]["ridealong"]["library_root"].endswith("/ridealong")
        rrow = ride_sweep["results"]["ridealong"]["domains"][0]["tasks"][0]
        assert rrow["status"] == "ok", rrow
        rns = harness_schedule.ns("zcode", "zcode", "agg", 1, persona="ridealong")
        assert rns == "zcode-zcode-agg1-Pridealong", rns
        rsum = json.loads(
            (rtmp / "runs" / rns / t0.replace("/", "__") / "summary.json").read_text()
        )
        assert rsum["persona"] == "ridealong", rsum.get("persona")
        rled = rsum["modes"]["agg"]["ledger"]
        assert (rled["n_dims"], rled["R"], rled["P"]) == (3, 5, 4), rled
        assert rled["R"] == rled["expected_R"] and rled["P"] == rled["expected_P"], rled
        rmarks = list((rtmp / "runs").rglob(".adapt_complete"))
        assert len(rmarks) == 4, len(rmarks)
        assert all(zadapter.delivered(m.parent) for m in rmarks), "marked rollout lost deliverable"
    finally:
        shutil.rmtree(rtmp, ignore_errors=True)
    checks.append(
        "P4 scale-out: profiles/ridealong.json lands as data only (no harness source "
        "names it); 1-task sweep yields -Pridealong, R=5=5k, P=4=4k, own library root"
    )

    # 17. P4 degradation: a vector the band tables cannot compile still loads and
    # runs, but emits authored c1 text only and keeps the PSY lane off.
    otmp = Path(tempfile.mkdtemp(prefix="april-p4-oob-"))
    try:
        odir = otmp / "profiles"
        odir.mkdir()
        odata = json.loads((Path.cwd() / "profiles" / "ridealong.json").read_text())
        odata.pop("ocean")  # P6: ocean and facets are mutually exclusive — facet grain only
        odata["facets"] = {"trust": 90, "dutifulness": 70}
        (odir / "faceted.json").write_text(json.dumps(odata))
        faceted = personality.load_profile("faceted", odir)
        assert personality.out_of_band(faceted), "facet vector must report its ceiling"
        fblock = personality.compile_persona(faceted)
        assert "## Personality (authored)" in fblock, fblock
        assert "## Personality (OCEAN)" not in fblock and "## Voice" not in fblock, fblock
        assert "Narrate what you are about to do" in fblock, "authored rules must survive"
        assert personality.psy_mechanism(faceted) == "", "PSY leaked onto an uncompilable vector"

        # The spec seam keeps psy_levers empty, so the ledger stays 2-dimensional.
        old_load = personality.load_profile
        personality.load_profile = lambda name, profiles_dir=None: (  # type: ignore[assignment]
            faceted if name == "faceted" else old_load(name)
        )
        try:
            fadapt = type(
                "FacetAdapter",
                (),
                {
                    "spec": type(
                        "FacetSpec",
                        (),
                        {"profile": "faceted", "prompts": type(zres_p)()},
                    )()
                },
            )()
            fprompts = resolve_prompts(fadapt, t0)
        finally:
            personality.load_profile = old_load  # type: ignore[assignment]
        assert "## Personality (authored)" in fprompts.persona_guidance, fprompts.persona_guidance[:80]
        assert fprompts.psy_levers == "", "resolve_prompts activated PSY for a facet profile"
        assert harness_prompts.active_dims(fprompts) == ("INV", "DOM"), "dims must stay 2-D"
        assert "# ponytail:" in (
            Path.cwd() / "core" / "harness" / "personality.py"
        ).read_text(encoding="utf-8")
    finally:
        shutil.rmtree(otmp, ignore_errors=True)
    checks.append(
        "P4 degradation: a facet (out-of-band) vector compiles authored c1 text only, "
        "PSY stays off, ledger arithmetic stays 2-D; ceiling marked `# ponytail:`"
    )

    # 18. P4-4.2: the profile format is documented as a contract.
    schema = Path.cwd() / "docs" / "spec" / "ocean-profile-schema.md"
    assert schema.is_file(), schema
    stext = schema.read_text(encoding="utf-8")
    for needle in (
        "## 2. Fields",
        "## 3. Derived parameters",
        "## 7. Facet vectors and the degradation contract",
        "userContext",
        "SIMILARITY_FLOOR",
        "facets",
        "one JSON file",
    ):
        assert needle in stext, f"schema doc is missing {needle!r}"
    checks.append(
        "P4 schema contract: docs/spec/ocean-profile-schema.md documents fields, "
        "derivation, transfer gate, and the degradation ceiling"
    )

    # 19. P5: the ADE end-to-end, offline — deploy (stamp + fingerprint), tamper
    # refusal, boot (c1/c2/temperature), the permission layer, runtime wiring,
    # and the TUI view contract; plus the from_env APRIL_PERSONA pin.
    from core.ade import deploy as ade_deploy, load_deployed
    from core.ade.boot import ActionGuard, boot as ade_boot
    from core.ade.views import persona_view as ade_persona_view
    from core.harness import runmark
    from core.substrate.april import APRIL_SURFACE

    atmp = Path(tempfile.mkdtemp(prefix="april-p5-ade-"))
    aderoot = atmp / ".ade"
    old_ade_root = os.environ.get("APRIL_ADE_ROOT")
    old_persona_env = os.environ.get("APRIL_PERSONA")
    try:
        # from_env reads the persona id; empty stays the no-boot default.
        os.environ["APRIL_PERSONA"] = "april"
        assert AgentConfig.from_env().persona == "april", "from_env must read APRIL_PERSONA"
        os.environ["APRIL_PERSONA"] = ""
        assert AgentConfig.from_env().persona == "", "empty APRIL_PERSONA stays no-boot"

        # Deploy the shipped base tree under the april persona, with a synthetic
        # local override under the TEMP root (never the repo's real .ade/etc).
        os.environ["APRIL_ADE_ROOT"] = str(aderoot)
        etc = aderoot / "etc"
        etc.mkdir(parents=True)
        (etc / "persona-user-context.md").write_text(
            "## APRIL userContext (personal facts that shape behavior)\n\n"
            "- fact one\n- fact two\n",
            encoding="utf-8",
        )
        row = ade_deploy(
            Path.cwd() / "core" / "harness" / "basetree" / "april",
            surface=APRIL_SURFACE,
            persona="april",
            domain="default",
            task_id="demo/demo-0001",
        )
        fdir = aderoot / "harnesses" / "april" / "default"
        assert row["fingerprint"] not in ("", "absent", "base") and runmark.fingerprint(
            fdir
        ) == row["fingerprint"], row
        stamped = (fdir / "systemprompt.md").read_text(encoding="utf-8")
        assert "## persona: compiled" in stamped, "deployment did not stamp the persona"
        assert "## persona: protocols" in (fdir / "guardrails.md").read_text(encoding="utf-8")

        # Tamper evidence: bytes changed after deployment -> refusal, not fallback.
        sp = fdir / "systemprompt.md"
        original = sp.read_text(encoding="utf-8")
        sp.write_text(original + "\n<!-- tampered -->", encoding="utf-8")
        try:
            load_deployed("april")
            raise AssertionError("a tampered deployment must be refused")
        except ValueError:
            pass
        sp.write_text(original, encoding="utf-8")
        assert load_deployed("april") is not None, "restored tree must load again"

        # Boot: c1 (+ local facts) -> system prompt, c2 -> guardrails, temp derived.
        b = ade_boot("april", domain="default")
        assert b.source == "deployed:default", b.source
        assert b.system_prompt.startswith("# APRIL"), b.system_prompt[:40]
        assert "## About the user" in b.system_prompt and b.user_context == (
            "fact one",
            "fact two",
        )
        assert "## Protocols" in b.guardrails and b.machine_rules == (
            "no-unapproved-public-action",
            "no-secrets-stored-echoed-logged",
        )

        # The permission layer reuses the post-selection machine gates verbatim.
        g = ActionGuard("april", b.guardrails)
        blocked, why = g.check("git push origin main")
        assert not blocked and "approval" in why, why
        assert g.check("git push origin main\nuser approved the release")[0]
        bad, why2 = g.check("echo sk-" + "A" * 24)
        assert not bad and "secrets" in why2, why2
        assert g.check("ls -la")[0]
        assert len(g.attested_rules()) >= 7, g.attested_rules()

        # Runtime wiring: system head, derived temperature, guard on shell calls.
        rt = AgentRuntime(
            AgentConfig(
                model="m",
                api_key="dummy",
                api_base_url="http://localhost:1",
                persona="april",
            )
        )
        pb = rt.persona_boot
        assert pb is not None and pb.source == "deployed:default", (
            pb.source if pb else None
        )
        head = rt.session.context[0]
        assert head["role"] == "system" and head["content"].startswith("# APRIL")
        assert rt.config.temperature == pb.temperature, "derive() must own sampling"
        assert rt.config.temperature != 0.7, "the persona temperature overrode the default"
        res = rt._process_tool_calls(
            [
                type(
                    "BlockedCall",
                    (),
                    {
                        "function": type(
                            "F",
                            (),
                            {
                                "name": "shell_execute",
                                "arguments": '{"command": "git push origin main"}',
                            },
                        )(),
                        "id": "call_p5",
                    },
                )()
            ]
        )
        assert str(res[0]["content"]).startswith("[persona-guard]"), res[0]["content"]
        plain = AgentRuntime(
            AgentConfig(model="m", api_key="dummy", api_base_url="http://localhost:1")
        )
        assert plain.persona_boot is None and plain.persona_guard is None

        # The view contract: boot summary + deployments, facts as a COUNT only.
        pv = ade_persona_view("april", domain="default", library_root=aderoot / "library")
        assert pv["source"] == "deployed:default" and pv["fingerprint"] == row["fingerprint"]
        assert pv["deployed_dir"] == str(fdir), "the view must read the temp ADE root"
        assert len(pv["attested_rules"]) >= 7
        assert pv["user_context_facts"] == len(b.user_context) == 2
        assert "fact one" not in json.dumps(pv), "the view must never carry fact text"
        assert len(pv["deployments"]) == 1 and pv["deployments"][0]["fingerprint"] == row["fingerprint"]
    finally:
        if old_ade_root is None:
            os.environ.pop("APRIL_ADE_ROOT", None)
        else:
            os.environ["APRIL_ADE_ROOT"] = old_ade_root
        if old_persona_env is None:
            os.environ.pop("APRIL_PERSONA", None)
        else:
            os.environ["APRIL_PERSONA"] = old_persona_env
        shutil.rmtree(atmp, ignore_errors=True)
    checks.append(
        "P5 ADE: deploy stamps + fingerprints (tamper refused, not fallback); boot maps "
        "c1/c2/derived temperature (+ local facts); guard blocks unapproved public actions "
        "and secrets, attests the rest; runtime boots in one construction; view exposes "
        "counts, never fact text; from_env reads APRIL_PERSONA"
    )

    # 20. P6: facet vectors compile. A full-coverage facet profile aggregates to
    # OCEAN at load (identical kernel output as its ocean-grain twin) and rides
    # the same mission seams; partial coverage degrades (check 17); load-time
    # gates refuse contradictions.
    ptmp = Path(tempfile.mkdtemp(prefix="april-p6-facets-"))
    try:
        pdir = ptmp / "profiles"
        pdir.mkdir()
        (pdir / "facetride.json").write_text(
            json.dumps(
                {
                    "name": "FacetRidealong",
                    # pairs (s-1, s) per domain: mean s-0.5; the kernel's half-up
                    # rounding must land on ridealong's own domain scores
                    # (O 60, C 55, E 50, A 85, N 15).
                    "facets": {
                        "fantasy": 59, "aesthetics": 60,
                        "order": 54, "competence": 55,
                        "warmth": 49, "gregariousness": 50,
                        "trust": 84, "straightforwardness": 85,
                        "anxiety": 14, "angry_hostility": 15,
                    },
                }
            ),
            encoding="utf-8",
        )
        fp = personality.load_profile("facetride", pdir)
        assert personality.out_of_band(fp) == "", "full facet coverage must compile"
        pc = personality.compile_persona(fp)
        ride = personality.load_profile("ridealong").persona

        def ocean_section(text: str) -> str:
            i = text.index("## Personality (OCEAN)")
            j = text.find("\n## ", i + 3)
            return text[i : j if j != -1 else None].strip()

        assert ocean_section(pc) == ocean_section(personality.compile_persona(ride)), (
            "kernel purity failed: aggregated facets must compile identically"
        )
        assert personality.derive(fp) == personality.derive(ride), "derived params must match"
        assert "## Facets" in pc and "- trust 84 (agreeableness)" in pc, "facet data block missing"
        assert personality.psy_mechanism(fp) != "", "PSY must follow a compiled facet vector"

        # Load-time gates refuse contradictions loudly (file path in, ValueError out).
        for bad, frag in (
            (
                {"name": "b1", "ocean": {t: 50 for t in personality.TRAITS}, "facets": {"trust": 90}},
                "mutually exclusive",
            ),
            ({"name": "b2", "facets": {"trust": 90, "truffle_pig": 10}}, "unknown facet name"),
        ):
            (pdir / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
            try:
                personality.profile_from_path(pdir / "bad.json")
            except ValueError as e:
                assert frag in str(e), (frag, str(e))
            else:
                raise AssertionError(f"must refuse loudly: {frag}")

        # Mission seams: the facet-grain profile goes through the same slots as
        # any ocean-grain profile, and the PSY lane goes 3-D.
        old_load = personality.load_profile
        personality.load_profile = lambda name, profiles_dir=None: (  # type: ignore[assignment]
            fp if name == "facetride" else old_load(name)
        )
        try:
            padapt = type(
                "FacetFullAdapter",
                (),
                {
                    "spec": type(
                        "FacetFullSpec",
                        (),
                        {"profile": "facetride", "prompts": type(zres_p)()},
                    )()
                },
            )()
            pprompts = resolve_prompts(padapt, t0)
        finally:
            personality.load_profile = old_load  # type: ignore[assignment]
        assert "## Personality (OCEAN)" in pprompts.persona_guidance, pprompts.persona_guidance[:80]
        assert "## Facets" in pprompts.persona_guidance, "facet grain must ride the mission slot"
        assert pprompts.psy_levers != "", "resolve_prompts must activate PSY for a compiled facet vector"
        assert harness_prompts.active_dims(pprompts) == ("INV", "DOM", "PSY"), "dims must go 3-D"
    finally:
        shutil.rmtree(ptmp, ignore_errors=True)
    checks.append(
        "P6 facets: a full-coverage facet vector aggregates to OCEAN at load — "
        "identical compiled section + derived params vs ridealong (half-up pin), "
        "data-only ## Facets rides the missions, PSY goes 3-D; ocean+facets and "
        "unknown facet names are refused at load"
    )

    # 21. P7-1: facet-conditioned directives. The ridealong-shaped facet twin's
    # (s-1, s) pairs put A in veryHigh and N in veryLow, so exactly four
    # directive lines ride the mission slot, above the data block; the
    # ocean-grain original renders no facet section at all.
    ftwin = personality.persona_from_dict(
        {
            "name": "DirectiveTwin",
            "facets": {
                "fantasy": 59, "aesthetics": 60,
                "order": 54, "competence": 55,
                "warmth": 49, "gregariousness": 50,
                "trust": 84, "straightforwardness": 85,
                "anxiety": 14, "angry_hostility": 15,
            },
        }
    )
    old_load = personality.load_profile
    personality.load_profile = lambda name, profiles_dir=None: ftwin  # type: ignore[assignment]
    try:
        dadapt = type(
            "DirectiveAdapter",
            (),
            {
                "spec": type(
                    "DirectiveSpec",
                    (),
                    {"profile": "directivetwin", "prompts": type(zres_p)()},
                )()
            },
        )()
        dprompts = resolve_prompts(dadapt, t0)
    finally:
        personality.load_profile = old_load  # type: ignore[assignment]
    pg = dprompts.persona_guidance
    assert "## Facet directives" in pg and "## Facets" in pg, "facet directives must ride the mission slot"
    assert pg.index("## Facet directives") < pg.index("## Facets"), pg
    dsec = pg[pg.index("## Facet directives") :]
    dcut = dsec.find("\n## ", 1)
    dsec = dsec[: dcut if dcut != -1 else len(dsec)]
    dlines = [ln for ln in dsec.splitlines()[1:] if ln.strip()]
    assert len(dlines) == 4, dlines
    assert any(ln.startswith("- trust (veryHigh): ") for ln in dlines), dlines
    assert any(ln.startswith("- anxiety (veryLow): ") for ln in dlines), dlines
    oprompts = resolve_prompts(ZcodeAdapter(profile="ridealong"), t0)
    assert "## Facet" not in oprompts.persona_guidance, "ocean grain must not emit a facet section"
    checks.append(
        "P7-1 facet directives: facet grain compiles behavior into the mission slot "
        "(## Facet directives above the data block; 4 lines, - trust (veryHigh): "
        "needle); ocean grain renders none"
    )

    # 22. P7-3: the legacy backfill, inert. Pure synthetic pins (nearest_profile
    # gate, assign/stay-transferable/stay-free, dry-run writes nothing, idempotent
    # re-run); apply() refuses when nothing is profileable; no real data written.
    from core.harness import backfill as backfill_mod
    backfill_mod.demo()
    checks.append(
        "P7-3 backfill: synthetic mix exercises assign / stay-transferable / "
        "stay-free; dry-run writes nothing; re-run is idempotent; apply refuses "
        "empty input; runs on fixtures only (inert)"
    )

    # 23. P7-4: seeds are a driver parameter, not a caller loop. Multi-seed
    # sweep runs once per seed and aggregates per-seed ledger rows under one
    # library_root; each namespace carries -s<seed>; the seedless path is
    # byte-identical because `seeds=None` (the default) takes the old branch.
    from core.harness.execution_manager import _DryProposer

    old_zbin = os.environ.get("APRIL_ZCODE_BIN")
    old_zroot = os.environ.get("APRIL_RUNS_ROOT")
    mtmp = Path(tempfile.mkdtemp(prefix="april-p74-seeds-"))
    os.environ.update(
        {"APRIL_ZCODE_BIN": str(zstub), "APRIL_RUNS_ROOT": str(mtmp / "runs")}
    )
    try:
        seed_a, seed_b = 3, 7
        msweep = harness_schedule.run_sweep_zcode(
            1,
            runs_root=mtmp / "runs",
            library_root=mtmp / "library",
            modes=("agg",),
            only_tasks=(t0,),
            max_tasks=1,
            prop=_DryProposer(),
            seeds=(seed_a, seed_b),
        )
    finally:
        if old_zbin is None:
            os.environ.pop("APRIL_ZCODE_BIN", None)
        else:
            os.environ["APRIL_ZCODE_BIN"] = old_zbin
        if old_zroot is None:
            os.environ.pop("APRIL_RUNS_ROOT", None)
        else:
            os.environ["APRIL_RUNS_ROOT"] = old_zroot
    try:
        assert msweep["seeds"] == [seed_a, seed_b], msweep["seeds"]
        assert set(msweep["results_by_seed"]) == {str(seed_a), str(seed_b)}, msweep["results_by_seed"].keys()
        for s in (seed_a, seed_b):
            ns_dir = harness_schedule.ns("zcode", "zcode", "agg", 1, seed=s)
            task_dir = mtmp / "runs" / ns_dir / t0.replace("/", "__")
            summary = json.loads((task_dir / "summary.json").read_text())
            led = summary["modes"]["agg"]["ledger"]
            # ledger exactness per seed (R=4k/P=3k at 2 dims, k=1).
            assert (led["n_dims"], led["R"], led["P"]) == (2, 4, 3), led
            assert led["R"] == led["expected_R"] and led["P"] == led["expected_P"], led
            assert summary.get("seed") == s, (summary.get("seed"), s)
            row = msweep["results_by_seed"][str(s)]["domains"][0]["tasks"][0]
            assert row["status"] == "ok", row
    finally:
        shutil.rmtree(mtmp, ignore_errors=True)
    # No-seed path is byte-identical: calling with seeds=None takes the old branch.
    ns_tmp = Path(tempfile.mkdtemp(prefix="april-p74-none-"))
    old_zbin = os.environ.get("APRIL_ZCODE_BIN")
    old_zroot = os.environ.get("APRIL_RUNS_ROOT")
    os.environ.update(
        {"APRIL_ZCODE_BIN": str(zstub), "APRIL_RUNS_ROOT": str(ns_tmp / "runs")}
    )
    try:
        ns_sweep = harness_schedule.run_sweep_zcode(
            1,
            runs_root=ns_tmp / "runs",
            library_root=ns_tmp / "library",
            modes=("agg",),
            only_tasks=(t0,),
            max_tasks=1,
            prop=_DryProposer(),
        )
    finally:
        if old_zbin is None:
            os.environ.pop("APRIL_ZCODE_BIN", None)
        else:
            os.environ["APRIL_ZCODE_BIN"] = old_zbin
        if old_zroot is None:
            os.environ.pop("APRIL_RUNS_ROOT", None)
        else:
            os.environ["APRIL_RUNS_ROOT"] = old_zroot
    try:
        assert "seeds" not in ns_sweep or ns_sweep.get("seeds") in (None, []), ns_sweep.get("seeds")
        assert "results_by_seed" not in ns_sweep, ns_sweep.keys()
    finally:
        shutil.rmtree(ns_tmp, ignore_errors=True)
    checks.append(
        "P7-4 seeds: multi-seed runs two distinct ns dirs with exact R=4k/P=3k "
        "ledgers per seed; aggregate carries both; seeds=None (default) takes "
        "the seedless branch (byte-identical contract held)"
    )

    for line in checks:
        print(f"  ok: {line}")
    print("APRIL offline self-checks passed.")

