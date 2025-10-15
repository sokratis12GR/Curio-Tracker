import customtkinter as ctk


class CTkMessageBox:
    def __init__(self, parent=None, min_size=(250, 20), max_size=(300, 100)):
        self.parent = parent
        self.min_size = min_size
        self.max_size = max_size

    def _show(self, title, message, type="info"):
        popup = ctk.CTkToplevel(self.parent)
        popup.title(title)
        popup.minsize(width=self.min_size[0], height=self.min_size[1])
        popup.maxsize(width=self.max_size[0], height=self.max_size[1])
        popup.resizable(False, False)
        popup.grab_set()
        popup.focus_force()

        frame = ctk.CTkFrame(popup)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        ctk.CTkLabel(frame, text=message, wraplength=300).pack(pady=(0, 10))

        result = {"value": None}

        def on_ok():
            result["value"] = True
            popup.destroy()

        def on_cancel():
            result["value"] = False
            popup.destroy()

        if type == "askyesno":
            btn_frame = ctk.CTkFrame(frame)
            btn_frame.pack(pady=(5, 0))
            ctk.CTkButton(btn_frame, text="Yes", command=on_ok, width=80).pack(side="left", padx=5)
            ctk.CTkButton(btn_frame, text="No", command=on_cancel, width=80).pack(side="left", padx=5)
        else:
            ctk.CTkButton(frame, text="OK", command=on_ok, width=80).pack()

        # Center popup
        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (w // 2)
        y = (popup.winfo_screenheight() // 2) - (h // 2)
        popup.geometry(f"{w}x{h}+{x}+{y}")

        popup.wait_window()
        return result["value"]

    def showinfo(self, title, message):
        self._show(title, message, type="info")

    def showwarning(self, title, message):
        self._show(title, message, type="warning")

    def showerror(self, title, message):
        self._show(title, message, type="error")

    def askyesno(self, title, message):
        return self._show(title, message, type="askyesno")
