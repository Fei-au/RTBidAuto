from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from playwright.async_api import async_playwright
import threading
import asyncio
from exceptions import NavigationError
from automation import Automation
from tools import load_credentials, save_credentials, get_local_dir
import os
import traceback

class BidGui:

    def __init__(self, root) -> None:
        self.registered = False
        self.message = None
        self.log = None
        self.bot_page = None
        self.automation = Automation(self.show_log)

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
        
        # Log area setup
        self.log_text = Text(mainframe, wrap="word", width=50, height=15)
        self.log_text.grid(column=2, row=151, sticky=(W, E))
        self.log_text.config(state="disabled")  # Start as read-only
        
        # Scrollbar for the log area
        self.scrollbar = ttk.Scrollbar(mainframe, orient="vertical", command=self.log_text.yview)
        self.scrollbar.grid(column=3, row=151, sticky=(N, S))
        self.log_text["yscrollcommand"] = self.scrollbar.set
        
        
        # Log area setup
        self.message = Text(mainframe, wrap="word", width=30, height=15)
        self.message.grid(column=1, row=151, sticky=(W, E))
        self.message.config(state="disabled")  # Start as read-only

        
        # Add padding to each widget
        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)
        # Focus on root window
        self.mainframe = mainframe
        root.focus()
        
        
        # # Test values
        # self.bot_acc.set(os.getenv('BOT_ACC'))
        # self.bot_pwd.set(os.getenv('BOT_PWD'))
        # self.bid_lot_link.set(os.getenv('AUCTION_LINK'))
        
        # self.manager_acc.set(os.getenv('MNG_ACC'))
        # self.manager_pwd.set(os.getenv('MNG_PWD'))
        # self.management_lot_link.set(os.getenv('MNG_LINK'))
        
        # Load credential from local json file
        credentials = load_credentials()
        if credentials:
            bot_acc = credentials.get("BOT_ACC")
            bot_pwd = credentials.get("BOT_PWD")
            manager_acc = credentials.get("MNG_ACC")
            manager_pwd = credentials.get("MNG_PWD")
            self.bot_acc.set(bot_acc)
            self.bot_pwd.set(bot_pwd)
            self.manager_acc.set(manager_acc)
            self.manager_pwd.set(manager_pwd)
        
        # Start asyncio loop
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.start_event_loop, daemon=True)
        self.loop_thread.start()
    #     self.loop = asyncio.get_event_loop()
    #     self.root = root
    #     self.root.after(100, self.process_events)
        
    # def process_events(self):
    #     self.loop.call_soon_threadsafe(self.loop.stop)
    #     self.root.after(100, self.process_events)
    
    def start_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    # Open file dialog to import auction export file, must have msrp_price and lot columns
    def open_file(self):
        try:
            filepath = filedialog.askopenfilename()
            if(filepath):
                self.automation.file_to_lot_dict(filepath)
                self.show_message('File import success!')
        except Exception as e:
            error_details = traceback.format_exc()
            self.show_log(error_details)
    
    # Login manager and bot accounts
    def login_accounts(self):
        if self.check_form():
            asyncio.run_coroutine_threadsafe(self.login_accounts_async(), self.loop)
            
    def start_automation(self):
        try:
            # if hasattr(self, 'mng_page') and self.mng_page is not None and hasattr(self, 'bot_page') and self.bot_page is not None:
                
                asyncio.run_coroutine_threadsafe(self.automation.start_automation_async(self.bot_page, self.mng_page, self.bot_acc.get(), self.manager_acc.get()), self.loop)
                # asyncio.run_coroutine_threadsafe(self.automation.bot_bid(self.bot_page, "2", 425), self.loop)
            # else:
            #     self.show_message('Please login accounts first')
        except Exception as e:
            error_details = traceback.format_exc()
            self.show_log(error_details)
            
    def show_message(self, msg):
        # Enable text widget to insert new msg
        self.message.config(state="normal")
        
        # Insert log at the end with a new line
        self.message.insert("end", msg + "\n")
        
        # Scroll to the end
        self.message.see("end")
        
        # Disable text widget to prevent editing
        self.message.config(state="disabled")
        
    # def hide_message(self):
    #     if(self.message):
    #         # Enable text widget to insert new msg
    #         self.message.config(state="normal")
    #         self.message.("end", msg + "\n")
    
    def show_log(self, log):
        # Enable text widget to insert new log
        self.log_text.config(state="normal")
        
        # Insert log at the end with a new line
        self.log_text.insert("end", log + "\n")
        
        # Scroll to the end
        self.log_text.see("end")
        
        # Disable text widget to prevent editing
        self.log_text.config(state="disabled")
    
        
        
    async def login_accounts_async(self):
        self.playwright = await async_playwright().start()
        bot_data_dir = get_local_dir() / "playwright-bot-data"
        manager_data_dir = get_local_dir() / "playwright-mng-data"
        bot_data_dir.mkdir(exist_ok=True)  # Create the folder if it doesn't exist
        manager_data_dir.mkdir(exist_ok=True)  # Create the folder if it doesn't exist

        try:
            self.bot_browser = await self.playwright.chromium.launch_persistent_context(bot_data_dir, headless=False)
            self.bot_page = self.bot_browser.pages[0]
            bot_acc = self.bot_acc.get()
            bot_pwd = self.bot_pwd.get()
            manager_acc = self.manager_acc.get()
            manager_pwd = self.manager_pwd.get()
            await self.automation.login_bot(self.bot_page, self.bot_acc.get(), self.bot_pwd.get(), self.bid_lot_link.get())
            self.mng_browser = await self.playwright.chromium.launch_persistent_context(manager_data_dir, headless=False)
            self.mng_page = self.mng_browser.pages[0]
            await self.automation.login_manager(self.mng_page, self.manager_acc.get(), self.manager_pwd.get(), self.management_lot_link.get())
            save_credentials(bot_acc, bot_pwd, manager_acc, manager_pwd)
            self.show_message('Login success! Now you can start automation.')
        except NavigationError as e:
            self.show_message(e)
            # await self.browser.close()
        except Exception as e:
            self.show_message(e)
            await self.browser.close()

    def check_form(self):
        check_success = False if self.manager_acc.get() == '' or self.manager_pwd.get() == '' or self.bot_acc.get() == '' or self.bot_pwd.get() == '' or self.bid_lot_link.get() == '' or self.management_lot_link.get() == '' else True
        if not check_success:
            self.show_message("Please input all required fileds")
        # else:
        #     self.hide_message()
        return check_success
            
        




    

