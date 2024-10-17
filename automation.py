import asyncio


class Automation:
    
    def __init__(self) -> None:
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
        print(page.url)
        
        
        await page.wait_for_selector('#sortOrder', state='visible', timeout=10000)
        # await sort_order.click()
        await page.select_option('#sortOrder', value="5")
        # Find a table with id 'lot-list', which includes a tbody with multiple tr
        trs = page.locator('table[id="lot-list"] tbody tr')
        count = await trs.count()
        for i in range(count):
            tr = trs.nth(i)
            # Find a td with class 'lot-number', which includes a text 'Lot'
            lot_leads = tr.locator('a[class="lot-number-lead lot-link"]')
            it = await lot_leads[0].inner_text()
            print(it)
        return
        # Sometimes, there is subscrition modal, we need to close it. modal role is dialog, button with text 'No thanks'
    
    async def start_automation_async(self, bot_page, mng_page):
        try:
            await self.get_bids_info(mng_page)
            # self.bot_bid(lot=2, max_bid_price=350)
        except Exception as e:
            print(e)
    
    async def bot_bid(self, page, max_bid_price, lot=61):
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
            current_bid_amount = float(bid_modal.get_by_label("Bid amount", exact=True).input_value())
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
        
        
        