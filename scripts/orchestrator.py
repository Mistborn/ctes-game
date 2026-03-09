#!/usr/bin/env python3
"""
orchestrator.py — AI agent loop for continuous game improvement.

Reads features from backlog.json (dependency-ordered), spawns a Claude sub-agent
in an isolated git worktree for each one, validates with 3 layers (mechanical,
feature-specific, LLM evaluation), and auto-merges via GitHub PR.

Usage:
    export PATH="$PATH:/c/Users/me/.local/bin:/c/Program Files/GitHub CLI"
    uv run python scripts/orchestrator.py --max-iterations 18
    uv run python scripts/orchestrator.py --resume
    uv run python scripts/orchestrator.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.resolve()
STATE_FILE = Path(__file__).parent / "orchestrator_state.json"
BACKLOG_FILE = Path(__file__).parent / "backlog.json"
WORKTREES_DIR = REPO_ROOT / ".claude" / "worktrees"
MODEL = "claude-opus-4-6"
EVAL_MODEL = "claude-sonnet-4-6"
MAX_REVISIONS = 2
DEFAULT_MAX_ITER = 18
DEFAULT_BASELINE_RUNS = 20
VALIDATION_RUNS = 10
SUBAGENT_TIMEOUT = 1800  # 30 minutes

# ---------------------------------------------------------------------------
# Orchestrator state (persisted to JSON after every iteration)
# ---------------------------------------------------------------------------


@dataclass
class OrchestratorState:
    iteration: int = 0
    baseline: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)
    revision_count: int = 0
    completed_features: List[str] = field(default_factory=list)
    current_feature_id: Optional[str] = None


def load_state() -> Optional[OrchestratorState]:
    if not STATE_FILE.exists():
        return None
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    s = OrchestratorState()
    s.iteration = data.get("iteration", 0)
    s.baseline = data.get("baseline", {})
    s.history = data.get("history", [])
    s.revision_count = data.get("revision_count", 0)
    s.completed_features = data.get("completed_features", [])
    s.current_feature_id = data.get("current_feature_id")
    return s


def save_state(state: OrchestratorState) -> None:
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(
            {
                "iteration": state.iteration,
                "baseline": state.baseline,
                "history": state.history,
                "revision_count": state.revision_count,
                "completed_features": state.completed_features,
                "current_feature_id": state.current_feature_id,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    tmp.replace(STATE_FILE)


# ---------------------------------------------------------------------------
# Backlog management
# ---------------------------------------------------------------------------


def load_backlog() -> List[Dict]:
    return json.loads(BACKLOG_FILE.read_text(encoding="utf-8"))


def save_backlog(backlog: List[Dict]) -> None:
    BACKLOG_FILE.write_text(json.dumps(backlog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def select_next_feature(backlog: List[Dict], completed: List[str]) -> Optional[Dict]:
    """Select highest-priority pending feature whose dependencies are all completed."""
    for feature in sorted(backlog, key=lambda f: f["priority"]):
        if feature["status"] != "pending":
            continue
        deps = feature.get("depends_on", [])
        if all(d in completed for d in deps):
            return feature
    return None


def update_backlog_status(backlog: List[Dict], feature_id: str, status: str) -> None:
    for f in backlog:
        if f["id"] == feature_id:
            f["status"] = status
            break


# ---------------------------------------------------------------------------
# Baseline computation
# ---------------------------------------------------------------------------


def compute_baseline(runs: int = DEFAULT_BASELINE_RUNS) -> Dict[str, Any]:
    print(f"\n  Computing baseline ({runs} runs x 4 strategies)...")
    sys.path.insert(0, str(REPO_ROOT))
    from game.agent.playtest import STRATEGIES, run_strategy  # type: ignore[import]

    baseline: Dict[str, Any] = {}
    for name, strategy in STRATEGIES.items():
        print(f"    {name}...", end=" ", flush=True)
        result = run_strategy(name, strategy, runs=runs, max_ticks=1000)
        baseline[name] = result
        win_rate = result.get("won", {}).get("mean", 0.0)
        print(f"win_rate={win_rate:.2f}")
    return baseline


def _format_baseline_table(baseline: Dict[str, Any]) -> str:
    lines = [
        "| Strategy | Win Rate | Ticks (mean) | Gold (mean) | Starvations (mean) |",
        "|----------|----------|--------------|-------------|-------------------|",
    ]
    for name, stats in baseline.items():
        won = stats.get("won", {}).get("mean", 0.0)
        ticks = stats.get("ticks_survived", {}).get("mean", 0.0)
        gold = stats.get("gold_earned", {}).get("mean", 0.0)
        starve = stats.get("starvation_events", {}).get("mean", 0.0)
        lines.append(f"| {name} | {won:.2f} | {ticks:.0f} | {gold:.1f} | {starve:.1f} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Git worktree management
# ---------------------------------------------------------------------------


def make_worktree(branch_name: str) -> Path:
    worktree_path = WORKTREES_DIR / branch_name
    # Remove stale worktree if present
    if worktree_path.exists():
        subprocess.run(
            ["git", "worktree", "remove", str(worktree_path), "--force"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
    subprocess.run(
        ["git", "branch", "-D", branch_name],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", branch_name],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return worktree_path


def remove_worktree(branch_name: str) -> None:
    worktree_path = WORKTREES_DIR / branch_name
    subprocess.run(
        ["git", "worktree", "remove", str(worktree_path), "--force"],
        cwd=REPO_ROOT,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Agent task file — enhanced with full feature spec
# ---------------------------------------------------------------------------

_AGENT_TASK_TEMPLATE = """\
# Agent Task — Feature {feature_id}: {title}

