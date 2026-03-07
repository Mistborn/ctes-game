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

## Environment notes

- GitHub CLI (`gh`) is at `C:\Program Files\GitHub CLI\gh.exe`
- Git identity: name="Vlad Dolezal", email="4179152+Mistborn@users.noreply.github.com"
