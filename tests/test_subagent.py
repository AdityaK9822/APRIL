"""Test subagent concurrency and lifecycle"""

import time
import unittest

from core.config import AgentConfig
from core.subagent import (
    SubagentManager,
    SubagentConfig,
    SubagentStatus,
    Task,
    TaskStatus,
)


class FakeRuntime:
    """
    Stands in for AgentRuntime

    Records each run as a (start, end) timestamp pair (into `log`, if
    provided) and can be made artificially slow to exercise concurrency and
    timeout behavior without a model.
    """

    def __init__(self, agent_config: AgentConfig, delay: float = 0.0, log=None):
        self.agent_config = agent_config
        self.delay = delay
        self.ran = log if log is not None else []

    def run(self, description, max_iterations=None):
        start = time.monotonic()
        time.sleep(self.delay)
        end = time.monotonic()
        self.ran.append((start, end, description))
        return f"done: {description}"


class SubagentManagerTestCase(unittest.TestCase):
    """Shared setUp/tearDown: manager with an injected runtime factory"""

    def setUp(self):
        self.config = AgentConfig(
            model="test-model",
            api_key="test-key",
            api_base_url="http://test"
        )
        self.manager = SubagentManager(self.config, runtime_factory=self._factory)
        self._runtimes = []

    def tearDown(self):
        # wait=True keeps no task running past the test
        self.manager.shutdown(wait=True)

    def _factory(self, agent_config):
        runtime = FakeRuntime(agent_config, delay=self.RUNTIME_DELAY)
        self._runtimes.append(runtime)
        return runtime

    RUNTIME_DELAY = 0.0

    def spawn_ids(self, n):
        ids = []
        for i in range(n):
            process = self.manager.spawn(SubagentConfig(name=f"worker-{i}", role="executor"))
            ids.append(process.id)
        return ids


class TestSubagentManager(SubagentManagerTestCase):

    def test_spawn_uses_injected_runtime(self):
        ids = self.spawn_ids(1)

        subagent = self.manager.get_subagent(ids[0])
        self.assertIsInstance(subagent.agent, FakeRuntime)
        self.assertEqual(len(self._runtimes), 1)

    def test_unknown_subagent_raises(self):
        task = Task(description="orphan")
        with self.assertRaises(ValueError):
            self.manager.dispatch("missing", task)
        with self.assertRaises(ValueError):
            self.manager.dispatch_async("missing", task)
        with self.assertRaises(ValueError):
            self.manager.dispatch_and_wait("missing", task)
        with self.assertRaises(ValueError):
            self.manager.dispatch_parallel({"missing": task})

    def test_dispatch_sync_result_and_state(self):
        ids = self.spawn_ids(1)
        task = Task(description="check the shell")

        result = self.manager.dispatch(ids[0], task)

        self.assertTrue(result.success)
        self.assertEqual(result.data, "done: check the shell")
        self.assertEqual(result.subagent_id, ids[0])
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(self.manager.get_subagent(ids[0]).status, SubagentStatus.COMPLETED)

    def test_dispatch_async_future(self):
        ids = self.spawn_ids(1)
        task = Task(description="async job")

        future = self.manager.dispatch_async(ids[0], task)
        result = future.result(timeout=5)

        self.assertTrue(result.success)
        self.assertEqual(result.data, "done: async job")
        self.assertEqual(self.manager.get_subagent(ids[0]).status, SubagentStatus.COMPLETED)

    def test_dispatch_and_wait(self):
        ids = self.spawn_ids(1)
        result = self.manager.dispatch_and_wait(ids[0], Task(description="waited job"))

        self.assertTrue(result.success)

    def test_dispatch_and_wait_enforces_timeout(self):
        """0.5s of work against a 0.05s timeout must raise, not hang"""
        slow = SubagentManager(
            self.config,
            runtime_factory=lambda cfg: FakeRuntime(cfg, delay=0.5)
        )
        try:
            subagent = slow.spawn(SubagentConfig(name="slow-worker", role="executor"))
            with self.assertRaises(TimeoutError):
                slow.dispatch_and_wait(subagent.id, Task(description="slow job"), timeout=0.05)
        finally:
            slow.shutdown(wait=True)


class TestParallelDispatch(SubagentManagerTestCase):

    RUNTIME_DELAY = 0.15

    def test_parallel_overlaps_llm_waits(self):
        """Three 0.15s tasks overlap instead of queueing: wall time ~ 1 delay"""
        log = []

        def logging_factory(agent_config):
            runtime = FakeRuntime(agent_config, delay=self.RUNTIME_DELAY, log=log)
            self._runtimes.append(runtime)
            return runtime

        manager = SubagentManager(self.config, runtime_factory=logging_factory)
        try:
            ids = manager.split_worker_ids = [
                manager.spawn(SubagentConfig(name=f"parallel-{i}", role="executor")).id
                for i in range(3)
            ]
            tasks = {sid: Task(description=f"job {sid}") for sid in ids}

            started = time.monotonic()
            results = manager.dispatch_parallel(tasks)
            elapsed = time.monotonic() - started
        finally:
            manager.shutdown(wait=True)

        self.assertEqual(len(log), 3)
        for result in results.values():
            self.assertTrue(result.success)

        # Concurrency check: at least two runs were live at the same moment
        overlap = 0.0
        for i, (s1, e1, _d1) in enumerate(log):
            for (s2, e2, _d2) in log[i + 1:]:
                overlap = max(overlap, min(e1, e2) - max(s1, s2))
        self.assertGreater(overlap, 0.01, "tasks should overlap, not serialize")

        # Generous wall bound: 3 serial delays would be ~0.45s; overlapped ~0.15s
        self.assertLess(elapsed, self.RUNTIME_DELAY * 3, "wall time should be nearer one delay than three")

    def test_parallel_results_map_to_subagents(self):
        ids = self.spawn_ids(3)
        tasks = {sid: Task(description=f"part {sid}") for sid in ids}

        results = self.manager.dispatch_parallel(tasks)

        self.assertEqual(set(results.keys()), set(ids))
        for sid, result in results.items():
            self.assertTrue(result.success)
            self.assertEqual(result.subagent_id, sid)


if __name__ == "__main__":
    unittest.main()
