import asyncio
import re
from urllib.parse import urlparse
from tools import get_upper_level_url, add_log, save_bidder_registration, block_bidder_log, filter_bidder_txns
import pandas as pd
from datetime import datetime, timezone
import requests
import os
import uuid
import traceback
import random
from playwright.async_api import Page
import time

    

class Automation:

    # HiBid's PWA redesign dropped the aria-label from every text button, so
    # each selector below matches the old label first and the visible text
    # second, keeping both site versions working.
    RECONFIRM_BUTTON = (
        '[aria-label*="Click Here to Reconfirm"], '
        'button:has-text("Click Here to Reconfirm")'
    )
    # First money-looking number in a label, e.g. "Click Here to Reconfirm CA$1,234.00".
    BID_AMOUNT_RE = re.compile('([0-9][0-9,]*[.]?[0-9]*)')
    # Auction header button text. The title attribute reads "Registered" in both
    # states, so only the text tells the two apart.
    REGISTERED_BUTTON_TEXT = 'You are Registered'
    # Registration moved out of the PWA into a separate three step wizard.
    REGISTRATION_PATH = '/pf/auction-registration/'
    DELIVERY_METHOD = 'input#delivery-method-1'  # Pickup

    def __init__(self, show_log, show_message, update_block_list) -> None:
        # Starts empty rather than None: the uploaded file is optional, and
        # get_bids_info fills this in from the manager site either way.
        self.lot_dict = {}
        self.bid_link = None
        self.show_log = show_log
        self.show_message = show_message
        self.update_block_list = update_block_list
        self.registered = False
        self.bid_cust_win_count = 0
        self.bid_to_cust_max = 0
        self.bid_bot_win_count = 0
        self.bid_to_bot_max = 0
        self.twenty_switch = False
        self.is_running = False
        self.is_filter_running = False
        self.special_allowed_list = []
        self.already_blocked_list = []
        pass
    
    def stop_automation(self):
        self.is_running = False
    
    def set_bid_link(self, bid_link):
        self.bid_link = bid_link
        
    def set_twenty_switch(self, twenty_switch):
        self.twenty_switch = twenty_switch
        self.show_log('15% 规则：' + ('开' if self.twenty_switch else '关'))
        
    def log_auto_bid(self, func):
        pass
    
    def log_auto_filter(self, func):
        pass
    
    async def login_bot(self, page, bot_acc, bot_pwd, url):
        # await page.goto(url)
        self.bid_link = url
        await page.goto(url)
        #    # Add a random delay of 1 to 5 seconds to simulate human behavior
        # await asyncio.sleep(random.uniform(1, 5))

        # # Scroll the page to load additional content
        # await page.evaluate("window.scrollBy(0, window.innerHeight)")

        # # Add another random delay of 1 to 5 seconds
        # await asyncio.sleep(random.uniform(1, 5))
        # Check if login success or not
        # login_status = page.get_by_text("Sign In", exact=True)
        # if await login_status.count() == 0:
        #     return
        
        # # Login
        # await login_status.click()
        # await page.locator('[aria-labelledby="email-label"]').fill(bot_acc)
        # await asyncio.sleep(1)
        # await page.locator('[aria-labelledby="password-label"]').fill(bot_pwd)
        # await asyncio.sleep(1.5)
        # await page.get_by_text("Log On", exact=True).click()
        
        
        # await asyncio.sleep(10)
        # await page.wait_for_load_state('networkidle')
        # login_status = page.locator('[class="welcome-label"]')
        # if await login_status.count() == 0:
        #     await asyncio.sleep(10)
        # await page.goto(url)
        # await page.wait_for_load_state('networkidle')
        await self.untick_refresh(page)

        if not await self.is_bot_logged_in(page):
            self.show_log(f'登录检查未通过，当前页面：{page.url}')
            self.show_log(self.signed_out_banner(url))
            return False

        self.show_log('bot 已就绪')
        return True

    async def is_bot_logged_in(self, page, timeout=15000):
        # The header greets the account by name once the session is live. Look
        # for it in the DOM rather than on screen: that header sits in a
        # `d-none d-md-block` wrapper, so a Chrome window narrower than 768px
        # hides it, and a narrow window does not mean signed out.
        deadline = time.monotonic() + timeout / 1000
        while True:
            try:
                if await page.locator('.welcome-label').count() > 0:
                    return True
            except Exception:
                pass
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.5)

    def signed_out_banner(self, url):
        rule = "=" * 60
        return f"""
{rule}
    bot 账号未登录
{rule}
    已经为你打开 Chrome 窗口：
        {url}

    请在那个窗口里用 bot 账号登录，然后重新点
    "2. Login Accounts"
{rule}"""

    async def login_manager(self, page, mng_acc, mng_pwd, url):
        await page.goto('https://my.hibid.com/auctioneer/auctions/current/')
        # Check if manager login success
        if(page.url == 'https://my.hibid.com/auctioneer/auctions/current/'):
            await page.goto(url)
            self.show_log('管理端已登录')
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
        self.show_log('管理端已登录')
        
    # mode: 1 for static bid, 2 for infinate bid
    async def get_bids_info(self, page, mode):
        # Sort by bid count
        
        # sort_order = await page.wait_for_selector('#sortOrder', state='visible', timeout=10000)
        # await sort_order.click()
        
        # This does not work, cannot find any options by any methods
        # await page.click('option[value="5"]')  # This might vary based on the custom implementation

        # clean self.lot_dict first, only leave msrp price
        if self.lot_dict is None:
            self.lot_dict = {}
        for lot in self.lot_dict:
            self.lot_dict[lot] = {
                'msrp_price': self.lot_dict[lot]['msrp_price'],
                'skipped': self.lot_dict[lot]['skipped'],
                'second_hand': self.lot_dict[lot]['second_hand'],
            }
        
        if mode == 1:
            query = '?q=&buyer=0&hide=true&SortOrder=5&ProductStatus=0&All=True'
        elif mode == 2:
            query = '?q=&buyer=0&hide=true&SortOrder=7&ProductStatus=0&All=False'
        if page.url.find('?q=') == -1:
            url = get_upper_level_url(page.url)
            url = url + query
        else:
            domain = page.url.split('?')[0]
            url = domain + query
        await page.goto(url)
        await page.wait_for_load_state('networkidle')
        # await page.select_option('#sortOrder', value="5")

        valid_lot_count = 0
        
        rows_data = await page.evaluate("""
            () => {
                const rows = Array.from(document.querySelectorAll('table#lot-list tbody tr'));
                const valid_rows = rows.filter(tr => tr.querySelector('.lot-bid-max').innerText != '0.00');
                return rows.map(tr => ({
                    maxBid: parseFloat(tr.querySelector('.lot-bid-max').innerText.replace(',', '')),
                    highBid: parseFloat(tr.querySelector('.lot-high-bid').innerText.split(' ')[0].replace(',', '')),
                    lotNumber: tr.querySelector('.lot-number-lead.lot-link').innerText.split(' ')[0],
                    bidder: tr.querySelector('.name-expand')?.innerText.split(' ')[0] || '-1',
                }));
            }
        """)
            
        
        # Process the data in Python
        for row in rows_data:
            lot = row['lotNumber']
            max_bid_price = row['maxBid']
            high_bid = float(row['highBid'])
            bidder_id = float(row['bidder'])
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
                    'high_bid': high_bid,
                    'skipped': False,
                    'second_hand': False,
                }
            valid_lot_count += 1
        self.show_log(f'已收集 {valid_lot_count} 个 lot 的出价信息')
        return 'lot 信息收集完成'
        
        # break_flag = False
        # Process the rows in batches
        # while True:
            
        #     # Find a table with id 'lot-list', which includes a tbody with multiple tr
        #     trs = page.locator('table[id="lot-list"] tbody tr')
        #     count = await trs.count()
        #     if(count == 0 or break_flag):
        #         break
            
        #     for i in range(count):
        #         print(f'Processing lot {i+1}/{count}')
        #         tr = trs.nth(i)
        #         # Get max price by Find a td with class 'lot-bid-max'
        #         lot_max = tr.locator('[class="lot-bid-max"]')
        #         max_bid_price = await lot_max.nth(0).inner_text()
        #         max_bid_price = float(max_bid_price.replace(',', ''))
        #         if(max_bid_price == 0):
        #             # break while loop
        #             break_flag = True
        #             break
                
        #         # Get lot number by finding a td with class 'lot-number-lead lot-link'
        #         lot_leads = tr.locator('[class="lot-number-lead lot-link"]')
        #         leads = await lot_leads.nth(0).inner_text()
        #         lot = leads.split(' ')[0]

        #         # Get currently lot-high-bid by Find a span with div class 'lot-high-bid'
        #         lot_high_bid = tr.locator('[class="lot-high-bid"]')
        #         high_bid_text = await lot_high_bid.nth(0).inner_text()
        #         high_bid = float(high_bid_text.split(' ')[0].replace(',', ''))
        #         # Get bid high person by Find a span with class 'name-expand'
        #         name_expanded = tr.locator('[class="name-expand"]')
        #         bidder = await name_expanded.nth(0).inner_text()
        #         bidder_id = bidder.split(' ')[0]
                
        #         lot_info = self.lot_dict.get(lot) 
        #         if lot_info:
        #             lot_info['max_bid_price'] = max_bid_price
        #             lot_info['bidder_id'] = bidder_id
        #             lot_info['high_bid'] = high_bid
        #         else:
        #             self.lot_dict[lot] = {
        #                 'msrp_price': 0,
        #                 'max_bid_price': max_bid_price,
        #                 'bidder_id': bidder_id,
        #                 'high_bid': high_bid
        #             }
        #         valid_lot_count += 1
                
        #         self.show_log(f'lot: {lot}, data: {self.lot_dict[lot]}')
        #         # Find text with 'Next' and click
                
        #     last_li = page.locator('table[id="lot-list"] thead tr th ul li').nth(-1)
        #     print(f'last_li: {last_li}')
        #     print(f'last_li type: {type(last_li)}')
        #     span = last_li.locator('span', has_text="Next")
        #     if await span.count() > 0 and not break_flag:
        #         await span.click()
        #         await page.wait_for_load_state('networkidle')
        #     else:
        #         break_flag = True
        # self.show_log(f'Get valid lot info totally: {valid_lot_count}')
        # return 'lot 信息收集完成'
            
    # mode: 1 for static bid, 2 for infinate bid
    async def start_automation_async(self, bot_page, mng_page, bot_acc, mng_acc, mode):
        if not self.lot_dict:
            self.show_log('还没有 lot 数据，请先点 3. Collect Information')
            return
        unique_id = str(uuid.uuid4())
        item_log = []
        self.is_running = True
        
        # bid limit and bid count
        # as per item cost around 6 seconds, one round should be finished in 90 seconds
        # so totally 14*6=84 seconds fo bid, and 6 seconds for get lot info 
        limit = 14
        i = 0
        start = datetime.now()
        for lot in self.lot_dict:
            diff = (datetime.now() - start).total_seconds()
            if not self.is_running or (mode == 2 and (i >= limit or diff > 90)):
                break
            
            bid_info = self.lot_dict[lot]
            
            if pd.isna(bid_info.get("max_bid_price")):
                bid_info['max_bid_price'] = 0
            if pd.isna(bid_info.get("msrp_price")):
                bid_info['msrp_price'] = 0

            final_bid_price = 0
            status = ''
            try:
                if bid_info['msrp_price'] > 0 and bid_info['msrp_price'] < 100:
                    # current bid price is less than max bid price, then bid
                    if bid_info.get('high_bid', 0) < bid_info['max_bid_price']:
                        final_bid_price, status = await self.bot_bid(bot_page, lot, bid_info['max_bid_price'])
                        # statistics
                        if status == 'success' and final_bid_price != 0:
                            self.bid_cust_win_count += 1
                            self.bid_to_cust_max += (bid_info['max_bid_price'] - bid_info.get('high_bid', 0))
                    else:
                        continue
                # If no msrp price, bid to max_bid_price
                elif bid_info['msrp_price'] >= 100 or bid_info['msrp_price'] == 0:
                    # current bid price is less than max bid price or 13% of msrp price, then bid
                    # If the lot has never been bidden, do we still need to bid? Which means the high_bid or max_bid_price =  0
                    if self.twenty_switch:
                        multiplier = 0.15
                        if bid_info.get('second_hand'):
                            multiplier = 0.08
                            self.show_log(f'lot {lot}：二手，系数 {multiplier}')
                        if bid_info.get('skipped'):
                            multiplier = 0
                            self.show_log(f'lot {lot}：跳过 15% 规则')
                        target_price = max(bid_info['max_bid_price'], round(bid_info['msrp_price'] * multiplier, 2))
                    else:
                        target_price = bid_info['max_bid_price']
                    if bid_info.get('high_bid', 0) < target_price:
                        final_bid_price, status = await self.bot_bid(bot_page, lot, target_price)
                        # statistics
                        if status == 'success' and final_bid_price != 0:
                            if(target_price == bid_info['max_bid_price']):
                                self.bid_cust_win_count += 1
                                self.bid_to_cust_max += (bid_info['max_bid_price'] - bid_info.get('high_bid', 0))
                            else:
                                self.bid_bot_win_count += 1
                                self.bid_to_bot_max += (final_bid_price - bid_info.get('high_bid', 0))
                    else:
                        continue
                else:
                    self.show_log(f'lot {lot}：没有 msrp，跳过')
                    continue
                i += 1
                await asyncio.sleep(random.random() + 1)  # Add a random delay 1-2s to simulate human behavior
            except Exception:
                self.show_log(f'lot {lot}：出价出错，跳过')
                self.show_log(traceback.format_exc())
                continue
            try:
                item_log.append({
                    # "automation_link": self.bid_link,
                    "lot": lot,
                    # "client": bot_acc,
                    "target_price": final_bid_price,
                    "previous_price": bid_info.get('high_bid', 0),
                    "status": status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                if(len(item_log) == 20):
                    data = {
                            "transaction_id": unique_id,
                            "items": item_log, 
                            "automation_link": self.bid_link, 
                            "client": bot_acc
                            }
                    text = add_log('/items', data)
                    item_log.clear()
            except Exception:
                self.show_log('上报出价日志失败')
                self.show_log(traceback.format_exc())
        try:
            if(len(item_log) != 0):
                    data = {
                            "transaction_id": unique_id,
                            "items": item_log, 
                            "automation_link": self.bid_link, 
                            "client": bot_acc
                            }
                    text = add_log('/items', data)
            transaction_data = {
                                    "transaction_id": unique_id,
                                    "automation_link": self.bid_link,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "client": mng_acc,
                                    "action": "Automated Bid",
                                    "success": True,
                                    # "message": "",
                                    "cust_win_count": self.bid_cust_win_count,
                                    "cust_win_increased_price": self.bid_to_cust_max,
                                    "bot_win_count": self.bid_bot_win_count,
                                    "bot_win_increased_price": self.bid_to_bot_max
                                }
            text = add_log('/transaction', transaction_data)
        except Exception:
                self.show_log('上报本轮汇总失败')
                self.show_log(traceback.format_exc())
        self.show_message('本次自动出价汇总')
        self.show_message(f'按客户委托价成交 {self.bid_cust_win_count} 个，加价合计 {self.bid_to_cust_max}')
        self.show_message(f'按 15% 规则出价 {self.bid_bot_win_count} 个，加价合计 {self.bid_to_bot_max}')
        # reset statistics
        self.bid_cust_win_count = 0
        self.bid_to_cust_max = 0
        self.bid_bot_win_count = 0
        self.bid_to_bot_max = 0
        return '本轮自动出价结束'
        
    async def bot_bid(self, page, lot, target_price):
        try:
            await page.goto(self.bid_link + f'?q={lot}')
            await page.wait_for_load_state('networkidle')
            await self.clear_subscribe_modal(page)

            if not self.registered:
                self.registered = await self.ensure_registered(page)
                if not self.registered:
                    self.show_log(f'lot {lot}：本场拍卖未注册，跳过')
                    return 0, 'skip'
                # Registering navigates away, so come back to this lot.
                await page.goto(self.bid_link + f'?q={lot}')
                await page.wait_for_load_state('networkidle')
                await self.clear_subscribe_modal(page)

            # Start bid
            lot_title = page.locator(f'app-lot-tile:has-text("Lot {lot} | ")').first
            if await lot_title.count() == 0:
                self.show_log(f'lot {lot}：搜索页找不到，跳过')
                return 0, 'skip'
            # HiBid's PWA moved the tile bid button into an <app-button> wrapper
            # with no aria-label, so match the visible text and keep the old
            # aria-label as a fallback.
            bid_button = lot_title.locator(
                '[aria-label="Bid"], '
                'app-lot-buttons .lot-bid-container button:has(span.lot-bid-text)'
            ).first
            if await bid_button.count() == 0:
                self.show_log(f'lot {lot}：没有出价按钮（可能已结束），跳过')
                return 0, 'skip'
            await bid_button.click()

            bid_modal = page.locator("app-login-container")

            # Initial bid price
            bid_amount_text = await bid_modal.get_by_label("Bid amount", exact=True).nth(0).input_value()
            current_bid_amount = float(bid_amount_text.replace(',', ''))
            bid_price_list = [current_bid_amount]
            
            bid_increase_button = bid_modal.get_by_label("Click to increase the bid increment", exact=True)
            # Bid to the target price
            while bid_price_list[-1] <= target_price:
                await asyncio.sleep(random.uniform(0, 0.1))  # Add a random delay to simulate human behavior
                await bid_increase_button.click()
                bid_amount_text = await bid_modal.get_by_label("Bid amount", exact=True).nth(0).input_value()
                current_bid_amount = float(bid_amount_text.replace(',', ''))
                bid_price_list.append(current_bid_amount)
                # prevent infinite loop when the price is not increasing
                if current_bid_amount == bid_price_list[-2]:
                    break
            bid_price_list.pop()
            
            if len(bid_price_list) == 0:
                await bid_modal.get_by_label("Close", exact=True).click()
                return target_price, 'skip'
            else:
                bid_amount_input = bid_modal.get_by_label("Bid amount", exact=True).nth(0)
                await bid_amount_input.fill(str(bid_price_list[-1]))
                # Never submit more than the target. Re-read the field instead
                # of trusting what we typed, in case the site rewrote it.
                submitted = self.parse_amount(await bid_amount_input.input_value())
                if submitted is None or submitted > target_price:
                    self.show_log(
                        f'lot {lot}：输入框里是 {submitted}，超过上限 {target_price}，不提交'
                    )
                    await self.click_if_possible(
                        bid_modal.get_by_label("Close", exact=True).first, '关闭按钮', lot
                    )
                    return target_price, 'skip'
                self.show_log(f'lot {lot}：出价 {bid_price_list[-1]}')
                # The confirm button also lost its aria-label in the PWA
                # redesign; match the visible text, keep the old label as a
                # fallback.
                confirm_bid_button = bid_modal.locator(
                    '[aria-label="Click to confirm bid"], '
                    'app-bid-modal button:has-text("Confirm Bid")'
                ).first
                await confirm_bid_button.click()
                # await bid_modal.get_by_label("Close", exact=True).click()
                # return 0, 'skip'
                
                # Click another confirm when bid price over too much
                confirmed = await self.confirm_your_bid_modal(bid_modal, lot)
                if confirmed:
                    return bid_price_list[-1], 'success'
                else:
                    return target_price, 'skip'
        except Exception as e:
            raise(e)
            # send error to server
            # return previous_price, previous_price, 'failed'
            
    async def decline_items(self, bidder_id, page, total_bid_amount_a):
        self.show_log(f'[{bidder_id}] 正在拒绝其全部出价')
        await total_bid_amount_a.click()
        bid_history_modal = page.locator('div#bid-history-modal div.modal-content')
        await page.wait_for_load_state('networkidle')
        await bid_history_modal.wait_for(state='visible')
        bid_history_table = bid_history_modal.locator('table#bid-history-table tbody')
        await bid_history_table.wait_for(state='visible')
        bid_history_trs = bid_history_table.locator('> tr')
        bid_history_trs_count = await bid_history_trs.count()
        for j in range(bid_history_trs_count):
            bid_tr = bid_history_trs.nth(j)
            edit_button = bid_tr.locator('button.bid-history-edit.btn')
            await edit_button.click()
            edit_modal = page.locator('div[id="edit-bid-modal"]').locator('div[class="modal-content"]')
            await edit_modal.get_by_role('combobox').select_option('3')
            confirm_input = edit_modal.locator('input#ConfirmText')
            if await confirm_input.count() > 0 and await confirm_input.is_visible():
                await confirm_input.fill('CONFIRM')
            edit_modal_footer = edit_modal.locator('[class="modal-footer"]')
            await edit_modal_footer.get_by_text('Save').click()
            # After click save, the whole page will reload, so wait the network
            await page.wait_for_load_state('networkidle')
        self.show_log(f'[{bidder_id}] 出价已全部拒绝')
        await bid_history_modal.get_by_label('Close').click()
        
    async def block_profile(self, bidder_id, page, bidder_profile_ele):
        self.show_log(f'[{bidder_id}] 正在封禁账号')
        bidder_id_ele_a = bidder_profile_ele.get_by_role('link').nth(0)
        try:
            await bidder_id_ele_a.click()
        except Exception:
            self.show_log(f'[{bidder_id}] 无法打开该行，未封禁')
            return False
        await bidder_profile_ele.locator('a[class="bidder-profile"]').click()
        profile_modal_content = page.locator('div#bidder-profile-modal div.modal-content')
        await profile_modal_content.locator('select[name="bidder-profile-decline-reason"]').select_option('7')
        await profile_modal_content.locator('button[id="bidder-profile-save"]').click()
        profile_saved_modal = page.locator('div[id="bidder-profile-saved-modal"]')
        await profile_saved_modal.get_by_label('Close').click()
        await profile_modal_content.get_by_label('Close').click()
        self.already_blocked_list.append(bidder_id)
        self.update_block_list(self.already_blocked_list)
        self.show_log(f'[{bidder_id}] 已封禁')
        return True

    async def wait_for_register_list(self, page, timeout=30000):
        table = page.locator('div.register-list-container table#register-list tbody')
        try:
            await table.wait_for(state='visible', timeout=timeout)
            return True
        except Exception:
            return False

    async def find_bidder_row(self, page, bidder_id):
        # Row indexes do not survive a reload: the list is sorted, and declining
        # a bidder's items moves them. Always look the row up by id again.
        table = page.locator('div.register-list-container table#register-list tbody')
        rows = table.get_by_role('row')
        for i in range(await rows.count()):
            cell = rows.nth(i).locator('td.bidder')
            try:
                text = await cell.get_by_role('link').nth(0).inner_text()
            except Exception:
                continue
            if text.strip().split(' ')[0] == bidder_id:
                return cell
        return None

    async def is_win_item_half_high_value(self, bidder_id, page, total_bid_amount_a, high_value, high_value_percent):
        await total_bid_amount_a.click()
        bid_history_modal = page.locator('div#bid-history-modal div.modal-content')
        await page.wait_for_load_state('networkidle')
        await bid_history_modal.wait_for(state='visible')
        bid_history_table = bid_history_modal.locator('table#bid-history-table tbody')
        await bid_history_table.wait_for(state='visible')
        bid_history_trs = bid_history_table.locator('> tr')
        bid_history_trs_count = await bid_history_trs.count()
        high_value_bid_count = 0
        winning_bid_count = 0
        for j in range(bid_history_trs_count):
            bid_tr = bid_history_trs.nth(j)
            lot_lead = (await bid_tr.locator('span[class="lot-lead"]').inner_text()).split('-')[0]
            # Only check Winning items
            bid_status = bid_tr.locator('td[class="bid-history-status hidden-xs text-center"]')
            bid_winning_count = await bid_status.locator('div.bid-status-winning:not([class*=" "])').count()
            if bid_winning_count == 0:
                continue
            winning_bid_count += 1
            bid_history_max_bid = await bid_tr.locator('td[class="bid-history-max-bid"]').inner_text()
            bid_max = float(bid_history_max_bid)
            if bid_max > high_value:
                high_value_bid_count += 1
            else:
                continue
        self.show_log(f'[{bidder_id}] 高价领先 {high_value_bid_count} / 领先总数 {winning_bid_count}')
        await bid_history_modal.get_by_label('Close').click()
        if winning_bid_count != 0 and (high_value_bid_count / winning_bid_count) >= high_value_percent:
            return True
        else:
            return False
        
    # This includes decline all items and block the account
    async def block_acc(self, bidder_id, page, total_bid_amount_a, data):
        # 2.1.1 Decline items
        await self.decline_items(bidder_id=bidder_id, page=page, total_bid_amount_a=total_bid_amount_a)
        # Closing the decline modal reloads the page by itself. Wait for the
        # list to come back rather than guessing how long that takes.
        if not await self.wait_for_register_list(page):
            self.show_log(f'[{bidder_id}] 拒绝后列表没刷新出来，未封禁')
            return False
        # 2.1.2 Block account, against the row as it stands now
        row = await self.find_bidder_row(page, bidder_id)
        if row is None:
            self.show_log(f'[{bidder_id}] 拒绝后已不在列表中，未封禁')
            return False
        if not await self.block_profile(bidder_id=bidder_id, page=page, bidder_profile_ele=row):
            return False
        # 2.1.3 Send log
        try:
            request_res = block_bidder_log(data)
        except Exception:
            self.show_log(f'[{bidder_id}] 上报封禁日志失败')
            self.show_log(traceback.format_exc())
        return True

    # Force-navigate to refresh_url and wait for it to settle. Used as a recovery
    # path when row processing throws (stale DOM, blank page after a block, etc.).
    # Retries when the site bounces to an internal-error page or goto throws.
    async def _force_refresh_page(self, page, refresh_url, context='', max_attempts=5):
        prefix = f'{context} ' if context else ''
        for attempt in range(1, max_attempts + 1):
            try:
                await page.goto(refresh_url)
                await page.wait_for_load_state('networkidle')
                landed = (page.url or '').lower()
                if 'internalservererror' in landed or 'error' in landed:
                    self.show_log(f'{prefix}刷新第 {attempt}/{max_attempts} 次落到了错误页：{page.url}')
                else:
                    return True
            except Exception:
                self.show_log(f'{prefix}刷新第 {attempt}/{max_attempts} 次失败：{traceback.format_exc()}')
            await asyncio.sleep(min(2 ** attempt, 30))
        self.show_log(f'{prefix}刷新 {max_attempts} 次都失败，放弃')
        return False
        self.show_log(f'{prefix}刷新 {max_attempts} 次都失败，放弃')
        return False

    # Wraps block_acc so that if the post-decline page refresh stalls or lands on
    # an empty page, we recover by force-navigating to refresh_url. Returns True
    # on normal completion, False if recovery was triggered (caller should
    # re-enumerate the current page rather than click Next).
    async def block_acc_safe(self, bidder_id, page, total_bid_amount_a, data, refresh_url):
        try:
            return await self.block_acc(bidder_id=bidder_id,
                                        page=page,
                                        total_bid_amount_a=total_bid_amount_a,
                                        data=data)
        except Exception as e:
            error_details = traceback.format_exc()
            self.show_log(f'[{bidder_id}] 封禁过程出错，刷新页面继续')
            self.show_log(error_details)
            await self._force_refresh_page(page, refresh_url, context=f'[{bidder_id}]')
            return False

    # Check if a bidder can be skipped, if any of followings applied, skip
    # - bidder in special allowed list
    # - bidder in blocked list
    # - bidder's bidding are appending
    # - bidder's total amount is 0, which means it hasn't bidden
    async def skip_acc(self, bidder_id, total_bid_amount_a):
        # Skip processed ids
        if bidder_id in self.special_allowed_list:
            return True
        if bidder_id in self.already_blocked_list:
            return True
        # 1. Check bid history total amount
        ct = await total_bid_amount_a.count()
        # The bidder's bidding are all pending
        if ct == 2:
            return True
        total_bid_amount_div = total_bid_amount_a.locator('div')
        total_bid_amount_div_count = await total_bid_amount_div.count()
        # The bidder hasn't bid yet
        if total_bid_amount_div_count == 0:
            return True
        
        return False
    
    async def filter_bidder(self, page: Page, auction_id, mng_acc=None, reputation=20, high_value=200, high_value_percent=0.5, block_us_switch=True):
        query = '?buyer=0&siteId=0&regsortorder=8&All=False'
        state_query = '?buyer=0&siteId=0&regsortorder=13&All=False'
        if page.url.find('?q=') == -1:
            upper_url = get_upper_level_url(page.url)
            url = upper_url + query
            url_state_desc = upper_url + state_query
        else:
            domain = page.url.split('?')[0]
            url = domain + query
            url_state_desc = domain + state_query
        filter_round = 0
        transaction_id = str(uuid.uuid4())
        block_count = 0
        check_count = 0
        # Infinate running
        while self.is_filter_running:
            await self._force_refresh_page(page, url, context='[score round]')
            round_continue = True
            start = datetime.now()
            filter_round += 1
            
            # Check score under 20
            while round_continue and self.is_filter_running:
                await page.wait_for_load_state('networkidle')
                register_list_container = page.locator('div.register-list-container')
                register_list_tbody = register_list_container.locator('table#register-list tbody')
                trs = register_list_tbody.get_by_role("row")
                count = await trs.count()
                for i in range(count):
                    declined_flag = False
                    if not self.is_filter_running:
                        break
                    try:
                        tr = trs.nth(i)
                        # Bidder id
                        bidder_profile_ele = tr.locator('td.bidder')
                        bidder_id_ele_a = bidder_profile_ele.get_by_role('link').nth(0)
                        bidder_id_text = await bidder_id_ele_a.inner_text()
                        bidder_id = bidder_id_text.strip().split(' ')[0]
                        total_bid_amount_a = tr.locator('td.text-center.bids').locator('a[class="lot-bid-history"]')

                        # Score
                        score_text = await tr.locator('td.score a.bidder-profile div').first.inner_text()
                        score = int(score_text)
                        if score >= reputation:
                            self.show_log(f'[{bidder_id}] 信誉分不低于 {reputation}，本轮结束')
                            round_continue = False
                            break
                        check_count += 1
                        skip_flag = await self.skip_acc(bidder_id=bidder_id, total_bid_amount_a=total_bid_amount_a)
                        if skip_flag:
                            continue

                        # Check if total bid amount larger than high value
                        total_bid_amount_div = total_bid_amount_a.locator('div')
                        total_bid_amount_text = await total_bid_amount_div.inner_text()
                        try:
                            total_bid_amount = float(total_bid_amount_text[1:-1].replace(',', ''))
                        except Exception as e:
                            self.show_log('读取出价记录失败，跳过')
                            continue
                        # 2. If amount is larger than high_value, do further investigate
                        if total_bid_amount > high_value:
                            self.show_log(f"[{bidder_id}] 出价总额 {total_bid_amount}，进一步检查")
                            declined_flag = await self.is_win_item_half_high_value(bidder_id=bidder_id,
                                                                             page=page,
                                                                             total_bid_amount_a=total_bid_amount_a,
                                                                             high_value=high_value,
                                                                             high_value_percent=high_value_percent
                                                                             )

                        # 2.1 Half items are over 50%, decline items
                        # Block the bidder, add to the list
                        if declined_flag:
                            data = {
                                "transaction_id": transaction_id,
                                "automation_link": url,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "client": mng_acc,
                                "bidder_id": bidder_id,
                                "status": "success",
                                "message": "The bidder has been blocked"
                            }
                            success = await self.block_acc_safe(bidder_id=bidder_id,
                                           page=page,
                                           total_bid_amount_a=total_bid_amount_a,
                                           data=data,
                                           refresh_url=url)
                            if not success:
                                # Page was force-refreshed; skip this entry, move on
                                continue
                            block_count += 1
                        else:
                            continue
                    except Exception:
                        error_details = traceback.format_exc()
                        self.show_log(f'第 {i} 行处理失败，刷新页面继续')
                        self.show_log(error_details)
                        await self._force_refresh_page(page, url, context=f'[row {i}]')
                        continue
                # If last bidder's reputation is still less than reputation, go to next page
                if round_continue and self.is_filter_running:
                    next_page_button = register_list_container.locator('div#register-list_paginate ul li').get_by_text('Next')
                    await next_page_button.click()
            
            # Check US customers
            
            if block_us_switch:
                await self._force_refresh_page(page, url_state_desc, context='[us round]')
                round_continue = True
                while round_continue and self.is_filter_running:
                    await page.wait_for_load_state('networkidle')
                    register_list_container = page.locator('div.register-list-container')
                    register_list_tbody = register_list_container.locator('table#register-list tbody')
                    trs = register_list_tbody.get_by_role("row")
                    count = await trs.count()
                    for i in range(count):
                        declined_flag = False
                        if not self.is_filter_running:
                            break
                        try:
                            tr = trs.nth(i)
                            # Bidder id
                            bidder_profile_ele = tr.locator('td.bidder')
                            bidder_id_ele_a = bidder_profile_ele.get_by_role('link').nth(0)
                            bidder_id_text = await bidder_id_ele_a.inner_text()
                            bidder_id = bidder_id_text.strip().split(' ')[0]
                            total_bid_amount_a = tr.locator('td.text-center.bids').locator('a[class="lot-bid-history"]')

                            check_count += 1

                            skip_flag = await self.skip_acc(bidder_id=bidder_id, total_bid_amount_a=total_bid_amount_a)
                            if skip_flag:
                                continue

                            # Bidder country
                            bidder_profile = bidder_profile_ele.locator('div[class="buyer-profile collapse"]')
                            bidder_profile_location = bidder_profile.locator('[class="location"]')
                            location = await bidder_profile_location.inner_text()
                            if "United States" in location:
                                self.show_log(f"[{bidder_id}] 美国竞拍者，封禁")
                                data = {
                                    "transaction_id": transaction_id,
                                    "automation_link": url,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "client": mng_acc,
                                    "bidder_id": bidder_id,
                                    "status": "success",
                                    "message": "The bidder has been blocked due to no shipping to the US."
                                }
                                success = await self.block_acc_safe(bidder_id=bidder_id,
                                            page=page,
                                            total_bid_amount_a=total_bid_amount_a,
                                            data=data,
                                            refresh_url=url_state_desc)
                                if not success:
                                    # Page was force-refreshed; skip this entry, move on
                                    continue
                                block_count += 1
                            else:
                                round_continue = False
                                break
                        except Exception:
                            error_details = traceback.format_exc()
                            self.show_log(f'第 {i} 行处理失败，刷新页面继续')
                            self.show_log(error_details)
                            await self._force_refresh_page(page, url_state_desc, context=f'[row {i}]')
                            continue
                    # If last bidder's reputation is still less than reputation, go to next page
                    if round_continue and self.is_filter_running:
                        next_page_button = register_list_container.locator('div#register-list_paginate ul li').get_by_text('Next')
                        await next_page_button.click()
                            
            if self.is_filter_running:
                end = datetime.now()
                # Every 90 seconds a round
                time_diff = round((end - start).total_seconds(), 2)
                if time_diff < 90:
                    self.show_message(f'过滤第 {filter_round} 轮完成，用时 {time_diff} 秒')
                    sleep_time = round(90 - time_diff, 2)
                    self.show_message(f'等待 {sleep_time} 秒后进入下一轮')
                    await asyncio.sleep(sleep_time)
        # TODO: Log this transaction
        try:
            txns_data = {
                "transaction_id": transaction_id,
                "automation_link": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "client": mng_acc,
                "status":"success",
                "checked_bidder_count": check_count,
                "blocked_bidder_count": block_count,
                "message":"The transaction blocked"
            }
            request_res = filter_bidder_txns(txns_data)
        except Exception as e:
            error_details = traceback.format_exc()
            self.show_log(error_details)
        # Save special and blocked list locally
        self.already_blocked_list = [entry for entry in self.already_blocked_list if entry not in self.special_allowed_list]
        save_bidder_registration(auction_id, self.special_allowed_list, self.already_blocked_list)
        
        # Add this to this transaction
        return '竞拍者过滤完成'
    
    def registration_url(self, catalog_url):
        parsed = urlparse(catalog_url)
        parts = [part for part in parsed.path.split('/') if part]
        if len(parts) < 2 or parts[0] != 'catalog':
            return None
        return f'{parsed.scheme}://{parsed.netloc}{self.REGISTRATION_PATH}{parts[1]}'

    async def is_registered(self, page):
        header_button = page.locator(
            f'app-auction-header app-button:has-text("{self.REGISTERED_BUTTON_TEXT}")'
        )
        return await header_button.count() > 0

    async def ensure_registered(self, page):
        if await self.is_registered(page):
            return True
        # Older sites showed an in-page modal instead of the wizard.
        if await page.locator('app-register-auction').count() > 0:
            return await self.bot_register_auction(page)
        return await self.register_auction(page)

    async def wait_enabled(self, locator, timeout):
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            try:
                if await locator.is_enabled():
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.2)
        return False

    async def open_section(self, page):
        section = page.locator('button.accordion-header[aria-expanded="true"]').first
        if await section.count() == 0:
            return None
        return await section.get_attribute('aria-label')

    async def register_auction(self, page):
        """Walk the three step registration wizard for the current auction.

        payment -> delivery method -> terms, each one unlocking the submit
        button at the bottom. This accepts the auction terms and confirms the
        card already on file, which the site verifies with a temporary hold.
        """
        url = self.registration_url(page.url)
        if not url:
            self.show_log(f'无法从 {page.url} 推出注册页地址')
            return False
        self.show_log('本场拍卖未注册，开始自动注册')
        await page.goto(url)
        await page.wait_for_load_state('networkidle')

        # Three sections, with slack in case the site adds one.
        for _ in range(6):
            if self.REGISTRATION_PATH not in page.url:
                break
            section = await self.open_section(page)
            if section is None:
                self.show_log('注册：没有待填写的步骤了')
                break
            if section == 'payment':
                card = page.locator('input#selected-card-0')
                if await card.count() == 0:
                    self.show_log('注册中止：账号里没有在档银行卡')
                    return False
                if not await card.is_checked():
                    await card.check()
            elif section == 'delivery-method':
                await page.locator(self.DELIVERY_METHOD).check()
            elif section == 'terms':
                await page.locator('input#terms-input').check()
            else:
                self.show_log(f'注册中止：遇到未知步骤 {section}')
                return False

            submit = page.locator('button[type="submit"]').last
            if not await self.wait_enabled(submit, 5000):
                self.show_log(f'注册中止：{section} 这步的提交按钮一直不可点')
                return False
            label = (await submit.inner_text()).strip()
            await submit.click()
            self.show_log(f'注册：{section} 已完成')

            # The wizard swaps the open section in place, so wait for that
            # rather than for a navigation.
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                await asyncio.sleep(0.3)
                if self.REGISTRATION_PATH not in page.url:
                    break
                if await self.open_section(page) != section:
                    break

        if self.REGISTRATION_PATH in page.url:
            self.show_log('注册未完成，仍停在注册页')
            return False
        # When it is done, and also when the account turns out to be registered
        # already, the site drops us on some other page, sometimes on the public
        # hibid.com catalog. Check on the auction page itself.
        await page.goto(self.bid_link)
        await page.wait_for_load_state('networkidle')
        registered = await self.is_registered(page)
        self.show_log('注册完成' if registered else '注册流程走完，但页面仍显示未注册')
        return registered

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
        
    async def untick_refresh(self, page):
        # Untick the refresh checkbox
        refresh_container = page.locator('app-live-lot-refresh')
        refresh_checkbox = refresh_container.locator('input[type="checkbox"]')
        if await refresh_checkbox.count() == 0:
            return
        if await refresh_checkbox.is_checked():
            await refresh_checkbox.uncheck()
            self.show_log('已关闭页面自动刷新')
        
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
        
    async def confirm_your_bid_modal(self, bid_modal, lot=''):
        # This one is not guaranteed to render inside the bid modal.
        confirm_button = bid_modal.page.locator(self.RECONFIRM_BUTTON).first
        close_button = bid_modal.get_by_label("Close", exact=True).first
        try:
            # is_visible() ignores its timeout and answers immediately, so wait
            # for the reconfirmation to arrive instead of asking straight away.
            await confirm_button.wait_for(state='visible', timeout=2000)
            await confirm_button.click(timeout=2000)
            self.show_log(f'lot {lot}：已二次确认')
        except Exception:
            pass
        # An accepted bid closes the modal on its own. Wait for that rather than
        # sampling once, because the site only closes it after the round trip.
        try:
            await bid_modal.first.wait_for(state='hidden', timeout=3000)
            return True
        except Exception:
            pass
        # previous bid visible
        try:
            message = ' '.join((await bid_modal.first.inner_text()).split())[:300]
            self.show_log(f'lot {lot}：出价未成功，网站提示：{message}')
        except Exception:
            pass
        try:
            if await close_button.is_visible():
                await close_button.click(timeout=2000)
        except Exception:
            pass
        return False
    
    def parse_amount(self, text):
        # None means "could not read it", which callers must treat as unsafe.
        match = self.BID_AMOUNT_RE.search(text or '')
        if not match:
            return None
        try:
            return float(match.group(1).replace(',', ''))
        except ValueError:
            return None

    async def click_if_possible(self, locator, description, lot):
        try:
            await locator.click(timeout=2000)
            return True
        except Exception:
            self.show_log(f'lot {lot}：点击{description}失败')
            return False


    def file_to_lot_dict(self, filepath):
        with open(filepath, 'r') as f:
            df = pd.read_csv(f)
            df['lot'] = df['lot'].astype(str)  # Convert the 'lot' column to string type
            self.lot_dict = df.set_index('lot')[['msrp_price', 'skipped', 'second_hand']].to_dict('index')
            self.show_log(f'文件已导入，共 {len(self.lot_dict)} 个 lot')
