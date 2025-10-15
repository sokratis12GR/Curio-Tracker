from customtkinter import *


class CustomHoursPopup:
    def __init__(self, parent, initial_hours=1, callback=None):
        self.parent = parent
        self.callback = callback

        self.popup = CTkToplevel(self.parent)
        self.popup.title("Custom Hours Filter")
        self.popup.geometry("250x200")
        self.popup.resizable(False, False)
        self.popup.grab_set()

        self.popup.protocol("WM_DELETE_WINDOW", self._close)
        self.popup.bind("<Escape>", lambda e: self._close())
        self.popup.focus_force()

        # Container frame
        frame = CTkFrame(self.popup)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Label
        lbl = CTkLabel(frame, text="Enter hours:")
        lbl.pack(pady=(10, 5))

        # Entry
        self.entry_var = StringVar(value=str(initial_hours))
        entry = CTkEntry(frame, textvariable=self.entry_var, width=200)
        entry.pack(pady=5)
        entry.focus()
        entry.bind("<Return>", lambda e: self._apply())

        # Apply Button
        btn = CTkButton(frame, text="Apply", command=self._apply)
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
            CTkMessagePopup(self.popup, title="Invalid Input", message="Please enter a valid number.")
            return
        self._close()

    def _close(self):
        self.popup.grab_release()
        self.popup.destroy()


class CTkMessagePopup:
    def __init__(self, parent, title="Error", message=""):
        self.popup = CTkToplevel(parent)
        self.popup.title(title)
        self.popup.geometry("300x120")
        self.popup.resizable(False, False)
        self.popup.grab_set()
        self.popup.focus_force()
        self.popup.protocol("WM_DELETE_WINDOW", self.popup.destroy)
        self.popup.bind("<Escape>", lambda e: self.popup.destroy())

        # Frame
        frame = CTkFrame(self.popup, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Message label
        CTkLabel(frame, text=message, wraplength=260).pack(pady=(0, 10))

        # Close button
        CTkButton(frame, text="OK", command=self.popup.destroy).pack()

        # Center popup
        self.popup.update_idletasks()
        w, h = self.popup.winfo_width(), self.popup.winfo_height()
        x = (self.popup.winfo_screenwidth() // 2) - (w // 2)
        y = (self.popup.winfo_screenheight() // 2) - (h // 2)
        self.popup.geometry(f"{w}x{h}+{x}+{y}")
        parent.wait_window(self.popup)
