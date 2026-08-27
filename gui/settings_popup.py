import re
import threading
import webbrowser
from tkinter import colorchooser

import customtkinter as ctk
from PIL import Image, ImageGrab, ImageTk

import config as c
import curio_collection_fetch
import toasts
from fonts import update_all_fonts, make_font, init_font_var
from load_utils import get_datasets
from logger import log_message
from settings import get_setting, set_setting
from themes import apply_theme
from tree_manager import TreeManager
from win_utils import center_window_on_parent, get_poe_bbox


# -------------------------------
# Collapsible Section
# -------------------------------
class CollapsibleSection(ctk.CTkFrame):
    def __init__(self, parent, title, expanded=True):
        super().__init__(parent, fg_color="transparent")
        self.title = title
        self.expanded = expanded
        self.settings_window = None

        self.header = ctk.CTkButton(self, text="", anchor="w", height=34, command=self.toggle)
        self.header.pack(fill="x", pady=(3, 0))

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        if self.expanded:
            self.content.pack(fill="x", padx=8, pady=(5, 8))

        self._update_header()

    def _update_header(self):
        arrow = "▼" if self.expanded else "▶"
        self.header.configure(text=f"{arrow}  {self.title}")

    def toggle(self):
        self.expanded = not self.expanded

        if self.expanded:
            self.content.pack(fill="x", padx=8, pady=(5, 8))
        else:
            self.content.pack_forget()

        self._update_header()


# -------------------------------
# Main Popup
# -------------------------------
class SettingsPopup:
    def __init__(self, parent, tracker, theme_manager, tree_manager):
        self.tracker = tracker
        self.theme_manager = theme_manager
        self.tree_manager = tree_manager
        init_font_var(parent)

        self.popup = ctk.CTkToplevel(parent)
        self.popup.title("Application Settings")
        self.popup.geometry("470x540")
        self.popup.resizable(False, False)
        self.popup.transient(parent.winfo_toplevel())
        self.popup.protocol("WM_DELETE_WINDOW", self.close)

        self.scroll_frame = ctk.CTkScrollableFrame(
            self.popup,
            label_text="Configuration",
            label_font=make_font(14, "bold")
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=10)

        self.app_section = UnifiedSettingsSection(parent, tracker, theme_manager, tree_manager)
        self.app_section.build(self.scroll_frame)

        bottom_frame = ctk.CTkFrame(self.popup, fg_color="transparent")
        bottom_frame.pack(fill="x", pady=(5, 10))
        ctk.CTkButton(bottom_frame, text="Close", command=self.close, width=100).pack(pady=5)

        center_window_on_parent(
            self.popup,
            parent
        )

        self.popup.grab_set()
        self.popup.focus_force()

    def close(self):
        toasts.hide_example()
        self.popup.destroy()


