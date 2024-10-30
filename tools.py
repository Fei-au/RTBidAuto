
from urllib.parse import urlparse, urlunparse
import os
from pathlib import Path
import json


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

def save_credentials(bot_acc, bot_pwd, mng_acc, mng_pwd):
    with open(credentials_file, 'w') as file:
        json.dump({"BOT_ACC": bot_acc, "BOT_PASS": bot_pwd, "MNG_ACC": mng_acc, "MNG_PWD": mng_pwd}, file)

def get_local_dir():
    return app_data_path

        
        