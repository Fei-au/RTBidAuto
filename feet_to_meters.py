from tkinter import *
from tkinter import ttk
from tools import print_hierarchy

def calculate(feet, meters, *args):
    try:
        print(args[0])
        value = float(feet.get())
        meters.set(int(0.3048 * value * 10000.0 + 0.5) / 10000.0)
    except ValueError:
        pass

def feet_to_meters_gui():
    root = Tk()
    root.title("Feed to Meters")

    mainframe = ttk.Frame(root, padding="3 3 12 12")
    mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    feet = StringVar()
    feet_entry = ttk.Entry(mainframe, width=7, textvariable=feet)
    feet_entry.grid(column=2, row=1, sticky=(W, E))

    meters = StringVar()
    ttk.Label(mainframe, textvariable=meters).grid(column=2, row=2, sticky=(W, E))

    ttk.Button(mainframe, text='Calculate', command=lambda: calculate(feet, meters)).grid(column=3, row=3, sticky=W)

    ttk.Label(mainframe, text="feet").grid(column=3, row=1, sticky=W)
    ttk.Label(mainframe, text="is equivalent to").grid(column=1, row=2, sticky=E)
    ttk.Label(mainframe, text="meters").grid(column=3, row=2, sticky=W)

    ttk.Button(mainframe, text="Quit", command=root.destroy).grid(column=3, row=4, sticky=E)

    for child in mainframe.winfo_children():
        child.grid_configure(padx=5, pady=5)

    feet_entry.focus()
    root.bind("<Return>", (lambda event: calculate(feet, meters, event)))

    root.mainloop()

class FeetToMeters:

    def __init__(self, root) -> None:
        
        root.title("Feed to Meters")

        mainframe = ttk.Frame(root, padding="3 3 12 12")
        mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        self.feet = StringVar()
        feet_entry = ttk.Entry(mainframe, width=7, textvariable=self.feet)
        feet_entry.grid(column=2, row=1, sticky=(W, E))

        self.meters = StringVar()
        ttk.Label(mainframe, textvariable=self.meters).grid(column=2, row=2, sticky=(W, E))

        ttk.Button(mainframe, text='Calculate', command=self.calculate).grid(column=3, row=3, sticky=W)

        ttk.Label(mainframe, text="feet").grid(column=3, row=1, sticky=W)
        ttk.Label(mainframe, text="is equivalent to").grid(column=1, row=2, sticky=E)
        ttk.Label(mainframe, text="meters").grid(column=3, row=2, sticky=W)

        ttk.Button(mainframe, text="Quit", command=root.destroy).grid(column=3, row=4, sticky=E)
        print_btn = ttk.Button(mainframe, text="Print hierarchy", command=lambda: print_hierarchy(root))
        print_btn.grid(column=3, row=4, sticky=E)
        
        

        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        feet_entry.focus()
        feet_entry.bind("<Return>", self.calculate)

    def calculate(self, *args):
        try:
            print(args)
            value = float(self.feet.get())
            self.meters.set(int(0.3048 * value * 10000.0 + 0.5) / 10000.0)
        except ValueError:
            pass


    

