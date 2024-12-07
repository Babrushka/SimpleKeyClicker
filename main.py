import threading
import time
import sys
import pydirectinput
import keyboard  # for hotkey start/stop
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import Toplevel, PhotoImage
from tkinter import Frame, LEFT, BOTH, YES, X, Y, RIGHT, TOP, BOTTOM, HORIZONTAL, VERTICAL

# -----------------------------
# Configuration
# -----------------------------
TOOL_NAME = "SimpleKeyClicker"
POSSIBLE_KEYS = """
Possible Keys/Mouse Actions:
- Single keys: a, b, c, ..., z
- Digits: 0-9
- Special keys: TAB, SPACE, ENTER, ESC, SHIFT, CTRL, ALT, BACKSPACE
- Mouse clicks: click (left click), rclick (right click), mclick (middle click)
- Other keys: up, down, left, right, home, end, pageup, pagedown
- Characters: !, @, #, $, %, ^, &, *, (, ), -, _, =, +, [, ], {, }, ;, :, ', ", \\, |, ,, <, ., >, /, ?
"""

ICON_PATH = "logo.ico"
LOGO_PATH = "logo.png"  # For the UI banner and error windows

class KeyClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(TOOL_NAME)
        self.root.geometry("500x250")
        self.root.resizable(False, True)
        self.root.minsize(500, 250)
        # Set window icon if available
        try:
            self.root.iconbitmap(ICON_PATH)
        except:
            pass

        # Style and theme
        self.style = tb.Style("sandstone")  # use any ttkbootstrap theme you prefer

        # Main frame
        self.main_frame = tb.Frame(self.root, padding=10)
        self.main_frame.pack(fill=BOTH, expand=YES)

        # -----------------------------
        # Top Frame (Row 1: Logo & Buttons)
        # -----------------------------
        self.top_frame = tb.Frame(self.main_frame)
        self.top_frame.pack(fill=X, pady=(0,5))

        # Create a horizontal container for the logo and text/buttons
        logo_btn_frame = tb.Frame(self.top_frame)
        logo_btn_frame.pack(fill=X, pady=5)

        # Logo
        try:
            self.logo_image = PhotoImage(file=LOGO_PATH)
            logo_label = tb.Label(logo_btn_frame, image=self.logo_image)
            logo_label.pack(side=LEFT, padx=(5, 20))
        except:
            pass

        # Info button
        self.info_button = tb.Button(logo_btn_frame, text="Info (Keys)", bootstyle=INFO, command=self.show_info)
        self.info_button.pack(side=LEFT, padx=5)

        # Start/Stop Buttons
        self.start_button = tb.Button(logo_btn_frame, text="Start", padding=(40, 6), bootstyle=PRIMARY, command=self.start_action)
        self.start_button.pack(side=LEFT, padx=5)

        self.stop_button = tb.Button(logo_btn_frame, text="Stop", padding=(40, 6), bootstyle=DANGER, command=self.stop_action)
        self.stop_button.pack(side=LEFT, padx=5)

        # Hint label
        tb.Label(self.top_frame, text="Hint: Press Ctrl+F2 to Start, Ctrl+F3 to Stop", 
                 font=("Helvetica", 10, "italic")).pack(pady=(5,0))

        # -----------------------------
        # Bottom Frame (Row 2: Scrollable Action Rows)
        # -----------------------------
        self.bottom_frame = tb.Frame(self.main_frame)
        self.bottom_frame.pack(fill=BOTH, expand=YES, pady=(10, 0))

        # Add Row button (at the top of bottom frame)
        add_row_frame = tb.Frame(self.bottom_frame)
        add_row_frame.pack(fill=X)
        tb.Button(add_row_frame, text="Add Row", bootstyle=SUCCESS, command=self._add_row).pack(side=LEFT, padx=5, pady=5)

        # Scrollable area
        self.canvas = tb.Canvas(self.bottom_frame, highlightthickness=0)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=YES)

        self.scrollbar = tb.Scrollbar(self.bottom_frame, orient=VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=RIGHT, fill=Y)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # A frame inside the canvas
        self.rows_container = tb.Frame(self.canvas)
        self.canvas.create_window((0,0), window=self.rows_container, anchor="nw")

        self.rows_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Store rows
        self.rows = []

        # Add the first mandatory row
        self._add_row(mandatory=True)

        # State variables
        self.running = False
        self.thread = None

        # Setup hotkeys
        keyboard.add_hotkey('ctrl+f2', self.start_action)
        keyboard.add_hotkey('ctrl+f3', self.stop_action)

    def _add_row(self, mandatory=False):
        """Add a new row for key/sleep input and center it."""
        row_frame = tb.Frame(self.rows_container)
        row_frame.pack(fill=X, pady=2)

        sub_frame = tb.Frame(row_frame)
        sub_frame.pack(anchor='center')

        key_var = tb.StringVar(value="")
        sleep_var = tb.StringVar(value="0.5")  # default sleep time

        tb.Label(sub_frame, text="Key/Button:", width=12).pack(side=LEFT)
        tb.Entry(sub_frame, textvariable=key_var, width=20).pack(side=LEFT, padx=5)

        tb.Label(sub_frame, text="Delay (s):", width=10).pack(side=LEFT)
        tb.Entry(sub_frame, textvariable=sleep_var, width=10).pack(side=LEFT, padx=5)

        remove_btn = None
        if not mandatory:
            remove_btn = tb.Button(sub_frame, text="Remove", bootstyle=DANGER, command=lambda f=row_frame: self._remove_row(f))
            remove_btn.pack(side=LEFT, padx=5)

        self.rows.append({
            'frame': row_frame,
            'key_var': key_var,
            'sleep_var': sleep_var,
            'remove_btn': remove_btn,
            'mandatory': mandatory
        })

    def _remove_row(self, frame):
        """Remove a row from the UI and the list."""
        for r in self.rows:
            if r['frame'] == frame:
                r['frame'].destroy()
                self.rows.remove(r)
                break

    def show_info(self):
        info_win = Toplevel(self.root)
        info_win.title("Info - Possible Keys")
        try:
            info_win.iconbitmap(ICON_PATH)
        except:
            pass
        info_win.grab_set()
        tb.Label(info_win, text=POSSIBLE_KEYS, font=("Helvetica", 13), padding=20, justify=LEFT).pack()
        tb.Button(info_win, text="Close", bootstyle=PRIMARY, command=info_win.destroy).pack(pady=10)

    def show_custom_error(self, title, message):
        """Show a custom error window with the logo instead of the default icon."""
        error_win = Toplevel(self.root)
        error_win.title(title)
        try:
            error_win.iconbitmap(ICON_PATH)
        except:
            pass
        error_win.grab_set()

        frm = tb.Frame(error_win, padding=10)
        frm.pack()

        # Load the logo image
        try:
            logo = PhotoImage(file=LOGO_PATH)
            logo_label = tb.Label(frm, image=logo)
            logo_label.image = logo  # keep a reference so it's not garbage-collected
            logo_label.pack()
        except:
            pass

        tb.Label(frm, text=message, padding=10, justify=LEFT, foreground="red", font=("Helvetica", 12)).pack()
        tb.Button(frm, text="OK", bootstyle=PRIMARY, command=error_win.destroy).pack(pady=10)

        # Center the error window relative to the main window
        error_win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (error_win.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (error_win.winfo_height() // 2)
        error_win.geometry(f"+{x}+{y}")

    def start_action(self):
        if self.running:
            return
        # Validate input
        for r in self.rows:
            if r['key_var'].get().strip() == "":
                self.show_custom_error("Error", "Please specify a key/button in all rows.")
                return
            try:
                float(r['sleep_var'].get())
            except ValueError:
                self.show_custom_error("Error", f"Invalid delay value: {r['sleep_var'].get()}")
                return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop_action(self):
        self.running = False

    def _run_loop(self):
        # Loop indefinitely until stopped
        while self.running:
            for r in self.rows:
                if not self.running:
                    break
                key = r['key_var'].get().strip()
                delay = float(r['sleep_var'].get())
                self._perform_action(key)
                time.sleep(delay)

    def _perform_action(self, key):
        # Determine if it's a mouse action or a key press
        k = key.lower()
        if k == "click":
            pydirectinput.click()
        elif k == "rclick":
            pydirectinput.rightClick()
        elif k == "mclick":
            pydirectinput.middleClick()
        else:
            pydirectinput.press(key)

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    root = tb.Window(themename="cosmo")
    app = KeyClickerApp(root)
    root.mainloop()
