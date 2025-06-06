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
import random
import datetime
import time
from urllib.parse import urlparse
from tools import get_upper_level_url, save_bidder_registration, load_bidder_registration, get_auction_id




'''
1. add a start filter bidder button
2. add a stop filter bidder button
3. click start filter button
4. open a tag in management browser
5. goto registration link by replace "lotstats" with "register" in mng link
6. replace link with query string ?buyer=0&siteId=0&regsortorder=8&All=False
7. find bidder table tds, then iterate through each td
8. find if 1. the bid total price is greater than 200, 2. reputation is lower than 20, 3. not in the special_allowed_list, click the td to further inspect
9. in the detailed modal, iterate all items, if in the accepted items, 50% of them are larger than 200, then block the bidder.
    block bidder:
    1. declined all items that the bidder wins
    2. back to main registration page, block the bidder
    3. add the blocked bidder id into the already_blocked_list, so next time it won't be checked again
10. every 1.5 minutes, repeat the process
'''


class BidGui:

    def __init__(self, root) -> None:
        self.registered = False
        self.message = None
        self.log = None
        self.playwright = None
        self.mng_browser = None
        self.mng_bidder_page = None
        self.bot_page = None
        self.mng_page = None
        self.auction_id = None
        self.automation = Automation(self.show_log, self.show_message)
        # Add variables for infinite bid
        self.rd = 1
        self.start = None
        self.end = None

        root.title("Hibid Automation")

        mainframe = ttk.Frame(root, padding=5)
        mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        self.manager_acc = StringVar()
        self.manager_pwd = StringVar()

        self.bot_acc = StringVar()
        self.bot_pwd = StringVar()

        self.management_lot_link = StringVar()
        self.bid_lot_link = StringVar()
        
        self.twenty_switch = BooleanVar()


        mainframe.grid_rowconfigure(151, weight=1)  # Log/message row
        mainframe.grid_columnconfigure(1, weight=1)  # Left area start
        mainframe.grid_columnconfigure(2, weight=1)
        mainframe.grid_columnconfigure(3, weight=1)  # Left area end
        mainframe.grid_columnconfigure(5, weight=4)  # Right area start
        mainframe.grid_columnconfigure(6, weight=4)
        mainframe.grid_columnconfigure(7, weight=1) 

        ttk.Label(mainframe, text='*Hibid Management Account').grid(column=1, row=1, sticky=W)
        manager_acc_entry = ttk.Entry(mainframe, width=30, textvariable=self.manager_acc)
        manager_acc_entry.grid(column=2, row=1, sticky=(W))

        ttk.Label(mainframe, text='*Hibid Management Password').grid(column=1, row=2, sticky=W)
        manager_pwd_entry = ttk.Entry(mainframe, show="*", width=30, textvariable=self.manager_pwd)
        manager_pwd_entry.grid(column=2, row=2, sticky=(W))

        ttk.Label(mainframe, text='Hibit Bot Account').grid(column=1, row=3, sticky=W)
        bot_acc_entry = ttk.Entry(mainframe, width=30, textvariable=self.bot_acc, state='disabled')
        bot_acc_entry.grid(column=2, row=3, sticky=(W))

        ttk.Label(mainframe, text='Hibit Bot Password').grid(column=1, row=4, sticky=W)
        bot_pwd_entry = ttk.Entry(mainframe, show="*", width=30, textvariable=self.bot_pwd, state='disabled')
        bot_pwd_entry.grid(column=2, row=4, sticky=(W))

        ttk.Label(mainframe, text='*Hibid Management Link').grid(column=1, row=5, sticky=W)
        bot_pwd_entry = ttk.Entry(mainframe, width=30, textvariable=self.management_lot_link)
        bot_pwd_entry.grid(column=2, row=5, sticky=(W))

        ttk.Label(mainframe, text='*Bid Lot Link').grid(column=1, row=6, sticky=W)
        bot_pwd_entry = ttk.Entry(mainframe, width=30, textvariable=self.bid_lot_link)
        bot_pwd_entry.grid(column=2, row=6, sticky=(W))  
        
        ttk.Label(mainframe, text=">100 20% switch").grid(column=1, row=7, sticky=W)
        twenty_switch = ttk.Checkbutton(mainframe, variable=self.twenty_switch)
        twenty_switch.grid(column=2, row=7, sticky=(W))

        ttk.Button(mainframe, text='1. Open Auction File', command=self.open_file).grid(ipadx=5, column=1, row=101, sticky=W)
        ttk.Button(mainframe, text='2. Login Accounts', command=self.login_accounts).grid(ipadx=5, column=2, row=101, sticky=W)
        ttk.Button(mainframe, text='3. Collect Information', command=self.collect_information).grid(ipadx=5, column=1, row=102, sticky=W)
        self.start_button = ttk.Button(mainframe, text='4. Start Automation', command=self.start_automation)
        self.start_button.grid(ipadx=5, column=2, row=102, sticky=W)
        self.stop_button = ttk.Button(mainframe, text='Stop Automation', command=self.stop_automation, state='disabled')
        self.stop_button.grid(ipadx=5, column=3, row=102, sticky=(W))
        
        self.infinate_button = ttk.Button(mainframe, text='Infinate Bid', command=self.infinite_bid)
        self.infinate_button.grid(ipadx=5, column=3, row=103, sticky=(W))

        ttk.Button(mainframe, text="Quit", command=root.destroy).grid(ipadx=5, column=7, row=201, sticky=W)
        
        # Add a divider
        ttk.Separator(mainframe, orient='horizontal').grid(column=1, row=104, columnspan=3, sticky=(W,E))
        
        # Registration filter buttons
        self.start_filter = ttk.Button(mainframe, text='Start Filter Bidder', command=self.start_filter_bidder)
        self.start_filter.grid(ipadx=5, column=2, row=110, sticky=W)
        self.stop_filter = ttk.Button(mainframe, text='Stop Filter Bidder', command=self.stop_filter_bidder, state='disabled')
        self.stop_filter.grid(ipadx=5, column=3, row=110, sticky=(W))

        # Msg area setup
        self.message = Text(mainframe, wrap="word", height=30)
        self.message.grid(column=1, row=151, columnspan=3,  sticky=(N, S, W, E))
        self.message.config(state="disabled")  # Start as read-only
        
        # Scrollbar for the msg area
        self.scrollbar = ttk.Scrollbar(mainframe, orient="vertical", command=self.message.yview)
        self.scrollbar.grid(column=4, row=151, sticky=(N, S, W, E))
        self.message["yscrollcommand"] = self.scrollbar.set

        # Log area setup
        self.log_text = Text(mainframe, wrap="word", height=30)
        self.log_text.grid(column=5, row=1, rowspan=151, columnspan=3, sticky=(N, S, E, W))
        self.log_text.config(state="disabled")  # Start as read-only
        
        # Scrollbar for the log area
        self.scrollbar = ttk.Scrollbar(mainframe, orient="vertical", command=self.log_text.yview)
        self.scrollbar.grid(column=8, row=1, rowspan=151, sticky=(N, S, W, E))
        self.log_text["yscrollcommand"] = self.scrollbar.set
        
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
            # bot_acc = credentials.get("BOT_ACC")
            # bot_pwd = credentials.get("BOT_PWD")
            manager_acc = credentials.get("MNG_ACC")
            manager_pwd = credentials.get("MNG_PWD")
            # self.bot_acc.set(bot_acc)
            # self.bot_pwd.set(bot_pwd)
            self.manager_acc.set(manager_acc)
            self.manager_pwd.set(manager_pwd)
            
            mng_link = credentials.get("MNG_LINK")
            bid_link = credentials.get("BID_LINK")
            self.management_lot_link.set(mng_link)
            self.bid_lot_link.set(bid_link)
            
        
        # Set twenty switch as default
        self.twenty_switch.set(False)
        
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
            future = asyncio.run_coroutine_threadsafe(self.login_accounts_async(), self.loop)
            def done_callback(fut):
                try:
                    res = fut.result()
                    self.show_message(res)
                except Exception as e:
                    self.show_log(f"Error in login: {str(e)}")
            future.add_done_callback(done_callback)
            
    def collect_information(self):
        future = asyncio.run_coroutine_threadsafe(self.automation.get_bids_info(
            self.mng_page, 1,
            ), self.loop)
        def done_callback(fut):
            try:
                res = fut.result()
                self.show_message(res)
            except Exception as e:
                self.show_log(f"Error in collection information: {str(e)}")
        future.add_done_callback(done_callback)
        
    def infinite_bid(self):
        if not self.automation.is_running:
            self.automation.is_running = True
            self.automation.set_twenty_switch(self.twenty_switch.get())
            self.stop_button.config(state='normal')
            self.infinate_button.config(state='disabled')
            self.start_button.config(state='disabled')
            self.rd = 1
            # Create the async task
            self.start = None
            self.end = None
            
            async def sleep_func(diff):
                if diff < 90:
                    sleep_time = round(90 - diff, 2)
                    self.show_message(f"Waiting for {sleep_time} seconds before next auto bid round...")
                    await asyncio.sleep(sleep_time)
                return
                
            def get_info():
                self.start = datetime.datetime.now()
                self.show_message(f"Starting infinite bid automation round [ {self.rd} ]...")
                futrue_get_info = asyncio.run_coroutine_threadsafe(
                    self.automation.get_bids_info(
                        self.mng_page, 2,
                    ),
                    self.loop
                )
                def get_info_done_callback(fut):
                    try:
                        res = fut.result()
                        self.show_message(res)
                        if self.automation.is_running:
                            automation()
                        else:
                            self.clean_infinite_bid()
                    except Exception as e:
                        self.show_log(f"Error in getting bid information: {str(e)}")
                futrue_get_info.add_done_callback(get_info_done_callback)
            
            def automation():
                self.start = datetime.datetime.now()
                future_automation = asyncio.run_coroutine_threadsafe(
                    self.automation.start_automation_async(
                        self.bot_page,
                        self.mng_page,
                        self.bot_acc.get(),
                        self.manager_acc.get(),
                        2,  # 2 for infinite bid
                    ),
                    self.loop
                )
                
                def automation_done_callback(fut):
                    try:
                        res = fut.result()
                        self.show_message(res)
                        self.end = datetime.datetime.now()
                        diff = round((self.end - self.start).total_seconds(), 2)
                        self.show_message(f"Auto bid round [ {self.rd} ] completed in {diff} seconds.")
                        self.rd += 1
                        if self.automation.is_running:
                                sleep_future = asyncio.run_coroutine_threadsafe(
                                    sleep_func(diff),
                                    self.loop
                                )
                                def sleep_done(_):
                                    get_info()
                                sleep_future.add_done_callback(sleep_done)
                        else:
                            self.clean_infinite_bid()
                    except Exception as e:
                        self.show_log(f"Error in automation: {str(e)}")
                future_automation.add_done_callback(automation_done_callback)
            
            # Start the first get_info call
            get_info()
                

    def start_automation(self):
        try:
            if not self.automation.is_running:
                self.automation.is_running = True
                self.automation.set_twenty_switch(self.twenty_switch.get())
                self.stop_button.config(state='normal')
                self.start_button.config(state='disabled')
                self.infinate_button.config(state='disabled')
                
                # Create the async task
                future = asyncio.run_coroutine_threadsafe(
                    self.automation.start_automation_async(
                        self.bot_page,
                        self.mng_page,
                        self.bot_acc.get(),
                        self.manager_acc.get(),
                        1, # 1 for single bid
                    ),
                    self.loop
                )
                
                def done_callback(fut):
                    try:
                        res = fut.result()
                        print(f"Automation result: {res}")
                        self.show_message(res)
                    except Exception as e:
                        self.show_log(f"Error in automation: {str(e)}")
                    finally:
                        # For normal finish
                        self.stop_automation_cleanup()
                future.add_done_callback(done_callback)
                
        except Exception as e:
            self.automation.stop_automation()
            self.stop_button.config(state='disabled') 
            self.start_button.config(state='normal')
            error_details = traceback.format_exc()
            self.show_log(error_details)
          

    def stop_automation_cleanup(self):
        if self.automation.is_running:
            self.automation.stop_automation()
            self.stop_button.config(state='disabled')
            self.start_button.config(state='normal')
            self.infinate_button.config(state='normal')
            
    def clean_infinite_bid(self):
        self.rd = 1
        self.start = None
        self.end = None
            
    def stop_automation(self):
        self.show_log("Stopping automation... Please wait for current operation to complete.")
        self.stop_automation_cleanup()
        
    def show_message(self, msg):
        # Enable text widget to insert new msg
        self.message.config(state="normal")
        
        # Insert log at the end with a new line
        self.message.insert("end", f"[{datetime.datetime.now().replace(microsecond=0)}]: " + msg + "\n")
        
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
        self.log_text.insert("end", f"[{datetime.datetime.now().replace(microsecond=0)}]: " + log + "\n")
        
        # Scroll to the end
        self.log_text.see("end")
        
        # Disable text widget to prevent editing
        self.log_text.config(state="disabled")
    
        
        
    async def login_accounts_async(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        # bot_data_dir = get_local_dir() / "playwright-bot-data"
        # bot_data_dir.mkdir(exist_ok=True)  # Create the folder if it doesn't exist
        try:
            browser = await self.playwright.chromium.connect_over_cdp("http://localhost:9222")
            # Get the first existing context or create one if none exists
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
            else:
                context = await browser.new_context()
            
            # Get the first existing page or open a new one
            pages = context.pages
            if pages:
                page = pages[0]
            else:
                page = await context.new_page()
            
            self.bot_page = page
            
            # self.bot_browser = await self.playwright.chromium.launch_persistent_context(
            #     bot_data_dir, 
            #     headless=False, 
            #     viewport=viewport,
            #     locale="en-US",
            #     timezone_id="America/New_York",
            #     user_agent="Mozilla/5.0 (Windows NT 5.0; Win64; x64) AppleWebKit/537.36 "
            #             "(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
            #     args=[
            #         "--start-maximized",   # Optional: starts maximized (can help mimic real user)
            #     ],
            #     # accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            #     # accept-encoding: 'gzip, deflate, br, zsdch, zstd',

            # )
            # self.bot_page = self.bot_browser.pages[0]
            bot_acc = self.bot_acc.get()
            bot_pwd = self.bot_pwd.get()
            manager_acc = self.manager_acc.get()
            manager_pwd = self.manager_pwd.get()
            management_lot_link = self.management_lot_link.get()
            bid_lot_link = self.bid_lot_link.get()
            
            await self.automation.login_bot(self.bot_page, self.bot_acc.get(), self.bot_pwd.get(), self.bid_lot_link.get())
            if not self.mng_browser:
                self.mng_browser = await self.launch_context()
            if not self.mng_page:
                self.mng_page = await self.mng_browser.new_page()
            
            await self.automation.login_manager(self.mng_page, manager_acc, manager_pwd, management_lot_link)
            save_credentials(bot_acc, bot_pwd, manager_acc, manager_pwd, management_lot_link, bid_lot_link)
            return 'Login success! Please collect bid information.'
        except NavigationError as e:
            self.show_log(e)
            await self.browser.close()
        except Exception as e:
            self.show_log(e)
            await self.browser.close()

    async def launch_context(self):
        manager_data_dir = get_local_dir() / "playwright-mng-data"
        manager_data_dir.mkdir(exist_ok=True)  # Create the folder if it doesn't exist
        context = await self.playwright.chromium.launch_persistent_context(manager_data_dir, headless=False)
        return context


    def start_filter_bidder(self):
        asyncio.run_coroutine_threadsafe(self.start_filter_bidder_async(), self.loop)
            
    async def start_filter_bidder_async(self):
        if not self.automation.is_filter_running:
            self.automation.is_filter_running = True
            self.start_filter.config(state='disabled')
            self.stop_filter.config(state='normal')
            self.show_message("Starting filter bidder automation...")
            try:
                result = await self.login_filter_bidder_async()
                self.show_message(result)
                self.show_message("Start filtering...")
                result2 = await self.automation.filter_bidder(self.mng_bidder_page, self.auction_id)
                self.stop_filter_bidder()
                self.show_message(result2)
            except Exception as e:
                self.show_log(f"Error in filter bidder: {str(e)}")
            
            
    def stop_filter_bidder(self):
        if self.automation.is_filter_running:
            self.automation.is_filter_running = False
            self.start_filter.config(state='normal')
            self.stop_filter.config(state='disabled')
            self.show_message("Filter bidder automation stopped.")

    async def login_filter_bidder_async(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        if not self.mng_browser:
            self.mng_browser = await self.launch_context()
        if not self.mng_bidder_page:
            self.mng_bidder_page = await self.mng_browser.new_page()
        manager_acc = self.manager_acc.get()
        manager_pwd = self.manager_pwd.get()
        manager_link = self.management_lot_link.get()
        await self.automation.login_manager(self.mng_bidder_page, manager_acc, manager_pwd, manager_link.replace("lotstats", "register"))
        # Load bidder registration information
        self.auction_id = get_auction_id(manager_link)
        lists = load_bidder_registration(self.auction_id)
        if lists:
            self.automation.special_allowed_list = lists.get("special_allowed_list", [])
            self.automation.already_blocked_list = lists.get("already_blocked_list", [])
        else:
            self.automation.special_allowed_list = []
            self.automation.already_blocked_list = []
        return "Login filter bidder success"

    
    def check_form(self):
        check_success = False if self.manager_acc.get() == '' or self.manager_pwd.get() == '' else True
        if not check_success:
            self.show_message("Please input all required fileds")
        # else:
        #     self.hide_message()
        return check_success








