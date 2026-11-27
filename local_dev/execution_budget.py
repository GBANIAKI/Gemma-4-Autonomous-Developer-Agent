"""Shared execution limits for the main agent and delegated analyzer."""

import threading
import time


class ExecutionBudget:
    """Enforce shared tool-call and wall-clock limits."""

    def __init__(
        self,
        max_total_calls=8,
        max_exploratory_calls=5,
        max_verification_calls=3,
        max_seconds=300,
        clock=time.monotonic,
    ):
        if max_total_calls < 1:
            raise ValueError("max_total_calls must be positive")
        if max_exploratory_calls < 0:
            raise ValueError("max_exploratory_calls cannot be negative")
        if max_verification_calls < 0:
            raise ValueError("max_verification_calls cannot be negative")
        if max_seconds <= 0:
            raise ValueError("max_seconds must be positive")

        if max_exploratory_calls + max_verification_calls < max_total_calls:
            raise ValueError(
                "Category limits must cover the total call limit"
            )

        self.max_total_calls = max_total_calls
        self.max_exploratory_calls = max_exploratory_calls
        self.max_verification_calls = max_verification_calls
        self.max_seconds = max_seconds

        self._clock = clock
        self._started_at = clock()
        self._exploratory_calls = 0
        self._verification_calls = 0
        self._lock = threading.Lock()

    def remaining_seconds(self):
        """Return remaining wall-clock time, never below zero."""
        elapsed = self._clock() - self._started_at
        return max(0.0, self.max_seconds - elapsed)

    def reserve(self, category="exploratory"):
        """
        Reserve one tool call before dispatch.

        Categories:
        - exploratory: agent, delegation, and analyzer tools
        - verification: targeted tests and patch verification
        """
        if category not in ("exploratory", "verification"):
            raise ValueError(f"Unknown budget category: {category}")

        with self._lock:
            if self.remaining_seconds() <= 0:
                return False

            total = (
                self._exploratory_calls
                + self._verification_calls
            )

            if total >= self.max_total_calls:
                return False

            if (
                category == "exploratory"
                and self._exploratory_calls >= self.max_exploratory_calls
            ):
                return False

            if (
                category == "verification"
                and self._verification_calls >= self.max_verification_calls
            ):
                return False

            if category == "exploratory":
                self._exploratory_calls += 1
            else:
                self._verification_calls += 1

            return True

    def timeout_for(self, maximum_seconds):
        """Return a positive timeout bounded by the remaining deadline."""
        if maximum_seconds <= 0:
            raise ValueError("maximum_seconds must be positive")

        remaining = self.remaining_seconds()
        if remaining <= 0:
            return 0

        return min(float(maximum_seconds), remaining)

    def snapshot(self):
        """Return a serializable view of current budget usage."""
        with self._lock:
            exploratory = self._exploratory_calls
            verification = self._verification_calls

        total = exploratory + verification
        remaining = self.remaining_seconds()

        return {
            "total_calls": total,
            "max_total_calls": self.max_total_calls,
            "exploratory_calls": exploratory,
            "max_exploratory_calls": self.max_exploratory_calls,
            "verification_calls": verification,
            "max_verification_calls": self.max_verification_calls,
            "remaining_seconds": round(remaining, 3),
            "max_seconds": self.max_seconds,
            "exhausted": (
                total >= self.max_total_calls
                or remaining <= 0
            ),
        }