import threading
import time
import os
import sys
import json
import pydirectinput
import keyboard  # for hotkey start/stop
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import Toplevel, PhotoImage, filedialog
from tkinter import Frame, LEFT, BOTH, YES, X, Y, RIGHT, TOP, BOTTOM, HORIZONTAL, VERTICAL
import pyautogui  # For pixel color detection
from PIL import ImageGrab  # For screen capture
from pynput import mouse  # For mouse event listening

# Resource Path Function
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Configuration Constants
TOOL_NAME = "SimpleKeyClicker"
ICON_PATH = resource_path("logo.ico")
LOGO_PATH = resource_path("logo.png")
EMERGENCY_STOP_KEY = 'esc'

# Set of known single keys for pydirectinput.press/keyDown/keyUp
# Based on POSSIBLE_KEYS and pydirectinput capabilities
# All lowercase for easy checking
SINGLE_ACTION_KEYS = {
    # Basic
    'tab', 'space', 'enter', 'esc', 'backspace', 'delete', 'insert',
    # Arrows
    'up', 'down', 'left', 'right',
    # Navigation
    'home', 'end', 'pageup', 'pagedown',
    # Locks
    'capslock', 'numlock', 'scrolllock',
    # Special
    'printscreen', 'prntscrn', 'prtsc', 'pause',
    # Function Keys (Common range)
    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
    'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24',
    # Modifiers
    'shift', 'ctrl', 'alt', 'win', 'cmd', # Note: Holding these often needs keyDown/Up
    # Mouse (handled separately, but good to list if needed elsewhere)
    # 'click', 'rclick', 'mclick'
}

POSSIBLE_KEYS = """
--- Possible Keys/Mouse Actions ---

Use the 'Key/Button' field for the desired action.
Use 'Hold Time' (seconds) to hold down a key or mouse button.
Use 'Delay' (seconds) for the pause *after* the action completes.
Use the 'Capture' button to easily get coordinates (x,y) and color (r,g,b).

Basic Keyboard Input:
- Letters: a, b, c, ... z (case-insensitive for keys, sensitive for typing)
- Digits: 0, 1, 2, ... 9
- Symbols: !, @, #, $, %, ^, &, *, (, ), -, _, =, +, [, ], {, }, \\, |, ;, :, ', ", ,, <, ., >, /, ?
  (Note: For typing symbols, ensure the correct modifier like SHIFT is not active unless intended)
- Special Keys:
    tab, space, enter, esc (also emergency stop key), backspace, delete, insert
    up, down, left, right (arrow keys)
    home, end, pageup, pagedown
    capslock, numlock, scrolllock
    printscreen (or prntscrn, prtsc), pause
- Function Keys: f1, f2, f3, ... f12 (up to f24 may work depending on system)
- Modifier Keys: shift, ctrl, alt, win (or cmd on Mac)
  (Use 'Hold Time' > 0 to hold these keys down)

Typing Strings:
- Any text not recognized as a special key or command above will be typed out character by character.
  Example: Hello World!

Basic Mouse Input (at current cursor position):
- click   (Left mouse button click)
- rclick  (Right mouse button click)
- mclick  (Middle mouse button click)
  (Use 'Hold Time' > 0 to hold the mouse button down)

Advanced Mouse Input (at specific coordinates):
- moveto(x,y)       - Move mouse cursor to screen coordinates (X, Y)
- click(x,y)        - Move to (X, Y) and perform a left click
- rclick(x,y)       - Move to (X, Y) and perform a right click
- mclick(x,y)       - Move to (X, Y) and perform a middle click
  (Use 'Hold Time' > 0 with click(x,y), rclick(x,y), mclick(x,y) to hold the click at the specified position)

Color Detection:
- waitcolor(r,g,b,x,y) - Pause execution until the color (R, G, B) is detected
                         at screen coordinates (X, Y).
                       - If the color is not found within the timeout (~30s),
                         an error message appears, and automation stops after 'OK'.

--- Notes ---
- Safe Mode: Blocks potentially disruptive keys (Alt, Ctrl, Shift, Win, F4, Delete, Tab) and commands (waitcolor).
- Coordinates/Color: Use the 'Capture' button next to the Key/Button field to easily get mouse position and pixel color for commands.
"""

DANGEROUS_KEYS = {'alt', 'ctrl', 'shift', 'win', 'cmd', 'f4', 'delete', 'tab'}
SYSTEM_COMMANDS = {'type(', 'paste(', 'waitcolor', 'ifcolor'}
DEFAULT_MOUSE_SPEED = 0.5
COLOR_MATCH_TOLERANCE = 10
WAITCOLOR_TIMEOUT = 30 # Default timeout for waitcolor in seconds

