# RTBidAuto

## Start
```
python main.py
```
## Deploy an app
Include browsers in .exe
```
pyinstaller --onefile --noconsole --name="Auto Bid" --add-data=".env;." --add-data "playwright-browsers;playwright-browsers" main.py
```




## Steps to bypass login checker
1. Open local browser and expose port 9222
   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-dev-profile"
   ```
2. Manully go to the page and login , note: login the same domain like company.bid.com, instead of www.bid.com
   
3. Start the app and connect with browser
4. Now it's ready to use