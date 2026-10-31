"""
APRIL Agent Runtime

The core agent loop: manage context, call LLM, process tool calls.
"""

from typing import List, Dict, Optional, Callable, AsyncGenerator, Any
import json
import threading
import os
from openai import OpenAI

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
        self._event_bus.emit(LogEvent(level="INFO", source="user", message=truncated))
        
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
            self._event_bus.emit(LogEvent(level="INFO", source="llm", message=f"Request to {self.config.model} ({len(self.session.context)} messages)"))
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.session.context,
                tools=self.tool_schemas,
                temperature=self.config.temperature
            )
            
            message = response.choices[0].message
            
            # Log LLM response
            self._event_bus.emit(LogEvent(level="INFO", source="llm", message=f"Response from {self.config.model}"))
            
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
                    self._event_bus.emit(LogEvent(level="INFO", source="tool", message=f"Calling: {tool_name}"))
                
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
            self._event_bus.emit(LogEvent(level="INFO", source="agent", message=final_response[:100] + "..." if len(final_response) > 100 else final_response))
            
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
            
            self._event_bus.emit(LogEvent(level="DEBUG", source="memory", message=f"Extracting memories from {len(messages)} messages"))
            
            memories = self.extractor.extract(messages, client=self.client)
            
            self._event_bus.emit(LogEvent(level="DEBUG", source="memory", message=f"Extracted {len(memories)} memories"))
            
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
            
            self._event_bus.emit(LogEvent(level="DEBUG", source="memory", message=f"Marked {len(message_ids)} messages as processed"))
            
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
        self._event_bus.emit(LogEvent(level="INFO", source="session", message="Context cleared"))
    
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
        
        Yields tokens as they arrive from the model.
        """
        if max_iterations is None:
            max_iterations = self.config.max_iterations
        
        # Emit start events
        msg_id = self._event_bus.emit_message_start(is_assistant=True)
        self._event_bus.emit_status("thinking", {"user_input": user_input[:50]})
        
        # Log user message
        truncated = user_input[:100] + "..." if len(user_input) > 100 else user_input
        self._event_bus.emit(LogEvent(level="INFO", source="user", message=truncated))
        
        # Augment context
        self._augment_context_with_memories(user_input)
        self._save_conversation_turn('user', user_input)
        self.session.add_message('user', user_input)
        
        # Agent loop
        iterations = 0
        while iterations < max_iterations:
            # Emit status
            self._event_bus.emit_status("streaming" if iterations == 0 else "running_tool")
            
            # Log LLM request
            self._event_bus.emit(LogEvent(level="INFO", source="llm", message=f"Request to {self.config.model} ({len(self.session.context)} messages)"))
            
            # Call LLM
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=self.session.context,
                tools=self.tool_schemas,
                temperature=self.config.temperature,
                stream=True  # Enable streaming
            )
            
            full_response = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    yield token
                    self._event_bus.emit_message_delta(token, is_assistant=True, is_complete=False)
            
            # Complete message
            self._event_bus.emit_message_delta("", is_assistant=True, is_complete=True)
            
            # Check for tool calls in final message
            message = response.choices[0].message if hasattr(response, 'choices') else None
            if not message:
                # Get from accumulated chunks
                message = type('obj', (object,), {
                    'content': full_response,
                    'tool_calls': None
                })()
            
            if message.tool_calls:
                # Tool calls - emit start
                self._event_bus.emit_status("running_tool", {"tool_calls": len(message.tool_calls)})
                
                for tc in message.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)
                    self._event_bus.emit_tool_call_start(tool_name, tool_args, tc.id)
                
                # Process tool calls
                tool_results = self._process_tool_calls(message.tool_calls)
                
                for result in tool_results:
                    tool_name = result.get('name', 'unknown')
                    self._event_bus.emit_tool_call_output(result.get('tool_call_id', ''), f"Result from {tool_name}")
                    self._event_bus.emit_tool_call_done(tool_name, result.get('content', ''), result.get('tool_call_id', ''), True)
                
                # Add to context
                self.session.context.append({
                    'role': 'assistant',
                    'content': message.content,
                    'tool_calls': [
                        {
                            'id': tc.id,
                            'type': 'function',
                            'function': {'name': tc.function.name, 'arguments': tc.function.arguments}
                        } for tc in message.tool_calls
                    ]
                })
                
                for result in tool_results:
                    self.session.context.append(result)
                
                iterations += 1
                continue
            
            # No tool calls
            self.session.add_message('assistant', full_response)
            
            if full_response:
                self._save_conversation_turn('assistant', full_response)
                self._extract_and_store_memories()
            
            self._event_bus.emit_message_done(msg_id, full_response, is_assistant=True)
            self._event_bus.emit_status("idle")
            
            return
        
        self._event_bus.emit_status("idle")
        yield f'Reached maximum iterations ({max_iterations}) without completing.'
    
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

    for line in checks:
        print(f"  ok: {line}")
    print("APRIL offline self-checks passed.")

