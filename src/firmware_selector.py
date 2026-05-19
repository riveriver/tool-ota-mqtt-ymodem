import os
from tkinter import Tk
from tkinter.filedialog import askopenfilename

def select_firmware():
    """Open a file dialog to select a firmware file and return its path."""
    Tk().withdraw()  # Prevents the root window from appearing
    # Show all files in the dialog instead of filtering to .bin/.hex only
    firmware_file = askopenfilename(title="Select Firmware File", filetypes=[("All Files", "*.*")])
    
    if not firmware_file:
        print("No file selected.")
        return None
    
    if not os.path.isfile(firmware_file):
        print("Selected path is not a valid file.")
        return None
    
    return firmware_file