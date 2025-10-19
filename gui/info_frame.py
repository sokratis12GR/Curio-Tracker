import customtkinter as ctk

import curio_keybinds


class InfoPanelPopup:
    def __init__(self, parent=None, title="Hotkey Info"):
        self.parent = parent
        self.title = title

    def show(self):
        popup = ctk.CTkToplevel(self.parent)
        popup.title(self.title)
        popup.minsize(260, 320)
        popup.resizable(False, False)
        popup.grab_set()
        popup.focus_force()

        frame = ctk.CTkFrame(popup)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        texts = {
            "capture": lambda: f"Press {curio_keybinds.get_display_hotkey('capture')} to capture all curios on screen (no duplicates).",
            "snippet": lambda: f"Press {curio_keybinds.get_display_hotkey('snippet')} to snippet a region (allows duplicates).",
            "layout": lambda: f"Press {curio_keybinds.get_display_hotkey('layout_capture')} to set current layout.",
            "exit": lambda: f"Press {curio_keybinds.get_display_hotkey('exit')} to exit the script.",
            "duplicate_latest": lambda: f"Press {curio_keybinds.get_display_hotkey('duplicate_latest')} to duplicate the latest saved entry.",
            "delete_latest": lambda: f"Press {curio_keybinds.get_display_hotkey('delete_latest')} to delete the latest saved entry (must be loaded in the tool)"
        }

        # Wrap text labels properly
        for key, get_text in texts.items():
            lbl = ctk.CTkLabel(
                frame,
                text=get_text(),
                wraplength=240,
                justify="left",
                anchor="w"
            )
            lbl.pack(anchor="w", pady=5)


        # OK button
        ctk.CTkButton(frame, text="OK", command=popup.destroy, width=100).pack(pady=(10, 0))

        # Center popup
        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (w // 2)
        y = (popup.winfo_screenheight() // 2) - (h // 2)
        popup.geometry(f"{w}x{h}+{x}+{y}")

        popup.wait_window()
