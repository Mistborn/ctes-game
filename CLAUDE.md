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

## Environment notes

- Git identity: name="Vlad Dolezal", email="4179152+Mistborn@users.noreply.github.com"
