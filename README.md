# RTBidAuto

## Start
```
python main.py
```
## Set env in powershell
If change the value in .env and restart program, the value hasn't changed when load dotenv, close current powershell and use a new one
```powershell
# Manully set env var in powershell
$env:LOG_BACK = "your_value"
```
## Deploy an app
Include browsers in .exe
```
pyinstaller --onefile --noconsole --name="Auto Bid3.3" --add-data=".env;." --add-data "playwright-browsers;playwright-browsers" main.py
```




## Steps to bypass login checker
The bot account lives in the Chrome profile `C:\chrome-dev-profile`. **2. Login Accounts** opens Chrome on it with port 9222 by itself (or reuses a Chrome already on that port), so the command below is only needed for the first sign-in on a machine, or to open it by hand.

1. Open local browser and expose port 9222
   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-dev-profile"
   ```
2. Manully go to the page and login , note: login the same domain like company.bid.com, instead of www.bid.com. The profile keeps the session, so this is needed only once, and again when HiBid expires it (about a month).
   
3. Start the app and connect with browser
4. Now it's ready to use