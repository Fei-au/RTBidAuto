from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from playwright.async_api import async_playwright
import pandas as pd
from time import sleep
import threading
import os
import asyncio
from exceptions import NavigationError
from automation import Automation

class BidGui:

    def __init__(self, root) -> None:
        self.form_msg = None
        self.registered = False
        self.bot_page = None
        self.automation = Automation()

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
        ttk.Button(mainframe, text='Login accounts', command=self.login_accounts).grid(ipadx=5, column=1, row=102, sticky=W)
        ttk.Button(mainframe, text='Start Automation', command=self.start_automation).grid(ipadx=5, column=2, row=102, sticky=W)

        ttk.Button(mainframe, text="Quit", command=root.destroy).grid(ipadx=5, column=3, row=201, sticky=E)
        
        # Add padding to each widget
        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)
        # Focus on root window
        self.mainframe = mainframe
        root.focus()
        
        
        # Test values
        self.bot_acc.set(os.getenv('BOT_ACC'))
        self.bot_pwd.set(os.getenv('BOT_PWD'))
        self.bid_lot_link.set(os.getenv('AUCTION_LINK'))
        
        self.manager_acc.set(os.getenv('MNG_ACC'))
        self.manager_pwd.set(os.getenv('MNG_PWD'))
        self.management_lot_link.set(os.getenv('MNG_LINK'))
        # Start asyncio loop
    #     self.loop = asyncio.get_event_loop()
    #     self.root = root
    #     self.root.after(100, self.process_events)
        
    # def process_events(self):
    #     self.loop.call_soon_threadsafe(self.loop.stop)
    #     self.root.after(100, self.process_events)
    
    def open_file(self):
        filepath = filedialog.askopenfilename()
        print(f'file name is: {filepath}')
        with open(filepath, 'r') as f:
            df = pd.read_csv(f)
            self.lot_dict = df.set_index('lot')['msrp_price']

        ttk.Label(self.mainframe, text='File import success!').grid(column=3, row=101, sticky=W, padx=5)
        return
    
    def login_accounts(self):
        if self.check_form():
            asyncio.run(self.login_accounts_async())
            
    def start_automation(self):
        asyncio.run(self.automation.start_automation_async(self.bot_page, self.mng_page))
        
    
    async def login_accounts_async(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()
        try:
            # self.bot_page = await self.context.new_page()
            # await self.automation.login_bot(self.bot_page, self.bot_acc.get(), self.bot_pwd.get(), self.bid_lot_link.get())
            self.mng_page = await self.context.new_page()
            await self.automation.login_manager(self.mng_page, self.manager_acc.get(), self.manager_pwd.get(), self.management_lot_link.get())
        except NavigationError as e:
            ttk.Label(self.mainframe, text=e).grid(column=1, row=151, sticky=W)
            # await self.browser.close()
        except Exception as e:
            ttk.Label(self.mainframe, text=e).grid(column=1, row=151, sticky=W)
            await self.browser.close()
            
    


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
            
        




    

