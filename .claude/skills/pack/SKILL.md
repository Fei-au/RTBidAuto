---
name: pack
description: Build the RTBidAuto Windows .exe with PyInstaller. Activates the project's .venv and runs the bundled-browsers one-file build from the README. Takes a version string as the only argument (e.g. "3.2"), which is appended to the executable name as "Auto Bid<version>". Use when the user asks to pack/build/bundle/release the app.
---

# Pack RTBidAuto

Build the Windows one-file executable for RTBidAuto.

## Argument

A single version string, e.g. `3.2`. It is substituted into the `--name` flag as `Auto Bid<version>`. If the user did not supply a version, ask before running.

## Steps

Run these in **one PowerShell call** (chained with `;` since `&&` is not available in Windows PowerShell 5.1, and grouped so one bad command does not stop the next silently — check `$?` between activate and pyinstaller):

```powershell
.\.venv\Scripts\Activate.ps1; if ($?) { pyinstaller --onefile --noconsole --name="Auto Bid<VERSION>" --add-data=".env;." --add-data "playwright-browsers;playwright-browsers" main.py }
```

Replace `<VERSION>` with the argument the user passed.

The build is long-running (PyInstaller bundles the `playwright-browsers` directory). Run it with `run_in_background: true` and let the user know the build started; you will be notified when it finishes. Output goes to `dist/Auto Bid<VERSION>.exe`.

## Notes

- Working directory is already `E:\code\RTBidAuto` — do not `cd`.
- Do **not** delete existing `build/`, `dist/`, or older `.spec` files unless the user asks.
- If activation fails because of execution policy, surface the error to the user rather than working around it with `-ExecutionPolicy Bypass`.
- If a `.spec` file already exists for the same version (e.g. `Auto Bid3.1.spec`), PyInstaller will reuse it; mention this to the user so they can decide whether to delete it first.
