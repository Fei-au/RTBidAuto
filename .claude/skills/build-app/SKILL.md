---
name: build-app
description: Package the RTBidAuto desktop app into a single Windows .exe using PyInstaller. Auto-detects whether sv-ttk is installed and adds the matching --collect-data flag. Accepts an optional version string (e.g. "3.4"); if omitted, asks the user. Bundles .env and the playwright-browsers folder as required by main.py at runtime.
---

# Build the RTBidAuto exe

You are packaging the RTBidAuto Tkinter app for distribution. The user has invoked this skill — your job is to produce one `Auto Bid<version>.exe` in `dist/`.

## Inputs

- **Version string** (e.g. `3.4`, `3.4.1`, `4.0-beta`): take from the skill arguments if provided. If not, ask the user — do not guess.

## Pre-flight checks (run in parallel)

1. **`.venv` exists** — `Test-Path .venv\Scripts\pyinstaller.exe`. If missing, stop and tell the user to `pip install pyinstaller` inside their `.venv`.
2. **`.env` exists** at repo root. If missing, stop and tell the user — PyInstaller will fail without it.
3. **`playwright-browsers/` folder exists** at repo root. If missing, stop and tell the user to either run `playwright install chromium` and copy/move the browsers in, or remove that `--add-data` flag (warn that the frozen exe will not work without bundled browsers because `main.py` sets `PLAYWRIGHT_BROWSERS_PATH` to the bundled path under `sys._MEIPASS`).
4. **sv-ttk presence** — run `.venv\Scripts\pip.exe show sv-ttk` (exit 0 = installed). Record the result; you'll branch the command on it.

Run these as parallel `PowerShell` tool calls. Do not proceed past the first failure — abort and report.

## Build command

Compose the command from these pieces:

```
.venv\Scripts\pyinstaller.exe ^
  --onefile ^
  --noconsole ^
  --name="Auto Bid<VERSION>" ^
  --add-data=".env;." ^
  --add-data="playwright-browsers;playwright-browsers" ^
  [--collect-data sv_ttk]   ← only if sv-ttk was detected
  main.py
```

Where `<VERSION>` is the version string the user supplied (no leading "v").

Reference: README.md "Deploy an app" section and CLAUDE.md "Build" section.

### Why each flag

- `--onefile` — single distributable exe (slower startup, but one file).
- `--noconsole` — hide the console window; this is a GUI app.
- `--add-data=".env;."` — `main.py` calls `load_dotenv(os.path.join(extDataDir, '.env'))` where `extDataDir = sys._MEIPASS` when frozen.
- `--add-data="playwright-browsers;playwright-browsers"` — `main.py` sets `PLAYWRIGHT_BROWSERS_PATH` to the bundled folder so Playwright finds Chromium at runtime.
- `--collect-data sv_ttk` — bundles `sv.tcl` and the theme's PNG assets. Without it, frozen exe silently falls back to the native ttk theme (the `import sv_ttk` in `bid_gui.py` is wrapped in try/except).

## Execution

Run via the `PowerShell` tool. The build takes 1–3 minutes — set `timeout: 300000` (5 min) and stream output normally. Do **not** use `run_in_background` for the build itself; the user is waiting on the artifact.

## After the build

Run these in parallel:

1. Confirm the exe exists: `Test-Path "dist\Auto Bid<VERSION>.exe"`.
2. Report its size: `(Get-Item "dist\Auto Bid<VERSION>.exe").Length / 1MB`.

Then summarize: exe path, size in MB, whether sv-ttk was bundled. Remind the user that the bot account expects Chrome on `localhost:9222` at runtime (CDP attach) — they need to launch Chrome with `--remote-debugging-port=9222 --user-data-dir=...` and log in manually first.

## Don'ts

- Don't `pip install` anything implicitly — if sv-ttk is missing and the user wanted it, ask first.
- Don't clean `build/` or `dist/` unless the user asks — PyInstaller reuses them and a clean rebuild is much slower.
- Don't run PyInstaller with `--noconfirm` — that silently overwrites; let it prompt so the user notices overwrites.
- Don't bump the version in any file or commit anything — this skill only builds.
