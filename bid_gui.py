from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter import font as tkfont
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
from tools import load_bidder_registration, get_auction_id
from risky_scan import RiskyScanner
import csv

try:
    import sv_ttk
    _HAS_SV_TTK = True
except ImportError:
    _HAS_SV_TTK = False

# Sun Valley light palette (matches sv-ttk light theme)
COLOR_TEXT_BG = "#fafafa"
COLOR_TEXT_FG = "#1a1a1a"
COLOR_BORDER = "#d1d1d1"
COLOR_SUBTLE_FG = "#5a5a5a"
COLOR_ACCENT = "#0067c0"




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
        self.root = root
        self.registered = False
        self.message = None
        self.log = None
        self.playwright = None
        self.mng_browser = None
        self.mng_bidder_page = None
        self.bot_page = None
        self.mng_page = None
        self.auction_id = None
        self.automation = Automation(self.show_log, self.show_message, self.update_block_list)
        self.rd = 1
        self.start = None
        self.end = None

        self.manager_acc = StringVar()
        self.manager_pwd = StringVar()
        self.allowed_list = StringVar()
        self.blocked_list = StringVar()
        self.bot_acc = StringVar()
        self.bot_pwd = StringVar()
        self.management_lot_link = StringVar()
        self.bid_lot_link = StringVar()
        self.twenty_switch = BooleanVar()
        self.block_us_bidder_switch = BooleanVar()

        self.risky_scanner = RiskyScanner(self.show_log, self.show_message)
        self.risky_lotstat_page = None
        self.risky_register_page = None
        self.risky_auction_id = StringVar()
        self.risky_high_bid_threshold = StringVar(value='50')
        self.risky_score_threshold = StringVar(value='20')

        self.status_var = StringVar(value='Ready')
        self.round_var = StringVar(value='')
        self.last_action_var = StringVar(value='')

        root.title("Hibid Automation")
        root.geometry("1320x880")
        root.minsize(1080, 740)

        self._init_styles()
        self._build_menu(root)
        self._build_header(root)
        self._build_statusbar(root)

        main_paned = ttk.PanedWindow(root, orient='horizontal')
        main_paned.pack(fill=BOTH, expand=True, padx=12, pady=(0, 6))

        left_container = ttk.Frame(main_paned)
        main_paned.add(left_container, weight=3)
        notebook = ttk.Notebook(left_container)
        notebook.pack(fill=BOTH, expand=True, padx=2, pady=2)

        self._build_bid_tab(notebook)
        self._build_filter_tab(notebook)
        self._build_risky_tab(notebook)

        right_container = ttk.Frame(main_paned)
        main_paned.add(right_container, weight=2)
        self._build_right_panel(right_container)

        credentials = load_credentials()
        if credentials:
            self.manager_acc.set(credentials.get("MNG_ACC") or '')
            self.manager_pwd.set(credentials.get("MNG_PWD") or '')
            self.management_lot_link.set(credentials.get("MNG_LINK") or '')
            self.bid_lot_link.set(credentials.get("BID_LINK") or '')

        self.twenty_switch.set(False)
        self.block_us_bidder_switch.set(True)

        root.focus()

        # Start asyncio loop
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.start_event_loop, daemon=True)
        self.loop_thread.start()

    # ---------- UI scaffolding ----------

    def _init_styles(self):
        if _HAS_SV_TTK:
            sv_ttk.set_theme('light')
        else:
            fallback = ttk.Style()
            for theme in ('vista', 'xpnative', 'winnative', 'clam'):
                if theme in fallback.theme_names():
                    try:
                        fallback.theme_use(theme)
                        break
                    except Exception:
                        continue

        style = ttk.Style()
        base_family = 'Segoe UI'
        try:
            for fname in ('TkDefaultFont', 'TkTextFont', 'TkHeadingFont',
                          'TkMenuFont', 'TkIconFont'):
                f = tkfont.nametofont(fname)
                f.configure(family=base_family, size=10)
        except Exception:
            pass

        # Switch style: sv-ttk provides a proper toggle; fall back to standard checkbutton
        self.switch_style = 'Switch.TCheckbutton' if _HAS_SV_TTK else 'TCheckbutton'

        # Only configure what we add on top of sv-ttk's defaults — leave
        # backgrounds alone so the theme's coherent palette wins.
        style.configure('Title.TLabel', font=(base_family, 18, 'bold'))
        style.configure('Subtitle.TLabel', font=(base_family, 10),
                        foreground=COLOR_SUBTLE_FG)
        style.configure('Hint.TLabel', font=(base_family, 9),
                        foreground=COLOR_SUBTLE_FG)
        style.configure('Field.TLabel', font=(base_family, 10))
        style.configure('Status.TLabel', font=(base_family, 9),
                        foreground=COLOR_SUBTLE_FG)
        style.configure('StatusAccent.TLabel', font=(base_family, 9, 'bold'),
                        foreground=COLOR_ACCENT)
        style.configure('Section.TLabelframe.Label',
                        font=(base_family, 10, 'bold'),
                        foreground=COLOR_ACCENT)
        style.configure('TNotebook.Tab', padding=(22, 10),
                        font=(base_family, 10))

    def _build_menu(self, root):
        menubar = Menu(root)

        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label='Open Auction File...', command=self.open_file)
        file_menu.add_command(label='Load Processed List', command=self.load_processed_list)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=root.destroy)
        menubar.add_cascade(label='File', menu=file_menu)

        action_menu = Menu(menubar, tearoff=0)
        action_menu.add_command(label='Login Accounts', command=self.login_accounts)
        action_menu.add_command(label='Collect Information', command=self.collect_information)
        action_menu.add_separator()
        action_menu.add_command(label='Start Automation', command=self.start_automation)
        action_menu.add_command(label='Stop Automation', command=self.stop_automation)
        action_menu.add_command(label='Infinite Bid', command=self.infinite_bid)
        menubar.add_cascade(label='Actions', menu=action_menu)

        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label='About', command=self._show_about)
        menubar.add_cascade(label='Help', menu=help_menu)

        root.config(menu=menubar)

    def _build_header(self, root):
        header = ttk.Frame(root, style='Header.TFrame', padding=(16, 12))
        header.pack(fill=X)
        ttk.Label(header, text='Hibid Automation', style='Title.TLabel').pack(anchor=W)
        ttk.Label(header,
                  text='Automated bidding · Bidder filter · Risk scanner',
                  style='Subtitle.TLabel').pack(anchor=W, pady=(2, 0))
        ttk.Separator(root, orient='horizontal').pack(fill=X)

    def _build_bid_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=14)
        notebook.add(tab, text='  Auto Bid  ')
        tab.columnconfigure(0, weight=1)

        # Prerequisite: launch Chrome with remote debugging + log in manually
        prereq = ttk.Labelframe(
            tab,
            text=' Before "Login Accounts": run this Chrome cmd, then log in manually on company.bid.com ',
            style='Section.TLabelframe', padding=8)
        prereq.grid(row=0, column=0, sticky=(W, E), pady=(0, 8))
        prereq.columnconfigure(0, weight=1)

        self._chrome_cmd = (
            '"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" '
            '--remote-debugging-port=9222 '
            '--user-data-dir="C:\\chrome-dev-profile"'
        )
        # Keep StringVar on self so it isn't GC'd after this method returns
        # (which would silently empty the readonly Entry).
        self._chrome_cmd_var = StringVar(value=self._chrome_cmd)
        cmd_entry = ttk.Entry(prereq, textvariable=self._chrome_cmd_var,
                              state='readonly', font=('Consolas', 9))
        cmd_entry.grid(row=0, column=0, sticky=(W, E), padx=(0, 6))
        ttk.Button(prereq, text='Copy', width=8,
                   command=self._copy_chrome_cmd).grid(row=0, column=1)

        # Accounts group
        acc = ttk.Labelframe(tab, text=' Accounts ', style='Section.TLabelframe', padding=12)
        acc.grid(row=1, column=0, sticky=(W, E), pady=(0, 10))
        acc.columnconfigure(1, weight=1)

        self._add_field(acc, 0, 'Management Account *', self.manager_acc)
        self._add_field(acc, 1, 'Management Password *', self.manager_pwd, show='*')
        self._add_field(acc, 2, 'Bot Account', self.bot_acc, state='disabled')
        self._add_field(acc, 3, 'Bot Password', self.bot_pwd, show='*', state='disabled')

        # Links group
        links = ttk.Labelframe(tab, text=' Auction Links ', style='Section.TLabelframe', padding=12)
        links.grid(row=2, column=0, sticky=(W, E), pady=(0, 10))
        links.columnconfigure(1, weight=1)

        self._add_field(links, 0, 'Management Link *', self.management_lot_link)
        self._add_field(links, 1, 'Bid Lot Link *', self.bid_lot_link)

        # Options
        opts = ttk.Labelframe(tab, text=' Options ', style='Section.TLabelframe', padding=12)
        opts.grid(row=3, column=0, sticky=(W, E), pady=(0, 10))
        opts.columnconfigure(1, weight=1)
        ttk.Checkbutton(opts, text='>$100 lots: use 15% of MSRP as floor',
                        variable=self.twenty_switch,
                        style=self.switch_style).grid(row=0, column=0, columnspan=2, sticky=W)
        ttk.Label(opts,
                  text='When enabled, target = max(max_bid_price, msrp_price × multiplier).',
                  style='Hint.TLabel', wraplength=480).grid(row=1, column=0, columnspan=2,
                                                            sticky=W, pady=(4, 0))

        # Actions
        actions = ttk.Labelframe(tab, text=' Workflow ', style='Section.TLabelframe', padding=12)
        actions.grid(row=4, column=0, sticky=(W, E))
        for c in range(4):
            actions.columnconfigure(c, weight=1, uniform='btn')

        btn_w = 22
        ttk.Button(actions, text='1. Open Auction File',
                   width=btn_w, command=self.open_file).grid(row=0, column=0, padx=4, pady=4, sticky=(W, E))
        ttk.Button(actions, text='2. Login Accounts',
                   width=btn_w, command=self.login_accounts).grid(row=0, column=1, padx=4, pady=4, sticky=(W, E))
        ttk.Button(actions, text='3. Collect Information',
                   width=btn_w, command=self.collect_information).grid(row=0, column=2, padx=4, pady=4, sticky=(W, E))

        self.start_button = ttk.Button(actions, text='4. Start Automation',
                                       style='Accent.TButton', width=btn_w,
                                       command=self.start_automation)
        self.start_button.grid(row=1, column=0, padx=4, pady=4, sticky=(W, E))

        self.infinate_button = ttk.Button(actions, text='Infinite Bid',
                                          width=btn_w, command=self.infinite_bid)
        self.infinate_button.grid(row=1, column=1, padx=4, pady=4, sticky=(W, E))

        self.stop_button = ttk.Button(actions, text='Stop Automation',
                                      width=btn_w, command=self.stop_automation,
                                      state='disabled')
        self.stop_button.grid(row=1, column=2, padx=4, pady=4, sticky=(W, E))

    def _build_filter_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=14)
        notebook.add(tab, text='  Bidder Filter  ')
        tab.columnconfigure(0, weight=1)

        intro = ttk.Labelframe(tab, text=' How it works ', style='Section.TLabelframe', padding=12)
        intro.grid(row=0, column=0, sticky=(W, E), pady=(0, 10))
        ttk.Label(intro,
                  text=('Bidders with reputation < 20 and total bid > $200 are inspected. '
                        'If ≥50% of their winning items have max bid > $200, all their bids are '
                        'declined and their profile is blocked.'),
                  style='Hint.TLabel', wraplength=520).pack(anchor=W)

        lists = ttk.Labelframe(tab, text=' Lists ', style='Section.TLabelframe', padding=12)
        lists.grid(row=1, column=0, sticky=(W, E), pady=(0, 10))
        lists.columnconfigure(1, weight=1)

        self._add_field(lists, 0, 'Allowed list', self.allowed_list)
        self._add_field(lists, 1, 'Blocked list', self.blocked_list, state='readonly')

        opts = ttk.Labelframe(tab, text=' Options ', style='Section.TLabelframe', padding=12)
        opts.grid(row=2, column=0, sticky=(W, E), pady=(0, 10))
        ttk.Checkbutton(opts, text='Block bidders located in the United States',
                        variable=self.block_us_bidder_switch,
                        style=self.switch_style).grid(row=0, column=0, sticky=W)

        actions = ttk.Labelframe(tab, text=' Workflow ', style='Section.TLabelframe', padding=12)
        actions.grid(row=3, column=0, sticky=(W, E))
        for c in range(3):
            actions.columnconfigure(c, weight=1, uniform='fbtn')

        btn_w = 22
        ttk.Button(actions, text='1. Load Processed List',
                   width=btn_w, command=self.load_processed_list).grid(row=0, column=0, padx=4, pady=4, sticky=(W, E))
        self.start_filter = ttk.Button(actions, text='2. Start Filter',
                                       style='Accent.TButton', width=btn_w,
                                       command=self.start_filter_bidder)
        self.start_filter.grid(row=0, column=1, padx=4, pady=4, sticky=(W, E))
        self.stop_filter = ttk.Button(actions, text='Stop Filter',
                                      width=btn_w, command=self.stop_filter_bidder,
                                      state='disabled')
        self.stop_filter.grid(row=0, column=2, padx=4, pady=4, sticky=(W, E))

    def _build_risky_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=14)
        notebook.add(tab, text='  Risk Scan  ')
        tab.columnconfigure(0, weight=1)

        intro = ttk.Labelframe(tab, text=' How it works ', style='Section.TLabelframe', padding=12)
        intro.grid(row=0, column=0, sticky=(W, E), pady=(0, 10))
        ttk.Label(intro,
                  text=('Among bidders with a high bid ≥ threshold, mark those with reputation < '
                        'threshold OR whose public notes contain Non Paying / Bad Check / '
                        'Chargeback / Difficult.'),
                  style='Hint.TLabel', wraplength=520).pack(anchor=W)

        params = ttk.Labelframe(tab, text=' Parameters ', style='Section.TLabelframe', padding=12)
        params.grid(row=1, column=0, sticky=(W, E), pady=(0, 10))
        params.columnconfigure(1, weight=1)

        self._add_field(params, 0, 'Auction ID', self.risky_auction_id)
        self._add_field(params, 1, 'High bid threshold ($)', self.risky_high_bid_threshold)
        self._add_field(params, 2, 'Score threshold', self.risky_score_threshold)

        actions = ttk.Labelframe(tab, text=' Workflow ', style='Section.TLabelframe', padding=12)
        actions.grid(row=2, column=0, sticky=(W, E))
        for c in range(2):
            actions.columnconfigure(c, weight=1, uniform='rbtn')

        btn_w = 22
        self.scan_risky_button = ttk.Button(actions, text='Scan Risky Bidders',
                                            style='Accent.TButton', width=btn_w,
                                            command=self.scan_risky_bidders)
        self.scan_risky_button.grid(row=0, column=0, padx=4, pady=4, sticky=(W, E))
        self.export_risky_button = ttk.Button(actions, text='Export CSV',
                                              width=btn_w,
                                              command=self.export_risky_bidders_csv,
                                              state='disabled')
        self.export_risky_button.grid(row=0, column=1, padx=4, pady=4, sticky=(W, E))

    def _build_right_panel(self, parent):
        paned = ttk.PanedWindow(parent, orient='vertical')
        paned.pack(fill=BOTH, expand=True)

        msg_section = ttk.Labelframe(paned, text=' Messages ',
                                     style='Section.TLabelframe', padding=6)
        self.message = self._make_text_widget(msg_section)
        paned.add(msg_section, weight=1)

        log_section = ttk.Labelframe(paned, text=' Debug Log ',
                                     style='Section.TLabelframe', padding=6)
        self.log_text = self._make_text_widget(log_section)
        paned.add(log_section, weight=1)

    def _make_text_widget(self, parent):
        container = ttk.Frame(parent)
        container.pack(fill=BOTH, expand=True)
        text = Text(container, wrap='word',
                    font=('Consolas', 9),
                    bg=COLOR_TEXT_BG, fg=COLOR_TEXT_FG,
                    relief='flat', borderwidth=0,
                    padx=8, pady=6,
                    highlightthickness=1,
                    highlightbackground=COLOR_BORDER,
                    highlightcolor=COLOR_BORDER)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=text.yview)
        text['yscrollcommand'] = scrollbar.set
        text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        text.config(state='disabled')
        return text

    def _build_statusbar(self, root):
        ttk.Separator(root, orient='horizontal').pack(fill=X, side=BOTTOM)
        bar = ttk.Frame(root, padding=(14, 6))
        bar.pack(fill=X, side=BOTTOM)

        ttk.Label(bar, text='Status:', style='Status.TLabel').pack(side=LEFT)
        ttk.Label(bar, textvariable=self.status_var, style='StatusAccent.TLabel').pack(side=LEFT, padx=(4, 16))

        ttk.Label(bar, textvariable=self.last_action_var, style='Status.TLabel').pack(side=RIGHT)
        ttk.Label(bar, textvariable=self.round_var, style='Status.TLabel').pack(side=RIGHT, padx=(0, 16))

    def _add_field(self, parent, row, label, var, show=None, state='normal'):
        ttk.Label(parent, text=label, style='Field.TLabel').grid(row=row, column=0,
                                                                  sticky=W, padx=(0, 10), pady=4)
        entry = ttk.Entry(parent, textvariable=var, show=show, state=state)
        entry.grid(row=row, column=1, sticky=(W, E), pady=4)
        return entry

    def _set_status(self, text):
        try:
            self.status_var.set(text)
        except Exception:
            pass

    def _copy_chrome_cmd(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self._chrome_cmd)
            self._set_status('Chrome command copied to clipboard')
        except Exception:
            pass

    def _show_about(self):
        from tkinter import messagebox
        messagebox.showinfo(
            'About Hibid Automation',
            'Hibid Automation\n\n'
            'Automated bidding, bidder filtering, and risk scanning\n'
            'for Hibid auctions via Playwright + CDP.'
        )

    # ---------- existing logic below ----------
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
            self._set_status('Infinite bidding')
            self.round_var.set(f'Round: {self.rd}')
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
                        self.round_var.set(f'Round: {self.rd}')
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
                self._set_status('Bidding (single pass)')
                
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
            self._set_status('Ready')
            self.round_var.set('')
            
    def clean_infinite_bid(self):
        self.rd = 1
        self.start = None
        self.end = None
            
    def stop_automation(self):
        self.show_log("Stopping automation... Please wait for current operation to complete.")
        self.stop_automation_cleanup()
        
    def show_message(self, msg):
        now = datetime.datetime.now().replace(microsecond=0)
        self.message.config(state="normal")
        self.message.insert("end", f"[{now}]: " + msg + "\n")
        self.message.see("end")
        self.message.config(state="disabled")
        try:
            self.last_action_var.set(f"Last activity: {now.strftime('%H:%M:%S')}")
        except Exception:
            pass
            
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
    
    def update_block_list(self, l):
        self.blocked_list.set(','.join([str(bidder) for bidder in l]))
        
        
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
            
            await self.automation.login_bot(self.bot_page, self.bot_acc.get(), self.bot_pwd.get(), self.bid_lot_link.get())
            if not self.mng_browser:
                self.mng_browser = await self.launch_context()
            if not self.mng_page:
                self.mng_page = await self.mng_browser.new_page()
            
            await self.automation.login_manager(self.mng_page, self.manager_acc.get(), self.manager_pwd.get(), self.management_lot_link.get())
            self.save_info()
            return 'Login success! Please collect bid information.'
        except NavigationError as e:
            self.show_log(e)
            await self.browser.close()
        except Exception as e:
            self.show_log(e)
            await self.browser.close()

    def save_info(self):
        bot_acc = self.bot_acc.get()
        bot_pwd = self.bot_pwd.get()
        manager_acc = self.manager_acc.get()
        manager_pwd = self.manager_pwd.get()
        management_lot_link = self.management_lot_link.get()
        bid_lot_link = self.bid_lot_link.get()
        save_credentials(bot_acc, bot_pwd, manager_acc, manager_pwd, management_lot_link, bid_lot_link)


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
            self._set_status('Filtering bidders')
            self.show_message("Starting filter bidder automation...")
            special_allowed_list = self.allowed_list.get()
            block_us_switch = self.block_us_bidder_switch.get()
            self.automation.special_allowed_list = special_allowed_list.replace('， ', ',').replace('，', ',').split(',')
            try:
                result = await self.login_filter_bidder_async()
                mng_acc = self.manager_acc.get()
                # TODO: Add inputs to those fields and pass to filter bidder
                # reputation = self.reputation.get()
                # high_value = self.high_value.get()
                # high_value_percent = self.high_value_percent.get()
                self.show_message(result)
                self.show_message("Start filtering...")
                
                self.save_info()                
                result2 = await self.automation.filter_bidder(self.mng_bidder_page, self.auction_id, mng_acc=mng_acc, block_us_switch=block_us_switch)
                self.stop_filter_bidder()
                self.show_message(result2)
            except Exception as e:
                self.show_log(f"Error in filter bidder: {str(e)}")
            
            
    def stop_filter_bidder(self):
        if self.automation.is_filter_running:
            self.automation.is_filter_running = False
            self.start_filter.config(state='normal')
            self.stop_filter.config(state='disabled')
            self._set_status('Ready')
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
        return "Login filter bidder success"


    def load_processed_list(self):
        manager_link = self.management_lot_link.get()
        if not manager_link:
            self.show_message("Please input management link first")
            return
        self.auction_id = get_auction_id(manager_link)
        lists = load_bidder_registration(self.auction_id)
        print(lists)
        if lists:
            self.automation.special_allowed_list = lists.get("special_allowed_list", [])
            self.automation.already_blocked_list = lists.get("already_blocked_list", [])
        else:
            self.automation.special_allowed_list = []
            self.automation.already_blocked_list = []
        self.allowed_list.set(','.join([str(bidder) for bidder in self.automation.special_allowed_list]))
        self.blocked_list.set(','.join([str(bidder) for bidder in self.automation.already_blocked_list]))
        self.show_message('Load processed list success')
        
    
    def check_form(self):
        check_success = False if self.manager_acc.get() == '' or self.manager_pwd.get() == '' else True
        if not check_success:
            self.show_message("Please input all required fileds")
        # else:
        #     self.hide_message()
        return check_success


    def scan_risky_bidders(self):
        auction_id = self.risky_auction_id.get().strip()
        if not auction_id:
            self.show_message("Please input auction id")
            return
        if not self.manager_acc.get() or not self.manager_pwd.get():
            self.show_message("Please input manager account/password")
            return
        if self.risky_scanner.is_running:
            self.show_message("Risky scan already running")
            return
        try:
            high_thr = float(self.risky_high_bid_threshold.get())
            score_thr = int(self.risky_score_threshold.get())
        except ValueError:
            self.show_message("Thresholds must be numbers")
            return

        self.scan_risky_button.config(state='disabled')
        self.export_risky_button.config(state='disabled')
        self._set_status('Scanning risky bidders')
        future = asyncio.run_coroutine_threadsafe(
            self.scan_risky_bidders_async(auction_id, high_thr, score_thr), self.loop)

        def done(fut):
            try:
                fut.result()
                if self.risky_scanner.risky_bidders:
                    self.export_risky_button.config(state='normal')
            except Exception as e:
                self.show_log(f"Risky scan failed: {e}\n{traceback.format_exc()}")
            finally:
                self.scan_risky_button.config(state='normal')
                self._set_status('Ready')
        future.add_done_callback(done)


    async def scan_risky_bidders_async(self, auction_id, high_thr, score_thr):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        if not self.mng_browser:
            self.mng_browser = await self.launch_context()
        if not self.risky_lotstat_page:
            self.risky_lotstat_page = await self.mng_browser.new_page()
        if not self.risky_register_page:
            self.risky_register_page = await self.mng_browser.new_page()

        await self.risky_scanner.login_manager(
            self.risky_lotstat_page, self.manager_acc.get(), self.manager_pwd.get())

        self.show_message(f"Scanning auction {auction_id} ...")
        await self.risky_scanner.scan(
            self.risky_lotstat_page, self.risky_register_page,
            auction_id, high_thr, score_thr)

        for b in self.risky_scanner.risky_bidders:
            self.show_message(f"[{b['bidcard_num']}] {b['name']} - score={b['score']} - {b['reason']}")


    def export_risky_bidders_csv(self):
        if not self.risky_scanner.risky_bidders:
            self.show_message("No risky bidders to export")
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV', '*.csv')],
            initialfile=f'risky_bidders_{self.risky_auction_id.get()}.csv')
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['bidcard_num', 'name', 'score', 'reason', 'notes'])
                writer.writeheader()
                for b in self.risky_scanner.risky_bidders:
                    writer.writerow(b)
            self.show_message(f"Exported to {path}")
        except Exception as e:
            self.show_log(f"Export failed: {e}\n{traceback.format_exc()}")








