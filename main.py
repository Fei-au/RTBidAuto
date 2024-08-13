from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from time import sleep
from feet_to_meters import feet_to_meters_gui, FeetToMeters
from tools import print_hierarchy
from bid_gui import BidGui

'''
Input:
1. Manager Acc
2. Bot Acc
3. Management Lots link
4. Bid link
'''

'''
1. @m Upload file
2. @m Add hibid manager acc and other accs
3. Open different browsers, instead only open diff pages
4. Go to manager page (if have link that will be better) and check items
    wait_to_bid = []
    Loop items on the page
    1. if the item haven't been bid, skip
    2. elif the item has been bid
        2.1 if item last bid is done by my accs, skip
        2.2 if last bid is not my accs
            Get item's msrp price from uploaded sheet

            A bid high price
            B max aim price
            2.2.1 if the item in the lot's msrp price is greater and equal to 100
                C 20% msrp price
                max = check the higher price between bidder's highest aim price B and 20% of msrp price C
            2.2.2 elif the item msrp price is less than 100
                max = bidder's highest aim price B
            2.2.3
            if max <= A
                skip
            if max > A
                bid to max
                wait_to_bid.append([
                    [
                        {highname: {lot: number, bid to highest: number},
                        {highname2: {lot: number, bid to highest: number},
                        {highname3: {lot: number, bid to highest: number},
                    ],
                    [
                        {highname2: {lot: number, bid to highest: number},
                    ],
                ] })

                dict 2:{
                    highname: (0,0),
                    highname2: (1,0),
                    highname3: (0,2),
                }

                1. Check highname in dict or not
                    not exist:
                        1. len = Get wait_to_bid length
                        2. Append to wait_to_bid 0, 
                        3. Log dict 2 with (0, len)
                    exist:
                        1. Init tuple(0) + 1 layer if needed and get len = tule(0) + 1
                        2. (Append to tuple(0) + 1, len(tule(0) + 1))
                        3. Log dict 2 with (tuple(0) + 1, len)

'''

'''
Bid to highest
1. Loop wait_to_bid
    1. Open bid link
    2. Login bot acc
    3. Go to bid link ?q=lot
    4. Find item? by its lot number to find its certain parent
    5. Find Bid button and click
    6. Enter bid to highest value
    7. Click confirm

'''



def tk_gui():

    root = Tk(screenName='Hibid Automation')
    
    # app.title("Hibid Automation")
    # root
    root_frm = ttk.Frame(root, padding=10)
    root_frm.grid()

    print_hierarchy(root)

    tit_frm = ttk.Frame(root_frm).grid(row=0, column=0)

    ttk.Label(root_frm, text='Automation').grid(column=0, row=0)

    # ttk.Label(l, text='Auto2')
    

    btn = ttk.Button(root_frm, text='Quit', command=root.destroy)
    btn.grid(column=1, row=0, padx=50, ipadx=20, ipady=20)
    btn.configure(text='goodbye')
    # Button(root_frm, text='Test Button', fg='red', bg='blue').grid(row=1, column=0)
    print(btn['text'])

    # btn_open = Button(root_frm, text="Open File", command=open_file)
    # btn_open.pack(pady=10)

    # btn_start = Button(root_frm, text="Start Automation", command=start_automation)
    # btn_start.pack(pady=10)

    root.mainloop()



if __name__ == '__main__':
    # tk_gui()

    
    # feet_to_meters_gui()

    root = Tk()
    BidGui(root)
    root.mainloop()

