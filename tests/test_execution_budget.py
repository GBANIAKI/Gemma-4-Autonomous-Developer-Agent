import pytest

from local_dev.execution_budget import ExecutionBudget
from concurrent.futures import ThreadPoolExecutor


def test_default_budget_limits():
    budget = ExecutionBudget()

    snapshot = budget.snapshot()

    assert snapshot["max_total_calls"] == 8
    assert snapshot["max_exploratory_calls"] == 5
    assert snapshot["max_verification_calls"] == 3
    assert snapshot["total_calls"] == 0


def test_exploratory_call_limit():
    budget = ExecutionBudget()

    for _ in range(5):
        assert budget.reserve("exploratory") is True

    assert budget.reserve("exploratory") is False
    assert budget.snapshot()["exploratory_calls"] == 5


def test_verification_call_limit():
    budget = ExecutionBudget()

    for _ in range(3):
        assert budget.reserve("verification") is True

    assert budget.reserve("verification") is False
    assert budget.snapshot()["verification_calls"] == 3


def test_shared_total_call_limit():
    budget = ExecutionBudget()

    for _ in range(5):
        assert budget.reserve("exploratory") is True

    for _ in range(3):
        assert budget.reserve("verification") is True

    assert budget.reserve("verification") is False
    assert budget.snapshot()["total_calls"] == 8


def test_categories_share_one_budget():
    budget = ExecutionBudget(
        max_total_calls=4,
        max_exploratory_calls=3,
        max_verification_calls=2,
    )

    assert budget.reserve("exploratory") is True
    assert budget.reserve("exploratory") is True
    assert budget.reserve("verification") is True
    assert budget.reserve("exploratory") is True

    assert budget.reserve("verification") is False
    assert budget.snapshot()["total_calls"] == 4


def test_remaining_time_and_timeout():
    current_time = [100.0]

    budget = ExecutionBudget(
        max_seconds=300,
        clock=lambda: current_time[0],
    )

    assert budget.remaining_seconds() == 300
    assert budget.timeout_for(120) == 120

    current_time[0] = 250.0

    assert budget.remaining_seconds() == 150
    assert budget.timeout_for(120) == 120

    current_time[0] = 290.0

    assert budget.remaining_seconds() == 110
    assert budget.timeout_for(120) == 110


def test_deadline_prevents_new_reservations():
    current_time = [100.0]

    budget = ExecutionBudget(
        max_seconds=300,
        clock=lambda: current_time[0],
    )

    current_time[0] = 400.0

    assert budget.reserve("exploratory") is False
    assert budget.snapshot()["exhausted"] is True


def test_invalid_category_is_rejected():
    budget = ExecutionBudget()

    with pytest.raises(ValueError):
        budget.reserve("unknown")


def test_invalid_budget_configuration_is_rejected():
    with pytest.raises(ValueError):
        ExecutionBudget(max_total_calls=0)

    with pytest.raises(ValueError):
        ExecutionBudget(max_seconds=0)

def test_concurrent_reservations_never_exceed_total_limit():
    budget = ExecutionBudget()

    def reserve_call(_):
        return budget.reserve("exploratory")

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(reserve_call, range(100)))

    assert sum(results) == 5
    assert budget.snapshot()["total_calls"] == 5
    assert budget.snapshot()["exploratory_calls"] == 5