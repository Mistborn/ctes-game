# CLAUDE.md — Project instructions for Claude Code

## Launching the game

Claude's bash tool is headless, so use PowerShell to spawn the window:

```bash
powershell.exe -Command "Start-Process -FilePath 'C:\Users\me\.local\bin\uv.exe' -ArgumentList 'run python main.py' -WorkingDirectory 'C:\Users\me\Programming\ctes-game'"
```

## Running headless / balance report

```bash
uv run python main.py --headless
```

## Load pre-boss save on world map

```bash
uv run python main.py --load saves/scenario_pre_boss.json --view world_map
```

## Taking a screenshot

```bash
powershell.exe -ExecutionPolicy Bypass -File "C:/Users/me/Programming/ctes-game/dev_scripts/screenshot.ps1"
```

Then read `screenshot.png` in the repo root to view it.

## Killing the game

```bash
powershell.exe -Command "Stop-Process -Name python -Force"
```

## Sprite workflow

After generating fresh sprite(s), verify by launching the game to the world map (see "Load pre-boss save on world map" above), take a screenshot, and ask the user to check the look.

## Running the orchestrator

The orchestrator reads features from `scripts/backlog.json` and spawns Claude sub-agents to implement them. Sub-agents use the Claude Pro subscription (not API credits).

```bash
# Full run (implements up to N features from the backlog)
uv run python scripts/orchestrator.py --max-iterations 5 --baseline-runs 10

# Resume after interruption (picks up where it left off)
uv run python scripts/orchestrator.py --resume

# Dry run (select next feature + write AGENT_TASK.md, don't spawn sub-agent)
uv run python scripts/orchestrator.py --dry-run

# Standalone validation (check current codebase health)
uv run python scripts/validate.py --layer 1 --runs 5
```

After the run, merge any open PRs manually if `gh pr merge` failed. Rebase may be needed when multiple PRs touch the same files.

## Environment notes

- Git identity: name="Vlad Dolezal", email="4179152+Mistborn@users.noreply.github.com"
