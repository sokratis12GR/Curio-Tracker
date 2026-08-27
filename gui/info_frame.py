import customtkinter as ctk

import curio_keybinds
from win_utils import center_window_on_parent


class InfoPanelPopup:
    def __init__(self, parent=None, title="Hotkey Info"):
        self.parent = parent
        self.title = title

    def show(self):
        popup = ctk.CTkToplevel(self.parent)
        popup.title(self.title)
        popup.geometry("720x520")
        popup.resizable(False, False)
        popup.transient(self.parent.winfo_toplevel())

        frame = ctk.CTkFrame(popup)
        frame.pack(
            padx=20,
            pady=20,
            fill="both",
            expand=True
        )

        # -------------------------------
        # Title
        # -------------------------------
        ctk.CTkLabel(
            frame,
            text="Hotkey Reference",
            font=("Segoe UI", 16, "bold")
        ).grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
            padx=10,
            pady=(5, 15)
        )

        # -------------------------------
        # Column setup
        # -------------------------------
        frame.grid_columnconfigure(0, weight=0)
        frame.grid_columnconfigure(1, weight=0)
        frame.grid_columnconfigure(2, weight=1)

        # -------------------------------
        # Header
        # -------------------------------
        headers = (
            "Action",
            "Hotkey",
            "Description"
        )

        for col, text in enumerate(headers):
            label = ctk.CTkLabel(
                frame,
                text=text,
                font=("Segoe UI", 11, "bold"),
                anchor="w"
            )

            label.grid(
                row=1,
                column=col,
                sticky="ew",
                padx=8,
                pady=(5, 8)
            )

        # -------------------------------
        # Hotkey rows
        # -------------------------------
        rows = [
            (
                "Capture",
                "capture",
                "Capture all curios currently visible on screen. "
                "Duplicate entries are ignored."
            ),
            (
                "Snippet",
                "snippet",
                "Select and capture a specific screen region. "
                "Duplicate entries are allowed."
            ),
            (
                "Set Layout",
                "layout_capture",
                "Capture and set the current blueprint layout."
            ),
            (
                "Exit",
                "exit",
                "Exit the application."
            ),
            (
                "Duplicate Latest",
                "duplicate_latest",
                "Duplicate the latest saved entry."
            ),
            (
                "Delete Latest",
                "delete_latest",
                "Delete the latest saved entry. "
                "The entry must currently be loaded in the tool."
            ),
            (
                "Highest Value",
                "show_highest_value",
                "Show the highest-value entry from the current wing."
            ),
            (
                "Cycle Enchantment",
                "cycle_bp_enchantment",
                "Cycle through the blueprint enchantment types."
            ),
        ]

        for row_index, (
            action,
            hotkey_name,
            description
        ) in enumerate(rows, start=2):

            # Action
            ctk.CTkLabel(
                frame,
                text=action,
                anchor="w",
                font=("Segoe UI", 10, "bold")
            ).grid(
                row=row_index,
                column=0,
                sticky="nw",
                padx=8,
                pady=6
            )

            # Hotkey
            hotkey = curio_keybinds.get_display_hotkey(
                hotkey_name
            )

            hotkey_label = ctk.CTkLabel(
                frame,
                text=hotkey,
                anchor="center",
                corner_radius=6,
                fg_color=("gray85", "gray25"),
                width=120
            )

            hotkey_label.grid(
                row=row_index,
                column=1,
                sticky="n",
                padx=8,
                pady=6
            )

            # Description
            ctk.CTkLabel(
                frame,
                text=description,
                anchor="w",
                justify="left",
                wraplength=390
            ).grid(
                row=row_index,
                column=2,
                sticky="nw",
                padx=8,
                pady=6
            )

        # -------------------------------
        # Close
        # -------------------------------
        ctk.CTkButton(
            frame,
            text="OK",
            command=popup.destroy,
            width=120
        ).grid(
            row=len(rows) + 2,
            column=0,
            columnspan=3,
            pady=(18, 5)
        )

        center_window_on_parent(
            popup,
            self.parent
        )

        popup.grab_set()
        popup.focus_force()
        popup.wait_window()