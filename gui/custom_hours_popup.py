import tkinter as tk
from tkinter import ttk, messagebox


class CustomHoursPopup:
    def __init__(self, parent, is_dark_mode, initial_hours=1, callback=None):
        self.parent = parent
        self.callback = callback

        # Determine colors based on theme
        if is_dark_mode:
            self.bg = "#36393f"
            self.fg = "#dcddde"
            self.accent = "#5865f2"
        else:
            self.bg = "#f4f6f8"
            self.fg = "black"
            self.accent = "#0078d7"

        self.popup = tk.Toplevel(self.parent)
        self.popup.title("Custom Hours Filter")
        self.popup.geometry("250x200")
        self.popup.resizable(False, False)
        self.popup.configure(bg=self.bg)
        self.popup.grab_set()

        self.popup.protocol("WM_DELETE_WINDOW", self._close)
        self.popup.bind("<Escape>", lambda e: self._close())
        self.popup.focus_force()

        # Style
        self.style = ttk.Style(self.popup)
        self.style.configure("CustomPopup.TLabel", background=self.bg, foreground=self.fg)
        self.style.configure("CustomPopup.TEntry", fieldbackground=self.bg, foreground=self.fg, insertcolor=self.fg)
        self.style.configure("CustomPopup.TButton", background=self.bg, foreground=self.fg)
        self.style.map(
            "CustomPopup.TButton",
            background=[("active", self.accent)],
            foreground=[("active", "white")]
        )

        # Container frame
        frame = tk.Frame(self.popup, bg=self.bg)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Label
        lbl = ttk.Label(frame, text="Enter hours:", style="CustomPopup.TLabel")
        lbl.pack(pady=(10,5))

        # Entry
        self.entry_var = tk.StringVar(value=str(initial_hours))
        entry = ttk.Entry(frame, textvariable=self.entry_var, width=10, style="CustomPopup.TEntry")
        entry.pack(pady=5)
        entry.focus()
        entry.bind("<Return>", lambda e: self._apply())

        # Apply Button
        btn = ttk.Button(frame, text="Apply", style="CustomPopup.TButton", command=self._apply)
        btn.pack(pady=10)

        # Center popup
        self.popup.update_idletasks()
        w, h = self.popup.winfo_width(), self.popup.winfo_height()
        x = (self.popup.winfo_screenwidth() // 2) - (w // 2)
        y = (self.popup.winfo_screenheight() // 2) - (h // 2)
        self.popup.geometry(f"{w}x{h}+{x}+{y}")

    def _apply(self):
        try:
            hours = float(self.entry_var.get())
            if self.callback:
                self.callback(hours)
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number.")
            return
        self._close()

    def _close(self):
        self.popup.grab_release()
        self.popup.destroy()