## Feature Specification
{spec}

## Files to Touch
{files_list}

## Architecture Rules (NON-NEGOTIABLE)
1. `game/core/` must NEVER import from `game/renderer/`
2. ALL numeric constants must go in `game/core/config.py`
3. GameState must remain JSON-serializable — update `to_dict()` AND `from_dict()` for every new field
4. Follow existing code patterns exactly — match naming, style, structure
5. Run `ruff format` + `ruff check` before committing
6. Run headless balance report and include output in OUTCOME.md

## Implementation Order
config.py → entities.py → state.py → engine.py → playtest.py → [display.py if needed]

## Acceptance Criteria (machine-checked)
{acceptance_criteria}

## Baseline Metrics
{baseline_table}

## After Implementation
1. Run: uv run python main.py --headless --runs 10
2. Run: uv run python -m ruff check .
3. Verify serialization roundtrip:
   python -c "from game.core.engine import new_game; \\
   from game.core.state import GameState; import json; \\
   s = new_game(); j = s.to_json(); s2 = GameState.from_json(j); \\
   assert s.to_json() == s2.to_json(); print('OK')"
4. Commit incrementally with descriptive messages (don't wait until the end for large changes)
5. Push and create PR via gh:
   git push -u origin {branch_name}
   export PATH="$PATH:/c/Users/me/.local/bin:/c/Program Files/GitHub CLI"
   gh pr create --title "{pr_title}" --body "..."
6. Write OUTCOME.md in the repo root with the schema below. This is MANDATORY.

## OUTCOME.md Schema
```
# Outcome
## Summary
## Changes Made
## Files Modified
## Metrics After Change
## Delta vs Baseline
## Acceptance Criteria Results
## PR URL
## Status
(success | partial | failure)
## Notes
```

## Revision Request
{revision_notes}
"""

_SUBAGENT_PROMPT = (
    "You are implementing a specific feature for 'Kingdoms of the Forgotten', "
    "a medieval colony builder in Python. Read AGENT_TASK.md in the current directory "
    "completely before writing any code. Follow the implementation order strictly: "
    "config.py → entities.py → state.py → engine.py → playtest.py → display.py. "
    "Architecture rules: game/core/ never imports renderer/, all constants in config.py, "
    "GameState must remain JSON-serializable (update to_dict AND from_dict for every new field). "
    "Run ruff format + ruff check before committing. "
    "Run the headless balance report after changes and include output in OUTCOME.md. "
    "Verify serialization roundtrip: "
    'python -c "from game.core.engine import new_game; from game.core.state import GameState; '
    "import json; s = new_game(); j = s.to_json(); s2 = GameState.from_json(j); "
    "assert s.to_json() == s2.to_json(); print('OK')\" "
    "Commit your changes with a descriptive message, push, and create a GitHub PR via gh. "
    "Write OUTCOME.md with all required sections — the orchestrator cannot proceed without it. "
    "Do not modify AGENT_TASK.md. "
    r'PATH: export PATH="$PATH:/c/Users/me/.local/bin:/c/Program Files/GitHub CLI"'
)


def write_agent_task(
    worktree_path: Path,
    feature: Dict,
    baseline: Dict[str, Any],
    branch_name: str,
    revision_notes: str = "",
) -> None:
    files_list = "\n".join(f"- `{f}`" for f in feature.get("files_to_touch", []))
    acceptance_list = "\n".join(f'- `python -c "{a}"`' for a in feature.get("acceptance_criteria", []))
    pr_title = f"feat({feature['category']}): {feature['title']}"

    content = _AGENT_TASK_TEMPLATE.format(
        feature_id=feature["id"],
        title=feature["title"],
        spec=feature["spec"],
        files_list=files_list,
        acceptance_criteria=acceptance_list,
        baseline_table=_format_baseline_table(baseline),
        branch_name=branch_name,
        pr_title=pr_title[:70],
        revision_notes=revision_notes or "None — this is the first attempt.",
    )
    (worktree_path / "AGENT_TASK.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Sub-agent runner
# ---------------------------------------------------------------------------


def _find_claude() -> str:
    cmd = shutil.which("claude")
    if cmd:
        return cmd
    candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Claude" / "claude.exe"
    if candidate.exists():
        return str(candidate)
    raise RuntimeError("claude CLI not found. Install Claude Code and ensure `claude` is on your PATH.")


def run_subagent(worktree_path: Path) -> tuple[int, str]:
    claude_cmd = _find_claude()

    env = os.environ.copy()
    extra = [r"C:\Users\me\.local\bin", r"C:\Program Files\GitHub CLI"]
    sep = ";" if sys.platform == "win32" else ":"
    env["PATH"] = sep.join(extra) + sep + env.get("PATH", "")

    try:
        result = subprocess.run(
            [claude_cmd, "-p", _SUBAGENT_PROMPT, "--dangerously-skip-permissions"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            timeout=SUBAGENT_TIMEOUT,
            env=env,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output[-3000:]
    except subprocess.TimeoutExpired as exc:
        out = ""
        if exc.stdout:
            out += exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode(errors="replace")
        if exc.stderr:
            out += exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode(errors="replace")
        return -1, f"TIMEOUT after {SUBAGENT_TIMEOUT}s\n{out[-2000:]}"


# ---------------------------------------------------------------------------
# Strategy update sub-agent
# ---------------------------------------------------------------------------

_STRATEGY_UPDATE_PROMPT = (
    "You are updating the headless playtest strategies in game/agent/playtest.py. "
    "A new game feature has been merged. Read the recent git log to understand what changed. "
    "Update the 4 strategies (food_first, production_rush, balanced, gold_rush) to exercise "
    "the new mechanic where appropriate. Do NOT break existing strategy logic — only add to it. "
    "If the new feature adds a building, add build + staffing logic. "
    "If it adds a resource, consider how strategies should produce/consume it. "
    "Run the headless balance report: uv run python main.py --headless --runs 10 "
    "Ensure all 4 strategies still win. Commit, push, and create a PR. "
    "Write OUTCOME.md with the results. "
    r'PATH: export PATH="$PATH:/c/Users/me/.local/bin:/c/Program Files/GitHub CLI"'
)


def run_strategy_update_agent(branch_name: str) -> tuple[int, str]:
    """Spawn a follow-up sub-agent to update playtest strategies after a feature merge."""
    worktree_path = make_worktree(branch_name)
    claude_cmd = _find_claude()

    env = os.environ.copy()
    extra = [r"C:\Users\me\.local\bin", r"C:\Program Files\GitHub CLI"]
    sep = ";" if sys.platform == "win32" else ":"
    env["PATH"] = sep.join(extra) + sep + env.get("PATH", "")

    try:
        result = subprocess.run(
            [claude_cmd, "-p", _STRATEGY_UPDATE_PROMPT, "--dangerously-skip-permissions"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            timeout=SUBAGENT_TIMEOUT,
            env=env,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output[-3000:]
    except subprocess.TimeoutExpired as exc:
        out = ""
        if exc.stdout:
            out += exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode(errors="replace")
        if exc.stderr:
            out += exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode(errors="replace")
        return -1, f"TIMEOUT\n{out[-2000:]}"


# ---------------------------------------------------------------------------
# OUTCOME.md parser
# ---------------------------------------------------------------------------


def parse_outcome(worktree_path: Path) -> Optional[Dict]:
    outcome_file = worktree_path / "OUTCOME.md"
    if not outcome_file.exists():
        return None
    text = outcome_file.read_text(encoding="utf-8")

    sections: Dict[str, str] = {}
    current: Optional[str] = None
    current_lines: List[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(current_lines).strip()
            current = line[3:].strip().lower().replace(" ", "_")
            current_lines = []
        elif current is not None:
            current_lines.append(line)
    if current is not None:
        sections[current] = "\n".join(current_lines).strip()

    pr_url = None
    url_match = re.search(r"https://github\.com/\S+/pull/\d+", sections.get("pr_url", ""))
    if url_match:
        pr_url = url_match.group(0)

    return {
        "summary": sections.get("summary", ""),
        "changes_made": sections.get("changes_made", ""),
        "metrics_text": sections.get("metrics_after_change", ""),
        "delta_text": sections.get("delta_vs_baseline", ""),
        "pr_url": pr_url,
        "status": sections.get("status", "unknown").split()[0].lower(),
        "notes": sections.get("notes", ""),
        "raw_text": text,
    }


# ---------------------------------------------------------------------------
# Validation — 3-layer system
# ---------------------------------------------------------------------------


def run_validation_layer1(worktree_path: Path) -> tuple[bool, List[str]]:
    """
    Layer 1: Mechanical checks. Returns (all_passed, list_of_failure_messages).
    Runs in the worktree directory to validate the sub-agent's changes.
    """
    failures: List[str] = []

    # 1. Ruff check
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        failures.append(f"ruff check failed:\n{proc.stdout[:300]}")

    # 2. Import check
    proc = subprocess.run(
        [sys.executable, "-c", "from game.core.engine import new_game; print('OK')"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0 or "OK" not in proc.stdout:
        failures.append(f"import check failed:\n{proc.stderr[:300]}")

    # 3. Serialization roundtrip
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from game.core.engine import new_game; "
                "from game.core.state import GameState; "
                "import json; "
                "s = new_game(); j = s.to_json(); "
                "s2 = GameState.from_json(j); "
                "assert s.to_json() == s2.to_json(), 'Mismatch'; "
                "print('OK')"
            ),
        ],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0 or "OK" not in proc.stdout:
        failures.append(f"serialization roundtrip failed:\n{proc.stderr[:300]}")

    # 4. Architecture check
    core_dir = worktree_path / "game" / "core"
    for py_file in core_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(r"from\s+game\.renderer", line) or re.search(r"import\s+game\.renderer", line):
                failures.append(f"renderer import in core: {py_file.name}:{i}: {line.strip()}")

    # 5. Headless run
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from game.agent.playtest import STRATEGIES, run_strategy; "
                f"results = {{}}; "
                f"[results.__setitem__(n, run_strategy(n, s, runs={VALIDATION_RUNS}, max_ticks=1000)) "
                "for n, s in STRATEGIES.items()]; "
                "import json; print(json.dumps(results))"
            ),
        ],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        failures.append(f"headless run crashed:\n{proc.stderr[:500]}")
    else:
        try:
            results = json.loads(proc.stdout.strip())
            for name, stats in results.items():
                win_rate = stats.get("won", {}).get("mean", 0.0)
                if win_rate < 0.5:
                    failures.append(f"strategy {name} win_rate={win_rate:.2f} (below 0.5 floor)")
        except (json.JSONDecodeError, ValueError) as exc:
            failures.append(f"could not parse headless results: {exc}")

    return len(failures) == 0, failures


def run_validation_layer2(worktree_path: Path, feature: Dict) -> tuple[bool, List[str]]:
    """Layer 2: Feature-specific acceptance criteria."""
    failures: List[str] = []
    for assertion in feature.get("acceptance_criteria", []):
        proc = subprocess.run(
            [sys.executable, "-c", assertion],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            failures.append(f"assertion failed: {assertion}\n{proc.stderr[:200]}")
    return len(failures) == 0, failures


def run_validation_layer3(
    client: anthropic.Anthropic,
    feature: Dict,
    outcome: Dict,
    baseline: Dict[str, Any],
    layer1_failures: List[str],
    layer2_failures: List[str],
) -> tuple[str, str, str]:
    """
    Layer 3: LLM evaluation. Returns (decision, reasoning, revision_instructions).
    Only called if layers 1-2 pass.
    """
    l1_status = "ALL PASSED" if not layer1_failures else f"FAILED: {'; '.join(layer1_failures[:3])}"
    l2_status = "ALL PASSED" if not layer2_failures else f"FAILED: {'; '.join(layer2_failures[:3])}"

    user = (
        f"## Feature: {feature['title']} ({feature['id']})\n\n"
        f"## Spec\n{feature['spec'][:1500]}\n\n"
        f"## Baseline Metrics\n{_format_baseline_table(baseline)}\n\n"
        f"## Outcome (OUTCOME.md)\n{outcome['raw_text'][:3000]}\n\n"
        f"## Layer 1 (Mechanical): {l1_status}\n"
        f"## Layer 2 (Assertions): {l2_status}\n"
    )

    system = (
        "You are evaluating a game feature implementation. Decide: merge, request_changes, or decline.\n"
        "Merge if: the feature exists and works as specified, metrics are stable (no strategy dropped "
        "below 0.5 win rate), and code quality is acceptable.\n"
        "Request changes if: the direction is sound but there's a specific fixable flaw.\n"
        "Decline if: the feature is broken, metrics regressed badly, or architecture rules were violated.\n"
        "Respond EXACTLY as:\n"
        "DECISION: merge | request_changes | decline\n"
        "REASONING: <2-4 sentences>\n"
        "REVISION_INSTRUCTIONS: <specific instructions — only if request_changes, otherwise omit>"
    )

    text = call_llm(client, system, user, model=EVAL_MODEL)

    decision_match = re.search(r"DECISION:\s*(merge|request_changes|decline)", text, re.IGNORECASE)
    decision = decision_match.group(1).lower() if decision_match else "decline"

    reasoning_match = re.search(r"REASONING:\s*(.+?)(?=\nREVISION_INSTRUCTIONS:|$)", text, re.DOTALL)
    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

    revision_match = re.search(r"REVISION_INSTRUCTIONS:\s*(.+?)$", text, re.DOTALL)
    revision_instructions = revision_match.group(1).strip() if revision_match else ""

    return decision, reasoning, revision_instructions


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------


def call_llm(client: anthropic.Anthropic, system: str, user: str, model: str = MODEL) -> str:
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text.strip()
        except anthropic.APIError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    return ""


# ---------------------------------------------------------------------------
# PR operations
# ---------------------------------------------------------------------------


def merge_pr(pr_url: str) -> bool:
    gh_cmd = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
    result = subprocess.run(
        [gh_cmd, "pr", "merge", pr_url, "--squash", "--delete-branch", "--yes"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  WARNING: gh pr merge failed: {result.stderr[:300]}")
        return False
    return True


def pull_main() -> None:
    subprocess.run(["git", "pull", "--ff-only"], cwd=REPO_ROOT, capture_output=True)


# ---------------------------------------------------------------------------
# Baseline regression check against stored baseline
# ---------------------------------------------------------------------------


def check_baseline_regression(new_results: Dict, baseline: Dict) -> List[str]:
    """Check no strategy regresses >30% on key metrics."""
    regressions = []
    for name in baseline:
        if name not in new_results:
            continue
        for metric in ["won", "ticks_survived", "gold_earned"]:
            base_val = baseline[name].get(metric, {}).get("mean", 0)
            new_val = new_results[name].get(metric, {}).get("mean", 0)
            if base_val > 0 and new_val < base_val * 0.7:
                regressions.append(f"{name}/{metric}: {base_val:.2f} -> {new_val:.2f} (>{30}% regression)")
    return regressions


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Backlog-driven AI orchestrator for ctes-game.")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITER,
        help=f"Max features to implement (default: {DEFAULT_MAX_ITER})",
    )
    parser.add_argument(
        "--baseline-runs",
        type=int,
        default=DEFAULT_BASELINE_RUNS,
        help=f"Runs per strategy for baseline (default: {DEFAULT_BASELINE_RUNS})",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from saved orchestrator_state.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Select feature + write AGENT_TASK.md, but don't spawn sub-agent",
    )
    args = parser.parse_args()

    client = anthropic.Anthropic()

    # Load or create state
    if args.resume:
        state = load_state()
        if state is None:
            print("No saved state found — starting fresh.")
            state = OrchestratorState()
        else:
            print(f"Resuming from iteration {state.iteration} ({len(state.completed_features)} features done).")
    else:
        state = OrchestratorState()

    # Compute baseline if needed
    if not state.baseline:
        state.baseline = compute_baseline(runs=args.baseline_runs)
        save_state(state)

    print(f"\nBaseline ready. Starting loop (max {args.max_iterations} features).")
    print(f"Completed features: {state.completed_features or '(none)'}")

    backlog = load_backlog()

    while state.iteration < args.max_iterations:
        print(f"\n{'=' * 72}")
        print(f"  Iteration {state.iteration + 1} / {args.max_iterations}")
        print("=" * 72)

        # Select next feature
        feature = select_next_feature(backlog, state.completed_features)
        if feature is None:
            print("  No eligible features remaining in backlog. Stopping.")
            break

        feature_id = feature["id"]
        state.current_feature_id = feature_id
        print(f"\n  Feature: [{feature_id}] {feature['title']} (priority {feature['priority']})")
        print(f"  Category: {feature['category']}")
        print(f"  Depends on: {feature.get('depends_on', []) or '(none)'}")

        # Dry run: write task and exit
        if args.dry_run:
            branch = f"agent/feature-{feature_id.lower()}"
            worktree_path = make_worktree(branch)
            write_agent_task(worktree_path, feature, state.baseline, branch)
            print(f"\n  Dry run: wrote AGENT_TASK.md to {worktree_path}")
            print(f"  Branch: {branch}")
            remove_worktree(branch)
            break

        # Mark in-progress
        update_backlog_status(backlog, feature_id, "in_progress")
        save_backlog(backlog)

        state.revision_count = 0
        revision_instructions = ""
        feature_merged = False

        while True:
            rev_suffix = f"-rev-{state.revision_count}" if state.revision_count > 0 else ""
            branch = f"agent/feature-{feature_id.lower()}{rev_suffix}"
            print(f"\n  Branch: {branch}")

            try:
                worktree_path = make_worktree(branch)
            except subprocess.CalledProcessError as exc:
                print(f"  ERROR creating worktree: {exc}")
                break

            write_agent_task(
                worktree_path,
                feature,
                state.baseline,
                branch,
                revision_notes=revision_instructions,
            )

            print("  Running sub-agent (may take up to 30 min)...")
            returncode, agent_output = run_subagent(worktree_path)
            if returncode != 0:
                print(f"  Sub-agent exited with code {returncode}.")
                if returncode == -1:
                    print(f"  {agent_output[:200]}")

            # Parse outcome
            outcome = parse_outcome(worktree_path)
            if outcome is None:
                print("  No OUTCOME.md found — declining.")
                record = {
                    "iteration": state.iteration,
                    "feature_id": feature_id,
                    "branch": branch,
                    "revision": state.revision_count,
                    "decision": "decline",
                    "llm_reasoning": "Sub-agent produced no OUTCOME.md.",
                }
                state.history.append(record)
                save_state(state)
                remove_worktree(branch)
                break

            # --- Layer 1: Mechanical validation ---
            print("\n  --- Layer 1: Mechanical Validation ---")
            l1_passed, l1_failures = run_validation_layer1(worktree_path)
            for f in l1_failures:
                print(f"    FAIL: {f[:100]}")
            if l1_passed:
                print("    All mechanical checks passed.")

            # --- Layer 2: Feature assertions ---
            print("\n  --- Layer 2: Feature Assertions ---")
            l2_passed, l2_failures = run_validation_layer2(worktree_path, feature)
            for f in l2_failures:
                print(f"    FAIL: {f[:100]}")
            if l2_passed:
                print("    All assertions passed.")

            # --- Layer 3: LLM evaluation (only if L1+L2 pass) ---
            if l1_passed and l2_passed:
                print("\n  --- Layer 3: LLM Evaluation ---")
                decision, reasoning, revision_instructions = run_validation_layer3(
                    client, feature, outcome, state.baseline, l1_failures, l2_failures
                )
            elif not l1_passed:
                decision = "request_changes" if state.revision_count < MAX_REVISIONS else "decline"
                reasoning = f"Layer 1 failed: {'; '.join(l1_failures[:2])}"
                revision_instructions = f"Fix these mechanical issues: {'; '.join(l1_failures[:3])}"
            else:
                decision = "request_changes" if state.revision_count < MAX_REVISIONS else "decline"
                reasoning = f"Layer 2 failed: {'; '.join(l2_failures[:2])}"
                revision_instructions = f"Fix these assertion failures: {'; '.join(l2_failures[:3])}"

            print(f"  Decision: {decision.upper()}")
            print(f"  Reasoning: {reasoning[:120]}")

            record = {
                "iteration": state.iteration,
                "feature_id": feature_id,
                "branch": branch,
                "revision": state.revision_count,
                "pr_url": outcome.get("pr_url"),
                "decision": decision,
                "llm_reasoning": reasoning,
                "l1_passed": l1_passed,
                "l2_passed": l2_passed,
            }
            state.history.append(record)
            save_state(state)

            if decision == "merge":
                pr_url = outcome.get("pr_url")
                if pr_url:
                    print(f"  Merging: {pr_url}")
                    if merge_pr(pr_url):
                        pull_main()
                        feature_merged = True
                        state.completed_features.append(feature_id)
                        update_backlog_status(backlog, feature_id, "completed")
                        save_backlog(backlog)

                        # Recompute baseline
                        print("  Recomputing baseline...")
                        state.baseline = compute_baseline(runs=args.baseline_runs)
                    else:
                        print("  WARNING: merge failed — declining feature.")
                        update_backlog_status(backlog, feature_id, "declined")
                        save_backlog(backlog)
                else:
                    print("  WARNING: No PR URL — skipping merge.")
                remove_worktree(branch)
                break

            elif decision == "request_changes" and state.revision_count < MAX_REVISIONS:
                print(f"  Requesting changes (revision {state.revision_count + 1}/{MAX_REVISIONS}).")
                remove_worktree(branch)
                state.revision_count += 1

            else:
                if decision == "request_changes":
                    print(f"  Max revisions ({MAX_REVISIONS}) reached — declining.")
                update_backlog_status(backlog, feature_id, "declined")
                save_backlog(backlog)
                remove_worktree(branch)
                break

        # --- Strategy update phase ---
        if feature_merged and feature.get("needs_strategy_update"):
            print(f"\n  --- Strategy Update Phase for {feature_id} ---")
            strategy_branch = f"agent/strategy-update-{feature_id.lower()}"
            print(f"  Spawning strategy update sub-agent on {strategy_branch}...")
            ret, out = run_strategy_update_agent(strategy_branch)
            if ret == 0:
                strategy_outcome = parse_outcome(WORKTREES_DIR / strategy_branch)
                if strategy_outcome and strategy_outcome.get("pr_url"):
                    print(f"  Merging strategy update: {strategy_outcome['pr_url']}")
                    if merge_pr(strategy_outcome["pr_url"]):
                        pull_main()
                        print("  Recomputing baseline after strategy update...")
                        state.baseline = compute_baseline(runs=args.baseline_runs)
                    else:
                        print("  WARNING: strategy update merge failed.")
                else:
                    print("  WARNING: no OUTCOME.md or PR URL from strategy update agent.")
            else:
                print(f"  WARNING: strategy update agent failed (code {ret}).")
            remove_worktree(strategy_branch)

        state.current_feature_id = None
        state.iteration += 1
        save_state(state)

    # --- Summary ---
    print(f"\n{'=' * 72}")
    print("  Orchestrator complete.")
    merges = sum(1 for h in state.history if h["decision"] == "merge")
    declines = sum(1 for h in state.history if h["decision"] == "decline")
    revisions = sum(1 for h in state.history if h["decision"] == "request_changes")
    print(
        f"  Total records: {len(state.history)} | Merges: {merges} | "
        f"Declines: {declines} | Revision requests: {revisions}"
    )
    print(f"  Completed features: {state.completed_features}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
