# keybinds_popup.py

import customtkinter as ctk

import curio_keybinds
from fonts import make_font
from win_utils import center_window_on_parent


class KeybindsPopup:
    def __init__(
            self,
            parent,
            update_labels_callback
    ):
        self.parent = parent

        self.update_labels_callback = (
                update_labels_callback
                or (lambda: None)
        )

        self.popup_buttons = []

        self.popup = ctk.CTkToplevel(parent)

        self.popup.title("Keybind Settings")

        self.popup.geometry("380x520")

        self.popup.resizable(
            False,
            False
        )

        self.popup.transient(
            parent.winfo_toplevel()
        )

        frame = ctk.CTkFrame(
            self.popup
        )

        frame.pack(
            padx=20,
            pady=20,
            fill="both",
            expand=True
        )

        # -------------------------------
        # Grid configuration
        # -------------------------------
        frame.grid_columnconfigure(0, weight=0, minsize=190)
        frame.grid_columnconfigure(1, weight=0, minsize=150)

        # -------------------------------
        # Title
        # -------------------------------
        ctk.CTkLabel(
            frame,
            text="Configure Your Keybinds",
            font=make_font(
                16,
                "bold"
            ),
            anchor="w"
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=10,
            pady=(5, 10)
        )

        # -------------------------------
        # Table header
        # -------------------------------
        headers = (
            "Action",
            "Hotkey"
        )

        for col, text in enumerate(
                headers
        ):
            ctk.CTkLabel(
                frame,
                text=text,
                font=make_font(
                    11,
                    "bold"
                ),
                anchor="w"
            ).grid(
                row=1,
                column=col,
                sticky="ew",
                padx=10,
                pady=(3, 5)
            )

        # -------------------------------
        # Divider below header
        # -------------------------------
        separator = ctk.CTkFrame(
            frame,
            height=2,
            fg_color=(
                "gray75",
                "gray30"
            )
        )

        separator.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(0, 4)
        )

        # -------------------------------
        # Keybind rows
        # -------------------------------
        self._create_buttons(
            frame,
            start_row=3
        )

        # -------------------------------
        # Divider before footer
        # -------------------------------
        footer_row = (
                len(
                    curio_keybinds.keybinds
                )
                + 3
        )

        separator = ctk.CTkFrame(
            frame,
            height=2,
            fg_color=(
                "gray75",
                "gray30"
            )
        )

        separator.grid(
            row=footer_row,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(8, 8)
        )

        # -------------------------------
        # Bottom buttons
        # -------------------------------
        self._create_reset_and_close(
            frame,
            start_row=footer_row + 1
        )

        center_window_on_parent(
            self.popup,
            self.parent
        )

        self.popup.grab_set()
        self.popup.focus_force()

    def _create_buttons(
            self,
            frame,
            start_row=0
    ):
        for i, (
                label_text,
                default_value,
                hotkey_name
        ) in enumerate(
            curio_keybinds.keybinds
        ):
            row = start_row + i

            # Action
            ctk.CTkLabel(
                frame,
                text=label_text,
                font=make_font(
                    10,
                    "bold"
                ),
                anchor="w"
            ).grid(
                row=row,
                column=0,
                sticky="w",
                padx=(10, 12),
                pady=4
            )

            # Current hotkey
            current_label = (
                curio_keybinds
                .get_display_hotkey(
                    hotkey_name
                )
            )

            btn = ctk.CTkButton(
                frame,
                text=current_label,
                width=135,
                command=lambda idx=i: (
                    self._start_recording(
                        idx
                    )
                )
            )

            btn.grid(
                row=row,
                column=1,
                sticky="w",
                padx=(0, 10),
                pady=4
            )

            self.popup_buttons.append(
                btn
            )

    def _create_reset_and_close(
            self,
            frame,
            start_row=0
    ):
        def reset_all():
            for i, (
                    _,
                    default_value,
                    name
            ) in enumerate(
                curio_keybinds
                        .DEFAULT_KEYBINDS
            ):
                btn = (
                    self.popup_buttons[i]
                )

                btn.configure(
                    text=default_value
                )

                curio_keybinds.update_keybind(
                    name,
                    default_value
                )

            print(
                "[INFO] Keybinds reset to defaults."
            )

            self.update_labels_callback()

        bottom_frame = ctk.CTkFrame(
            frame,
            fg_color="transparent"
        )

        bottom_frame.grid(
            row=start_row,
            column=0,
            columnspan=2,
            pady=(5, 5)
        )

        reset_btn = ctk.CTkButton(
            bottom_frame,
            text="Reset All Keybinds",
            width=160,
            command=reset_all
        )

        reset_btn.pack(
            side="left",
            padx=5
        )

        close_btn = ctk.CTkButton(
            bottom_frame,
            text="Close",
            width=120,
            command=self.popup.destroy
        )

        close_btn.pack(
            side="left",
            padx=5
        )

    def _start_recording(
            self,
            index
    ):
        curio_keybinds.cancel_recording_popup(
            self.popup_buttons
        )

        curio_keybinds.start_recording_popup(
            index,
            self.popup_buttons,
            self.popup,
            self.update_labels_callback
        )


def show_keybind_popup(
        parent,
        update_labels_callback=None
):
    KeybindsPopup(
        parent,
        update_labels_callback
    )
