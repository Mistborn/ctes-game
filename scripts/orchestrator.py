#!/usr/bin/env python3
"""
orchestrator.py — AI agent loop for continuous game improvement.

Each iteration:
  1. An LLM picks an improvement direction.
  2. A claude sub-agent implements it in an isolated git worktree,
     tests it headlessly, creates a GitHub PR, and writes OUTCOME.md.
  3. An LLM evaluates the outcome and decides: merge / request_changes / decline.
  4. State is saved after every iteration so the loop is resumable.

Usage:
    export PATH="$PATH:/c/Users/me/.local/bin:/c/Program Files/GitHub CLI"
    python scripts/orchestrator.py
    python scripts/orchestrator.py --max-iterations 20 --baseline-runs 30
    python scripts/orchestrator.py --resume
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
WORKTREES_DIR = REPO_ROOT / ".claude" / "worktrees"
MODEL = "claude-opus-4-6"
MAX_REVISIONS = 2
DEFAULT_MAX_ITER = 10
DEFAULT_BASELINE_RUNS = 20
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


def load_state() -> Optional[OrchestratorState]:
    if not STATE_FILE.exists():
        return None
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    s = OrchestratorState()
    s.iteration = data.get("iteration", 0)
    s.baseline = data.get("baseline", {})
    s.history = data.get("history", [])
    s.revision_count = data.get("revision_count", 0)
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
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    tmp.replace(STATE_FILE)


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
            cwd=REPO_ROOT, capture_output=True,
        )
    subprocess.run(
        ["git", "branch", "-D", branch_name],
        cwd=REPO_ROOT, capture_output=True,
    )
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", branch_name],
        cwd=REPO_ROOT, check=True, capture_output=True,
    )
    return worktree_path


def remove_worktree(branch_name: str) -> None:
    worktree_path = WORKTREES_DIR / branch_name
    subprocess.run(
        ["git", "worktree", "remove", str(worktree_path), "--force"],
        cwd=REPO_ROOT, capture_output=True,
    )


# ---------------------------------------------------------------------------
# Agent task file
# ---------------------------------------------------------------------------

_AGENT_TASK_TEMPLATE = """\
# Agent Task

## Direction
{direction}

## Context
You are improving "Kingdoms of the Forgotten" (medieval colony builder in Python).

Architecture rules (non-negotiable):
- game/core/ must NEVER import from game/renderer/
- All numeric constants must stay in game/core/config.py
- GameState must remain JSON-serialisable at any tick

## Baseline Metrics
{baseline_table}

## Your Task
1. Read the codebase thoroughly. Understand existing code before making any changes.
2. Implement the direction above — one focused, coherent change.
3. Run the headless balance report to get your metrics:
   export PATH="$PATH:/c/Users/me/.local/bin"
   uv run python main.py --headless --runs 20
4. Commit your changes with a clear message.
5. Push and create a GitHub PR:
   git push -u origin {branch_name}
   export PATH="$PATH:/c/Users/me/.local/bin:/c/Program Files/GitHub CLI"
   gh pr create --title "..." --body "..."
6. Write OUTCOME.md in the repo root with the schema below. This is MANDATORY.

## OUTCOME.md Schema
```
# Outcome
## Summary
## Changes Made
## Metrics After Change
## Delta vs Baseline
## PR URL
## Status
(success | partial | failure)
## Notes
```

