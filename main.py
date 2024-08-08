import tkinter as tk
from tkinter import filedialog
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
from time import sleep
        

def start_automation():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page2 = context.new_page()
        page.goto('https://www.google.com')
        page2.goto('https://www.youtube.com')
        sleep(60)
        browser.close()



def open_file():
    filepath = filedialog.askopenfilename()
    print(f'file name is: {filepath}')

'''
1. Upload file
2. Add hibid manager acc and other accs
3. Open different browsers, instead only open diff pages
4. Go to manager page (if have link that will be better) and check items
    1. if the item haven't been bid, skip
    2. if the item has been bid
        2.1 if item is bid by my accs, skip
        2.2 if last bid is not my acc
            Get item's msrp price from uploaded sheet
            2.2.1 if the item in the lot price is greater and equal to 100
                if the 

            2.2.2 if the item in the lot price is less than 100
'''

if __name__ == '__main__':

    app = tk.Tk()
    app.title("Hibid Automation")

    btn_open = tk.Button(app, text="Open File", command=open_file)
    btn_open.pack(pady=10)

    btn_start = tk.Button(app, text="Start Automation", command=start_automation)
    btn_start.pack(pady=10)

    app.mainloop()
