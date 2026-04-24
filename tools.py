from urllib.parse import urlparse, urlunparse
import os
from pathlib import Path
import json
import requests
import httpx


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

        
LOG_BACK = f'{os.getenv("LOG_BACK")}/logs'
IS_ONLINE = os.getenv("IS_ONLINE", "FALSE").upper() == "TRUE"
def add_log(path, data):
    if not IS_ONLINE:
        return "Offline mode - log not sent"
    response = requests.post(f'{os.getenv("LOG_BACK")}/logs{path}', 
        json=data)
    if response.status_code == 200:
        return response.text
    else:
        return f"Warning: {response.status_code} - {response.text}"
    
def filter_bidder_txns(data):
    if not IS_ONLINE:
        return "Offline mode - log not sent"
    response = requests.post(f'{os.getenv("LOG_BACK")}/logs/filter_bidder_txns', json=data)
    if response.status_code == 200:
        return response.text
    else:
        return f"Warning: {response.status_code} - {response.text}"
    
def block_bidder_log(data):
    if not IS_ONLINE:
        return "Offline mode - log not sent"
    response = requests.post(f'{os.getenv("LOG_BACK")}/logs/block_bidder_log', json=data)
    if response.status_code == 200:
        return response.text
    else:
        return f"Warning: {response.status_code} - {response.text}"
    
    