## Revision Request
{revision_notes}
"""

_SUBAGENT_PROMPT = (
    "You are a game balance engineer. Read AGENT_TASK.md in the current directory "
    "completely before writing any code. "
    "Architecture rules: game/core/ never imports renderer/, all constants in config.py. "
    "Run the headless balance report after your changes and include the output in OUTCOME.md. "
    "Commit your changes, push, and create a GitHub PR via gh. "
    "Write OUTCOME.md with all required sections — the orchestrator cannot proceed without it. "
    "Do not modify AGENT_TASK.md. "
    r'PATH: export PATH="$PATH:/c/Users/me/.local/bin:/c/Program Files/GitHub CLI"'
)


def write_agent_task(
    worktree_path: Path,
    direction: str,
    baseline: Dict[str, Any],
    branch_name: str,
    revision_notes: str = "",
) -> None:
    content = _AGENT_TASK_TEMPLATE.format(
        direction=direction,
        baseline_table=_format_baseline_table(baseline),
        branch_name=branch_name,
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
    # Common Windows install location
    candidate = (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Claude" / "claude.exe"
    )
    if candidate.exists():
        return str(candidate)
    raise RuntimeError(
        "claude CLI not found. Install Claude Code and ensure `claude` is on your PATH."
    )


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
# LLM helpers
# ---------------------------------------------------------------------------


def call_llm(client: anthropic.Anthropic, system: str, user: str) -> str:
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text.strip()
        except anthropic.APIError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return ""


_CHOOSE_DIRECTION_SYSTEM = """\
You are a game design consultant for "Kingdoms of the Forgotten", a medieval colony builder.
Propose ONE small, testable improvement for an AI sub-agent to implement and test.
The game has buildings (Farm, Lumber Mill, Market, Quarry, Sawmill), resources (food,
wood, gold, stone, planks), and 5 research techs. Win: 500 gold. Balance is measured
via 4 headless strategies over 20+ runs each.
Scope: 1-2 files, ~20-50 lines of change. Do NOT suggest directions already in history.
Respond EXACTLY as:
DIRECTION: <one sentence>
RATIONALE: <2-3 sentences>
FILES_TO_TOUCH: <comma-separated file paths>"""

_EVALUATE_OUTCOME_SYSTEM = """\
You are evaluating a proposed game balance change. Decide: merge, request_changes, or decline.
Merge if: at least one key metric improved meaningfully (win_rate +0.05 or ticks_survived +50)
  without significant regression elsewhere, and architecture rules were followed.
Request changes if: the direction is sound but execution has a specific fixable flaw.
  Provide exact revision instructions.
Decline if: the change made things worse overall, direction was misguided, or no
  testable output was produced.
