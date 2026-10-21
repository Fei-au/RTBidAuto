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
