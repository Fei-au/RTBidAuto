"""Flags the backend controls, so an install can be reconfigured without a build.

The exe embeds its `.env`, so a flag that lives only there can be changed only by
handing the operator a new exe. `is_online` is asked of the backend instead, and
`.env` is the fallback for a backend that has not answered yet.
"""
import os
import threading
import time

import requests

FETCH_TIMEOUT = 5       # Config is never worth making the operator wait for.
REFRESH_SECONDS = 300

# The last answer from the backend. Replaced whole, never mutated, so readers
# need no lock.
_remote = None


def is_online():
    """Whether the remote logs are sent at all.

    Read at call time, so flipping the switch on the backend takes effect
    without a restart.
    """
    if _remote and "is_online" in _remote:
        return bool(_remote["is_online"])
    return os.getenv("IS_ONLINE", "FALSE").upper() == "TRUE"


# Tuning the backend can change without a build. Each value here is what the
# client does when the backend says nothing about that key.
DEFAULTS = {
    "log_round_summary": True,   # One line per bidding round: what was read, what was done
    "log_upload_minutes": 30,    # Upload the log box this often while running; 0 = never
    "log_upload_lot_step": 500,  # Also upload each time the closing lot passes a multiple; 0 = never
    "round_seconds": 90,         # Length of one infinite-bid round
    "round_lot_cap": 14,         # Most lots one round bids on
    "collect_pages": 1,          # Manager lot-stats pages (100 lots each) read per round
}


def get(key):
    """The backend's value for `key`, else the client default.

    A value of the wrong type (a typo in the config document) falls back to the
    default instead of breaking a round.
    """
    default = DEFAULTS[key]
    value = (_remote or {}).get(key, default)
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    try:
        return type(default)(value)
    except (TypeError, ValueError):
        return default


def start_background_refresh():
    """Poll the backend on a daemon thread.

    Started when the app starts, not when anyone logs in: the switch has to be
    in force for the first log of the run. Never blocks the caller, and a backend
    that cannot be reached leaves the last answer standing.
    """
    # Imported here rather than at the top of the module: tools imports this one
    # for is_online(), so importing it up there would be a cycle.
    from tools import load_credentials

    def refresh_forever():
        global _remote
        while True:
            try:
                # Re-read the credentials every time: this runs before anyone has
                # logged in, and the account can change without a restart.
                client = (load_credentials() or {}).get("MNG_ACC") or ""
                response = requests.get(f'{os.getenv("LOG_BACK")}/config/client',
                                        params={"client": client},
                                        timeout=FETCH_TIMEOUT)
                if response.status_code == 200:
                    _remote = response.json()
            except Exception:
                pass    # Backend down: keep the last answer, keep bidding.
            time.sleep(REFRESH_SECONDS)

    threading.Thread(target=refresh_forever, daemon=True).start()
