import asyncio
from tools import get_upper_level_url
import pandas as pd


class Automation:
    
    def __init__(self, show_log) -> None:
        self.lot_dict = None
        self.bid_link = None
        self.show_log = show_log
        self.registered = False
        self.bid_cust_win_count = 0
        self.bid_to_cust_max = 0
        self.bid_bot_win_count = 0
        self.bid_to_bot_max = 0
        pass
    
    def set_bid_link(self, bid_link):
        self.bid_link = bid_link
    
    async def login_bot(self, page, bot_acc, bot_pwd, url):
        await page.goto("https://hibid.com/")
        self.bid_link = url
        # Check if login success or not
        login_status = page.locator('[class="welcome-label"]')
        if await login_status.count() != 0:
            return
        
        # Login
        await page.get_by_label("Login / New Bidder", exact=True).click()
        await page.locator('[aria-labelledby="email-label"]').fill(bot_acc)
        await asyncio.sleep(1)
        await page.locator('[aria-labelledby="password-label"]').fill(bot_pwd)
        await asyncio.sleep(1.5)
        await page.get_by_text("Log On", exact=True).click()
        # await asyncio.sleep(10)
        # await page.wait_for_load_state('networkidle')
        # login_status = page.locator('[class="welcome-label"]')
        # if await login_status.count() == 0:
        #     await asyncio.sleep(10)
        # await page.goto(url)
        # await page.wait_for_load_state('networkidle')
        return
        
    async def login_manager(self, page, mng_acc, mng_pwd, url):
        await page.goto('https://my.hibid.com/auctioneer/auctions/current/')
        
        # Check if manager login success
        if(page.url == 'https://my.hibid.com/auctioneer/auctions/current/'):
            await page.goto(url)
            return
        
        await page.locator('[id="auctioneer-logon-username"]').fill(mng_acc)
        await asyncio.sleep(1)
        await page.locator('[id="Password"]').fill(mng_pwd)
        await asyncio.sleep(1.2)
        await page.get_by_text("Log On", exact=True).click()
        
        try:
            await page.wait_for_url("**/auctioneer/**")
        except Exception:
            await asyncio.sleep(10)
            
        # Check the current url include auctioneer
        # if 'auctioneer' not in page.url:
        #     raise Exception('Login manager account failed, please restart automation')
        await page.goto(url)
        return
        
    async def get_bids_info(self, page):
        # Sort by bid count
        
        # sort_order = await page.wait_for_selector('#sortOrder', state='visible', timeout=10000)
        # await sort_order.click()
        
        # This does not work, cannot find any options by any methods
        # await page.click('option[value="5"]')  # This might vary based on the custom implementation

        url = get_upper_level_url(page.url)
        url = url + '?q=&buyer=0&SortOrder=5&ProductStatus=0&All=False'
        await page.goto(url)
        await page.wait_for_load_state('networkidle')
        # await page.select_option('#sortOrder', value="5")

        break_flag = False
        valid_lot_count = 0
        
        while True:
            
            # Find a table with id 'lot-list', which includes a tbody with multiple tr
            trs = page.locator('table[id="lot-list"] tbody tr')
            count = await trs.count()
            if(count == 0 or break_flag):
                break
            
            for i in range(count):
                
                tr = trs.nth(i)
                # Get max price by Find a td with class 'lot-bid-max'
                lot_max = tr.locator('[class="lot-bid-max"]')
                max_bid_price = await lot_max.nth(0).inner_text()
                max_bid_price = float(max_bid_price.replace(',', ''))
                if(max_bid_price == 0):
                    # break while loop
                    break_flag = True
                    break
                
                # Get lot number by finding a td with class 'lot-number-lead lot-link'
                lot_leads = tr.locator('[class="lot-number-lead lot-link"]')
                leads = await lot_leads.nth(0).inner_text()
                lot = leads.split(' ')[0]

                # Get currently lot-high-bid by Find a span with div class 'lot-high-bid'
                lot_high_bid = tr.locator('[class="lot-high-bid"]')
                high_bid_text = await lot_high_bid.nth(0).inner_text()
                high_bid = float(high_bid_text.split(' ')[0].replace(',', ''))
                # Get bid high person by Find a span with class 'name-expand'
                name_expanded = tr.locator('[class="name-expand"]')
                bidder = await name_expanded.nth(0).inner_text()
                bidder_id = bidder.split(' ')[0]
                
                lot_info = self.lot_dict.get(lot) 
                if lot_info:
                    lot_info['max_bid_price'] = max_bid_price
                    lot_info['bidder_id'] = bidder_id
                    lot_info['high_bid'] = high_bid
                else:
                    self.lot_dict[lot] = {
                        'msrp_price': 0,
                        'max_bid_price': max_bid_price,
                        'bidder_id': bidder_id,
                        'high_bid': high_bid
                    }
                valid_lot_count += 1
                
                print(f'lot: {lot}, data: {self.lot_dict[lot]}')
                # Find text with 'Next' and click
                
            last_li = page.locator('table[id="lot-list"] thead tr th ul li').nth(-1)
            span = last_li.locator('span', has_text="Next")
            if await span.count() > 0 and not break_flag:
                await span.click()
                await page.wait_for_load_state('networkidle')
            else:
                break_flag = True
        self.show_log(f'Get valid lot info totally: {valid_lot_count}')
        return
            
    async def start_automation_async(self, bot_page, mng_page):
        await self.get_bids_info(mng_page)
        # return
        try:
            for lot in self.lot_dict:
                bid_info = self.lot_dict[lot]
                if bid_info.get("max_bid_price") == None:
                    continue
                # if lot == "2":
                # price is less than 100
                if bid_info['msrp_price'] > 0 and bid_info['msrp_price'] < 100: 
                    # current bid price is less than max bid price, then bid
                    if bid_info['high_bid'] < bid_info['max_bid_price']:
                        final_bid_price = await self.bot_bid(bot_page, lot, bid_info['max_bid_price'])
                        if final_bid_price != 0:
                            self.bid_cust_win_count += 1
                            self.bid_to_cust_max += (final_bid_price - bid_info['high_bid'])
                elif bid_info['msrp_price'] > 100:
                    # current bid price is less than max bid price or 20% of msrp price, then bid
                    # If the lot has never been bidden, do we still need to bid? Which means the high_bid or max_bid_price =  0
                    target_price = max(bid_info['max_bid_price'], round(bid_info['msrp_price'] * 0.2, 2))
                    if bid_info['high_bid'] < target_price:
                        final_bid_price = await self.bot_bid(bot_page, lot, target_price)
                        if final_bid_price != 0:
                            if(target_price == bid_info['max_bid_price']):
                                self.bid_cust_win_count += 1
                                self.bid_to_cust_max += (final_bid_price - bid_info['high_bid'])
                            else:
                                self.bid_bot_win_count += 1
                                self.bid_to_bot_max += (final_bid_price - bid_info['high_bid'])
                else:
                    print('Loss msrp price indication')
                await asyncio.sleep(5)
            self.show_log(f'Bid customer win totally: {self.bid_cust_win_count}')
            self.show_log(f'Bid customer win price total: {self.bid_to_cust_max}')
            self.show_log(f'Bid bot win totally: {self.bid_bot_win_count}')
            self.show_log(f'Bid bot win totally: {self.bid_to_bot_max}')
        except Exception as e:
            self.show_log(e)
        
    
    async def bot_bid(self, page, lot, target_price):
        print(self.bid_link + f'?q={lot}')
        
        await page.goto(self.bid_link + f'?q={lot}')
        await self.clear_subscribe_modal(page)
        
        # Start bid
        lot_title = page.locator(f'app-lot-tile:has-text("Lot {lot} | ")')
        await lot_title.get_by_label('Bid', exact=True).click()
        
        # Get rid of register modal for first time bid on this auction
        if not self.registered:
            self.registered = await self.bot_register_auction(page)

        bid_modal = page.locator('app-bid-modal')
        # Initial bid price
        bid_amount_text = await bid_modal.get_by_label("Bid amount", exact=True).nth(0).input_value()
        current_bid_amount = float(bid_amount_text.replace(',', ''))
        bid_price_list = [current_bid_amount]
        
        bid_button = bid_modal.get_by_label("Click to increase the bid increment", exact=True)
        # Bid to the target price
        while bid_price_list[-1] <= target_price:
            await asyncio.sleep(0.2)
            await bid_button.click()
            bid_amount_text = await bid_modal.get_by_label("Bid amount", exact=True).nth(0).input_value()
            current_bid_amount = float(bid_amount_text.replace(',', ''))
            bid_price_list.append(current_bid_amount)
            if current_bid_amount == bid_price_list[-2]:
                break
        bid_price_list.pop()
        
        if len(bid_price_list) == 0:
            await bid_modal.get_by_label("Close", exact=True).click()
        else:
            await bid_modal.get_by_label("Bid amount", exact=True).fill(str(bid_price_list[-1]))
            self.show_log(f'Bid lot {lot} to {bid_price_list[-1]}')

            await bid_modal.get_by_label("Close", exact=True).click()
            return bid_price_list[-1]
        return 0
        # page.get_by_label("Click to confirm bid", exact=True)
        # await asyncio.sleep(30)
    
    
    async def bot_register_auction(self, page):
        modals = page.locator('app-register-auction')
        if await modals.count() == 0:
            return True
        else:
            await page.get_by_label("Agree to the terms and conditions").check()
            await page.get_by_label("Click to register for the auction").click()
            welcome_banner = page.locator('modal-container:has-text("Welcome to")')
            await welcome_banner.get_by_label("Close", exact=True).click()
            return True
        
        
    # Sometimes, there is subscrition modal, we need to close it. modal role is dialog, button with text 'No thanks'
    async def clear_subscribe_modal(self, page):
        no_thanks_button = page.locator('[id="subscribe-modal"] button', has_text='No thanks')
        try:
            # Check if the button is visible within 4 seconds (4000 ms)
            is_visible = await no_thanks_button.is_visible(timeout=4000)
            if is_visible:
                await no_thanks_button.click()
        except TimeoutError:
            # The button was not visible within 4 seconds
            pass
        

    def file_to_lot_dict(self, filepath):
        with open(filepath, 'r') as f:
            df = pd.read_csv(f)
            df['lot'] = df['lot'].astype(str)  # Convert the 'lot' column to string type
            self.lot_dict = df.set_index('lot')['msrp_price'].apply(lambda x: {'msrp_price': x}).to_dict()
            self.show_log(f'Totally items from uploaded file: {len(self.lot_dict)}')
        