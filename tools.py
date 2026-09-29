from urllib.parse import urlparse, urlunparse
import os
from pathlib import Path
import json
import requests
import httpx
# The switch lives on the backend so it can be flipped without a new build;
# .env is only the fallback. Read at call time, never frozen at import.
from config import is_online


def get_upper_level_url(url):
    # Parse the URL into components
    parsed = urlparse(url)
    
    # Split the path into segments and remove the last one
    path_parts = parsed.path.rstrip('/').split('/')
    if len(path_parts) > 1:
        upper_path = '/'.join(path_parts[:-1]) + '/'
    else:
        upper_path = parsed.path  # If there's only one segment, keep it as is
    
    # Reconstruct the URL with the new path
    new_url = urlunparse(parsed._replace(path=upper_path))
    return new_url

# def print_hierarchy(w, depth=0):
#     print('  '*depth + w.winfo_class() + ' w=' + str(w.winfo_width()) + ' h=' + str(w.winfo_height()) + ' x=' + str(w.winfo_rootx()) + ' y=' + str(w.winfo_rooty()))
#     for i in w.winfo_children():
#         print_hierarchy(i, depth+1)
        

app_data_path = Path(os.getenv('LOCALAPPDATA')) / "AutoBid"
app_data_path.mkdir(exist_ok=True)  # Create the folder if it doesn't exist
credentials_file = app_data_path / "credentials.json"
    
    
def load_credentials():
    if credentials_file.exists():
        with open(credentials_file, 'r') as file:
            return json.load(file)
    return None

def save_credentials(bot_acc, bot_pwd, mng_acc, mng_pwd, mng_link, bid_link):
    with open(credentials_file, 'w') as file:
        json.dump({"BOT_ACC": bot_acc, "BOT_PWD": bot_pwd, "MNG_ACC": mng_acc, "MNG_PWD": mng_pwd, "MNG_LINK": mng_link, "BID_LINK": bid_link}, file)

def save_bidder_registration(auction_id: int, special_allowed_list: list, already_blocked_list: list):
    with open(app_data_path / f'bidder_registration_{auction_id}.json', 'w') as file:
        json.dump({"special_allowed_list": special_allowed_list, "already_blocked_list": already_blocked_list}, file)
        
def load_bidder_registration(auction_id: int):
    file_path = app_data_path / f'bidder_registration_{str(auction_id)}.json'
    if file_path.exists():
        with open(file_path, 'r') as file:
            return json.load(file)
    return None


def get_auction_id(mng_link):
    link = get_upper_level_url(mng_link)
    parsed = urlparse(link)
    path_parts = parsed.path.rstrip('/').split('/')
    auction_id = path_parts[-1] if path_parts else ''
    return auction_id
    

def get_local_dir():
    return app_data_path


CHROME_APP_PATHS_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"


def find_chrome_path():
    """Locate the installed Google Chrome, or None.

    Chrome registers its own location under App Paths, which holds wherever the
    user installed it, so try the registry before guessing directories.
    """
    try:
        import winreg
    except ImportError:
        winreg = None
    if winreg is not None:
        views = [
            (winreg.HKEY_CURRENT_USER, 0),
            (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
            (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
        ]
        for hive, view in views:
            try:
                with winreg.OpenKey(hive, CHROME_APP_PATHS_KEY, 0, winreg.KEY_READ | view) as key:
                    path = winreg.QueryValue(key, '')
            except OSError:
                continue
            if path and os.path.isfile(path):
                return path
    for base in (os.environ.get('PROGRAMFILES'),
                 os.environ.get('PROGRAMFILES(X86)'),
                 os.environ.get('LOCALAPPDATA')):
        if not base:
            continue
        candidate = os.path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe')
        if os.path.isfile(candidate):
            return candidate
    return None


def bot_chrome_profile_dir():
    profile = app_data_path / 'chrome-bot-profile'
    profile.mkdir(exist_ok=True)
    return profile


def chrome_launch_command(chrome_path, port, url=None):
    """The command line that opens Chrome with the debugging port on its own profile."""
    command = [
        chrome_path,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={bot_chrome_profile_dir()}',
        '--no-first-run',
        '--no-default-browser-check',
    ]
    if url:
        command.append(url)
    return command

        
def add_log(path, data):
    if not is_online():
        return "Offline mode - log not sent"
    response = requests.post(f'{os.getenv("LOG_BACK")}/logs{path}', 
        json=data)
    if response.status_code == 200:
        return response.text
    else:
        return f"Warning: {response.status_code} - {response.text}"
    
def filter_bidder_txns(data):
    if not is_online():
        return "Offline mode - log not sent"
    response = requests.post(f'{os.getenv("LOG_BACK")}/logs/filter_bidder_txns', json=data)
    if response.status_code == 200:
        return response.text
    else:
        return f"Warning: {response.status_code} - {response.text}"
    
def block_bidder_log(data):
    if not is_online():
        return "Offline mode - log not sent"
    response = requests.post(f'{os.getenv("LOG_BACK")}/logs/block_bidder_log', json=data)
    if response.status_code == 200:
        return response.text
    else:
        return f"Warning: {response.status_code} - {response.text}"


REGISTRATION_TIMEOUT = 10


def _registration_url(auction_id, suffix=''):
    return f'{os.getenv("LOG_BACK").rstrip("/")}/bidder_registration/{auction_id}{suffix}'


def fetch_bidder_registration(auction_id):
    """The auction's shared lists from the backend (MongoDB), or None when offline.

    Raises on failure so the caller can fall back to the local file.
    """
    if not is_online():
        return None
    response = requests.get(_registration_url(auction_id), timeout=REGISTRATION_TIMEOUT)
    response.raise_for_status()
    return response.json()


def record_blocked_bidder(auction_id, bidder_id, client=None):
    """Add one blocked bidder to the backend's list. Raises on failure."""
    if not is_online():
        return None
    response = requests.post(_registration_url(auction_id, '/blocked'),
                             json={"bidder_id": bidder_id, "client": client},
                             timeout=REGISTRATION_TIMEOUT)
    response.raise_for_status()
    return response.json()


def save_allowed_bidders(auction_id, bidder_ids, client=None):
    """Replace the backend's allowed list; it drops those ids from the blocked list too."""
    if not is_online():
        return None
    response = requests.put(_registration_url(auction_id, '/allowed'),
                            json={"bidder_ids": bidder_ids, "client": client},
                            timeout=REGISTRATION_TIMEOUT)
    response.raise_for_status()
    return response.json()


def upload_log_text(text, filename, timeout=30):
    """Upload text as a .log file to ${LOG_BACK}/s3/upload.

    Same endpoint rt-af-controller uses. The text is sent straight from memory,
    nothing is written to disk. Raises on failure so the caller can report it.
    """
    response = requests.post(
        f'{os.getenv("LOG_BACK").rstrip("/")}/s3/upload',
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(f"{response.status_code} - {response.text}")
    return response.text
    
    