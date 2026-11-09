from tkinter import colorchooser

import customtkinter as ctk

import config as c
import toasts
from fonts import make_font
from logger import log_message
from settings import set_setting


class ToastSettingsMixin:
    # -------------------------------
    # Toasts
    # -------------------------------
    def _build_toasts(self, frame):
        row = 0

        # ==================================================
        # Placement & Timing
        # ==================================================
        ctk.CTkLabel(frame, text="Placement & Timing", font=make_font(12, "bold")).grid(row=row, column=0, columnspan=2,
                                                                                        sticky="w", pady=(0, 5))

        row += 1

        ctk.CTkCheckBox(frame, text="Enable Toasts", variable=self.toasts_var, command=self._toggle_toasts).grid(
            row=row, column=0, columnspan=2, sticky="w")

        row += 1

        ctk.CTkLabel(frame, text="Position:").grid(row=row, column=0, sticky="w")

        toast_position_cb = ctk.CTkComboBox(frame, variable=self.toasts_position_var, values=c.VALID_TOAST_POSITIONS,
                                            width=self.width, state="readonly")

        toast_position_cb.grid(row=row, column=1, sticky="w")

        self.toasts_position_var.trace_add("write", self._update_toasts_position)

        row += 1

        ctk.CTkLabel(frame, text="Y Offset (px):").grid(row=row, column=0, sticky="w")

        y_offset_entry = ctk.CTkEntry(frame, textvariable=self.toasts_y_offset_var, width=self.width)

        y_offset_entry.grid(row=row, column=1, sticky="w")

        self.toasts_y_offset_var.trace_add("write", self._update_toasts_y_offset)

        row += 1

        ctk.CTkLabel(frame, text="X Offset (px):").grid(row=row, column=0, sticky="w")

        x_offset_entry = ctk.CTkEntry(frame, textvariable=self.toasts_x_offset_var, width=self.width)

        x_offset_entry.grid(row=row, column=1, sticky="w")

        self.toasts_x_offset_var.trace_add("write", self._update_toasts_x_offset)

        row += 1

        ctk.CTkLabel(frame, text="Duration (sec):").grid(row=row, column=0, sticky="w", pady=(4, 0))

        duration_entry = ctk.CTkEntry(frame, textvariable=self.toasts_duration_var, width=self.width)

        duration_entry.grid(row=row, column=1, sticky="w", pady=(4, 0))

        self.toasts_duration_var.trace_add("write", self._update_toasts_duration)

        row += 1

        # ==================================================
        # Size & Fonts
        # ==================================================
        ctk.CTkLabel(frame, text="Size & Fonts", font=make_font(12, "bold")).grid(row=row, column=0, columnspan=2,
                                                                                  sticky="w", pady=(14, 5))

        row += 1

        ctk.CTkLabel(frame, text="Toast Size:").grid(row=row, column=0, sticky="w")

        toast_size_cb = ctk.CTkComboBox(frame, variable=self.toast_size_preset_var,
                                        values=[*c.TOAST_SIZE_PRESETS.keys(), "Custom"], width=self.width,
                                        state="readonly", command=self._apply_toast_size_preset)

        toast_size_cb.grid(row=row, column=1, sticky="w")

        row += 1

        # --------------------------------------------------
        # Custom-only size controls
        # --------------------------------------------------
        self.toast_custom_size_frame = ctk.CTkFrame(frame, fg_color="transparent")

        self.toast_custom_size_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        custom_row = 0

        ctk.CTkLabel(self.toast_custom_size_frame, text="Toast Image Width (px):").grid(row=custom_row, column=0,
                                                                                        sticky="w")

        image_width_entry = ctk.CTkEntry(self.toast_custom_size_frame, textvariable=self.toast_image_width_var,
                                         width=self.width)

        image_width_entry.grid(row=custom_row, column=1, sticky="w")

        image_width_entry.bind("<Return>", lambda e: self._update_toast_image_width())

        image_width_entry.bind("<FocusOut>", lambda e: self._update_toast_image_width())

        custom_row += 1

        ctk.CTkLabel(self.toast_custom_size_frame, text="Toast Image Height (px):").grid(row=custom_row, column=0,
                                                                                         sticky="w")

        image_height_entry = ctk.CTkEntry(self.toast_custom_size_frame, textvariable=self.toast_image_height_var,
                                          width=self.width)

        image_height_entry.grid(row=custom_row, column=1, sticky="w")

        image_height_entry.bind("<Return>", lambda e: self._update_toast_image_height())

        image_height_entry.bind("<FocusOut>", lambda e: self._update_toast_image_height())

        custom_row += 1

        ctk.CTkLabel(self.toast_custom_size_frame, text="Toast Font Size:").grid(row=custom_row, column=0, sticky="w")

        font_size_entry = ctk.CTkEntry(self.toast_custom_size_frame, textvariable=self.toast_font_size_var,
                                       width=self.width)

        font_size_entry.grid(row=custom_row, column=1, sticky="w")

        font_size_entry.bind("<Return>", lambda e: self._update_toast_font_size())

        font_size_entry.bind("<FocusOut>", lambda e: self._update_toast_font_size())

        custom_row += 1

        ctk.CTkLabel(self.toast_custom_size_frame, text="Toast Headline Font Size:").grid(row=custom_row, column=0,
                                                                                          sticky="w")

        headline_font_size_entry = ctk.CTkEntry(self.toast_custom_size_frame,
                                                textvariable=self.toast_headline_font_size_var, width=self.width)

        headline_font_size_entry.grid(row=custom_row, column=1, sticky="w")

        headline_font_size_entry.bind("<Return>", lambda e: self._update_toast_headline_font_size())

        headline_font_size_entry.bind("<FocusOut>", lambda e: self._update_toast_headline_font_size())

        # Hide custom controls unless Custom is selected.
        self._update_toast_custom_visibility()

        row += 1

        # ==================================================
        # Appearance
        # ==================================================
        ctk.CTkLabel(frame, text="Collection Missing Color:").grid(row=row, column=0, sticky="w", pady=(12, 0))

        self.color_preview = ctk.CTkFrame(frame, width=60, height=30, fg_color=self.collection_missing_color_var.get())

        self.color_preview.grid(row=row, column=1, sticky="w", padx=(0, 10), pady=(12, 0))

        pick_btn = ctk.CTkButton(frame, text="Pick", width=int(self.width / 1.4), command=self._pick_collection_color)

        pick_btn.grid(row=row, column=1, sticky="w", padx=(60, 0), pady=(12, 0))

        row += 1

        self.example_toast_btn = ctk.CTkButton(frame, text="SHOW EXAMPLE", command=self._toggle_example_toast,
                                               width=self.long_width)

        self.example_toast_btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 5))

        row += 1

        reset_toasts_btn = ctk.CTkButton(frame, text="Reset Toast Settings", fg_color="#8B0000", hover_color="#A00000",
                                         command=self._reset_toast_settings, width=self.long_width)

        reset_toasts_btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 5))

    # -------------------------------
    # Toast Handlers
    # -------------------------------
    def _update_toasts_position(self, *_):
        val = self.toasts_position_var.get()
        if not val:
            return

        toasts.set_toast_position(val, self.parent)

    def _update_toasts_y_offset(self, *_):
        val = self.toasts_y_offset_var.get()

        if val in ("", "-", "+"):
            return

        try:
            offset = int(val)
        except ValueError:
            return

        offset = max(c.TOAST_Y_OFFSET_MIN, min(c.TOAST_Y_OFFSET_MAX, offset))

        if str(offset) != val:
            self.toasts_y_offset_var.set(str(offset))
            return

        toasts.set_toast_y_offset(offset, self.parent)

    def _update_toasts_x_offset(self, *_):
        val = self.toasts_x_offset_var.get()

        if val in ("", "-", "+"):
            return

        try:
            offset = int(val)
        except ValueError:
            return

        offset = max(c.TOAST_X_OFFSET_MIN, min(c.TOAST_X_OFFSET_MAX, offset))

        if str(offset) != val:
            self.toasts_x_offset_var.set(str(offset))
            return

        toasts.set_toast_x_offset(offset, self.parent)

    def _update_toast_image_width(self, *_):
        val = self.toast_image_width_var.get().strip()

        try:
            width = int(val)
        except ValueError:
            width = c.DEFAULT_TOAST_IMAGE_WIDTH

        width = max(
            c.TOAST_IMAGE_WIDTH_MIN,
            min(c.TOAST_IMAGE_WIDTH_MAX, width)
        )

        self.toast_image_width_var.set(str(width))

        self._mark_toast_size_custom()

        toasts.set_toast_image_width(
            width,
            self.parent
        )

    def _update_toast_image_height(self, *_):
        val = self.toast_image_height_var.get().strip()

        try:
            height = int(val)
        except ValueError:
            height = c.DEFAULT_TOAST_IMAGE_HEIGHT

        height = max(
            c.TOAST_IMAGE_HEIGHT_MIN,
            min(c.TOAST_IMAGE_HEIGHT_MAX, height)
        )

        self.toast_image_height_var.set(str(height))

        self._mark_toast_size_custom()

        toasts.set_toast_image_height(
            height,
            self.parent
        )

    def _update_toast_font_size(self, *_):
        val = self.toast_font_size_var.get().strip()

        try:
            size = int(val)
        except ValueError:
            size = c.DEFAULT_TOAST_FONT_SIZE

        size = max(
            c.TOAST_FONT_SIZE_MIN,
            min(c.TOAST_FONT_SIZE_MAX, size)
        )

        self.toast_font_size_var.set(str(size))

        self._mark_toast_size_custom()

        toasts.set_toast_font_size(
            size,
            self.parent
        )

    def _update_toast_headline_font_size(self, *_):
        val = self.toast_headline_font_size_var.get().strip()

        try:
            size = int(val)
        except ValueError:
            size = c.DEFAULT_TOAST_HEADLINE_FONT_SIZE

        size = max(
            c.TOAST_HEADLINE_FONT_SIZE_MIN,
            min(c.TOAST_HEADLINE_FONT_SIZE_MAX, size)
        )

        self.toast_headline_font_size_var.set(str(size))

        self._mark_toast_size_custom()

        toasts.set_toast_headline_font_size(
            size,
            self.parent
        )

    def _apply_toast_size_preset(self, preset_name):
        if not preset_name:
            return

        set_setting(
            "Application",
            "toast_size_preset",
            preset_name
        )

        if preset_name == "Custom":
            self._update_toast_custom_visibility()
            return

        preset = c.TOAST_SIZE_PRESETS.get(preset_name)

        if not preset:
            return

        image_width = preset["image_width"]
        image_height = preset["image_height"]
        font_size = preset["font_size"]
        headline_font_size = preset["headline_font_size"]

        # Update UI variables.
        self.toast_image_width_var.set(str(image_width))
        self.toast_image_height_var.set(str(image_height))
        self.toast_font_size_var.set(str(font_size))
        self.toast_headline_font_size_var.set(
            str(headline_font_size)
        )

        toasts.set_toast_image_width(image_width, self.parent)

        toasts.set_toast_image_height(image_height, self.parent)

        toasts.set_toast_font_size(font_size, self.parent)

        toasts.set_toast_headline_font_size(headline_font_size, self.parent)

        self._update_toast_custom_visibility()

        try:
            toasts.refresh_example(self.parent)
            toasts.reposition(self.parent)
        except Exception:
            pass

        log_message(
            "Toast Size",
            (
                f"{preset_name}: "
                f"{image_width}x{image_height}, "
                f"font={font_size}, "
                f"headline={headline_font_size}"
            )
        )

    def _update_toast_custom_visibility(self):
        if not self.toast_custom_size_frame:
            return

        if self.toast_size_preset_var.get() == "Custom":
            self.toast_custom_size_frame.grid()
        else:
            self.toast_custom_size_frame.grid_remove()

    def _update_toasts_duration(self, *_):
        val = self.toasts_duration_var.get().strip()

        if not val:
            return

        try:
            dur = int(val)
        except ValueError:
            return

        toasts.set_toast_duration(dur)

    def _toggle_toasts(self):
        enabled = self.toasts_var.get()
        toasts.toggle_toasts(enabled)

    def _toggle_example_toast(self):
        visible = toasts.toggle_example(self.parent)

        if self.example_toast_btn:
            self.example_toast_btn.configure(text="HIDE EXAMPLE" if visible else "SHOW EXAMPLE")

    def _pick_collection_color(self):
        color_code = colorchooser.askcolor(title="Choose Collection Missing Color")

        if color_code and color_code[1]:
            chosen = color_code[1]
            self.collection_missing_color_var.set(chosen)
            self.color_preview.configure(fg_color=chosen)
            toasts.set_collection_missing_color(chosen)

    def _reset_toast_settings(self):
        log_message("Resetting toast settings to defaults")

        default_size_preset = c.DEFAULT_TOAST_SIZE_PRESET
        default_position = c.DEFAULT_TOAST_POSITION
        default_y = c.DEFAULT_TOAST_Y_OFFSET
        default_x = c.DEFAULT_TOAST_X_OFFSET
        default_duration = c.DEFAULT_TOAST_DURATION
        default_enabled = c.DEFAULT_TOAST_ENABLE
        default_image_width = c.DEFAULT_TOAST_IMAGE_WIDTH
        default_image_height = c.DEFAULT_TOAST_IMAGE_HEIGHT
        default_font_size = c.DEFAULT_TOAST_FONT_SIZE
        default_headline_font_size = c.DEFAULT_TOAST_HEADLINE_FONT_SIZE

        set_setting("Application", "toast_size_preset", default_size_preset)
        set_setting("Application", "toast_position", default_position)
        set_setting("Application", "toast_y_offset", default_y)
        set_setting("Application", "toast_x_offset", default_x)
        set_setting("Application", "toasts_duration_seconds", default_duration)
        set_setting("Application", "are_toasts_enabled", default_enabled)
        set_setting("Application", "toast_image_width", default_image_width)
        set_setting("Application", "toast_image_height", default_image_height)
        set_setting("Application", "toast_font_size", default_font_size)
        set_setting("Application", "toast_headline_font_size", default_headline_font_size)

        self.toast_size_preset_var.set(default_size_preset)
        self.toasts_position_var.set(default_position)
        self.toasts_y_offset_var.set(str(default_y))
        self.toasts_x_offset_var.set(str(default_x))
        self.toasts_duration_var.set(str(default_duration))
        self.toasts_var.set(default_enabled)
        self.toast_image_width_var.set(str(default_image_width))
        self.toast_image_height_var.set(str(default_image_height))
        self.toast_font_size_var.set(str(default_font_size))
        self.toast_headline_font_size_var.set(str(default_headline_font_size))

        toasts.toggle_toasts(default_enabled)
        toasts.set_toast_duration(default_duration)
        toasts.set_toast_position(default_position)
        toasts.set_toast_y_offset(default_y)
        toasts.set_toast_x_offset(default_x)
        toasts.set_toast_image_width(default_image_width)
        toasts.set_toast_image_height(default_image_height)
        toasts.set_toast_font_size(default_font_size)
        toasts.set_toast_headline_font_size(default_headline_font_size)
        self._update_toast_custom_visibility()

        try:
            toasts.refresh_example(self.parent)
            toasts.reposition(self.parent)
        except Exception:
            pass

        log_message("Toast settings reset complete")

    def _mark_toast_size_custom(self):
        if self.toast_size_preset_var.get() == "Custom":
            return

        self.toast_size_preset_var.set("Custom")

        set_setting("Application", "toast_size_preset", "Custom")

        self._update_toast_custom_visibility()
