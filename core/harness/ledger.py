# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Budget accounting: R = (2 + n_dims)·k rollouts and P = (n_dims + 1)·k stage sessions.

The default n_dims = 2 (INV + DOM) gives the standing identities R = 4k, P = 3k.
P3's PSY dimension raises n_dims to 3 (R = 5k, P = 4k) without touching a caller.
Base executions count toward each mode. Retries are separate invocation counts;
selection and reflection are recorded outside this ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def expected_rollouts(k: int, n_dims: int = 2) -> int:
    """R = (2 + n_dims)·k: k shared base + n_dims·k dimension candidates + k finals.

    n_dims=2 (INV + DOM) gives R = 4k; P3 adds the PSY dimension (n_dims=3 → 5k).
    """
    return (2 + int(n_dims)) * int(k)


def expected_sessions(k: int, n_dims: int = 2) -> int:
    """P = (n_dims + 1)·k: n_dims·k stage composers + k final compositions.

    Parallel mode runs agg1..aggk; sequential runs c1..ck. n_dims=2 gives
    P = 3k (k INV + k DOM + k compositions); n_dims=3 gives 4k.
    """
    return (int(n_dims) + 1) * int(k)


class BudgetError(AssertionError):
    """The ledger did not land on the budget identity."""


@dataclass
class Entry:
    kind: str
    label: str
    usd: float = 0.0
    cached: bool = False
    attempts: int = 1


@dataclass
class Ledger:
    """Everything one mode spent on one task, recorded as it happens.

    `n_dims` is the number of learnable dimensions this mode scheduled: 2 for
    INV + DOM, 3 once PSY is active (a profile-backed run). It is carried on the
    ledger so `assert_identity` and the summary use the same arithmetic instead
    of re-deriving the dimension count at each call site.
    """

    mode: str
    task_id: str
    k: int
    n_dims: int = 2
    entries: list[Entry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.n_dims not in (2, 3):
            raise ValueError(
                f"Ledger.n_dims must be 2 (INV+DOM) or 3 (INV+DOM+PSY), got {self.n_dims!r}"
            )

    def rollout(self, label: str, usd: float = 0.0, *, cached: bool = False) -> None:
        self.entries.append(Entry("rollout", label, usd, cached))

    def session(
        self, label: str, usd: float = 0.0, *, cached: bool = False, attempts: int = 1
    ) -> None:
        self.entries.append(Entry("session", label, usd, cached, attempts=attempts))

    @property
    def R(self) -> int:
        return sum(1 for e in self.entries if e.kind == "rollout")

    @property
    def P(self) -> int:
        return sum(1 for e in self.entries if e.kind == "session")

    @property
    def usd(self) -> float:
        return round(sum(e.usd for e in self.entries), 6)

    @property
    def rollout_usd(self) -> float:
        return round(sum(e.usd for e in self.entries if e.kind == "rollout"), 6)

    @property
    def session_usd(self) -> float:
        return round(sum(e.usd for e in self.entries if e.kind == "session"), 6)

    def labels(self, kind: str) -> list[str]:
        return [e.label for e in self.entries if e.kind == kind]

    def assert_identity(self) -> None:
        """Raise unless the recorded entries show exactly R=(2+n_dims)·k and
        P=(n_dims+1)·k (default n_dims=2: R=4k, P=3k) with no duplicate label.
        Duplicates are checked before the counts, because a duplicate can satisfy them.
        """
        want_r, want_p = (
            expected_rollouts(self.k, self.n_dims),
            expected_sessions(self.k, self.n_dims),
        )
        rl, sl = self.labels("rollout"), self.labels("session")
        dupes = sorted(
            {label for label in rl if rl.count(label) > 1}
            | {label for label in sl if sl.count(label) > 1}
        )
        if not dupes and self.R == want_r and self.P == want_p:
            return
        detail = [
            f"{self.mode}-{self.k} {self.task_id}: "
            f"R={self.R} (want {want_r}), P={self.P} (want {want_p})",
            f"  rollouts: {', '.join(self.labels('rollout')) or '(none)'}",
            f"  sessions: {', '.join(self.labels('session')) or '(none)'}",
        ]
        if dupes:
            detail.append(
                f"  DUPLICATE labels: {dupes} -- a repeated label means two stages "
                f"wrote the same run id and one silently overwrote the other, so a "
                f"candidate the ledger counts was never actually produced"
            )
        raise BudgetError("\n".join(detail))

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "task_id": self.task_id,
            "k": self.k,
            "n_dims": self.n_dims,
            "R": self.R,
            "expected_R": expected_rollouts(self.k, self.n_dims),
            "P": self.P,
            "session_attempts": sum(
                entry.attempts for entry in self.entries if entry.kind == "session"
            ),
            "expected_P": expected_sessions(self.k, self.n_dims),
            "usd": self.usd,
            "rollout_usd": self.rollout_usd,
            "session_usd": self.session_usd,
            "rollouts": self.labels("rollout"),
            "sessions": self.labels("session"),
        }
