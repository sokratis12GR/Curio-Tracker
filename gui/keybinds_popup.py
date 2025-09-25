# keybinds_popup.py
import tkinter as tk
from tkinter import ttk
import curio_keybinds

class KeybindsPopup:
    def __init__(self, parent, update_labels_callback):
        self.parent = parent
        self.update_labels_callback = update_labels_callback or (lambda: None)
        self.popup_buttons = []

        self.popup = tk.Toplevel(parent)
        self.popup.title("Keybind Settings")
        self.popup.geometry("300x320")
        self.popup.resizable(False, False)
        self.popup.grab_set()  # make modal

        # ---- Main frame with padding ----
        frame = ttk.Frame(self.popup, padding=15)
        frame.pack(fill="both", expand=True)

        # ---- Title ----
        title = ttk.Label(
            frame,
            text="Configure Your Keybinds",
            font=("Segoe UI", 14, "bold")
        )
        title.grid(row=0, column=0, columnspan=2, pady=(0, 15))

        # ---- Keybind buttons ----
        self._create_buttons(frame, start_row=1)

        # ---- Separator ----
        sep = ttk.Separator(frame, orient="horizontal")
        sep.grid(row=len(curio_keybinds.keybinds) + 1, column=0, columnspan=2, sticky="ew", pady=10)

        # ---- Reset & Close buttons ----
        self._create_reset_and_close(frame, start_row=len(curio_keybinds.keybinds) + 2)

    def _create_buttons(self, frame, start_row=0):
        for i, (label_text, default_value, hotkey_name) in enumerate(curio_keybinds.keybinds):
            row = start_row + i

            # Label
            ttk.Label(frame, text=label_text + ":", font=("Segoe UI", 10)).grid(
                row=row, column=0, sticky="w", pady=4
            )

            # Button showing current hotkey
            current_label = curio_keybinds.get_display_hotkey(hotkey_name)
            btn = ttk.Button(
                frame,
                text=current_label,
                width=20,
                command=lambda idx=i: self._start_recording(idx)
            )
            btn.grid(row=row, column=1, padx=8, pady=4, sticky="w")
            self.popup_buttons.append(btn)

    def _create_reset_and_close(self, frame, start_row=0):
        def reset_all():
            for i, (_, default_value, name) in enumerate(curio_keybinds.DEFAULT_KEYBINDS):
                btn = self.popup_buttons[i]
                btn.config(text=default_value)
                curio_keybinds.update_keybind(name, default_value)
            print("[INFO] Keybinds reset to defaults.")
            self.update_labels_callback()

        # Container frame for bottom buttons (centered)
        bottom_frame = ttk.Frame(frame)
        bottom_frame.grid(row=start_row, column=0, columnspan=2, pady=(10, 5))

        reset_btn = ttk.Button(bottom_frame, text="Reset All Keybinds", command=reset_all)
        reset_btn.pack(side="left", padx=5)

        close_btn = ttk.Button(bottom_frame, text="Close", command=self.popup.destroy)
        close_btn.pack(side="left", padx=5)


    def _start_recording(self, index):
        curio_keybinds.cancel_recording_popup(self.popup_buttons)
        curio_keybinds.start_recording_popup(index, self.popup_buttons, self.popup, self.update_labels_callback)


def show_keybind_popup(parent, update_labels_callback=None):
    KeybindsPopup(parent, update_labels_callback)