class OCRRegionEditor:
    PREVIEW_MAX_WIDTH = 900
    PREVIEW_MAX_HEIGHT = 600

    def __init__(self, parent, owner):
        self.parent = parent
        self.owner = owner

        self.window = ctk.CTkToplevel(parent)
        self.window.title("Configure OCR Region")
        self.window.resizable(False, False)
        self.window.grab_set()
        self.window.transient(parent.winfo_toplevel())

        self.drag_start_x = None
        self.drag_start_y = None

        self.rect_id = None

        self.rect_coords = None

        self.preview_image = None
        self.tk_image = None

        self.preview_width = 0
        self.preview_height = 0

        self._capture_preview()
        self._build_ui()
        self._draw_saved_region()

        center_window_on_parent(
            self.window,
            self.parent
        )

        self.window.grab_set()
        self.window.focus_force()

    def _capture_preview(self):
        bbox = get_poe_bbox()

        if not bbox:
            raise RuntimeError("Could not locate Path of Exile window.")

        screenshot = ImageGrab.grab(bbox=bbox)

        original_width, original_height = screenshot.size

        scale = min(
            self.PREVIEW_MAX_WIDTH / original_width,
            self.PREVIEW_MAX_HEIGHT / original_height,
            1.0
        )

        self.preview_width = int(original_width * scale)
        self.preview_height = int(original_height * scale)

        self.preview_image = screenshot.resize(
            (self.preview_width, self.preview_height),
            Image.Resampling.LANCZOS
        )

        self.tk_image = ImageTk.PhotoImage(self.preview_image)

    def _build_ui(self):
        container = ctk.CTkFrame(
            self.window,
            fg_color="transparent"
        )
        container.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        ctk.CTkLabel(
            container,
            text="Drag over the area that should be processed by OCR."
        ).pack(anchor="w", pady=(0, 8))

        self.canvas = ctk.CTkCanvas(
            container,
            width=self.preview_width,
            height=self.preview_height,
            highlightthickness=0,
            cursor="cross"
        )
        self.canvas.pack()

        self.canvas.create_image(
            0,
            0,
            anchor="nw",
            image=self.tk_image
        )

        self.canvas.bind(
            "<Button-1>",
            self._on_mouse_down
        )

        self.canvas.bind(
            "<B1-Motion>",
            self._on_mouse_drag
        )

        self.canvas.bind(
            "<ButtonRelease-1>",
            self._on_mouse_up
        )

        self.info_label = ctk.CTkLabel(
            container,
            text=""
        )
        self.info_label.pack(
            anchor="w",
            pady=(8, 5)
        )

        buttons = ctk.CTkFrame(
            container,
            fg_color="transparent"
        )
        buttons.pack(fill="x", pady=(5, 0))

        ctk.CTkButton(
            buttons,
            text="Reset",
            width=100,
            command=self._reset
        ).pack(side="left")

        ctk.CTkButton(
            buttons,
            text="Cancel",
            width=100,
            command=self.window.destroy
        ).pack(side="right")

        ctk.CTkButton(
            buttons,
            text="Save",
            width=100,
            command=self._save
        ).pack(side="right", padx=(0, 8))

    def _draw_saved_region(self):
        left = self.owner.ocr_region_left_var.get()
        top = self.owner.ocr_region_top_var.get()
        right = self.owner.ocr_region_right_var.get()
        bottom = self.owner.ocr_region_bottom_var.get()

        x1 = left * self.preview_width
        y1 = top * self.preview_height
        x2 = right * self.preview_width
        y2 = bottom * self.preview_height

        self._set_rectangle(x1, y1, x2, y2)

    def _on_mouse_down(self, event):
        self.drag_start_x = self._clamp(
            event.x,
            0,
            self.preview_width
        )

        self.drag_start_y = self._clamp(
            event.y,
            0,
            self.preview_height
        )

        self._set_rectangle(
            self.drag_start_x,
            self.drag_start_y,
            self.drag_start_x,
            self.drag_start_y
        )

    def _on_mouse_drag(self, event):
        if self.drag_start_x is None:
            return

        x = self._clamp(
            event.x,
            0,
            self.preview_width
        )

        y = self._clamp(
            event.y,
            0,
            self.preview_height
        )

        self._set_rectangle(
            self.drag_start_x,
            self.drag_start_y,
            x,
            y
        )

    def _on_mouse_up(self, event):
        if self.drag_start_x is None:
            return

        x = self._clamp(
            event.x,
            0,
            self.preview_width
        )

        y = self._clamp(
            event.y,
            0,
            self.preview_height
        )

        self._set_rectangle(
            self.drag_start_x,
            self.drag_start_y,
            x,
            y
        )

        self.drag_start_x = None
        self.drag_start_y = None

    def _set_rectangle(self, x1, y1, x2, y2):
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))

        x1 = self._clamp(x1, 0, self.preview_width)
        x2 = self._clamp(x2, 0, self.preview_width)
        y1 = self._clamp(y1, 0, self.preview_height)
        y2 = self._clamp(y2, 0, self.preview_height)

        # Keep our own authoritative copy.
        self.rect_coords = (x1, y1, x2, y2)

        if self.rect_id is None:
            self.rect_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline="red",
                width=3
            )
        else:
            self.canvas.coords(
                self.rect_id,
                x1,
                y1,
                x2,
                y2
            )

        self._update_info()

    def _update_info(self):
        if self.rect_coords is None:
            return

        x1, y1, x2, y2 = self.rect_coords

        width = max(0, x2 - x1)
        height = max(0, y2 - y1)

        total_area = self.preview_width * self.preview_height
        selected_area = width * height

        if total_area <= 0:
            percent = 0.0
        else:
            percent = (selected_area / total_area) * 100

        excluded = 100 - percent

        region_width_pct = (
            (width / self.preview_width) * 100
            if self.preview_width > 0
            else 0.0
        )

        region_height_pct = (
            (height / self.preview_height) * 100
            if self.preview_height > 0
            else 0.0
        )

        self.info_label.configure(
            text=(
                f"OCR area: {percent:.1f}%   |   "
                f"Width: {region_width_pct:.1f}%   |   "
                f"Height: {region_height_pct:.1f}%   |   "
                f"Excluded: {excluded:.1f}%"
            )
        )

    def _reset(self):
        left, top, right, bottom = c.OCR_REGION_PRESETS["Recommended"]

        self._set_rectangle(
            left * self.preview_width,
            top * self.preview_height,
            right * self.preview_width,
            bottom * self.preview_height
        )

    def _save(self):
        if self.rect_coords is None:
            return

        x1, y1, x2, y2 = self.rect_coords

        # Prevent accidentally saving an unusably tiny region.
        if x2 - x1 < 20 or y2 - y1 < 20:
            self.parent.bell()
            return

        if self.preview_width <= 0 or self.preview_height <= 0:
            return

        left = x1 / self.preview_width
        top = y1 / self.preview_height
        right = x2 / self.preview_width
        bottom = y2 / self.preview_height

        left = self._clamp(left, 0.0, 1.0)
        top = self._clamp(top, 0.0, 1.0)
        right = self._clamp(right, 0.0, 1.0)
        bottom = self._clamp(bottom, 0.0, 1.0)

        set_setting("Application", "ocr_region_left", left)
        set_setting("Application", "ocr_region_top", top)
        set_setting("Application", "ocr_region_right", right)
        set_setting("Application", "ocr_region_bottom", bottom)

        self.owner.ocr_region_left_var.set(left)
        self.owner.ocr_region_top_var.set(top)
        self.owner.ocr_region_right_var.set(right)
        self.owner.ocr_region_bottom_var.set(bottom)

        set_setting(
            "Application",
            "ocr_region_preset",
            "Custom"
        )

        self.owner.ocr_region_preset_var.set("Custom")

        if self.owner.ocr_region_label:
            self.owner.ocr_region_label.configure(
                text=self.owner._get_ocr_region_description()
            )

        log_message(
            "OCR Region",
            (
                f"{left:.4f}, {top:.4f}, "
                f"{right:.4f}, {bottom:.4f}"
            )
        )

        self.window.destroy()

    @staticmethod
    def _clamp(value, minimum, maximum):
        return max(
            minimum,
            min(maximum, value)
        )


