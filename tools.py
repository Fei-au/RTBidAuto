

def print_hierarchy(w, depth=0):
    print('  '*depth + w.winfo_class() + ' w=' + str(w.winfo_width()) + ' h=' + str(w.winfo_height()) + ' x=' + str(w.winfo_rootx()) + ' y=' + str(w.winfo_rooty()))
    for i in w.winfo_children():
        print_hierarchy(i, depth+1)