import os
import sys
from dotenv import load_dotenv

# The .env has to be loaded before the project modules are imported: they read
# the environment at import time, so loading it further down would be too late.
extDataDir = os.getcwd()
if getattr(sys, 'frozen', False):
    extDataDir = sys._MEIPASS
    # Browsers are only bundled when the build shipped them. Otherwise leave
    # the path alone: the manager context uses the installed Chrome, and
    # from source Playwright looks where `playwright install` puts them.
    bundled_browsers = os.path.join(extDataDir, "playwright-browsers")
    if os.path.isdir(bundled_browsers):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled_browsers
load_dotenv(dotenv_path=os.path.join(extDataDir, '.env'))

from tkinter import *
from bid_gui import BidGui


'''
Input:
1. Manager Acc
2. Bot Acc
3. Management Lots link
4. Bid link
'''

'''
1. @m Upload file
2. @m Add hibid manager acc and other accs
3. Open different browsers, instead only open diff pages
4. Go to manager page (if have link that will be better) and check items
    wait_to_bid = []
    Loop items on the page
    1. if the item haven't been bid, skip
    2. elif the item has been bid
        2.1 if item last bid is done by my accs, skip
        2.2 if last bid is not my accs
            Get item's msrp price from uploaded sheet

            A bid high price
            B max aim price
            2.2.1 if the item in the lot's msrp price is greater and equal to 100
                C 20% msrp price
                max = check the higher price between bidder's highest aim price B and 20% of msrp price C
            2.2.2 elif the item msrp price is less than 100
                max = bidder's highest aim price B
            2.2.3
            if max <= A
                skip
            if max > A
                bid to max
                wait_to_bid.append([
                    [
                        {highname: {lot: number, bid to highest: number},
                        {highname2: {lot: number, bid to highest: number},
                        {highname3: {lot: number, bid to highest: number},
                    ],
                    [
                        {highname2: {lot: number, bid to highest: number},
                    ],
                ] })

                dict 2:{
                    highname: (0,0),
                    highname2: (1,0),
                    highname3: (0,2),
                }

                1. Check highname in dict or not
                    not exist:
                        1. len = Get wait_to_bid length
                        2. Append to wait_to_bid 0, 
                        3. Log dict 2 with (0, len)
                    exist:
                        1. Init tuple(0) + 1 layer if needed and get len = tule(0) + 1
                        2. (Append to tuple(0) + 1, len(tule(0) + 1))
                        3. Log dict 2 with (tuple(0) + 1, len)

'''

'''
Bid to highest
1. Loop wait_to_bid
    1. Open bid link
    2. Login bot acc
    3. Go to bid link ?q=lot
    4. Find item? by its lot number to find its certain parent
    5. Find Bid button and click
    6. Enter bid to highest value
    7. Click confirm

'''



# def tk_gui():

#     root = Tk(screenName='Hibid Automation')
    
#     # app.title("Hibid Automation")
#     # root
#     root_frm = ttk.Frame(root, padding=10)
#     root_frm.grid()

#     print_hierarchy(root)

#     tit_frm = ttk.Frame(root_frm).grid(row=0, column=0)

#     ttk.Label(root_frm, text='Automation').grid(column=0, row=0)

#     # ttk.Label(l, text='Auto2')
    

#     btn = ttk.Button(root_frm, text='Quit', command=root.destroy)
#     btn.grid(column=1, row=0, padx=50, ipadx=20, ipady=20)
#     btn.configure(text='goodbye')
#     # Button(root_frm, text='Test Button', fg='red', bg='blue').grid(row=1, column=0)
#     print(btn['text'])

#     # btn_open = Button(root_frm, text="Open File", command=open_file)
#     # btn_open.pack(pady=10)

#     # btn_start = Button(root_frm, text="Start Automation", command=start_automation)
#     # btn_start.pack(pady=10)

#     root.mainloop()
    


# app_data_path = Path(os.getenv('LOCALAPPDATA')) / "AutoBid"
# app_data_path.mkdir(exist_ok=True)  # Create the folder if it doesn't exist
# credentials_file = app_data_path / "credentials.json"
    
# def load_credentials():
#     if credentials_file.exists():
#         with open(credentials_file, 'r') as file:
#             return json.load(file)
#     return None

# def save_credentials(bot_acc, bot_pwd, mng_acc, mng_pwd):
#     with open(credentials_file, 'w') as file:
#         json.dump({"BOT_ACC": bot_acc, "BOT_PASS": bot_pwd, "MNG_ACC": mng_acc, "MNG_PWD": mng_pwd}, file)

# def get_local_dir():
#     return app_data_path

if __name__ == '__main__':
    # tk_gui()
    
    # ENVFILE = os.getenv('ENV')
    # if(ENVFILE != 'development'):
    #     env_file = f".env"
    # else:
    #     env_file = f".env.{ENVFILE}"
    # load_dotenv(dotenv_path=env_file)

    root = Tk()
    BidGui(root)
    root.mainloop()
    
    
    # item_log = []
    # item_log.append({
    #     # "automation_link": "http:example.com",
    #     "lot": "50",
    #     # "client": "someaccount.com",
    #     "target_price": 100.0,
    #     "previous_price": 45.50,
    #     "status": "success",
    #     "timestamp": datetime.now().isoformat()
    # })
    # # if(len(item_log) == 20):
    # response = requests.post(f'{os.getenv("LOG_BACK")}/items/logs', json={"items": item_log, "automation_link": "http:example.com", "client": "someaccount.com"})
    # print(response.text)


    # response = requests.post(f'{os.getenv("LOG_BACK")}/logs/transaction', 
    #                 json={
    #                         "transaction_id": "abcd",
    #                         "automation_link": "abcd",
    #                         "timestamp": datetime.now().isoformat(),
    #                         "client": "abcd",
    #                         "action": "Automated Bid",
    #                         "success": True,
    #                         # "message": "",
    #                         "cust_win_count": 10,
    #                         "cust_win_increased_price": 10.55,
    #                         "bot_win_count": 10,
    #                         "bot_win_increased_price": 10.65
    #                     })
    # print(f'Log: {response.text}')