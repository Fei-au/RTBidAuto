# RTBidAuto

Tkinter desktop app that automates bidding and bidder filtering on Hibid auctions using Playwright.

## Run

```powershell
python main.py
```

Env vars are loaded from `.env` via `python-dotenv`. Relevant keys: `LOG_BACK` (logging API base URL), `IS_ONLINE` (`TRUE`/`FALSE` — disables remote logging when false).

## Build

PyInstaller one-file. Browsers are not bundled: both browsers come from the machine's own Google Chrome, so the exe stays small and the user installs nothing.

```powershell
pyinstaller --onefile --noconsole --name="Auto Bid<version>" --add-data=".env;." main.py
```

To ship Playwright's own browser as a fallback, install it into `playwright-browsers/` first (`PLAYWRIGHT_BROWSERS_PATH=<repo>/playwright-browsers python -m playwright install chromium`) and add `--add-data "playwright-browsers;playwright-browsers"`. `main.py` points `PLAYWRIGHT_BROWSERS_PATH` at that folder when frozen and the folder is actually there; that payload is ~326 MB, so prefer `--onedir` when including it.

## Architecture

- [main.py](main.py) — Entry point. Loads `.env`, points Playwright at bundled browsers, instantiates `BidGui`.
- [bid_gui.py](bid_gui.py) — Tkinter UI (`BidGui`). Owns Playwright lifecycle, three pages (`bot_page`, `mng_page`, `mng_bidder_page`), and an asyncio loop running on a daemon thread. UI callbacks dispatch coroutines via `asyncio.run_coroutine_threadsafe`.
- [automation.py](automation.py) — `Automation` class. All Playwright interactions: login, lot info collection, bidding logic, bidder filtering/blocking. Holds in-memory state (`lot_dict`, `is_running`, `is_filter_running`, `special_allowed_list`, `already_blocked_list`).
- [tools.py](tools.py) — Credential persistence (`%LOCALAPPDATA%/AutoBid/credentials.json`), per-auction bidder lists (`bidder_registration_<auction_id>.json`), URL helpers, and remote log POSTs gated on `IS_ONLINE`.
- [exceptions.py](exceptions.py) — `NavigationError`.

## Browser connection

The bot account drives the machine's own Chrome over CDP (`http://localhost:9222`). `BidGui.ensure_bot_chrome` reuses a Chrome already listening on that port; otherwise it locates `chrome.exe` (registry App Paths first, then the usual install folders) and starts it on a dedicated profile at `%LOCALAPPDATA%/AutoBid/chrome-bot-profile` with the bid link open. The bot account has to be signed in there once — the profile keeps the session — and `login_bot` checks for the `.welcome-label` header, printing a banner that asks for a sign-in when it is missing. Use the auctioneer subdomain (e.g. `company.bid.com`, not `www.bid.com`). The manager account uses a persistent context at `%LOCALAPPDATA%/AutoBid/playwright-mng-data`, driving the installed Chrome via `channel="chrome"` and falling back to Playwright's own browser if that fails.

## Bidding logic ([automation.py:253](automation.py:253))

For each lot in `lot_dict`:
- `msrp_price < 100`: bid up to `max_bid_price` if current `high_bid` is lower.
- `msrp_price >= 100` (or 0): target = `max_bid_price`. With "15% switch" on, target = `max(max_bid_price, msrp_price * multiplier)` where multiplier is `0.15` (default), `0.08` (`second_hand`), or `0` (`skipped`).
- Mode 1 = single pass; Mode 2 = infinite loop with a 90s round cadence and 14-lot cap per round (see `infinite_bid` in [bid_gui.py:280](bid_gui.py:280)).

Bid placement clicks the increment button until exceeding target, steps back one, fills the amount, confirms — then handles a possible "Confirm Your Bid" reconfirmation modal.

## Bidder filter ([automation.py:570](automation.py:570))

Two passes per round on the auction's `register` page:
1. Sort by reputation ascending. For bidders with score < 20 and total bid amount > $200, open bid history; if ≥50% of winning items have max bid > $200, decline all their bids and block the profile (decline reason `7`).
2. If `block_us_switch` on, sort by state and block any United States bidders (auction is non-US shipping).

Loops every 90s. `special_allowed_list` and `already_blocked_list` are persisted per `auction_id`.

## Logging

`tools.add_log` / `block_bidder_log` / `filter_bidder_txns` POST to `${LOG_BACK}/logs/...`. All become no-ops when `IS_ONLINE != "TRUE"`.

## Conventions

- Async work runs on `BidGui.loop` (background thread); never block it from Tk callbacks — schedule with `run_coroutine_threadsafe` and use `add_done_callback` to update UI.
- UI text widgets are read-only; always toggle `state="normal"` → insert → `state="disabled"` (see `show_log` / `show_message`).
- Lot keys in `lot_dict` are strings (CSV `lot` column is cast to `str` in `file_to_lot_dict`).
- Credentials file stores manager + bot creds and the two links; bot creds inputs are disabled in the UI by design — login is via CDP-attached Chrome.
