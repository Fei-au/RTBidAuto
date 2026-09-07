---
name: build
description: Build the RTBidAuto Windows executable with PyInstaller, picking the next version number and without bundling a browser. Use this whenever the user wants to package, build, ship, release, or "打包" the app, cut a new version, hand a new .exe to the operator, or asks what command produces the exe — even when they just say "打个包" or name a version themselves. It covers version selection, the pre-build checks, the exact flags, why Playwright's browser is deliberately left out, and how to sanity-check the result.
---

# Building the RTBidAuto exe

The build turns `main.py` and its imports into a single `Auto Bid<version>.exe` that
the operator runs on a Windows machine. Nothing else gets installed there: the
Playwright package and its 77 MB Node driver ride along inside the exe, and both
browsers the app drives come from the operator's own Google Chrome.

That last part is the thing to protect. Playwright's own Chromium is a 326 MB download
that is **not** part of the pip package, and earlier versions of this build shipped it.
It is no longer needed, so leaving it out is a deliberate choice rather than an
oversight — see "Shipping the fallback browser" for the one case where you would put it
back.

## Picking the version

Versions look like `2.13`, `2.14`. **A version number stands for one finished change,
not for one commit.** While a change is still being fixed — the last exe went out and
came back broken, or it was never handed over at all — rebuild under the same number.
Bump only once the previous version is genuinely done.

This matters because the operator identifies builds by that number. Burning a new one on
every fix leaves a trail of numbers that were never really shipped, and makes "which
version are you running?" a useless question.

Every successful build is tagged, so the newest tag says what the current number is and
which commit it was built from:

```bash
cd "E:/Code/RuitoTrading/RTBidAuto" && git tag --list "v*" --sort=-v:refname | head -3 && git log $(git tag --list "v*" --sort=-v:refname | head -1)..HEAD --oneline
```

Then decide:

- **The user named a version** — use theirs. They may be matching something already sent
  out, or deliberately reusing a number.
- **No commits since the tag and a clean tree** — nothing changed. Say so instead of
  producing a second exe of identical code.
- **There are changes** — ask whether the tagged version is finished, unless the
  conversation already makes it obvious. Still iterating on it (the previous exe failed,
  or never left the machine) means the same number; a version that was shipped and works
  means the next one.

Reusing a number means the tag has to move to the new commit:

```bash
cd "E:/Code/RuitoTrading/RTBidAuto" && git tag -f v<version> && git push -f origin v<version>
```

## Before building

Run from the repository root, `E:\Code\RuitoTrading\RTBidAuto` — **not** from a worktree
under `.claude/worktrees/`. `.env` is gitignored, so it exists only in the main
checkout, and the build embeds it.

1. `.env` is present at the root and has `LOG_BACK` and `IS_ONLINE`. Without it the exe
   starts with no logging configuration.
2. The code you want to ship is on `main` and committed.

## The build command

```bash
cd "E:/Code/RuitoTrading/RTBidAuto" && ./.venv/Scripts/pyinstaller.exe --noconfirm --onefile --noconsole --name "Auto Bid<version>" --add-data ".env;." main.py
```

It takes a couple of minutes. The result is `dist/Auto Bid<version>.exe`. `dist/`,
`build/` and `*.spec` are gitignored, so nothing from the build needs cleaning up.

What each flag is doing:

- `--onefile` keeps it to a single file the operator can drop anywhere. This is only
  reasonable because the payload is small now; a bundled browser would make startup
  crawl, since onefile unpacks everything to `%TEMP%` on every launch.
- `--noconsole` hides the terminal window behind the Tk UI.
- `--add-data ".env;."` embeds the environment file. `main.py` reads it from
  `sys._MEIPASS` when frozen.
- No Playwright flags are needed. Playwright ships its own PyInstaller hook at
  `playwright/_impl/__pyinstaller/hook-playwright.async_api.py`, which PyInstaller finds
  automatically and which collects the driver.

## After building

Tag the commit so the next build can tell what changed:

```bash
cd "E:/Code/RuitoTrading/RTBidAuto" && git tag v<version> && git --no-pager tag --list "v*" --sort=-v:refname | head -3
```

Then copy the exe somewhere outside the repo, start it, and check the two things most
likely to be broken by a bad build:

1. Press **2. Login Accounts**. A Chrome window should open by itself on the bid link.
   That proves the Chrome discovery and the debugging-port wait survive freezing. If the
   bot account is not signed in there, the log prints a banner asking for a sign-in —
   expected on a fresh machine, and signing in once is enough because the profile under
   `%LOCALAPPDATA%\AutoBid\chrome-bot-profile` keeps the session.
2. Watch for a second Chrome window for the manager account. That one is Playwright
   driving the installed Chrome through `channel="chrome"`.

If both windows appear, the parts that depend on packaging are working.

## What the operator's machine needs

Only **Google Chrome**. No Python, no pip, no `playwright install`, no separate Chromium
download. The app finds `chrome.exe` through the registry (`App Paths\chrome.exe`, then
the usual install folders), so a non-default install location is fine.

## Shipping the fallback browser

`launch_context()` falls back to Playwright's own browser when the installed Chrome
cannot be driven — for instance if a future Chrome release stops working with the pinned
Playwright version. That fallback only exists if the build carried the browser.

Include it only when there is a reason to, because it costs 326 MB:

```bash
cd "E:/Code/RuitoTrading/RTBidAuto" && PLAYWRIGHT_BROWSERS_PATH="E:/Code/RuitoTrading/RTBidAuto/playwright-browsers" ./.venv/Scripts/python.exe -m playwright install chromium && ./.venv/Scripts/pyinstaller.exe --noconfirm --onedir --noconsole --name "Auto Bid<version>" --add-data ".env;." --add-data "playwright-browsers;playwright-browsers" main.py
```

Note `--onedir` rather than `--onefile`: at that size, unpacking on every launch makes
the app look frozen for a minute. `main.py` points `PLAYWRIGHT_BROWSERS_PATH` at the
bundled folder only when the folder is actually there, so the same source builds both
ways.

## When something goes wrong

**`Executable doesn't exist at ...\playwright-browsers\chromium-XXXX\...`** — the app is
looking for a bundled browser that was not shipped. Either the frozen build set the path
when it should not have, or a source run is picking up a stale
`PLAYWRIGHT_BROWSERS_PATH` from the environment. Check `main.py`: it should only set that
variable when frozen *and* the folder exists.

**The exe starts and immediately closes** — `--noconsole` hides the traceback. Rebuild
with `--console` instead and run it from a terminal to see the error.

**PyInstaller reports a missing module** — add `--hidden-import <module>`. This has not
been needed so far; the playwright hook covers the non-obvious case.