class KeyClickerApp:
    """Main application class for SimpleKeyClicker."""

    def __init__(self, root):
        self.root = root
        self.root.title(TOOL_NAME)
        # Start with a slightly taller default to accommodate menu better if needed
        self.root.geometry("820x370") # Increased default height slightly
        self.root.resizable(True, True)
        self.root.minsize(800, 350) # Keep min width
        try:
            self.root.iconbitmap(ICON_PATH)
        except:
            pass

        self.safe_mode = True
        self.running = False
        self.rows = []
        self.thread = None
        # Event for handling modal error dialogs from background thread
        self.error_acknowledged = threading.Event()
        self.current_theme = "flatly" # Initial theme
        self.safe_mode_var = tb.BooleanVar(value=self.safe_mode) # Define here for menu access

        # Repetition control variables
        self.run_mode_var = tk.StringVar(value="infinite") # 'infinite' or 'limited'
        self.repetitions_var = tk.IntVar(value=10) # Default repetition count

        self._setup_style()
        self._create_menu() # Create menu first
        self._create_main_frame()
        self._create_top_frame() # Now contains only logo, start/stop, status
        self._create_bottom_frame()
        self._setup_hotkeys()
        self._update_safe_mode_ui() # Initialize safe mode label based on var
        self._update_repetition_entry_state() # Initialize repetition entry state

    def _setup_style(self):
        """Configure the visual theme."""
        self.style = tb.Style(self.current_theme)  # Use initial theme

    def _create_menu(self):
        """Create the main menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # --- File Menu ---
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Configuration", command=self.save_configuration)
        file_menu.add_command(label="Load Configuration", command=self.load_configuration)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # --- Options Menu ---
        options_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Options", menu=options_menu)
        # Link the checkbutton directly to the variable and a command to update the UI label
        options_menu.add_checkbutton(label="Safe Mode", variable=self.safe_mode_var,
                                      command=self._toggle_safe_mode_from_menu)
        options_menu.add_command(label="Toggle Theme", command=self._toggle_theme)

        # --- Help Menu ---
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Show Keys/Actions Info", command=self.show_info)

    def _create_main_frame(self):
        """Create the main container frame."""
        self.main_frame = tb.Frame(self.root, padding=10)
        self.main_frame.pack(fill=BOTH, expand=YES)

    def _create_top_frame(self):
        """Create the top frame with controls (Logo, Start/Stop, Status)."""
        self.top_frame = tb.Frame(self.main_frame)
        self.top_frame.pack(fill=X, pady=(0,5))

        # Frame for Logo, Start/Stop, Status
        control_frame = tb.Frame(self.top_frame)
        control_frame.pack(fill=X, pady=5)

        try:
            self.logo_image = PhotoImage(file=LOGO_PATH)
            # Keep logo relatively small
            logo_label = tb.Label(control_frame, image=self.logo_image)
            logo_label.image = self.logo_image # Keep reference
            logo_label.pack(side=LEFT, padx=(5, 20))
        except Exception as e:
            print(f"Logo load error: {e}")
            pass # Continue without logo

        # Start/Stop Buttons and Status Label remain prominent
        self.start_button = tb.Button(control_frame, text="Start", padding=(40, 6), bootstyle=PRIMARY, command=self.start_action)
        self.start_button.pack(side=LEFT, padx=5)
        self.stop_button = tb.Button(control_frame, text="Stop", padding=(40, 6), bootstyle=DANGER, command=self.stop_action)
        self.stop_button.pack(side=LEFT, padx=5)

        self.status_label = tb.Label(control_frame, text="Status: Stopped", bootstyle="secondary")
        self.status_label.pack(side=LEFT, padx=10, expand=True, fill=X) # Allow status to expand

        # --- Repetition Controls --- (Moved below Start/Stop)
        repetition_frame = tb.Frame(self.top_frame)
        repetition_frame.pack(fill=X, pady=(5,0))

        tb.Radiobutton(repetition_frame, text="Run Indefinitely", variable=self.run_mode_var, value="infinite",
                       command=self._update_repetition_entry_state).pack(side=LEFT, padx=(5, 10))

        tb.Radiobutton(repetition_frame, text="Run", variable=self.run_mode_var, value="limited",
                       command=self._update_repetition_entry_state).pack(side=LEFT, padx=(0, 2))

        self.repetitions_entry = tb.Entry(repetition_frame, textvariable=self.repetitions_var, width=5)
        self.repetitions_entry.pack(side=LEFT, padx=(0, 2))
        tb.Label(repetition_frame, text="Times").pack(side=LEFT)

        # Frame for Hints (including Safe Mode status)
        hints_frame = tb.Frame(self.top_frame)
        hints_frame.pack(fill=X, pady=(5,0))
        tb.Label(hints_frame, text="Hint: Ctrl+F2 to Start, Ctrl+F3 to Stop, ESC to Stop",
                 font=("Helvetica", 10, "italic")).pack(side=LEFT, padx=5)
        # Safe Mode label is still needed here for visual feedback
        self.safe_mode_label = tb.Label(hints_frame, text="", # Text set by _update_safe_mode_ui
                                        font=("Helvetica", 10, "bold"), foreground="green")
        self.safe_mode_label.pack(side=RIGHT, padx=5)

    def _create_bottom_frame(self):
        """Create the bottom frame with action rows."""
        self.bottom_frame = tb.Frame(self.main_frame)
        self.bottom_frame.pack(fill=BOTH, expand=YES, pady=(10, 0))

        add_row_frame = tb.Frame(self.bottom_frame)
        add_row_frame.pack(fill=X)
        tb.Button(add_row_frame, text="Add Row", bootstyle=SUCCESS, command=self._add_row).pack(side=LEFT, padx=5, pady=5)

        self.canvas = tb.Canvas(self.bottom_frame, highlightthickness=0)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        self.scrollbar = tb.Scrollbar(self.bottom_frame, orient=VERTICAL, command=self.canvas.yview)
        self.scrollbar.pack(side=RIGHT, fill=Y)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.rows_container = tb.Frame(self.canvas)
        self.canvas.create_window((0,0), window=self.rows_container, anchor="nw")
        self.rows_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self._add_row(is_first=True) # Add the initial mandatory row

    def _setup_hotkeys(self):
        """Setup global hotkeys."""
        try:
            keyboard.add_hotkey('ctrl+f2', self.start_action)
            keyboard.add_hotkey('ctrl+f3', self.stop_action)
            keyboard.add_hotkey(EMERGENCY_STOP_KEY, self.emergency_stop)
        except Exception as e:
            print(f"Warning: Could not set up global hotkeys. You might need root/admin privileges. Error: {e}")
            self.show_custom_error("Hotkey Warning", f"Could not set up global hotkeys (Ctrl+F2/F3, ESC).\nTry running as administrator.\nError: {e}")

    def _toggle_safe_mode_from_menu(self):
        """Handles the Safe Mode toggle specifically from the menu checkbutton."""
        # The variable (self.safe_mode_var) is automatically updated by the checkbutton.
        # We just need to update the internal state and the UI label.
        self.safe_mode = self.safe_mode_var.get()
        self._update_safe_mode_ui()

    def _update_safe_mode_ui(self):
         """Update the safe mode status label text and color."""
         is_safe = self.safe_mode_var.get() # Read from the variable
         self.safe_mode_label.config(text="[SAFE MODE ACTIVE]" if is_safe else "[SAFE MODE OFF]",
                                     foreground="green" if is_safe else "red")
         # Ensure internal state matches, although _toggle_safe_mode_from_menu should handle this too
         self.safe_mode = is_safe

    def _update_repetition_entry_state(self):
        """Enable/disable the repetition count entry based on radio button selection."""
        if self.run_mode_var.get() == "limited":
            self.repetitions_entry.config(state=NORMAL)
        else:
            self.repetitions_entry.config(state=DISABLED)

    def emergency_stop(self):
        """Halt automation immediately."""
        if self.running:
            self.running = False
            # Schedule UI update in main thread
            self.root.after(0, self._update_status_after_stop, "Status: Emergency Stop", "danger")
            self.show_custom_error("Emergency Stop", "Automation stopped.\nPress Start to begin again.")

    def _update_status_after_stop(self, text, style):
        """Helper to update status label and clear highlights from main thread."""
        self.status_label.config(text=text, bootstyle=style)
        self._clear_all_highlights()

    def _add_row(self, is_first=False, key="", sleep="0.5", hold="0.0"):
        """Add a new action row."""
        row_frame = tb.Frame(self.rows_container)
        # Packed later in _redraw_rows

        highlight_frame = tb.Frame(row_frame, bootstyle="default")
        highlight_frame.pack(fill=X, padx=2, pady=1) # Reduced pady
        sub_frame = tb.Frame(highlight_frame)
        sub_frame.pack(anchor='center', padx=5, pady=2) # Reduced pady

        key_var = tb.StringVar(value=key)
        sleep_var = tb.StringVar(value=sleep)
        hold_var = tb.StringVar(value=hold)

        status_label = tb.Label(sub_frame, text="", width=3)
        status_label.pack(side=LEFT)

        tb.Label(sub_frame, text="Key/Button:", width=10).pack(side=LEFT) # Reduced width
        key_entry = tb.Entry(sub_frame, textvariable=key_var, width=30) # Reduced width
        key_entry.pack(side=LEFT, padx=5)

        capture_btn = tb.Button(sub_frame, text="Capture", bootstyle=INFO, width=7,
                                command=lambda k=key_var: self._start_capture(k))
        capture_btn.pack(side=LEFT, padx=(0, 5))

        tb.Label(sub_frame, text="Hold(s):", width=7).pack(side=LEFT) # Reduced width
        tb.Entry(sub_frame, textvariable=hold_var, width=6).pack(side=LEFT, padx=(0,5)) # Reduced width
        tb.Label(sub_frame, text="Delay(s):", width=7).pack(side=LEFT) # Reduced width
        tb.Entry(sub_frame, textvariable=sleep_var, width=6).pack(side=LEFT, padx=(0,5)) # Reduced width

        # --- Row Manipulation Buttons ---
        button_width = 3
        up_btn = tb.Button(sub_frame, text="▲", bootstyle=SECONDARY, width=button_width,
                           command=lambda f=row_frame: self._move_row_up(self._find_row_index(f)))
        up_btn.pack(side=LEFT, padx=(5, 1))

        down_btn = tb.Button(sub_frame, text="▼", bootstyle=SECONDARY, width=button_width,
                             command=lambda f=row_frame: self._move_row_down(self._find_row_index(f)))
        down_btn.pack(side=LEFT, padx=1)

        dup_btn = tb.Button(sub_frame, text="❏", bootstyle=INFO, width=button_width, # Use a copy symbol
                            command=lambda f=row_frame: self._duplicate_row(self._find_row_index(f)))
        dup_btn.pack(side=LEFT, padx=1)

        remove_btn = tb.Button(sub_frame, text="X", bootstyle=DANGER, width=button_width,
                               command=lambda f=row_frame: self._remove_row_by_frame(f))
        remove_btn.pack(side=LEFT, padx=(1, 5))

        # Store all parts
        row_data = {
            'frame': row_frame,
            'highlight_frame': highlight_frame,
            'status_label': status_label,
            'key_var': key_var,
            'sleep_var': sleep_var,
            'hold_var': hold_var,
            'up_btn': up_btn,
            'down_btn': down_btn,
            'dup_btn': dup_btn,
            'remove_btn': remove_btn,
            'is_first': is_first # Mark if it's the original first row
        }
        self.rows.append(row_data)
        self._redraw_rows() # Redraw to apply packing and button states

    def _remove_row_by_frame(self, frame):
        """Removes a row using its frame widget."""
        index_to_remove = self._find_row_index(frame)
        if index_to_remove is not None and index_to_remove >= 0:
             # Keep original logic: prevent removing the very first row added
            if self.rows[index_to_remove]['is_first']:
                 self.show_custom_error("Action Denied", "Cannot remove the initial row.")
                 return
             # Or prevent removing the last row if you prefer that logic:
             # if len(self.rows) <= 1:
             #    self.show_custom_error("Action Denied", "Cannot remove the last row.")
             #    return

            self.rows[index_to_remove]['frame'].destroy()
            del self.rows[index_to_remove]
            self._redraw_rows()

    def _find_row_index(self, frame):
        """Find the index of a row by its frame."""
        for i, r in enumerate(self.rows):
            if r['frame'] == frame:
                return i
        return -1 # Should not happen

    def _redraw_rows(self):
        """Redraw all rows in the container and update button states."""
        # Forget all existing frames first
        for r in self.rows_container.winfo_children():
            r.pack_forget()

        # Repack frames in the current order and update buttons
        num_rows = len(self.rows)
        for i, r in enumerate(self.rows):
            r['frame'].pack(fill=X, pady=0) # Repack the frame

            # Update button states based on index
            r['up_btn'].config(state=NORMAL if i > 0 else DISABLED)
            r['down_btn'].config(state=NORMAL if i < num_rows - 1 else DISABLED)
            # Keep original logic: disable remove for the *initial* row
            r['remove_btn'].config(state=DISABLED if r['is_first'] else NORMAL)
            # Alternative: disable remove only for the last remaining row
            # r['remove_btn'].config(state=DISABLED if num_rows <= 1 else NORMAL)

        # Update canvas scroll region after repacking
        self.rows_container.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _move_row_up(self, index):
        """Move the row at the given index up by one position."""
        if index > 0 and not self.running:
            self.rows[index], self.rows[index - 1] = self.rows[index - 1], self.rows[index]
            self._redraw_rows()

    def _move_row_down(self, index):
        """Move the row at the given index down by one position."""
        if index < len(self.rows) - 1 and not self.running:
            self.rows[index], self.rows[index + 1] = self.rows[index + 1], self.rows[index]
            self._redraw_rows()

    def _duplicate_row(self, index):
        """Duplicate the row at the given index and insert it below."""
        if index >= 0 and not self.running:
            original_row = self.rows[index]
            key = original_row['key_var'].get()
            sleep = original_row['sleep_var'].get()
            hold = original_row['hold_var'].get()

            # Create the new row data structure (add_row handles UI creation)
            # Temporarily add it to the end
            self._add_row(is_first=False, key=key, sleep=sleep, hold=hold)

            # Now move the newly added row (currently last) to the correct position
            new_row_data = self.rows.pop() # Remove from end
            self.rows.insert(index + 1, new_row_data) # Insert after original

            self._redraw_rows() # Redraw everything to reflect the new order and UI

    def show_info(self):
        """Show possible keys and actions in a scrollable window."""
        info_win = Toplevel(self.root)
        info_win.title("Info - Possible Keys & Actions")
        info_win.geometry("650x500") # Give it a decent default size
        info_win.minsize(400, 300)
        info_win.transient(self.root) # Keep on top of main window

        try:
            info_win.iconbitmap(ICON_PATH)
        except Exception as e:
            print(f"Info window icon error: {e}") # Print error instead of just pass

        # Main frame for padding
        main_info_frame = tb.Frame(info_win, padding=10)
        main_info_frame.pack(fill=BOTH, expand=YES)

        # Frame to hold Text and Scrollbar
        text_frame = tb.Frame(main_info_frame)
        text_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

        # Scrollbar
        scrollbar = tb.Scrollbar(text_frame, orient=VERTICAL, bootstyle="round") # Use ttkbootstrap scrollbar
        scrollbar.pack(side=RIGHT, fill=Y)

        # Text widget
        info_text = tk.Text(
            text_frame,
            wrap=tk.WORD, # Wrap lines at word boundaries
            yscrollcommand=scrollbar.set,
            padx=10,
            pady=10,
            font=("Helvetica", 11), # Slightly smaller font for better density
            relief=FLAT, # Use ttk style if possible, otherwise flat
            borderwidth=0,
            highlightthickness=0 # Remove internal border
            # background=self.style.colors.get('bg') # Try to match theme background
        )
        # Try to apply theme background color
        try:
             bg_color = self.style.colors.get('bg')
             fg_color = self.style.colors.get('fg')
             info_text.config(background=bg_color, foreground=fg_color)
        except Exception:
             pass # Use default tk colors if theme colors fail

        info_text.pack(side=LEFT, fill=BOTH, expand=YES)

        # Link scrollbar back to text widget
        scrollbar.config(command=info_text.yview)

        # --- Add Formatting Tags ---
        info_text.tag_configure("heading", font=("Helvetica", 13, "bold"), spacing1=10, spacing3=5)
        info_text.tag_configure("subheading", font=("Helvetica", 11, "bold"), spacing1=8, spacing3=3)
        info_text.tag_configure("code", font=("Consolas", 10), background="#f0f0f0", relief=SOLID, borderwidth=1, lmargin1=15, lmargin2=15) # Monospace font, background
        info_text.tag_configure("bullet", lmargin1=10, lmargin2=25) # Indentation for bullet points
        info_text.tag_configure("note", font=("Helvetica", 10, "italic"), foreground="gray", lmargin1=5, lmargin2=5, spacing1=10)

        # Insert the text line by line and apply tags
        info_text.config(state=tk.NORMAL) # Enable editing to insert
        info_text.delete("1.0", tk.END) # Clear previous content if any

        lines = POSSIBLE_KEYS.strip().split('\n')
        for line in lines:
            stripped_line = line.strip()
            indent = len(line) - len(line.lstrip(' '))

            # Apply tags based on content or leading characters
            if stripped_line.startswith("---") and stripped_line.endswith("---"):
                info_text.insert(tk.END, stripped_line + "\n", "heading")
            elif stripped_line.endswith(":") and not stripped_line.startswith(('-', '*', ' ')):
                 info_text.insert(tk.END, stripped_line + "\n", "subheading")
            elif '(' in stripped_line and ')' in stripped_line and stripped_line.startswith('* '):
                 info_text.insert(tk.END, line.lstrip() + "\n", "code")
            elif stripped_line.startswith(('-', '*')):
                info_text.insert(tk.END, line + "\n", "bullet")
            elif stripped_line.startswith("Note:"):
                 info_text.insert(tk.END, line + "\n", "note")
            else:
                # Apply standard indentation if present
                if indent > 0:
                     info_text.insert(tk.END, line + "\n", f"indent{indent}")
                     info_text.tag_configure(f"indent{indent}", lmargin1=indent * 5, lmargin2=indent * 5)
                else:
                     info_text.insert(tk.END, line + "\n") # Insert normal line

        info_text.config(state=tk.DISABLED) # Make read-only again

        # Close button
        close_button = tb.Button(main_info_frame, text="Close", bootstyle=PRIMARY, command=info_win.destroy)
        close_button.pack(pady=(5, 0))

        # Make modal and center
        info_win.grab_set()
        self._center_window(info_win)
        info_win.wait_window() # Wait until this window is closed

    def show_custom_error(self, title, message):
        """Display a modal error dialog and signal acknowledgement."""
        # Ensure this runs in the main thread if called from background
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, self.show_custom_error, title, message)
            return

        self.error_acknowledged.clear() # Clear event before showing dialog

        error_win = Toplevel(self.root)
        error_win.title(title)
        error_win.transient(self.root)
        try:
            error_win.iconbitmap(ICON_PATH)
        except:
            pass
        error_win.grab_set() # Make modal
        error_win.protocol("WM_DELETE_WINDOW", lambda: None) # Prevent closing via 'X'

        frm = tb.Frame(error_win, padding=10)
        frm.pack()
        try:
            logo = PhotoImage(file=LOGO_PATH)
            tb.Label(frm, image=logo).pack()
            error_win.logo = logo  # Prevent garbage collection
        except:
            pass
        tb.Label(frm, text=message, padding=10, justify=LEFT, foreground="red", font=("Helvetica", 12)).pack()

        # Button command now also sets the event
        ok_button = tb.Button(frm, text="OK", bootstyle=PRIMARY,
                              command=lambda: [self.error_acknowledged.set(), error_win.destroy()])
        ok_button.pack(pady=10)
        self._center_window(error_win)
        ok_button.focus_set() # Set focus to OK button

    def _center_window(self, window):
        """Center a window on the main window."""
        window.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()
        win_w = window.winfo_width()
        win_h = window.winfo_height()
        x = main_x + (main_w // 2) - (win_w // 2)
        y = main_y + (main_h // 2) - (win_h // 2)
        # Ensure it's on screen if main window is partially off-screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        if x + win_w > screen_w: x = screen_w - win_w
        if y + win_h > screen_h: y = screen_h - win_h
        if x < 0: x = 0
        if y < 0: y = 0
        window.geometry(f"+{x}+{y}")

    def start_action(self):
        """Start the automation sequence."""
        if self.running:
            return
        if not self.rows:
             self.show_custom_error("Error", "Add at least one action row.")
             return

        # Validate action rows
        for i, r in enumerate(self.rows):
            if not r['key_var'].get().strip():
                self.show_custom_error("Error", f"Row {i+1}: Please specify a key/button.")
                return
            try:
                float(r['sleep_var'].get())
                float(r['hold_var'].get())
            except ValueError:
                self.show_custom_error("Error", f"Row {i+1}: Invalid delay or hold time value.")
                return

        # Validate repetition count if mode is limited
        if self.run_mode_var.get() == "limited":
            try:
                reps = self.repetitions_var.get()
                if reps <= 0:
                    raise ValueError("Repetitions must be positive.")
            except (tk.TclError, ValueError) as e:
                self.show_custom_error("Error", f"Invalid repetition count: Must be a positive whole number.\n({e})")
                return

        self.running = True
        # Initial status update before loop starts
        self.status_label.config(text="Status: Running", bootstyle="success")

        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop_action(self):
        """Stop the automation sequence."""
        if not self.running: # Prevent multiple stops if called rapidly
             return
        self.running = False
        # Schedule UI update in main thread
        if threading.current_thread() == threading.main_thread():
            self._update_status_after_stop("Status: Stopped", "secondary")
        else:
            # If called from background thread (e.g., after waitcolor error)
            self.root.after(0, self._update_status_after_stop, "Status: Stopped", "secondary")

    def _run_loop(self):
        """Main automation loop with repetition control."""
        # Capture settings at the start of the run
        run_mode = self.run_mode_var.get()
        repetitions_to_run = 0
        if run_mode == "limited":
            try:
                repetitions_to_run = self.repetitions_var.get()
                if repetitions_to_run <= 0: # Double check, though start_action should catch this
                    raise ValueError("Repetitions must be positive.")
            except (tk.TclError, ValueError):
                 # Should not happen if start_action validation is correct, but handle defensively
                 self.root.after(0, self.show_custom_error, "Internal Error", "Invalid repetition count during run.")
                 self.root.after(0, self.stop_action) # Stop immediately
                 return

        try:
            loop_count = 0
            if run_mode == "limited":
                # --- Loop X Times ---
                for i in range(repetitions_to_run):
                    if not self.running: break # Check before starting iteration
                    loop_count = i + 1
                    status_text = f"Status: Running ({loop_count}/{repetitions_to_run})"
                    # Schedule status update in main thread
                    self.root.after(0, lambda s=status_text: self.status_label.config(text=s, bootstyle="success"))

                    # --- Inner loop for one sequence execution ---
                    for j, r in enumerate(self.rows):
                        if not self.running: break # Check before starting action
                        self.root.after(0, self._update_row_highlight, j) # Highlight row

                        key = r['key_var'].get().strip()
                        delay_str = r['sleep_var'].get()
                        hold_str = r['hold_var'].get()
                        try:
                            delay = float(delay_str)
                            hold_time = float(hold_str)
                        except ValueError:
                            # Should be caught by start_action, but handle defensively
                            err_msg = f"Invalid number in Row {j+1} ('{delay_str}' or '{hold_str}'). Stopping."
                            self.root.after(0, self.show_custom_error, "Runtime Error", err_msg)
                            self.running = False
                            break # Break inner sequence loop

                        self.root.after(0, lambda row=r: row['status_label'].config(text="►"))
                        time.sleep(0.01) # Allow GUI update

                        action_success = self._perform_action(key, hold_time)

                        if not action_success or not self.running:
                            # _perform_action handles its own errors/stops
                            # If it returned False, it means we should stop.
                            self.running = False # Ensure flag is set if action failed
                            break # Exit inner sequence loop

                        self.root.after(0, lambda row=r: row['status_label'].config(text="✓"))
                        time.sleep(delay)
                        self.root.after(0, lambda row=r: row['status_label'].config(text=""))
                        self.root.after(0, lambda row=r: row['highlight_frame'].configure(bootstyle="default"))
                    # --- End Inner Sequence Loop ---

                    # Check if inner loop was broken by stop/failure before next repetition
                    if not self.running: break # Exit outer repetition loop

            else:
                # --- Loop Indefinitely ---
                while self.running:
                    loop_count += 1
                    status_text = f"Status: Running (Loop {loop_count})"
                    self.root.after(0, lambda s=status_text: self.status_label.config(text=s, bootstyle="success"))

                    # --- Inner loop for one sequence execution ---
                    for j, r in enumerate(self.rows):
                        if not self.running: break # Check before starting action
                        self.root.after(0, self._update_row_highlight, j)

                        key = r['key_var'].get().strip()
                        delay_str = r['sleep_var'].get()
                        hold_str = r['hold_var'].get()
                        try:
                            delay = float(delay_str)
                            hold_time = float(hold_str)
                        except ValueError:
                            err_msg = f"Invalid number in Row {j+1} ('{delay_str}' or '{hold_str}'). Stopping."
                            self.root.after(0, self.show_custom_error, "Runtime Error", err_msg)
                            self.running = False
                            break

                        self.root.after(0, lambda row=r: row['status_label'].config(text="►"))
                        time.sleep(0.01)

                        action_success = self._perform_action(key, hold_time)

                        if not action_success or not self.running:
                            self.running = False
                            break

                        self.root.after(0, lambda row=r: row['status_label'].config(text="✓"))
                        time.sleep(delay)
                        self.root.after(0, lambda row=r: row['status_label'].config(text=""))
                        self.root.after(0, lambda row=r: row['highlight_frame'].configure(bootstyle="default"))
                     # --- End Inner Sequence Loop ---

                    # Check if inner loop was broken before looping again (infinite mode)
                    if not self.running: break # Exit outer indefinite loop

        finally:
            # Ensure highlights/statuses are cleared and status is set to stopped
            # Use root.after to ensure these run on the main thread
            self.root.after(0, self._clear_all_highlights)
            # Only set status to Stopped if it wasn't an Emergency Stop
            current_status = self.status_label.cget("text")
            if self.running or "Emergency Stop" not in current_status:
                 # Check self.running again *after* the loop finishes
                 # If it finished naturally (limited loops) or was stopped cleanly
                 final_status = "Status: Completed" if run_mode == "limited" and loop_count == repetitions_to_run and self.running else "Status: Stopped"
                 self.root.after(0, self._update_status_after_stop, final_status, "secondary")

            # Explicitly set running to False if loop completes naturally (for limited runs)
            if run_mode == "limited" and loop_count == repetitions_to_run:
                self.running = False

    def _update_row_highlight(self, current_index):
        """Highlight the current row (runs in main thread)."""
        if not self.running: return # Don't update if stopped
        for i, row in enumerate(self.rows):
            style = "info" if i == current_index else "default"
            # Check if widget still exists (might be destroyed during stop)
            try:
                if row['highlight_frame'].winfo_exists():
                    row['highlight_frame'].configure(bootstyle=style)
            except Exception:
                pass # Ignore if widget is gone

    def _clear_all_highlights(self):
        """Clear all row highlights and statuses (runs in main thread)."""
        for row in self.rows:
             try:
                if row['highlight_frame'].winfo_exists():
                    row['highlight_frame'].configure(bootstyle="default")
                if row['status_label'].winfo_exists():
                    row['status_label'].config(text="")
             except Exception:
                 pass # Ignore if widgets are gone

    def _perform_action(self, key, hold_time):
        """Execute a key/mouse action. Returns True on success, False on handled failure (like waitcolor timeout)."""
        if not self.running: return False # Check if stopped during delay

        # Check safe mode first
        # Treat typing strings as generally safe, but block specific dangerous single keys/commands
        is_dangerous_single_key = key.lower() in DANGEROUS_KEYS
        is_system_command = any(cmd in key.lower() for cmd in SYSTEM_COMMANDS)

        if self.safe_mode and (is_dangerous_single_key or is_system_command):
            # Use the error mechanism that waits
            error_message = f"Action '{key}' is blocked in safe mode."
            self.root.after(0, self.show_custom_error, "Safe Mode Block", error_message)
            self.error_acknowledged.wait() # Wait for user to click OK
            if self.running: # Check if user pressed ESC while dialog was up
                self.root.after(0, self.stop_action)
            return False

        # Handle special commands like click(x,y), waitcolor(...), etc.
        if '(' in key and ')' in key:
            try:
                cmd = key.split('(')[0].lower()
                args_str = key[key.index('(')+1:key.rindex(')')] # Use rindex for safety
                args = [a.strip() for a in args_str.split(',')]

                if cmd in {'click', 'rclick', 'mclick'}:
                    if len(args) == 2:
                        x, y = map(int, args)
                        pydirectinput.moveTo(x, y) # Move first
                        time.sleep(0.05) # Small pause after move
                        button_map = {'click': 'left', 'rclick': 'right', 'mclick': 'middle'}
                        button = button_map[cmd]
                        if hold_time > 0:
                            pydirectinput.mouseDown(button=button)
                            time.sleep(hold_time)
                            pydirectinput.mouseUp(button=button)
                        else:
                            pydirectinput.click(button=button) # Use click with button arg
                    else:
                         raise ValueError("Click commands require 2 arguments (x,y)")
                    return True # Action performed

                elif cmd == 'moveto':
                    if len(args) == 2:
                        x, y = map(int, args)
                        # Use pydirectinput for consistency if preferred, or pyautogui
                        # pydirectinput.moveTo(x, y)
                        pyautogui.moveTo(x, y, duration=DEFAULT_MOUSE_SPEED)
                    else:
                        raise ValueError("moveto requires 2 arguments (x,y)")
                    return True # Action performed

                elif cmd == 'waitcolor':
                    if len(args) == 5:
                        r_val, g_val, b_val, x, y = map(int, args)
                        print(f"[DEBUG] Performing waitcolor({r_val},{g_val},{b_val},{x},{y}) timeout={WAITCOLOR_TIMEOUT}s") # DEBUG
                        found = self._wait_for_color(r_val, g_val, b_val, x, y, timeout=WAITCOLOR_TIMEOUT)
                        print(f"[DEBUG] _wait_for_color returned: {found}, self.running: {self.running}") # DEBUG

                        if not found and self.running:
                            # Color not found within timeout, show error and pause
                            print("[DEBUG] Condition 'not found and self.running' is TRUE. Showing 'Wait Color Failed' error.") # DEBUG
                            error_message = f"Color ({r_val},{g_val},{b_val}) not found at ({x},{y}) within {WAITCOLOR_TIMEOUT}s.\\nAutomation stopped."
                            # Schedule error in main thread, then wait here in background thread
                            self.root.after(0, self.show_custom_error, "Wait Color Failed", error_message)
                            print("[DEBUG] Waiting for error acknowledgement...") # DEBUG
                            self.error_acknowledged.wait() # PAUSE here
                            print("[DEBUG] Error acknowledged.") # DEBUG
                            # After error is acknowledged, ensure we stop
                            if self.running: # Check again if ESC wasn't pressed
                                print("[DEBUG] Still running after error ack, stopping.") # DEBUG
                                self.root.after(0, self.stop_action) # Stop from main thread
                            else:
                                print("[DEBUG] Not running after error ack.") # DEBUG
                            return False # Indicate failure/stop
                        elif not self.running:
                            print("[DEBUG] Condition 'not self.running' is TRUE after waitcolor check.") # DEBUG
                            return False # Stopped during wait
                        else: # found is True
                            print("[DEBUG] Condition 'found' is TRUE. Continuing.") # DEBUG
                            return True # Color found, continue
                    else:
                         raise ValueError("waitcolor requires 5 arguments (r,g,b,x,y)")
                # Add other commands like 'type(' or 'paste(' here if needed
                # Example:
                # elif cmd == 'type':
                #     text_to_type = args_str # Treat everything inside parentheses as the text
                #     pydirectinput.typewrite(text_to_type, interval=0.01)
                #     return True

            except Exception as e:
                 # Handle parsing errors or other issues with commands
                 error_message = f"Error processing action '{key}':\\n{type(e).__name__}: {e}\\nAutomation stopped."
                 self.root.after(0, self.show_custom_error, "Action Error", error_message)
                 self.error_acknowledged.wait()
                 if self.running:
                     self.root.after(0, self.stop_action)
                 return False # Indicate failure

        # Handle basic keys/clicks if not a special command
        else:
            k = key.lower()
            try:
                if k == "click":
                    if hold_time > 0:
                        pydirectinput.mouseDown()
                        time.sleep(hold_time)
                        pydirectinput.mouseUp()
                    else:
                        pydirectinput.click()
                elif k == "rclick":
                    if hold_time > 0:
                        pydirectinput.mouseDown(button='right')
                        time.sleep(hold_time)
                        pydirectinput.mouseUp(button='right')
                    else:
                        pydirectinput.rightClick()
                elif k == "mclick":
                    if hold_time > 0:
                        pydirectinput.mouseDown(button='middle')
                        time.sleep(hold_time)
                        pydirectinput.mouseUp(button='middle')
                    else:
                        pydirectinput.middleClick()
                # Check if it's a known single action key (lowercase check)
                elif k in SINGLE_ACTION_KEYS:
                    # Standard single key press/hold
                    # Use original 'key' for press/down/up to handle potential case sensitivity if needed by pdi for some keys?
                    # Although for SINGLE_ACTION_KEYS, case usually doesn't matter.
                    if hold_time > 0:
                        pydirectinput.keyDown(key)
                        time.sleep(hold_time)
                        pydirectinput.keyUp(key)
                    else:
                        pydirectinput.press(key)
                else:
                    # Assume it's a string or single character to typewrite
                    # Use pyautogui.write for better case handling reliability
                    pyautogui.write(key, interval=0.05) # Use pyautogui for typing

            except Exception as e:
                # Handle errors during basic input simulation
                error_message = f"Error performing action '{key}':\\n{type(e).__name__}: {e}\\nAutomation stopped."
                self.root.after(0, self.show_custom_error, "Action Error", error_message)
                self.error_acknowledged.wait()
                if self.running:
                    self.root.after(0, self.stop_action)
                return False # Indicate failure

        return True # Action performed successfully

    def _wait_for_color(self, r_val, g_val, b_val, x, y, timeout=30):
        """Wait for a color at a position. Returns True if found, False if timeout/stopped."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.running: # Check if stopped externally
                return False
            if self._check_pixel_color(r_val, g_val, b_val, x, y):
                return True # Color found
            time.sleep(0.1) # Check every 100ms

        return False # Timeout reached

    def _check_pixel_color(self, r_val, g_val, b_val, x, y):
        """Check if a pixel matches a color within tolerance."""
        try:
            # Ensure coordinates are integers
            x, y = int(x), int(y)
            # Grab a 1x1 pixel area
            pixel = ImageGrab.grab(bbox=(x, y, x+1, y+1)).getpixel((0, 0))
            # Check RGB values within tolerance
            return (abs(pixel[0] - r_val) <= COLOR_MATCH_TOLERANCE and
                    abs(pixel[1] - g_val) <= COLOR_MATCH_TOLERANCE and
                    abs(pixel[2] - b_val) <= COLOR_MATCH_TOLERANCE)
        except Exception as e:
            # Silently ignore pixel grab errors for now, or log them
            # print(f"Warning: Could not check pixel at ({x},{y}). Error: {e}")
            return False

    def save_configuration(self):
        """Save configuration to a JSON file."""
        if not self.rows:
            self.show_custom_error("Error", "No configuration to save.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                 filetypes=[("JSON files", "*.json")],
                                                 title="Save Configuration")
        if not file_path:
            return
        try:
            # Save the current state including row order and repetition settings
            config = {
                'run_mode': self.run_mode_var.get(),
                'repetitions': self.repetitions_var.get(),
                'rows': [{'key': r['key_var'].get(),
                           'sleep': r['sleep_var'].get(),
                           'hold': r['hold_var'].get()}
                          for r in self.rows]
            }
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=4)
            self.show_success("Configuration saved!")
        except Exception as e:
            self.show_custom_error("Save Error", f"Failed to save configuration:\n{str(e)}")

    def load_configuration(self):
        """Load configuration from a JSON file."""
        if self.running:
            self.show_custom_error("Error", "Stop the current action before loading.")
            return

        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")],
                                               title="Load Configuration")
        if not file_path:
            return
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)

            if 'rows' not in config or not isinstance(config['rows'], list):
                 raise ValueError("Invalid configuration file format.")

            # Load repetition settings (optional, provide defaults)
            loaded_run_mode = config.get('run_mode', 'infinite')
            loaded_repetitions = config.get('repetitions', 10)
            self.run_mode_var.set(loaded_run_mode)
            try:
                self.repetitions_var.set(int(loaded_repetitions))
            except (ValueError, TypeError):
                self.repetitions_var.set(10) # Default if invalid
            self._update_repetition_entry_state() # Update entry enable/disable state

            # --- Clear existing rows before loading ---
            # Destroy widgets and clear list
            for r in reversed(self.rows): # Iterate backwards for safe removal
                r['frame'].destroy()
            self.rows.clear()
            # ---

            # Add rows from the loaded configuration
            if not config['rows']: # Handle empty config file
                 self._add_row(is_first=True) # Add one default empty row
            else:
                for i, row_config in enumerate(config['rows']):
                    self._add_row(is_first=(i == 0), # Mark the first loaded row as 'is_first'
                                  key=row_config.get('key', ''),
                                  sleep=row_config.get('sleep', '0.5'),
                                  hold=row_config.get('hold', '0.0'))

            self._redraw_rows() # Ensure UI is correctly drawn after loading
            self.show_success("Configuration loaded!")

        except Exception as e:
            # Clean up partially loaded state if error occurs
            for r in reversed(self.rows):
                 r['frame'].destroy()
            self.rows.clear()
            self._add_row(is_first=True) # Add back the default row
            self._redraw_rows()
            self.show_custom_error("Load Error", f"Failed to load configuration:\n{str(e)}")

    def show_success(self, message):
        """Display a success message."""
        success_win = Toplevel(self.root)
        success_win.title("Success")
        success_win.transient(self.root)
        try:
            success_win.iconbitmap(ICON_PATH)
        except:
            pass
        success_win.grab_set()
        frm = tb.Frame(success_win, padding=10)
        frm.pack()
        try:
            logo = PhotoImage(file=LOGO_PATH)
            tb.Label(frm, image=logo).pack()
            success_win.logo = logo
        except:
            pass
        tb.Label(frm, text=message, padding=10, justify=LEFT, foreground="green", font=("Helvetica", 12)).pack()
        ok_button = tb.Button(frm, text="OK", bootstyle=SUCCESS, command=success_win.destroy)
        ok_button.pack(pady=10)
        self._center_window(success_win)
        ok_button.focus_set()

    def _start_capture(self, key_var):
        """Start capturing mouse coordinates and color."""
        if self.running:
            self.show_custom_error("Error", "Cannot capture while running.")
            return
        try:
            self.root.attributes('-alpha', 0.5) # Make window semi-transparent
            self.root.lower() # Lower window to click behind it
            # Maybe add a small delay or visual cue
            capture_info_win = Toplevel(self.root)
            capture_info_win.overrideredirect(True) # No window decorations
            capture_info_win.attributes('-topmost', True)
            tb.Label(capture_info_win, text="Click anywhere to capture...", padding=10, bootstyle=INVERSE).pack()
            self._center_window(capture_info_win)
            capture_info_win.update()

        except Exception: # Handle specific TclError if needed
            print("Info: Could not make window transparent/lower for capture.")
            self.root.iconify() # Fallback to iconifying

        data = self._capture_data() # This blocks until click

        # Restore main window
        try:
             capture_info_win.destroy()
             self.root.attributes('-alpha', 1.0)
             self.root.lift()
             self.root.focus_force()
        except Exception:
            self.root.deiconify() # Fallback from iconify

        if data:
            self._show_capture_options(data, key_var)
        else:
            # Optional: message if capture failed/cancelled
            # self.show_custom_error("Capture Failed", "Could not get mouse coordinates.")
            pass

    def _capture_data(self):
        """Capture mouse coordinates and color using pynput."""
        data = {'x': None, 'y': None, 'color': None}
        listener = None # Define listener variable

        def on_click(x, y, button, pressed):
            nonlocal listener # Allow modification of outer scope variable
            if button == mouse.Button.left and pressed:
                data['x'] = int(x) # Ensure integer coordinates
                data['y'] = int(y)
                try:
                    # Use pyautogui to get pixel color AFTER click coordinates are known
                    data['color'] = pyautogui.pixel(data['x'], data['y'])
                except Exception as e:
                    print(f"Warning: Could not get pixel color at ({data['x']},{data['y']}). Error: {e}")
                    data['color'] = (0, 0, 0) # Default color on error
                # Stop the listener
                if listener:
                    listener.stop()
                return False # Stop processing further events

        # Create and start the listener
        listener = mouse.Listener(on_click=on_click)
        listener.start()
        listener.join() # Wait here until listener is stopped (by on_click)

        return data if data['x'] is not None else None

    def _show_capture_options(self, data, key_var):
        """Show options for captured data."""
        options_win = Toplevel(self.root)
        options_win.title("Capture Options")
        options_win.transient(self.root)
        try:
            options_win.iconbitmap(ICON_PATH)
        except:
            pass
        options_win.grab_set()
        frm = tb.Frame(options_win, padding=10)
        frm.pack()

        info_frame = tb.Frame(frm)
        info_frame.pack(fill=X, pady=(0, 10))

        try:
            # Display color swatch
            color_hex = f"#{data['color'][0]:02x}{data['color'][1]:02x}{data['color'][2]:02x}"
            tb.Label(info_frame, text=" ", background=color_hex, width=3).pack(side=LEFT, padx=(0, 5))
        except Exception: # Handle potential color format errors
             tb.Label(info_frame, text="?", width=3).pack(side=LEFT, padx=(0, 5))

        tb.Label(info_frame, text=f"At ({data['x']}, {data['y']})  Color: {data['color']}",
                 font=("Helvetica", 11)).pack(side=LEFT)

        def insert_command(cmd):
            key_var.set(cmd)
            options_win.destroy()

        # Use lambda to capture current data values correctly
        x, y = data['x'], data['y']
        r_val, g_val, b_val = data['color']

        button_frame = tb.Frame(frm)
        button_frame.pack(fill=X)

        tb.Button(button_frame, text="Insert Click at Position", bootstyle=PRIMARY,
                  command=lambda x=x, y=y: insert_command(f"click({x},{y})")).pack(fill=X, pady=2)
        tb.Button(button_frame, text="Insert Move To Position", bootstyle=PRIMARY,
                  command=lambda x=x, y=y: insert_command(f"moveto({x},{y})")).pack(fill=X, pady=2)
        tb.Button(button_frame, text="Insert Wait for Color", bootstyle=PRIMARY,
                  command=lambda r=r_val, g=g_val, b=b_val, x=x, y=y: insert_command(f"waitcolor({r},{g},{b},{x},{y})")).pack(fill=X, pady=2)

        copy_frame = tb.Frame(frm)
        copy_frame.pack(fill=X, pady=(10, 2))

        tb.Button(copy_frame, text="Copy Coordinates", bootstyle=INFO,
                  command=lambda x=x, y=y: [self.root.clipboard_clear(), self.root.clipboard_append(f"{x},{y}"), options_win.destroy()]).pack(side=LEFT, expand=True, padx=2)
        tb.Button(copy_frame, text="Copy Color (RGB)", bootstyle=INFO,
                  command=lambda r=r_val, g=g_val, b=b_val: [self.root.clipboard_clear(), self.root.clipboard_append(f"{r},{g},{b}"), options_win.destroy()]).pack(side=LEFT, expand=True, padx=2)

        tb.Button(frm, text="Cancel", bootstyle=SECONDARY, command=options_win.destroy).pack(fill=X, pady=(10, 0))

        self._center_window(options_win)

    def _toggle_theme(self):
        """Toggle between light ('flatly') and dark ('darkly') themes."""
        if self.current_theme == "flatly":
            new_theme = "darkly"
        else:
            new_theme = "flatly"

        try:
            self.style.theme_use(new_theme)
            self.current_theme = new_theme
            # No button to update anymore
            # Optionally: Force redraw of elements if some don't update automatically
            # self.root.update_idletasks() # Maybe needed for some widgets
        except Exception as e:
            print(f"Error changing theme: {e}")
            self.show_custom_error("Theme Error", f"Failed to switch theme to '{new_theme}'.\\n{e}")


if __name__ == "__main__":
    # Handle potential DPI scaling issues on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except ImportError: # Not on Windows or ctypes not available
        pass
    except AttributeError: # Older Windows version
         try:
            windll.user32.SetProcessDPIAware()
         except Exception:
            pass

    root = tb.Window()
    app = KeyClickerApp(root)
    root.mainloop()