# -------------------------------
# Unified Settings
# -------------------------------
class UnifiedSettingsSection:
    def __init__(self, parent, tracker, theme_manager, tree_manager: TreeManager):
        self.parent = parent
        self.tracker = tracker
        self.theme_manager = theme_manager
        self.tree_manager = tree_manager

        self.dynamic_data_league_cb = None
        self.poe_entry = None
        self.fetch_collection_btn = None
        self.color_preview = None
        self.poeladder_label = None
        self.example_toast_btn = None
        self.dupe_label = None

        self.width = 220
        self.long_width = 420

        self.datasets = get_datasets()
        self.leagues_dict = self.datasets.get("leagues", {})
        self.poeladder_leagues = list(self.leagues_dict.keys())

        self.theme_selector_var = ctk.StringVar(value=get_setting("Application", "theme_mode", c.DEFAULT_THEME_MODE))

        self.top_right_target_area_percent_var = ctk.StringVar(
            value=str(get_setting("Application", "top_right_target_area_percent", c.DEFAULT_TOP_RIGHT_CAPTURE_PERCENT))
        )
        self.ocr_region_left_var = ctk.DoubleVar(
            value=get_setting("Application", "ocr_region_left", c.DEFAULT_OCR_REGION_LEFT))
        self.ocr_region_top_var = ctk.DoubleVar(
            value=get_setting("Application", "ocr_region_top", c.DEFAULT_OCR_REGION_TOP))
        self.ocr_region_right_var = ctk.DoubleVar(
            value=get_setting("Application", "ocr_region_right", c.DEFAULT_OCR_REGION_RIGHT))

        self.ocr_region_bottom_var = ctk.DoubleVar(
            value=get_setting("Application", "ocr_region_bottom", c.DEFAULT_OCR_REGION_BOTTOM))

        self.ocr_region_label = None

        self.toasts_position_var = ctk.StringVar(
            value=get_setting("Application", "toast_position", c.DEFAULT_TOAST_POSITION))
        self.toasts_y_offset_var = ctk.StringVar(
            value=str(get_setting("Application", "toast_y_offset", c.DEFAULT_TOAST_Y_OFFSET)))
        self.toasts_x_offset_var = ctk.StringVar(
            value=str(get_setting("Application", "toast_x_offset", c.DEFAULT_TOAST_X_OFFSET)))
        self.toasts_var = ctk.BooleanVar(value=toasts.ARE_TOASTS_ENABLED)
        self.toasts_duration_var = ctk.StringVar(value=str(toasts.TOASTS_DURATION))
        self.toast_image_width_var = ctk.StringVar(
            value=str(get_setting("Application", "toast_image_width", c.DEFAULT_TOAST_IMAGE_WIDTH))
        )
        self.toast_image_height_var = ctk.StringVar(
            value=str(get_setting("Application", "toast_image_height", c.DEFAULT_TOAST_IMAGE_HEIGHT))
        )
        self.toast_font_size_var = ctk.StringVar(
            value=str(get_setting("Application", "toast_font_size", c.DEFAULT_TOAST_FONT_SIZE))
        )
        self.toast_headline_font_size_var = ctk.StringVar(
            value=str(get_setting("Application", "toast_headline_font_size", c.DEFAULT_TOAST_HEADLINE_FONT_SIZE))
        )

        self.csv_current_record_number_var = ctk.IntVar(value=get_setting("Application", "csv_current_row", 0))
        self.json_current_record_number_var = ctk.IntVar(value=get_setting("Application", "json_current_row", 0))

        self.enable_poeladder_var = ctk.BooleanVar(
            value=get_setting("Application", "enable_poeladder", c.ENABLE_POELADDER)
        )
        self.data_league_var = ctk.StringVar(value=get_setting("Application", "data_league", c.LEAGUE))
        self.poe_player_var = ctk.StringVar(value=get_setting("User", "poe_user", ""))

        self.enable_hdr_filtering_var = ctk.BooleanVar(
            value=get_setting("Application", "is_hdr_filtering_enabled", c.IS_HDR_ENABLED)
        )

        self.dupe_duration = ctk.IntVar(value=get_setting("Application", "time_last_dupe_check_seconds", 60))
        self.font_selector_var = ctk.StringVar(value=get_setting("Application", "font_family", "Segoe UI"))
        self.collection_missing_color_var = ctk.StringVar(
            value=get_setting("Application", "collection_missing_color", "#FF0000")
        )
        self.dynamic_data_league_var = ctk.StringVar(
            value=get_setting("Application", "poeladder_ggg_league", c.FIXED_LADDER_IDENTIFIER)
        )

    def build(self, frame):
        self.settings_window = frame.winfo_toplevel()

        general = CollapsibleSection(
            frame,
            "General",
            expanded=True
        )

        general = CollapsibleSection(frame, "General", expanded=True)
        general.pack(fill="x", pady=2)
        self._build_general(general.content)

        player = CollapsibleSection(frame, "Player & League", expanded=True)
        player.pack(fill="x", pady=2)
        self._build_player(player.content)

        poeladder = CollapsibleSection(frame, "PoE Ladder", expanded=False)
        poeladder.pack(fill="x", pady=2)
        self._build_poeladder(poeladder.content)

        capture = CollapsibleSection(frame, "Capture / OCR", expanded=False)
        capture.pack(fill="x", pady=2)
        self._build_capture(capture.content)

        toast_section = CollapsibleSection(frame, "Toasts (Notifications)", expanded=False)
        toast_section.pack(fill="x", pady=2)
        self._build_toasts(toast_section.content)

        records = CollapsibleSection(frame, "Records & Duplicate Check", expanded=False)
        records.pack(fill="x", pady=2)
        self._build_records(records.content)

    # -------------------------------
    # General
    # -------------------------------
    def _build_general(self, frame):
        row = 0

        ctk.CTkLabel(frame, text="Theme:").grid(row=row, column=0, sticky="w")

        theme_cb = ctk.CTkComboBox(frame, variable=self.theme_selector_var, values=c.theme_modes, width=self.width,
                                   state="readonly", command=self._update_application_theme)

        theme_cb.grid(row=row, column=1, sticky="w")

        row += 1

        ctk.CTkLabel(frame, text="Font Family:").grid(row=row, column=0, sticky="w")
        font_cb = ctk.CTkComboBox(frame, variable=self.font_selector_var, values=c.available_fonts, width=self.width)
        font_cb.grid(row=row, column=1, sticky="w")
        self.font_selector_var.trace_add("write", self._update_application_font)
        row += 1

        ctk.CTkLabel(frame, text="(Experimental)", font=make_font(12, "bold")).grid(row=row, column=0, sticky="w",
                                                                                    pady=(5, 0))
        row += 1

        ctk.CTkCheckBox(frame, text="Enable HDR Filtering", variable=self.enable_hdr_filtering_var,
                        command=self._toggle_hdr).grid(row=row, column=0, columnspan=2, sticky="w")

    # -------------------------------
    # Player & League
    # -------------------------------
    def _build_player(self, frame):
        row = 0

        ctk.CTkLabel(frame, text="PoE Profile (player#1234):").grid(row=row, column=0, sticky="w")
        self.poe_entry = ctk.CTkEntry(frame, textvariable=self.poe_player_var, width=self.width)
        self.poe_entry.grid(row=row, column=1, sticky="w")
        self.poe_entry.configure(validate="key",
                                 validatecommand=(self.poe_entry.register(self._validate_poe_live), "%P"))
        self.poe_player_var.trace_add("write", self._update_tracker_poe_player)
        row += 1

        ctk.CTkLabel(frame, text="(poe.ninja) Data League:").grid(row=row, column=0, sticky="w")
        league_cb = ctk.CTkComboBox(frame, variable=self.data_league_var, values=c.LEAGUES_TO_FETCH, width=self.width)
        league_cb.grid(row=row, column=1, sticky="w")
        self.data_league_var.trace_add("write", self._on_data_league_change)

    # -------------------------------
    # PoE Ladder
    # -------------------------------
    def _build_poeladder(self, frame):
        row = 0

        self.poeladder_label = ctk.CTkLabel(frame, text="How to setup", font=make_font(9, "bold", underline=True),
                                            cursor="hand2")
        self.poeladder_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 5))
        self.poeladder_label.bind("<Button-1>", self.open_poeladder_link)
        row += 1

        ctk.CTkCheckBox(frame, text="Enable Integration", variable=self.enable_poeladder_var,
                        command=self._toggle_poeladder).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        ctk.CTkLabel(frame, text="Collection League:").grid(row=row, column=0, sticky="w")

        self.dynamic_data_league_cb = ctk.CTkComboBox(
            frame,
            variable=self.dynamic_data_league_var,
            values=self.poeladder_leagues,
            width=self.width,
            state="normal" if self.enable_poeladder_var.get() else "disabled"
        )
        self.dynamic_data_league_cb.grid(row=row, column=1, sticky="w")
        self.dynamic_data_league_var.trace_add("write", self._on_dynamic_league_change)
        row += 1

        fetch_btn_state = "normal" if self.enable_poeladder_var.get() else "disabled"
        self.fetch_collection_btn = ctk.CTkButton(frame, text="Fetch Collection", state=fetch_btn_state,
                                                  command=self._fetch_poeladder, width=self.long_width)
        self.fetch_collection_btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # -------------------------------
    # Capture / OCR
    # -------------------------------
    def _build_capture(self, frame):
        row = 0

        ctk.CTkLabel(frame, text="Layout Capture Area (% of screen):").grid(row=row, column=0, sticky="w")
        area_entry = ctk.CTkEntry(frame, textvariable=self.top_right_target_area_percent_var, width=self.width)
        area_entry.grid(row=row, column=1, sticky="w")
        self.top_right_target_area_percent_var.trace_add("write", self._update_top_right_target_area_percent)

        row += 1

        ctk.CTkLabel(
            frame,
            text="OCR Capture Region:"
        ).grid(
            row=row,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        self.ocr_region_label = ctk.CTkLabel(
            frame,
            text=self._get_ocr_region_description()
        )
        self.ocr_region_label.grid(
            row=row,
            column=1,
            sticky="w",
            pady=(10, 0)
        )

        row += 1

        ctk.CTkLabel(
            frame,
            text="OCR Region Preset:"
        ).grid(
            row=row,
            column=0,
            sticky="w",
            pady=(10, 0)
        )

        self.ocr_region_preset_var = ctk.StringVar(
            value=get_setting(
                "Application",
                "ocr_region_preset",
                c.DEFAULT_OCR_REGION_PRESET
            )
        )

        preset_cb = ctk.CTkComboBox(
            frame,
            variable=self.ocr_region_preset_var,
            values=list(c.OCR_REGION_PRESETS.keys()),
            width=self.width,
            state="readonly",
            command=self._apply_ocr_region_preset
        )

        preset_cb.grid(
            row=row,
            column=1,
            sticky="w",
            pady=(10, 0)
        )

        row += 1

        configure_btn = ctk.CTkButton(
            frame,
            text="Configure OCR Region",
            width=self.long_width,
            command=self._open_ocr_region_editor
        )
        configure_btn.grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0)
        )

    # -------------------------------
    # Toasts
    # -------------------------------
    def _build_toasts(self, frame):
        row = 0

        ctk.CTkCheckBox(frame, text="Enable Toasts", variable=self.toasts_var, command=self._toggle_toasts).grid(
            row=row, column=0, columnspan=2, sticky="w"
        )
        row += 1

        ctk.CTkLabel(frame, text="Position:").grid(row=row, column=0, sticky="w")
        toast_position_cb = ctk.CTkComboBox(frame, variable=self.toasts_position_var,
                                            values=c.VALID_TOAST_POSITIONS, width=self.width)
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

        ctk.CTkLabel(frame, text="Duration (sec):").grid(row=row, column=0, sticky="w")
        duration_entry = ctk.CTkEntry(frame, textvariable=self.toasts_duration_var, width=self.width)
        duration_entry.grid(row=row, column=1, sticky="w")
        self.toasts_duration_var.trace_add("write", self._update_toasts_duration)
        row += 1

        ctk.CTkLabel(frame, text="Toast Image Width (px):").grid(row=row, column=0, sticky="w")
        image_width_entry = ctk.CTkEntry(frame, textvariable=self.toast_image_width_var, width=self.width)
        image_width_entry.grid(row=row, column=1, sticky="w")
        image_width_entry.bind("<Return>", lambda e: self._update_toast_image_width())
        image_width_entry.bind("<FocusOut>", lambda e: self._update_toast_image_width())
        row += 1

        ctk.CTkLabel(frame, text="Toast Image Height (px):").grid(row=row, column=0, sticky="w")
        image_height_entry = ctk.CTkEntry(frame, textvariable=self.toast_image_height_var, width=self.width)
        image_height_entry.grid(row=row, column=1, sticky="w")
        image_height_entry.bind("<Return>", lambda e: self._update_toast_image_height())
        image_height_entry.bind("<FocusOut>", lambda e: self._update_toast_image_height())
        row += 1

        ctk.CTkLabel(frame, text="Toast Font Size:").grid(row=row, column=0, sticky="w")
        font_size_entry = ctk.CTkEntry(frame, textvariable=self.toast_font_size_var, width=self.width)
        font_size_entry.grid(row=row, column=1, sticky="w")
        font_size_entry.bind("<Return>", lambda e: self._update_toast_font_size())
        font_size_entry.bind("<FocusOut>", lambda e: self._update_toast_font_size())
        row += 1

        ctk.CTkLabel(frame, text="Toast Headline Font Size:").grid(row=row, column=0, sticky="w")
        headline_font_size_entry = ctk.CTkEntry(frame, textvariable=self.toast_headline_font_size_var, width=self.width)
        headline_font_size_entry.grid(row=row, column=1, sticky="w")
        headline_font_size_entry.bind("<Return>", lambda e: self._update_toast_headline_font_size())
        headline_font_size_entry.bind("<FocusOut>", lambda e: self._update_toast_headline_font_size())
        row += 1

        ctk.CTkLabel(frame, text="Collection Missing Color:").grid(row=row, column=0, sticky="w")

        self.color_preview = ctk.CTkFrame(frame, width=60, height=25, fg_color=self.collection_missing_color_var.get())
        self.color_preview.grid(row=row, column=1, sticky="w", padx=(0, 10))

        pick_btn = ctk.CTkButton(frame, text="Pick", width=60, command=self._pick_collection_color)
        pick_btn.grid(row=row, column=1, sticky="e")
        row += 1

        self.example_toast_btn = ctk.CTkButton(frame, text="SHOW EXAMPLE",
                                               command=self._toggle_example_toast, width=self.long_width)
        self.example_toast_btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 5))
        row += 1

        reset_toasts_btn = ctk.CTkButton(frame, text="Reset Toast Settings", fg_color="#8B0000",
                                         hover_color="#A00000", command=self._reset_toast_settings,
                                         width=self.long_width)
        reset_toasts_btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 5))

    # -------------------------------
    # Records / Duplicates
    # -------------------------------
    def _build_records(self, frame):
        row = 0

        ctk.CTkLabel(frame, text="CSV Current Record:").grid(row=row, column=0, sticky="w")
        csv_record_entry = ctk.CTkEntry(frame, state="disabled", textvariable=self.csv_current_record_number_var,
                                        width=self.width)
        csv_record_entry.grid(row=row, column=1, sticky="w")
        row += 1

        ctk.CTkLabel(frame, text="JSON Current Record:").grid(row=row, column=0, sticky="w")
        json_record_entry = ctk.CTkEntry(frame, state="disabled", textvariable=self.json_current_record_number_var,
                                         width=self.width)
        json_record_entry.grid(row=row, column=1, sticky="w")
        row += 1

        ctk.CTkLabel(frame, text="Seconds Between Dupe Checks:").grid(row=row, column=0, sticky="w")
        row += 1

        dupe_slider = ctk.CTkSlider(frame, from_=c.MIN_DUPE_DURATION, to=c.MAX_DUPE_DURATION,
                                    variable=self.dupe_duration)
        dupe_slider.grid(row=row, column=0, sticky="w", pady=(10, 0))
        dupe_slider.bind("<ButtonRelease-1>", lambda e: self._update_dupe_slider())

        self.dupe_label = ctk.CTkLabel(frame, text=f"{self.dupe_duration.get()}s")
        self.dupe_label.grid(row=row, column=1, sticky="w", padx=10, pady=(10, 0))

    # -------------------------------
    # Validation / Links
    # -------------------------------
    def _validate_poe_live(self, proposed_value):
        if re.match(r"^[A-Za-z0-9_#]*$", proposed_value):
            return True

        self.parent.bell()
        return False

    def open_poeladder_link(self, event=None):
        webbrowser.open(
            "https://poeladder.com/faqs#How_do_I_know_which_item_to_pick_from_a_Curio_box_when_I_run_a_Grand_Heist_Wing"
        )

    # -------------------------------
    # Application Handlers
    # -------------------------------
    def _update_application_theme(self, val):
        if not val:
            return

        log_message(
            "Theme Selector",
            val
        )

        set_setting(
            "Application",
            "theme_mode",
            val
        )

        settings_window = self.settings_window

        if not settings_window:
            return

        settings_window.after(
            100,
            lambda: self._apply_theme_safely(val)
        )

    def _apply_theme_safely(self, val):
        settings_window = self.settings_window

        if not settings_window:
            return

        try:
            if not settings_window.winfo_exists():
                return
        except Exception:
            return

        try:
            settings_window.grab_release()
        except Exception:
            pass

        apply_theme(val)

        settings_window.after(
            100,
            self._restore_settings_window
        )

    def _restore_settings_window(self):
        settings_window = self.settings_window

        if not settings_window:
            return

        try:
            if not settings_window.winfo_exists():
                return

            settings_window.deiconify()
            settings_window.lift()

            center_window_on_parent(
                settings_window,
                self.parent
            )

            settings_window.grab_set()
            settings_window.focus_force()

        except Exception as error:
            log_message(
                "Theme Switch",
                f"Failed to restore settings window: {error}"
            )

    def _update_application_font(self, *_):
        new_family = self.font_selector_var.get()
        if not new_family:
            return

        set_setting("Application", "font_family", new_family)

        from fonts import font_family_var, _ensure_font_var

        _ensure_font_var(master=self.parent)
        font_family_var.set(new_family)
        update_all_fonts(self.parent)

    def _toggle_hdr(self):
        enabled = self.enable_hdr_filtering_var.get()
        set_setting("Application", "is_hdr_filtering_enabled", enabled)
        log_message("HDR", enabled)
        c.IS_HDR_ENABLED = enabled

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

        width = max(c.TOAST_IMAGE_WIDTH_MIN, min(c.TOAST_IMAGE_WIDTH_MAX, width))

        self.toast_image_width_var.set(str(width))
        toasts.set_toast_image_width(width, self.parent)

    def _update_toast_image_height(self, *_):
        val = self.toast_image_height_var.get().strip()

        try:
            height = int(val)
        except ValueError:
            height = c.DEFAULT_TOAST_IMAGE_HEIGHT

        height = max(c.TOAST_IMAGE_HEIGHT_MIN, min(c.TOAST_IMAGE_HEIGHT_MAX, height))

        self.toast_image_height_var.set(str(height))
        toasts.set_toast_image_height(height, self.parent)

    def _update_toast_font_size(self, *_):
        val = self.toast_font_size_var.get().strip()

        try:
            size = int(val)
        except ValueError:
            size = c.DEFAULT_TOAST_FONT_SIZE

        size = max(c.TOAST_FONT_SIZE_MIN, min(c.TOAST_FONT_SIZE_MAX, size))

        self.toast_font_size_var.set(str(size))
        toasts.set_toast_font_size(size, self.parent)

    def _update_toast_headline_font_size(self, *_):
        val = self.toast_headline_font_size_var.get().strip()

        try:
            size = int(val)
        except ValueError:
            size = c.DEFAULT_TOAST_HEADLINE_FONT_SIZE

        size = max(c.TOAST_HEADLINE_FONT_SIZE_MIN, min(c.TOAST_HEADLINE_FONT_SIZE_MAX, size))

        self.toast_headline_font_size_var.set(str(size))
        toasts.set_toast_headline_font_size(size, self.parent)

    def _update_toasts_duration(self, *_):
        val = self.toasts_duration_var.get().strip()

        if not val:
            return

        try:
            dur = int(val)
        except ValueError:
            return

        set_setting("Application", "toasts_duration_seconds", dur)
        toasts.set_toast_duration(dur)

    def _toggle_toasts(self):
        enabled = self.toasts_var.get()
        set_setting("Application", "are_toasts_enabled", enabled)
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

        default_position = c.DEFAULT_TOAST_POSITION
        default_y = c.DEFAULT_TOAST_Y_OFFSET
        default_x = c.DEFAULT_TOAST_X_OFFSET
        default_duration = c.DEFAULT_TOAST_DURATION
        default_area = c.DEFAULT_TOP_RIGHT_CAPTURE_PERCENT
        default_enabled = c.DEFAULT_TOAST_ENABLE
        default_image_width = c.DEFAULT_TOAST_IMAGE_WIDTH
        default_image_height = c.DEFAULT_TOAST_IMAGE_HEIGHT
        default_font_size = c.DEFAULT_TOAST_FONT_SIZE
        default_headline_font_size = c.DEFAULT_TOAST_HEADLINE_FONT_SIZE

        set_setting("Application", "toast_position", default_position)
        set_setting("Application", "toast_y_offset", default_y)
        set_setting("Application", "toast_x_offset", default_x)
        set_setting("Application", "top_right_target_area_percent", default_area)
        set_setting("Application", "toasts_duration_seconds", default_duration)
        set_setting("Application", "are_toasts_enabled", default_enabled)
        set_setting("Application", "toast_image_width", default_image_width)
        set_setting("Application", "toast_image_height", default_image_height)
        set_setting("Application", "toast_font_size", default_font_size)
        set_setting("Application", "toast_headline_font_size", default_headline_font_size)

        self.toasts_position_var.set(default_position)
        self.toasts_y_offset_var.set(str(default_y))
        self.toasts_x_offset_var.set(str(default_x))
        self.top_right_target_area_percent_var.set(str(default_area))
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

        try:
            toasts.refresh_example(self.parent)
            toasts.reposition(self.parent)
        except Exception:
            pass

        log_message("Toast settings reset complete")

    # -------------------------------
    # Capture
    # -------------------------------
    def _update_top_right_target_area_percent(self, *_):
        val = self.top_right_target_area_percent_var.get()

        if val in ("", ".", "-", "+"):
            return

        try:
            percent = float(val)
        except ValueError:
            return

        percent = max(0.01, min(1.00, percent))

        if str(percent) != val:
            self.top_right_target_area_percent_var.set(str(percent))
            return

        log_message("Top Right Target Area Percent", percent)
        set_setting("Application", "top_right_target_area_percent", percent)

    def _get_ocr_region_description(self):
        left = self.ocr_region_left_var.get()
        top = self.ocr_region_top_var.get()
        right = self.ocr_region_right_var.get()
        bottom = self.ocr_region_bottom_var.get()

        area = (right - left) * (bottom - top)
        area = max(0.0, min(1.0, area))

        return f"{area * 100:.1f}% of game window"

    def _open_ocr_region_editor(self):
        OCRRegionEditor(
            parent=self.parent,
            owner=self
        )

    def _apply_ocr_region_preset(self, preset_name):
        region = c.OCR_REGION_PRESETS.get(preset_name)

        if region is None:
            return

        left, top, right, bottom = region

        self.ocr_region_left_var.set(left)
        self.ocr_region_top_var.set(top)
        self.ocr_region_right_var.set(right)
        self.ocr_region_bottom_var.set(bottom)

        set_setting("Application", "ocr_region_preset", preset_name)
        set_setting("Application", "ocr_region_left", left)
        set_setting("Application", "ocr_region_top", top)
        set_setting("Application", "ocr_region_right", right)
        set_setting("Application", "ocr_region_bottom", bottom)

        if self.ocr_region_label:
            self.ocr_region_label.configure(
                text=self._get_ocr_region_description()
            )

        log_message(
            "OCR Region Preset",
            f"{preset_name}: {left:.3f}, {top:.3f}, "
            f"{right:.3f}, {bottom:.3f}"
        )

    # -------------------------------
    # PoE Ladder
    # -------------------------------
    def _toggle_poeladder(self):
        enabled = self.enable_poeladder_var.get()
        set_setting("Application", "enable_poeladder", enabled)
        log_message("poeladder", enabled)

        fetch_btn_state = "normal" if enabled else "disabled"

        if self.fetch_collection_btn:
            self.fetch_collection_btn.configure(state=fetch_btn_state)

        if self.dynamic_data_league_cb:
            self.dynamic_data_league_cb.configure(state="normal" if enabled else "disabled")

        self.tree_manager.refresh_treeview(self.tracker)

    def _fetch_poeladder(self):
        player = self.poe_player_var.get().strip()

        if not re.match(r"^[A-Za-z0-9_]+#[0-9]{4}$", player):
            toasts.show_message(self.parent, "Invalid PoE profile! Must be in format 'player#1234'.")
            self.poe_entry.focus_set()
            return

        log_message(f"Fetching poeladder collection for {player}")
        curio_collection_fetch.run_fetch_curios_threaded(player)

        player_ladders = curio_collection_fetch.PLAYER_LADDERS.get(player, {})
        self.league_display_mapping = {**player_ladders}

        leagues = list(self.league_display_mapping.keys())
        self.dynamic_data_league_cb.configure(values=leagues)

        saved_identifier = get_setting("Application", "poeladder_ggg_league", c.FIXED_LADDER_IDENTIFIER)
        selected_name = next(
            (name for name, ident in self.league_display_mapping.items() if ident == saved_identifier),
            leagues[0] if leagues else ""
        )

        self.dynamic_data_league_var.set(selected_name)
        threading.Thread(target=self._threaded_on_league_change, daemon=True).start()
        self.tree_manager.refresh_treeview(self.tracker)

    def _threaded_on_league_change(self):
        self.parent.after(0, lambda: self.tracker.on_league_change())

    def _on_dynamic_league_change(self, *_):
        league_name = self.dynamic_data_league_var.get()
        if not league_name:
            return

        player = self.poe_player_var.get().strip()
        player_ladders = curio_collection_fetch.PLAYER_LADDERS.get(player, {})
        self.league_display_mapping = {**player_ladders}
        ladder_identifier = self.league_display_mapping.get(league_name)

        if ladder_identifier:
            set_setting("Application", "poeladder_ggg_league", league_name)
            set_setting("Application", "poeladder_league_identifier", ladder_identifier)
            log_message(f"PoELadder League set to {league_name} ({ladder_identifier})")

            self.tracker.on_league_change()
            self.tree_manager.refresh_treeview(self.tracker)

    # -------------------------------
    # Records / Player
    # -------------------------------
    def _update_dupe_slider(self):
        val = int(self.dupe_duration.get())

        if val == 0:
            return

        set_setting("Application", "time_last_dupe_check_seconds", val)
        self.dupe_label.configure(text=f"{val}s")
        self.tracker.set_duplicate_duration(val)

    def _on_data_league_change(self, *_):
        val = self.data_league_var.get()
        if not val:
            return

        set_setting("Application", "data_league", val)
        self.tracker.on_league_change()
        self.tree_manager.refresh_treeview(self.tracker)

    def _update_tracker_poe_player(self, *_):
        val = self.poe_player_var.get()
        if not val:
            return

        set_setting("User", "poe_user", val)
        self.tracker.poe_user = val
        self.tree_manager.total_frame.player_name.set(val)


# -------------------------------
# Helper Functions
# -------------------------------
def switch_mode(mode=c.DEFAULT_THEME_MODE):
    apply_theme(mode=mode)


def show_settings_popup(parent, tracker, theme_manager, tree_manager):
    SettingsPopup(parent, tracker, theme_manager, tree_manager)