Respond EXACTLY as:
DECISION: merge | request_changes | decline
REASONING: <2-4 sentences>
REVISION_INSTRUCTIONS: <specific instructions — only if request_changes, otherwise omit>"""


def _format_history_summary(history: List[Dict]) -> str:
    if not history:
        return "None — this is the first iteration."
    lines = [
        f"- Iter {h['iteration']}: {h['direction'][:70]} → {h['decision']}"
        for h in history[-8:]
    ]
    return "\n".join(lines)


def choose_direction(client: anthropic.Anthropic, state: OrchestratorState) -> str:
    user = (
        f"## Baseline Metrics\n{_format_baseline_table(state.baseline)}\n\n"
        f"## History of Prior Directions\n{_format_history_summary(state.history)}\n\n"
        "Propose ONE direction for the next sub-agent."
    )
    text = call_llm(client, _CHOOSE_DIRECTION_SYSTEM, user)
    match = re.search(r"DIRECTION:\s*(.+?)(?:\n|$)", text)
    return match.group(1).strip() if match else text[:200]


def evaluate_outcome(
    client: anthropic.Anthropic,
    state: OrchestratorState,
    direction: str,
    outcome: Dict,
) -> tuple[str, str, str]:
    """Returns (decision, reasoning, revision_instructions)."""
    user = (
        f"## Direction\n{direction}\n\n"
        f"## Baseline\n{_format_baseline_table(state.baseline)}\n\n"
        f"## Outcome (OUTCOME.md)\n{outcome['raw_text'][:3000]}"
    )
    text = call_llm(client, _EVALUATE_OUTCOME_SYSTEM, user)

    decision_match = re.search(r"DECISION:\s*(merge|request_changes|decline)", text, re.IGNORECASE)
    decision = decision_match.group(1).lower() if decision_match else "decline"

    reasoning_match = re.search(
        r"REASONING:\s*(.+?)(?=\nREVISION_INSTRUCTIONS:|$)", text, re.DOTALL
    )
    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

    revision_match = re.search(r"REVISION_INSTRUCTIONS:\s*(.+?)$", text, re.DOTALL)
    revision_instructions = revision_match.group(1).strip() if revision_match else ""

    return decision, reasoning, revision_instructions


# ---------------------------------------------------------------------------
# PR operations
# ---------------------------------------------------------------------------


def merge_pr(pr_url: str) -> bool:
    gh_cmd = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
    result = subprocess.run(
        [gh_cmd, "pr", "merge", pr_url, "--squash", "--delete-branch", "--yes"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  WARNING: gh pr merge failed: {result.stderr[:300]}")
        return False
    return True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="AI orchestrator loop for ctes-game improvement.")
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITER,
                        help=f"Max improvement iterations (default: {DEFAULT_MAX_ITER})")
    parser.add_argument("--baseline-runs", type=int, default=DEFAULT_BASELINE_RUNS,
                        help=f"Runs per strategy for baseline (default: {DEFAULT_BASELINE_RUNS})")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from saved orchestrator_state.json")
    args = parser.parse_args()

    client = anthropic.Anthropic()

    if args.resume:
        state = load_state()
        if state is None:
            print("No saved state found — starting fresh.")
            state = OrchestratorState()
        else:
            print(f"Resuming from iteration {state.iteration}.")
    else:
        state = OrchestratorState()

    if not state.baseline:
        state.baseline = compute_baseline(runs=args.baseline_runs)
        save_state(state)

    print(f"\nBaseline ready. Starting loop (max {args.max_iterations} iterations).")

    while state.iteration < args.max_iterations:
        print(f"\n{'=' * 72}")
        print(f"  Iteration {state.iteration + 1} / {args.max_iterations}")
        print("=" * 72)

        direction = choose_direction(client, state)
        print(f"\n  Direction: {direction}")

        state.revision_count = 0
        revision_instructions = ""

        while True:
            branch = f"agent-iter-{state.iteration}-rev-{state.revision_count}"
            print(f"\n  Branch: {branch}")

            try:
                worktree_path = make_worktree(branch)
            except subprocess.CalledProcessError as exc:
                print(f"  ERROR creating worktree: {exc}")
                break

            write_agent_task(
                worktree_path, direction, state.baseline, branch,
                revision_notes=revision_instructions,
            )

            print("  Running sub-agent (may take up to 30 min)...")
            returncode, agent_output = run_subagent(worktree_path)
            if returncode != 0:
                print(f"  Sub-agent exited with code {returncode}.")
                if returncode == -1:
                    print(f"  {agent_output[:200]}")

            outcome = parse_outcome(worktree_path)

            if outcome is None:
                decision = "decline"
                reasoning = "Sub-agent produced no OUTCOME.md."
                revision_instructions = ""
                print("  No OUTCOME.md found — declining.")
            else:
                decision, reasoning, revision_instructions = evaluate_outcome(
                    client, state, direction, outcome
                )
                print(f"  Decision: {decision.upper()}")
                print(f"  Reasoning: {reasoning[:120]}")

            record = {
                "iteration": state.iteration,
                "direction": direction,
                "branch": branch,
                "revision": state.revision_count,
                "pr_url": outcome.get("pr_url") if outcome else None,
                "decision": decision,
                "llm_reasoning": reasoning,
                "metrics_delta": outcome.get("delta_text", "") if outcome else "",
            }
            state.history.append(record)
            save_state(state)

            if decision == "merge":
                pr_url = outcome.get("pr_url") if outcome else None
                if pr_url:
                    print(f"  Merging: {pr_url}")
                    if merge_pr(pr_url):
                        # Pull merged changes into REPO_ROOT
                        subprocess.run(
                            ["git", "pull", "--ff-only"],
                            cwd=REPO_ROOT, capture_output=True,
                        )
                        print("  Recomputing baseline...")
                        state.baseline = compute_baseline(runs=args.baseline_runs)
                else:
                    print("  WARNING: No PR URL in OUTCOME.md — skipping merge.")
                remove_worktree(branch)
                break

            elif decision == "request_changes" and state.revision_count < MAX_REVISIONS:
                print(
                    f"  Requesting changes "
                    f"(revision {state.revision_count + 1}/{MAX_REVISIONS})."
                )
                remove_worktree(branch)
                state.revision_count += 1

            else:
                if decision == "request_changes":
                    print(f"  Max revisions ({MAX_REVISIONS}) reached — declining.")
                remove_worktree(branch)
                break

        state.iteration += 1
        save_state(state)

    print(f"\n{'=' * 72}")
    print("  Orchestrator complete.")
    merges = sum(1 for h in state.history if h["decision"] == "merge")
    declines = sum(1 for h in state.history if h["decision"] == "decline")
    revisions = sum(1 for h in state.history if h["decision"] == "request_changes")
    print(f"  Total records: {len(state.history)} | Merges: {merges} | "
          f"Declines: {declines} | Revision requests: {revisions}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
