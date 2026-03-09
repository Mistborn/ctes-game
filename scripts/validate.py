#!/usr/bin/env python3
"""
validate.py — Standalone validation script for the orchestrator.

Runs all three layers of validation checks against the current codebase.
Can be run independently or called by the orchestrator.

Usage:
    uv run python scripts/validate.py                          # full validation
    uv run python scripts/validate.py --layer 1                # mechanical checks only
    uv run python scripts/validate.py --layer 2 --feature A1   # feature assertions only
    uv run python scripts/validate.py --baseline baseline.json  # include baseline regression
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).parent.parent.resolve()
BACKLOG_PATH = Path(__file__).parent / "backlog.json"


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


class ValidationResult:
    def __init__(self):
        self.checks: List[Dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if detail and not passed:
            for line in detail.strip().splitlines()[:5]:
                print(f"         {line}")

    @property
    def all_passed(self) -> bool:
        return all(c["passed"] for c in self.checks)

    @property
    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        failed = total - passed
        return f"{passed}/{total} passed, {failed} failed"


# ---------------------------------------------------------------------------
# Layer 1: Mechanical checks (no LLM needed)
# ---------------------------------------------------------------------------


def run_layer1(result: ValidationResult, baseline: Optional[Dict] = None, headless_runs: int = 10) -> None:
    """Run all mechanical validation checks."""
    print("\n--- Layer 1: Mechanical Checks ---")

    # 1. Ruff linter
    _check_ruff(result)

    # 2. Import check
    _check_imports(result)

    # 3. Serialization roundtrip
    _check_serialization(result)

    # 4. Architecture: no renderer imports in core/
    _check_architecture(result)

    # 5. Headless run completes without crash
    _check_headless(result, runs=headless_runs)

    # 6. Win rate floor (if headless succeeded)
    _check_win_rates(result, runs=headless_runs)

    # 7. Baseline regression (if baseline provided)
    if baseline:
        _check_baseline_regression(result, baseline, runs=headless_runs)


def _check_ruff(result: ValidationResult) -> None:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "."],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        passed = proc.returncode == 0
        detail = proc.stdout[:500] if not passed else ""
        result.add("ruff check", passed, detail)
    except Exception as exc:
        result.add("ruff check", False, str(exc))


def _check_imports(result: ValidationResult) -> None:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", "from game.core.engine import new_game; print('OK')"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        passed = proc.returncode == 0 and "OK" in proc.stdout
        detail = proc.stderr[:300] if not passed else ""
        result.add("import game.core.engine", passed, detail)
    except Exception as exc:
        result.add("import game.core.engine", False, str(exc))


def _check_serialization(result: ValidationResult) -> None:
    code = (
        "from game.core.engine import new_game; "
        "from game.core.state import GameState; "
        "import json; "
        "s = new_game(); "
        "j = s.to_json(); "
        "s2 = GameState.from_json(j); "
        "j2 = s2.to_json(); "
        "assert j == j2, 'Roundtrip mismatch'; "
        "print('OK')"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        passed = proc.returncode == 0 and "OK" in proc.stdout
        detail = proc.stderr[:300] if not passed else ""
        result.add("serialization roundtrip", passed, detail)
    except Exception as exc:
        result.add("serialization roundtrip", False, str(exc))


def _check_architecture(result: ValidationResult) -> None:
    """Ensure core/ files never import from renderer/."""
    core_dir = REPO_ROOT / "game" / "core"
    violations = []
    for py_file in core_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(r"from\s+game\.renderer", line) or re.search(r"import\s+game\.renderer", line):
                violations.append(f"{py_file.name}:{i}: {line.strip()}")
    passed = len(violations) == 0
    detail = "\n".join(violations[:5]) if violations else ""
    result.add("no renderer imports in core/", passed, detail)


def _check_headless(result: ValidationResult, runs: int = 10) -> None:
    """Run the headless balance report and check it completes."""
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from game.agent.playtest import STRATEGIES, run_strategy; "
                    f"[run_strategy(n, s, runs={runs}, max_ticks=1000) for n, s in STRATEGIES.items()]; "
                    "print('OK')"
                ),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        passed = proc.returncode == 0 and "OK" in proc.stdout
        detail = proc.stderr[:500] if not passed else ""
        result.add(f"headless run ({runs} runs x 4 strategies)", passed, detail)
    except Exception as exc:
        result.add("headless run", False, str(exc))


def _check_win_rates(result: ValidationResult, runs: int = 10) -> None:
    """Check all strategies maintain win_rate >= 0.5."""
    code = (
        "import json; "
        "from game.agent.playtest import STRATEGIES, run_strategy; "
        "results = {}; "
        f"[results.__setitem__(n, run_strategy(n, s, runs={runs}, max_ticks=1000)) for n, s in STRATEGIES.items()]; "
        "print(json.dumps({n: r['won']['mean'] for n, r in results.items()}))"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            result.add("win rate floor (>=0.5)", False, proc.stderr[:300])
            return

        win_rates = json.loads(proc.stdout.strip())
        failed = [f"{name}: {rate:.2f}" for name, rate in win_rates.items() if rate < 0.5]
        passed = len(failed) == 0
        detail = "Below 0.5: " + ", ".join(failed) if failed else ""
        result.add("win rate floor (>=0.5)", passed, detail)
    except Exception as exc:
        result.add("win rate floor (>=0.5)", False, str(exc))


def _check_baseline_regression(result: ValidationResult, baseline: Dict, runs: int = 10) -> None:
    """Check no strategy regresses by more than 30% vs baseline."""
    code = (
        "import json; "
        "from game.agent.playtest import STRATEGIES, run_strategy; "
        "results = {}; "
        f"[results.__setitem__(n, run_strategy(n, s, runs={runs}, max_ticks=1000)) for n, s in STRATEGIES.items()]; "
        "print(json.dumps(results))"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            result.add("baseline regression (<30%)", False, proc.stderr[:300])
            return

        current = json.loads(proc.stdout.strip())
        regressions = []
        for name in baseline:
            if name not in current:
                continue
            for metric in ["won", "ticks_survived", "gold_earned"]:
                base_val = baseline[name].get(metric, {}).get("mean", 0)
                curr_val = current[name].get(metric, {}).get("mean", 0)
                if base_val > 0 and curr_val < base_val * 0.7:
                    regressions.append(f"{name}/{metric}: {base_val:.2f} -> {curr_val:.2f}")

        passed = len(regressions) == 0
        detail = "\n".join(regressions[:5]) if regressions else ""
        result.add("baseline regression (<30%)", passed, detail)
    except Exception as exc:
        result.add("baseline regression (<30%)", False, str(exc))


# ---------------------------------------------------------------------------
# Layer 2: Feature-specific assertions
# ---------------------------------------------------------------------------


def run_layer2(result: ValidationResult, feature_id: str) -> None:
    """Run acceptance criteria for a specific backlog feature."""
    print(f"\n--- Layer 2: Feature Assertions ({feature_id}) ---")

    backlog = json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))
    feature = next((f for f in backlog if f["id"] == feature_id), None)
    if feature is None:
        result.add(f"feature {feature_id} exists in backlog", False, "Not found")
        return

    for i, assertion in enumerate(feature.get("acceptance_criteria", [])):
        name = f"{feature_id} assertion {i + 1}"
        try:
            proc = subprocess.run(
                [sys.executable, "-c", assertion],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            passed = proc.returncode == 0
            detail = proc.stderr[:300] if not passed else ""
            result.add(name, passed, detail)
        except Exception as exc:
            result.add(name, False, str(exc))


# ---------------------------------------------------------------------------
# Layer 3: LLM evaluation (stub — called by orchestrator with LLM client)
# ---------------------------------------------------------------------------


def format_for_llm_eval(
    feature: Dict,
    diff_summary: str,
    baseline_table: str,
    new_metrics: str,
    assertion_results: List[Dict],
) -> str:
    """Format validation data for the LLM evaluator."""
    assertions_text = "\n".join(f"  [{'PASS' if a['passed'] else 'FAIL'}] {a['name']}" for a in assertion_results)
    return (
        f"## Feature: {feature['title']} ({feature['id']})\n\n"
        f"## Spec\n{feature['spec'][:1000]}\n\n"
        f"## Git Diff Summary\n{diff_summary[:2000]}\n\n"
        f"## Baseline Metrics\n{baseline_table}\n\n"
        f"## New Metrics\n{new_metrics}\n\n"
        f"## Acceptance Criteria Results\n{assertions_text}\n\n"
        "## Question\n"
        "Does the feature exist and work as specified? Are metrics stable? "
        "Is code quality acceptable? Respond EXACTLY as:\n"
        "DECISION: merge | request_changes | decline\n"
        "REASONING: <2-4 sentences>\n"
        "REVISION_INSTRUCTIONS: <only if request_changes>"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate ctes-game codebase.")
    parser.add_argument("--layer", type=int, choices=[1, 2, 3], help="Run only this layer")
    parser.add_argument("--feature", type=str, help="Feature ID for layer 2 assertions")
    parser.add_argument("--baseline", type=str, help="Path to baseline JSON for regression check")
    parser.add_argument("--runs", type=int, default=10, help="Headless runs for validation (default: 10)")
    args = parser.parse_args()

    result = ValidationResult()

    baseline = None
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))

    if args.layer is None or args.layer == 1:
        run_layer1(result, baseline=baseline, headless_runs=args.runs)

    if args.layer is None or args.layer == 2:
        if args.feature:
            run_layer2(result, args.feature)
        elif args.layer == 2:
            print("\n--- Layer 2: Skipped (no --feature specified) ---")

    if args.layer == 3:
        print("\n--- Layer 3: LLM evaluation must be run via orchestrator ---")

    print(f"\n{'=' * 50}")
    print(f"  Validation: {result.summary}")
    print(f"{'=' * 50}\n")

    sys.exit(0 if result.all_passed else 1)


if __name__ == "__main__":
    main()
