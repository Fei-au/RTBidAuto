from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from playwright.sync_api import sync_playwright
import pandas as pd
from time import sleep
import os

class BidGui:

    def __init__(self, root) -> None:
        self.form_msg = None
        self.registered = False
        self.bot_page = None

        root.title("Hibid Automation")

        mainframe = ttk.Frame(root, padding=10)
        mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        self.manager_acc = StringVar()
        self.manager_pwd = StringVar()

        self.bot_acc = StringVar()
        self.bot_pwd = StringVar()

        self.management_lot_link = StringVar()
        self.bid_lot_link = StringVar()

        ttk.Label(mainframe, text='Hibid Management Account').grid(column=1, row=1, sticky=W)
        manager_acc_entry = ttk.Entry(mainframe, width=10, textvariable=self.manager_acc)
        manager_acc_entry.grid(column=2, row=1, sticky=(W, E))

        ttk.Label(mainframe, text='Hibid Management Password').grid(column=1, row=2, sticky=W)
        manager_pwd_entry = ttk.Entry(mainframe, show="*", width=10, textvariable=self.manager_pwd)
        manager_pwd_entry.grid(column=2, row=2, sticky=(W, E))

        ttk.Label(mainframe, text='Hibit Bot Account').grid(column=1, row=3, sticky=W)
        bot_acc_entry = ttk.Entry(mainframe, width=10, textvariable=self.bot_acc)
        bot_acc_entry.grid(column=2, row=3, sticky=(W, E))

        ttk.Label(mainframe, text='Hibit Bot Password').grid(column=1, row=4, sticky=W)
        bot_pwd_entry = ttk.Entry(mainframe, show="*", width=10, textvariable=self.bot_pwd)
        bot_pwd_entry.grid(column=2, row=4, sticky=(W, E))

        ttk.Label(mainframe, text='Hibid Management Link').grid(column=1, row=5, sticky=W)
        bot_pwd_entry = ttk.Entry(mainframe, width=15, textvariable=self.management_lot_link)
        bot_pwd_entry.grid(column=2, row=5, sticky=(W, E))

        ttk.Label(mainframe, text='Bid Lot Link').grid(column=1, row=6, sticky=W)
        bot_pwd_entry = ttk.Entry(mainframe, width=15, textvariable=self.bid_lot_link)
        bot_pwd_entry.grid(column=2, row=6, sticky=(W, E))

        ttk.Button(mainframe, text='Open Auction File', command=self.open_file).grid(ipadx=5, column=2, row=101, sticky=W)
        ttk.Button(mainframe, text='Start Automation', command=self.start_automation).grid(ipadx=5, column=2, row=102, sticky=W)

        ttk.Button(mainframe, text="Quit", command=root.destroy).grid(ipadx=5, column=3, row=201, sticky=E)
        

        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.mainframe = mainframe
        root.focus()

    def open_file(self):
        filepath = filedialog.askopenfilename()
        print(f'file name is: {filepath}')
        with open(filepath, 'r') as f:
            df = pd.read_csv(f)
            self.lot_dict = df.set_index('lot')['msrp_price']

        ttk.Label(self.mainframe, text='File import success!').grid(column=3, row=101, sticky=W, padx=5)
        return
    
    def start_automation(self):
        if self.check_form() or True:
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False)
                    context = browser.new_context()

                    # Open hibid auction page and login bot acc
                    page = context.new_page()
                    page.goto("https://hibid.com/")
                    page.get_by_label("Login / New Bidder", exact=True).click()

                    # Test values
                    self.bot_acc.set(os.getenv('BOT_ACC'))
                    self.bot_pwd.set(os.getenv)
                    self.bid_lot_link.set(os.getenv('AUCTION_LINK'))

                    page.locator('[aria-labelledby="email-label"]').fill(self.bot_acc.get())
                    page.locator('[aria-labelledby="password-label"]').fill(self.bot_pwd.get())
                    sleep(10)
                    # page.get_by_text("Log On", exact=True).click()
                    # page.wait_for_load_state('networkidle')
                    login_status = page.locator('[class="welcome-label"]')
                    if login_status.count() == 0:
                        ttk.Label(self.mainframe, text='Login bot account failed, please restart automation').grid(column=1, row=151, sticky=W)
                        browser.close()
                        return
                    self.bot_page = page

                    # Test data
                    self.manager_acc.set('123@outlook.com')
                    self.manager_pwd.set('123456')

                    myhibid_page = context.new_page()
                    myhibid_page.goto('https://my.hibid.com/')
                    
                    myhibid_page.locator('[id="auctioneer-logon-username"]').fill(self.manager_acc.get())
                    myhibid_page.locator('[id="Password"]').fill(self.manager_pwd.get())
                    myhibid_page.get_by_role("button", )

                    sleep(600)
            except Exception as e:
                print(e)
                # self.bot_bid(lot=2, max_bid_price=350)
        else:
            ttk.Label(self.mainframe, text='Please input all required fields').grid(column=3, row=101, sticky=W, padx=5)
                

    def bot_bid(self, max_bid_price, lot=61):
        self.bot_page.goto(self.bid_lot_link.get() + f'?q={lot}')
        lot = self.bot_page.locator(f'app-lot-tile:has-text("Lot {lot} | ")')
        
        lot.get_by_label('Bid', exact=True).click()
        self.bot_register_auction()

        bid_modal = self.bot_page.locator('app-bid-modal')
        bid_price_list = []
        current_bid_amount = 0
        bid_button = bid_modal.get_by_label("Click to increase the bid increment", exact=True)
        while current_bid_amount < max_bid_price:
            bid_button.click()
            current_bid_amount = float(bid_modal.get_by_label("Bid amount", exact=True).input_value())
            bid_price_list.append(current_bid_amount)
            print(bid_price_list)
        bid_price_list.pop()
        if len(bid_price_list) <= 1:
            bid_modal.get_by_label("Close", exact=True).click()
        else:
            bid_modal.get_by_label("Bid amount", exact=True).fill(str(bid_price_list[-1]))

        # self.bot_page.get_by_label("Click to confirm bid", exact=True)
        sleep(600)

        
    def bot_register_auction(self):
        modals = self.bot_page.locator('modal-container')
        if modals.count() == 1:
            self.registered = True
        if not self.registered:
            self.bot_page.get_by_label("Agree to the terms and conditions").check()
            self.bot_page.get_by_label("Click to register for the auction").click()
            welcome_banner = self.bot_page.locator('modal-container:has-text("Welcome to")')
            welcome_banner.get_by_label("Close", exact=True).click()
            self.registered = True

    def clear_subscribe_modal(self):
        print('nothing')


    def check_form(self):
        result = False if self.manager_acc.get() == '' or self.manager_pwd.get() == '' or self.bot_acc.get() == '' or self.bot_pwd.get() == '' or self.bid_lot_link.get() == '' or self.management_lot_link.get() == '' else True
        if not result:
            if self.form_msg is None:
                self.form_msg = ttk.Label(self.mainframe, text='Please input all required fileds')
            self.form_msg.grid(row=151, column=1, sticky=W)
        else:
            self.form_msg is None or self.form_msg.grid_remove()
        return result
            
        




    

