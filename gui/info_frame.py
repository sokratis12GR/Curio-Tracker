from tkinter import ttk

import curio_keybinds


class InfoPanel:
    def __init__(self, parent, theme_manager, row_index_start=0):
        self.parent = parent
        self.theme_manager = theme_manager


        self.frame = ttk.LabelFrame(parent, text="Info", style="Info.TLabelframe", padding=(8, 4, 8, 4))
        self.frame.grid(row=row_index_start, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.theme_manager.register(self.frame)

        self.labels = {}
        row_index = 0

        for key, get_text in {
            "capture": lambda: f"Press {curio_keybinds.get_display_hotkey('capture')} to capture all curios on screen (no duplicates).",
            "snippet": lambda: f"Press {curio_keybinds.get_display_hotkey('snippet')} to snippet a region (allows duplicates).",
            "layout": lambda: f"Press {curio_keybinds.get_display_hotkey('layout_capture')} to set current layout.",
            "exit": lambda: f"Press {curio_keybinds.get_display_hotkey('exit')} to exit the script."
        }.items():
            lbl = ttk.Label(self.frame, text=get_text(), wraplength=220, justify="left", style="TLabel")
            lbl.grid(row=row_index, column=0, sticky="w", padx=4, pady=2)
            self.theme_manager.register(lbl)
            self.labels[key] = lbl
            row_index += 1

    def update_labels(self):
        for key, lbl in self.labels.items():
            if key == "capture":
                lbl.config(
                    text=f"Press {curio_keybinds.get_display_hotkey('capture')} to capture all curios on screen (no duplicates).")
            elif key == "snippet":
                lbl.config(
                    text=f"Press {curio_keybinds.get_display_hotkey('snippet')} to snippet a region (allows duplicates).")
            elif key == "layout":
                lbl.config(text=f"Press {curio_keybinds.get_display_hotkey('layout_capture')} to set current layout.")
            elif key == "exit":
                lbl.config(text=f"Press {curio_keybinds.get_display_hotkey('exit')} to exit the script.")
