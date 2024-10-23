import asyncio
from tools import get_upper_level_url
import pandas as pd


class Automation:
    
    def __init__(self) -> None:
        self.lot_dict = None
        
        pass
    
    async def login_bot(self, page, bot_acc, bot_pwd, url):
        await page.goto("https://hibid.com/")
        await page.get_by_label("Login / New Bidder", exact=True).click()
        await page.locator('[aria-labelledby="email-label"]').fill(bot_acc)
        await asyncio.sleep(1)
        await page.locator('[aria-labelledby="password-label"]').fill(bot_pwd)
        await asyncio.sleep(1.5)

        await page.get_by_text("Log On", exact=True).click()
        await asyncio.sleep(5)
        await page.wait_for_load_state('networkidle')
        # login_status = page.locator('[class="welcome-label"]')
        # if await login_status.count() == 0:
        #     await asyncio.sleep(10)
        await page.goto(url)
        await page.wait_for_load_state('networkidle')
        return
        
        
    async def login_manager(self, page, mng_acc, mng_pwd, url):
        await page.goto('https://my.hibid.com/')
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
        await page.wait_for_load_state('networkidle')
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
        # Find a table with id 'lot-list', which includes a tbody with multiple tr

        break_flag = False
        while True:
            if break_flag:
                break
            trs = page.locator('table[id="lot-list"] tbody tr')
            count = await trs.count()
            if(count == 0):
                break
            for i in range(count):
                tr = trs.nth(i)
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
                
                # Get max price by Find a td with class 'lot-bid-max'
                lot_max = tr.locator('[class="lot-bid-max"]')
                max_bid_price = await lot_max.nth(0).inner_text()
                max_bid_price = float(max_bid_price.replace(',', ''))
                if(max_bid_price == 0):
                    # break while loop
                    break_flag = True
                    break
                
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
                print(f'lot: {lot}, data: {self.lot_dict[lot]}')
            # Find text with 'Next' and click
            try:
                last_li = page.locator('table[id="lot-list"] thead tr th ul li').nth(-1)
            except Exception as e:
                print(e)
            span = last_li.locator('span', has_text="Next")
            if await span.count() > 0:
                await span.click()
                await page.wait_for_load_state('networkidle')
            else:
                raise Exception('Cannot find next page button')
        print(f'Get lot info totally: {len(self.lot_dict)}')
        return
            
    
    async def start_automation_async(self, bot_page, mng_page):
        self.bids_info = await self.get_bids_info(mng_page)
        # return
        for i in len(self.bids_info):
            bid_info = self.bids_info[i]
            if bid_info.lot == 700:
                # price is less than 100
                if bid_info.msrp_price > 0 and bid_info.msrp_price < 100: 
                    # current bid price is less than max bid price, then bid
                    if bid_info.high_bid < bid_info.max_bid_price:
                        await self.bot_bid(bot_page, bid_info.lot, bid_info.max_bid_price)
                elif bid_info.msrp_price > 100:
                    # current bid price is less than max bid price or 20% of msrp price, then bid
                    aimed_price = max(bid_info.max_bid_price, bid_info.msrp_price * 0.2)
                    if bid_info.high_bid < aimed_price:
                        await self.bot_bid(bot_page, bid_info.lot, aimed_price)
                else:
                    print('Loss msrp price indication')
    
    async def bot_bid(self, page, max_bid_price, lot):
        await page.goto(self.bid_lot_link.get() + f'?q={lot}')
        lot = await page.locator(f'app-lot-tile:has-text("Lot {lot} | ")')
        
        await lot.get_by_label('Bid', exact=True).click()
        self.registered = await self.bot_register_auction(page)

        bid_modal = page.locator('app-bid-modal')
        bid_price_list = []
        current_bid_amount = 0
        bid_button = await bid_modal.get_by_label("Click to increase the bid increment", exact=True)
        while current_bid_amount < max_bid_price:
            await bid_button.click()
            current_bid_amount = float(bid_modal.get_by_label("Bid amount", exact=True).input_value().replace(',', ''))
            bid_price_list.append(current_bid_amount)
        bid_price_list.pop()
        if len(bid_price_list) <= 1:
            await bid_modal.get_by_label("Close", exact=True).click()
        else:
            await bid_modal.get_by_label("Bid amount", exact=True).fill(str(bid_price_list[-1]))

        # page.get_by_label("Click to confirm bid", exact=True)
        await asyncio.sleep(60)
    
    
    async def bot_register_auction(self, page):
        modals = page.locator('modal-container')
        if await modals.count() == 1:
            return True
        else:
            await page.get_by_label("Agree to the terms and conditions").check()
            await page.get_by_label("Click to register for the auction").click()
            welcome_banner = await page.locator('modal-container:has-text("Welcome to")')
            await welcome_banner.get_by_label("Close", exact=True).click()
            return True
        
        
    # Sometimes, there is subscrition modal, we need to close it. modal role is dialog, button with text 'No thanks'
    def clear_subscribe_modal(self):
        print('nothing')
        

    def file_to_lot_dict(self, filepath):
        with open(filepath, 'r') as f:
            df = pd.read_csv(f)
            df['lot'] = df['lot'].astype(str)  # Convert the 'lot' column to string type
            self.lot_dict = df.set_index('lot')['msrp_price'].apply(lambda x: {'msrp_price': x}).to_dict()
            print(self.lot_dict)
        