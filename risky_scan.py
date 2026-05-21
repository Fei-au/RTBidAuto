import asyncio
import re
import traceback


class RiskyScanner:
    DECLINE_KEYWORDS = ['Bad Check', 'Chargeback', 'Difficult', 'Fraud', 'Scammer', 'Suspicious', 'Multiple Account', 'Multiple Accounts', 'Multi-Account', 'Multi-Accounts']

    def __init__(self, show_log, show_message):
        self.show_log = show_log
        self.show_message = show_message
        self.risky_bidders = []
        self.is_running = False

    async def login_manager(self, page, mng_acc, mng_pwd):
        landing = 'https://my.hibid.com/auctioneer/auctions/current/'
        await page.goto(landing)
        # If already logged in, the URL stays on landing; otherwise we get
        # redirected to https://my.hibid.com/ (the login page).
        if page.url == landing:
            self.show_log('Manager already logged in')
            return
        self.show_log('Manager not logged in, filling credentials...')
        await page.locator('[id="auctioneer-logon-username"]').fill(mng_acc)
        await asyncio.sleep(1)
        await page.locator('[id="Password"]').fill(mng_pwd)
        await asyncio.sleep(1.2)
        await page.get_by_text("Log On", exact=True).click()
        try:
            await page.wait_for_url("**/auctioneer/**")
        except Exception:
            await asyncio.sleep(10)

    async def scan(self, lotstat_page, register_page, auction_id,
                   high_bid_threshold=50, score_threshold=30):
        self.is_running = True
        try:
            high_bidders = await self._collect_high_bidders(
                lotstat_page, auction_id, high_bid_threshold)
            self.show_message(
                f"Collected {len(high_bidders)} high bidders (high bid >= {high_bid_threshold})")
            if not high_bidders:
                self.risky_bidders = []
                return []
            risky = await self._scan_register_modals(
                register_page, auction_id, high_bidders, score_threshold)
            self.risky_bidders = risky
            self.show_message(f"Found {len(risky)} risky bidders")
            return risky
        finally:
            self.is_running = False

    async def _collect_high_bidders(self, page, auction_id, threshold):
        cpage = 1
        seen = {}
        while True:
            url = (f"https://my.hibid.com/auctioneer/lotstats/index/{auction_id}/"
                   f"?q=&buyer=0&cat=&SortOrder=3&ProductStatus=0&All=False&cpage={cpage}")
            await page.goto(url)
            await page.wait_for_load_state('networkidle')
            rows = await page.evaluate("""
                () => {
                    const trs = Array.from(document.querySelectorAll('table#lot-list tbody tr'));
                    return trs.map(tr => {
                        const hb = tr.querySelector('.lot-high-bid');
                        const ne = tr.querySelector('.name-expand');
                        return {
                            highBid: hb ? (parseFloat(hb.innerText.split(' ')[0].replace(/,/g, '')) || 0) : 0,
                            nameText: ne ? ne.innerText.trim() : ''
                        };
                    });
                }
            """)
            if not rows:
                break
            self.show_log(f'[lotstats cpage={cpage}] {len(rows)} rows')
            stop = False
            for r in rows:
                if r['highBid'] < threshold:
                    stop = True
                    break
                if r['nameText']:
                    bidcard = r['nameText'].split(' ')[0]
                    seen.setdefault(bidcard, r['nameText'])
            if stop:
                break
            cpage += 1
        return [{'bidcard_num': k, 'name': v} for k, v in seen.items()]

    async def _scan_register_modals(self, page, auction_id, high_bidders, score_threshold):
        targets = {b['bidcard_num']: b['name'] for b in high_bidders}
        target_set = set(targets.keys())
        url = (f"https://my.hibid.com/auctioneer/register/index/{auction_id}/"
               f"?buyer=0&siteId=0&regsortorder=1&All=True")
        await page.goto(url)
        await page.wait_for_load_state('networkidle')

        risky = []
        processed = set()
        trs = page.locator('div.register-list-container table#register-list tbody tr')
        count = await trs.count()
        self.show_log(f'[register] iterating {count} rows, looking for {len(target_set)} targets')

        for i in range(count):
            if processed >= target_set:
                break
            tr = trs.nth(i)
            bidcard = None
            try:
                name_link = tr.locator('td.bidder a.name-expand').first
                if await name_link.count() == 0:
                    continue
                name_text = (await name_link.inner_text()).strip()
                bidcard = name_text.split(' ')[0]
                if bidcard not in target_set or bidcard in processed:
                    continue

                await name_link.click()
                await tr.locator('td.bidder a.bidder-profile').first.click()

                modal = page.locator('div#bidder-profile-modal div.modal-content')
                await modal.locator('p#bidder-profile-reputation').wait_for(
                    state='visible', timeout=10000)

                score_text = (await modal.locator('p#bidder-profile-reputation').inner_text()).strip()
                try:
                    score = int(score_text)
                except ValueError:
                    score = 0
                raw_notes = (await modal.locator('p#bidder-profile-other-public-notes').inner_text()).strip()
                # Collapse newlines and excessive whitespace so Excel doesn't blow up the row height.
                notes_text = re.sub(r'\s*\n\s*', ' | ', raw_notes)
                notes_text = re.sub(r'\s{2,}', ' ', notes_text).strip(' |')

                reason = None
                if score < score_threshold:
                    reason = f'Score < {score_threshold}'
                else:
                    notes_lower = notes_text.lower()
                    matched = [kw for kw in self.DECLINE_KEYWORDS if kw.lower() in notes_lower]
                    if matched:
                        reason = f'Bad notes: {", ".join(matched)}'

                if reason:
                    risky.append({
                        'bidcard_num': bidcard,
                        'name': name_text,
                        'score': score,
                        'reason': reason,
                        'notes': notes_text,
                    })
                    self.show_log(f'[{bidcard}] RISKY ({reason}, score={score})')
                else:
                    self.show_log(f'[{bidcard}] OK (score={score})')

                await modal.locator('button#bidder-profile-close').click()
                processed.add(bidcard)
            except Exception:
                self.show_log(f'row {i} (bidcard={bidcard}) failed:\n{traceback.format_exc()}')
                try:
                    close_btn = page.locator('div#bidder-profile-modal button#bidder-profile-close')
                    if await close_btn.count() > 0 and await close_btn.is_visible():
                        await close_btn.click()
                except Exception:
                    pass
                if bidcard:
                    processed.add(bidcard)
                continue
        return risky
