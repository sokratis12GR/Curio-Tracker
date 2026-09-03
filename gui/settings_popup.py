import json
import math
import re
import webbrowser
from tkinter import colorchooser

import customtkinter as ctk
from PIL import Image, ImageGrab, ImageTk

import config as c
import curio_collection_fetch
import toasts
from fonts import update_all_fonts, make_font, init_font_var
from img_utils import get_local_image
from load_utils import get_datasets
from logger import log_message
from settings import get_setting, set_setting
from themes import apply_theme
from tree_manager import TreeManager
from win_utils import center_window_on_parent, get_poe_bbox


def _safe_combo_values(values, fallback=None):
    cleaned = []

    if values is not None:
        try:
            iterable = list(values)
        except (TypeError, ValueError):
            iterable = []

        for value in iterable:
            if value is None:
                continue

            text = str(value).strip()

            if not text:
                continue

            if text not in cleaned:
                cleaned.append(text)

    if not cleaned and fallback is not None:
        fallback_text = str(fallback).strip()

        if fallback_text:
            cleaned.append(fallback_text)

    return cleaned


def _safe_json_dict_setting(section, key):
    value = get_setting(section, key, {})

    if isinstance(value, dict):
        return value

    if not value:
        return {}

    try:
        parsed = json.loads(value)

        if isinstance(parsed, dict):
            return parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    return {}


def _safe_float_setting(section, key, default, minimum=0.0, maximum=1.0):
    value = get_setting(
        section,
        key,
        default
    )

    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(default)

    value = max(
        minimum,
        min(maximum, value)
    )

    return value


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

        try:
            self.app_section._hide_top_right_capture_area()
        except Exception:
            pass

        self.popup.destroy()


class OCRRegionEditor:
    PREVIEW_MAX_WIDTH = 900
    PREVIEW_MAX_HEIGHT = 600

    def __init__(self, parent, owner):
        self.parent = parent
        self.owner = owner

        self.window = None

        self.drag_start_x = None
        self.drag_start_y = None

        self.rect_id = None
        self.rect_coords = None

        self.preview_image = None
        self.tk_image = None

        self.preview_width = 0
        self.preview_height = 0

        self.using_example_image = False

        self._capture_preview()

        self.window = ctk.CTkToplevel(parent)
        self.window.title("Configure OCR Region")
        self.window.resizable(False, False)

        self.window.transient(parent)

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self._close
        )

        self._build_ui()
        self._draw_saved_region()

        self.window.update_idletasks()

        center_window_on_parent(
            self.window,
            parent
        )

        self.window.lift()
        self.window.grab_set()
        self.window.focus_force()

    def _close(self):
        try:
            if self.window:
                self.window.grab_release()
        except Exception:
            pass

        try:
            if self.window:
                self.window.destroy()
        except Exception:
            pass

        try:
            if self.parent and self.parent.winfo_exists():
                self.parent.deiconify()
                self.parent.lift()
                self.parent.grab_set()
                self.parent.focus_force()
        except Exception:
            pass

    def _capture_preview(self):
        bbox = get_poe_bbox()

        if c.DEBUGGING:
            log_message(
                "OCR Region",
                f"PoE bbox returned: {bbox!r}"
            )

        if not bbox:
            log_message(
                "OCR Region",
                "Path of Exile window not found. Using example image."
            )

            screenshot = get_local_image(
                "assets/ocr_example.jpeg"
            )

            if screenshot is None:
                raise RuntimeError(
                    "Could not locate Path of Exile window and "
                    "the example OCR image could not be loaded."
                )

            self.using_example_image = True

        else:
            self.using_example_image = False

            left, top, right, bottom = bbox

            screenshot = ImageGrab.grab(
                bbox=(
                    int(left),
                    int(top),
                    int(right),
                    int(bottom)
                )
            )

        original_width, original_height = screenshot.size

        scale = min(
            self.PREVIEW_MAX_WIDTH / original_width,
            self.PREVIEW_MAX_HEIGHT / original_height,
            1.0
        )

        self.preview_width = int(
            original_width * scale
        )

        self.preview_height = int(
            original_height * scale
        )

        self.preview_image = screenshot.resize(
            (
                self.preview_width,
                self.preview_height
            ),
            Image.Resampling.LANCZOS
        )

        if c.DEBUGGING:
            log_message(
                "OCR Region",
                (
                    f"Using {'example' if self.using_example_image else 'live'} image | "
                    f"preview={self.preview_width}x{self.preview_height}"
                )
            )

    def _build_ui(self):
        self.tk_image = ImageTk.PhotoImage(
            self.preview_image,
            master=self.window
        )

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

        instruction_text = (
            "Drag over the area that should be processed by OCR."
        )

        if self.using_example_image:
            instruction_text += (
                "\nPath of Exile was not detected, so an example image is being used."
            )

        ctk.CTkLabel(
            container,
            text=instruction_text,
            justify="left"
        ).pack(
            anchor="w",
            pady=(0, 8)
        )

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
            command=self._close
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

        self._close()

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
        self.poeladder_leagues = _safe_combo_values(
            self.leagues_dict.keys()
        )

        self.theme_selector_var = ctk.StringVar(value=get_setting("Application", "theme_mode", c.DEFAULT_THEME_MODE))

        self.top_right_target_area_percent_var = ctk.StringVar(
            value=str(get_setting("Application", "top_right_target_area_percent", c.DEFAULT_TOP_RIGHT_CAPTURE_PERCENT))
        )

        self.top_right_target_capture_preview_window = None

        self.ocr_region_left_var = ctk.DoubleVar(
            value=_safe_float_setting(
                "Application",
                "ocr_region_left",
                c.DEFAULT_OCR_REGION_LEFT
            )
        )

        self.ocr_region_top_var = ctk.DoubleVar(
            value=_safe_float_setting(
                "Application",
                "ocr_region_top",
                c.DEFAULT_OCR_REGION_TOP
            )
        )

        self.ocr_region_right_var = ctk.DoubleVar(
            value=_safe_float_setting(
                "Application",
                "ocr_region_right",
                c.DEFAULT_OCR_REGION_RIGHT
            )
        )

        self.ocr_region_bottom_var = ctk.DoubleVar(
            value=_safe_float_setting(
                "Application",
                "ocr_region_bottom",
                c.DEFAULT_OCR_REGION_BOTTOM
            )
        )

        self.ocr_region_label = None

        self.toasts_position_var = ctk.StringVar(
            value=get_setting("Application", "toast_position", c.DEFAULT_TOAST_POSITION))
        self.toasts_y_offset_var = ctk.StringVar(
            value=str(get_setting("Application", "toast_y_offset", c.DEFAULT_TOAST_Y_OFFSET)))
        self.toasts_x_offset_var = ctk.StringVar(
            value=str(get_setting("Application", "toast_x_offset", c.DEFAULT_TOAST_X_OFFSET)))
        self.toasts_var = ctk.BooleanVar(value=toasts.ARE_TOASTS_ENABLED)
        self.toasts_duration_var = ctk.StringVar(value=str(toasts.TOASTS_DURATION))

        saved_toast_size_preset = str(
            get_setting("Application", "toast_size_preset", c.DEFAULT_TOAST_SIZE_PRESET) or "").strip()

        valid_toast_presets = [*c.TOAST_SIZE_PRESETS.keys(), "Custom"]

        if saved_toast_size_preset not in valid_toast_presets:
            saved_toast_size_preset = "Custom"

        self.toast_size_preset_var = ctk.StringVar(value=saved_toast_size_preset)

        self.toast_custom_size_frame = None

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
        self.data_league_values = _safe_combo_values(
            c.LEAGUES_TO_FETCH,
            fallback="Standard"
        )

        saved_data_league = get_setting(
            "Application",
            "data_league",
            c.LEAGUE
        )

        if saved_data_league is None:
            saved_data_league = ""

        saved_data_league = str(saved_data_league).strip()

        if saved_data_league not in self.data_league_values:
            saved_data_league = self.data_league_values[0]

            set_setting(
                "Application",
                "data_league",
                saved_data_league
            )

        if c.DEBUGGING:
            log_message(
                "Settings",
                (
                    f"Raw LEAGUES_TO_FETCH={c.LEAGUES_TO_FETCH!r} | "
                    f"Sanitized={self.data_league_values!r} | "
                    f"Selected={saved_data_league!r}"
                )
            )

        self.data_league_var = ctk.StringVar(value=saved_data_league)

        self.poe_player_var = ctk.StringVar(value=get_setting("User", "poe_user", ""))

        self.enable_hdr_filtering_var = ctk.BooleanVar(
            value=get_setting("Application", "is_hdr_filtering_enabled", c.IS_HDR_ENABLED))

        self.dupe_duration = ctk.IntVar(value=get_setting("Application", "time_last_dupe_check_seconds", 60))

        self.font_selector_var = ctk.StringVar(value=get_setting("Application", "font_family", "Segoe UI"))

        self.collection_missing_color_var = ctk.StringVar(
            value=get_setting("Application", "collection_missing_color", "#FF0000"))

        current_profile = self.poe_player_var.get().strip()

        self.poeladder_cached_profile = str(get_setting("Application", "poeladder_cached_profile", "") or "").strip()

        self.league_display_mapping = _safe_json_dict_setting("Application", "poeladder_league_mapping")

        in_memory_mapping = {}

        if current_profile:
            in_memory_mapping = dict(curio_collection_fetch.PLAYER_LADDERS.get(current_profile, {}))

        if in_memory_mapping:
            self.league_display_mapping = in_memory_mapping
            self.poeladder_cached_profile = current_profile

            set_setting("Application", "poeladder_cached_profile", current_profile)

            set_setting("Application", "poeladder_league_mapping", json.dumps(self.league_display_mapping))

        elif self.poeladder_cached_profile != current_profile:
            self.league_display_mapping = {}

        saved_collection_league = str(get_setting("Application", "poeladder_collection_league", "") or "").strip()
        if not saved_collection_league:
            saved_collection_league = str(get_setting("Application", "poeladder_ggg_league", "") or "").strip()

        saved_collection_identifier = str(get_setting("Application", "poeladder_league_identifier", "") or "").strip()

        if not saved_collection_league and saved_collection_identifier:
            saved_collection_league = next((name for name, identifier in self.league_display_mapping.items() if
                                            identifier == saved_collection_identifier), "")

        if self.league_display_mapping:
            self.poeladder_leagues = _safe_combo_values(self.league_display_mapping.keys())

        if saved_collection_league and self.league_display_mapping and saved_collection_league not in self.league_display_mapping:
            saved_collection_league = ""

        if not saved_collection_league:
            saved_collection_league = (self.poeladder_leagues[0] if self.poeladder_leagues else "")

        self.dynamic_data_league_var = ctk.StringVar(value=saved_collection_league)

    def build(self, frame):
        self.settings_window = frame.winfo_toplevel()

        sections = [
            ("General", True, self._build_general),
            ("Player & League", True, self._build_player),
            ("Capture / OCR", False, self._build_capture),
            ("Toasts (Notifications)", False, self._build_toasts),
            ("Records & Duplicate Check", False, self._build_records),
        ]

        for title, expanded, builder in sections:
            section = CollapsibleSection(
                frame,
                title,
                expanded=expanded
            )

            section.pack(
                fill="x",
                pady=2
            )

            try:
                if c.DEBUGGING:
                    log_message(
                        "Settings",
                        f"Building section: {title}"
                    )

                builder(section.content)

                if c.DEBUGGING:
                    log_message(
                        "Settings",
                        f"Built section successfully: {title}"
                    )

            except Exception as error:
                import traceback

                log_message(
                    "Settings",
                    (
                        f"Failed to build section {title}: {error}\n"
                        f"{traceback.format_exc()}"
                    )
                )

                if not section.expanded:
                    section.expanded = True

                    section.content.pack(
                        fill="x",
                        padx=8,
                        pady=(5, 8)
                    )

                    section._update_header()

                ctk.CTkLabel(
                    section.content,
                    text=(
                        "This section could not be loaded.\n"
                        "See the application log for details."
                    ),
                    justify="left"
                ).pack(
                    anchor="w",
                    pady=5
                )

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

        # --------------------------------
        # poe.ninja league
        # --------------------------------
        ctk.CTkLabel(frame, text="Pricing League:").grid(row=row, column=0, sticky="w", pady=(6, 0))

        league_cb = ctk.CTkComboBox(frame, variable=self.data_league_var, values=self.data_league_values,
                                    width=self.width, state="readonly")

        league_cb.grid(row=row, column=1, sticky="w", pady=(6, 0))

        self.data_league_var.trace_add("write", self._on_data_league_change)

        row += 1

        ctk.CTkLabel(frame, text="PoE Ladder Collection", font=make_font(12, "bold")
                     ).grid(row=row, column=0, sticky="w", pady=(5, 3))

        self.poeladder_label = ctk.CTkLabel(frame, text="How to setup", font=make_font(11, "bold", underline=True),
                                            cursor="hand2")
        self.poeladder_label.grid(row=row, column=1, sticky="w")

        self.poeladder_label.bind("<Button-1>", self.open_poeladder_link)

        row += 1

        already_fetched = (bool(
            self.poe_player_var.get().strip()) and self.poeladder_cached_profile == self.poe_player_var.get().strip() and bool(
            self.league_display_mapping))

        fetch_enabled = (self.enable_poeladder_var.get() and not already_fetched)

        self.fetch_collection_btn = ctk.CTkButton(frame, text=(
            "Collection Fetched" if already_fetched else "Fetch Collection"),
                                                  state=("normal" if fetch_enabled else "disabled"),
                                                  command=self._fetch_poeladder, width=self.long_width)

        self.fetch_collection_btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))

        row += 1

        ctk.CTkCheckBox(frame, text="Enable PoELadder | Collection", variable=self.enable_poeladder_var,
                        command=self._toggle_poeladder).grid(row=row, column=0, sticky="w", pady=(8, 0))

        poeladder_values = _safe_combo_values(
            self.league_display_mapping.keys() if self.league_display_mapping else self.poeladder_leagues)

        if not poeladder_values:
            poeladder_values = [""]

        selected = self.dynamic_data_league_var.get().strip()

        if selected and selected not in poeladder_values:
            poeladder_values.insert(0, selected)

        self.dynamic_data_league_cb = ctk.CTkComboBox(frame, variable=self.dynamic_data_league_var,
                                                      values=poeladder_values, width=self.width, state=(
                "readonly" if self.enable_poeladder_var.get() else "disabled"))

        self.dynamic_data_league_cb.grid(row=row, column=1, sticky="w", pady=(8, 0))

        self.dynamic_data_league_var.trace_add("write", self._on_dynamic_league_change)

    # -------------------------------
    # Capture / OCR
    # -------------------------------
    def _build_capture(self, frame):
        row = 0

        def section_title(text, pady=(0, 5)):
            nonlocal row

            ctk.CTkLabel(
                frame,
                text=text,
                font=make_font(12, "bold")
            ).grid(
                row=row,
                column=0,
                columnspan=2,
                sticky="w",
                pady=pady
            )

            row += 1

        def field_label(text, pady=(0, 0)):
            ctk.CTkLabel(
                frame,
                text=text
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=pady
            )

        # --------------------------------------------------
        # OCR region
        # --------------------------------------------------
        section_title("OCR Capture Region")

        field_label("Capture Area:")

        self.ocr_region_label = ctk.CTkLabel(
            frame,
            text=self._get_ocr_region_description()
        )

        self.ocr_region_label.grid(
            row=row,
            column=1,
            sticky="w"
        )

        row += 1

        field_label(
            "Preset:",
            pady=(6, 0)
        )

        self.ocr_region_preset_var = ctk.StringVar(
            value=get_setting(
                "Application",
                "ocr_region_preset",
                c.DEFAULT_OCR_REGION_PRESET
            )
        )

        ctk.CTkComboBox(
            frame,
            variable=self.ocr_region_preset_var,
            values=list(c.OCR_REGION_PRESETS.keys()),
            width=self.width,
            state="readonly",
            command=self._apply_ocr_region_preset
        ).grid(
            row=row,
            column=1,
            sticky="w",
            pady=(6, 0)
        )

        row += 1

        ctk.CTkButton(
            frame,
            text="Configure OCR Region",
            width=self.long_width,
            command=self._open_ocr_region_editor
        ).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0)
        )

        row += 1

        # --------------------------------------------------
        # Layout capture
        # --------------------------------------------------
        section_title(
            "Blueprint Layout Capture",
            pady=(14, 5)
        )

        field_label("Top Right Area %:")

        ctk.CTkEntry(
            frame,
            textvariable=self.top_right_target_area_percent_var,
            width=self.width
        ).grid(
            row=row,
            column=1,
            sticky="w"
        )

        self.top_right_target_area_percent_var.trace_add(
            "write",
            self._update_top_right_target_area_percent
        )

        row += 1

        ctk.CTkButton(
            frame,
            text="Visualise Capture Area",
            width=self.long_width,
            command=self._visualise_top_right_capture_area
        ).grid(
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

        # Persist values.
        set_setting("Application", "toast_image_width", image_width)

        set_setting("Application", "toast_image_height", image_height)

        set_setting("Application", "toast_font_size", font_size)

        set_setting("Application", "toast_headline_font_size", headline_font_size)

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

        default_size_preset = c.DEFAULT_TOAST_SIZE_PRESET
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

        set_setting("Application", "toast_size_preset", default_size_preset)
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

        self.toast_size_preset_var.set(default_size_preset)
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
        self._update_toast_custom_visibility()

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

        try:
            OCRRegionEditor(
                parent=settings_window,
                owner=self
            )

        except Exception as error:
            import traceback

            log_message(
                "OCR Region",
                (
                    f"Failed to open OCR region editor: {error}\n"
                    f"{traceback.format_exc()}"
                )
            )

            try:
                settings_window.grab_set()
                settings_window.lift()
                settings_window.focus_force()
            except Exception:
                pass

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

        log_message("PoE Ladder", enabled)

        if self.dynamic_data_league_cb:
            self.dynamic_data_league_cb.configure(state=("readonly" if enabled else "disabled"))

        self._refresh_poeladder_fetch_state()

        self.tree_manager.refresh_treeview(self.tracker)

    def _fetch_poeladder(self):
        player = self.poe_player_var.get().strip()

        if not re.match(r"^[A-Za-z0-9_]+#[0-9]{4}$", player):
            toasts.show_message(
                self.parent,
                "Invalid PoE profile! Must be in format 'player#1234'."
            )

            if self.poe_entry:
                self.poe_entry.focus_set()

            return

        log_message(
            "PoE Ladder",
            f"Fetching collection for {player}"
        )

        if self.fetch_collection_btn:
            self.fetch_collection_btn.configure(state="disabled", text="Fetching...")

        curio_collection_fetch.PLAYER_LADDERS.pop(
            player,
            None
        )

        try:
            curio_collection_fetch.run_fetch_curios_threaded(player, force=True)
        except Exception as error:
            log_message(
                "PoE Ladder",
                f"Failed to start collection fetch: {error}"
            )

            if self.fetch_collection_btn:
                self.fetch_collection_btn.configure(state="normal", text="Fetch Collection")

            return

        self._wait_for_poeladder_fetch(player, attempt=0)

    def _wait_for_poeladder_fetch(self, player, attempt=0):
        current_player = self.poe_player_var.get().strip()

        if current_player != player:
            self._refresh_poeladder_fetch_state()
            return

        player_ladders = (
            curio_collection_fetch.PLAYER_LADDERS.get(
                player,
                {}
            )
        )

        if player_ladders:
            self._complete_poeladder_fetch(
                player,
                player_ladders
            )
            return

        # Around 30 seconds total.
        max_attempts = 120

        if attempt >= max_attempts:
            log_message(
                "PoE Ladder",
                f"Timed out waiting for collection fetch for {player}"
            )

            if self.fetch_collection_btn:
                self.fetch_collection_btn.configure(
                    state="normal",
                    text="Fetch Collection"
                )

            return

        self.parent.after(
            250,
            lambda: self._wait_for_poeladder_fetch(
                player,
                attempt + 1
            )
        )

    def _complete_poeladder_fetch(self, player, player_ladders):
        self.league_display_mapping = dict(player_ladders)

        leagues = list(self.league_display_mapping.keys())

        self.poeladder_cached_profile = player

        set_setting("Application", "poeladder_cached_profile", player)

        set_setting("Application", "poeladder_league_mapping", json.dumps(self.league_display_mapping))

        saved_name = str(get_setting("Application", "poeladder_collection_league", "") or "").strip()

        saved_identifier = str(get_setting("Application", "poeladder_league_identifier", "") or "").strip()

        selected_name = ""

        if saved_name in self.league_display_mapping:
            selected_name = saved_name

        elif saved_identifier:
            selected_name = next(
                (
                    name
                    for name, identifier
                    in self.league_display_mapping.items()
                    if identifier == saved_identifier
                ),
                ""
            )

        if not selected_name and leagues:
            selected_name = leagues[0]

        if self.dynamic_data_league_cb:
            self.dynamic_data_league_cb.configure(values=leagues)

        if selected_name:
            self.dynamic_data_league_var.set(selected_name)

            self._save_poeladder_league(selected_name)

        if self.fetch_collection_btn:
            self.fetch_collection_btn.configure(state="disabled", text="Collection Fetched")

        log_message(
            "PoE Ladder",
            (
                f"Collection fetched for {player}; "
                f"{len(leagues)} league(s)"
            )
        )

        self.tracker.on_league_change()

        self.tree_manager.refresh_treeview(self.tracker)

    def _threaded_on_league_change(self):
        self.parent.after(0, lambda: self.tracker.on_league_change())

    def _on_dynamic_league_change(self, *_):
        league_name = (self.dynamic_data_league_var.get().strip())

        if not league_name:
            return

        self._save_poeladder_league(league_name)

    def _save_poeladder_league(self, league_name):
        ladder_identifier = (self.league_display_mapping.get(league_name))

        # Try the in-memory fetch result too.
        if not ladder_identifier:
            player = self.poe_player_var.get().strip()

            player_ladders = (curio_collection_fetch.PLAYER_LADDERS.get(player, {}))

            ladder_identifier = (player_ladders.get(league_name))

            if player_ladders:
                self.league_display_mapping = dict(player_ladders)

        set_setting("Application", "poeladder_collection_league", league_name)
        set_setting("Application", "poeladder_ggg_league", league_name)

        if ladder_identifier:
            set_setting("Application", "poeladder_league_identifier", ladder_identifier)

            log_message(
                "PoE Ladder",
                (
                    f"Collection league set to "
                    f"{league_name} "
                    f"({ladder_identifier})"
                )
            )
        else:
            log_message(
                "PoE Ladder",
                (
                    f"Collection league name saved as "
                    f"{league_name}; no identifier available"
                )
            )

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
        val = self.data_league_var.get().strip()

        if not val:
            return

        if val not in self.data_league_values:
            log_message(
                "Settings",
                f"Ignoring invalid data league selection: {val!r}"
            )
            return

        set_setting(
            "Application",
            "data_league",
            val
        )

        self.tracker.on_league_change()

        self.tree_manager.refresh_treeview(
            self.tracker
        )

    def _update_tracker_poe_player(self, *_):
        val = self.poe_player_var.get().strip()

        set_setting("User", "poe_user", val)

        self.tracker.poe_user = val

        try:
            self.tree_manager.total_frame.player_name.set(
                val
            )
        except Exception:
            pass

        self._refresh_poeladder_fetch_state()

    def _refresh_poeladder_fetch_state(self):
        if not self.fetch_collection_btn:
            return

        player = self.poe_player_var.get().strip()

        enabled = self.enable_poeladder_var.get()

        fetched_for_current_profile = (
                bool(player) and player == self.poeladder_cached_profile and bool(self.league_display_mapping))

        if not enabled:
            self.fetch_collection_btn.configure(state="disabled", text="Fetch Collection")
            return

        if fetched_for_current_profile:
            self.fetch_collection_btn.configure(state="disabled", text="Collection Fetched")
        else:
            self.fetch_collection_btn.configure(state="normal", text="Fetch Collection")

    def _mark_toast_size_custom(self):
        if self.toast_size_preset_var.get() == "Custom":
            return

        self.toast_size_preset_var.set("Custom")

        set_setting("Application", "toast_size_preset", "Custom")

        self._update_toast_custom_visibility()

    def _visualise_top_right_capture_area(self):
        # Toggle existing preview off.
        if self.top_right_target_capture_preview_window:
            self._hide_top_right_capture_area()
            return

        try:
            percent = float(
                self.top_right_target_area_percent_var.get()
            )
        except (TypeError, ValueError):
            percent = c.DEFAULT_TOP_RIGHT_CAPTURE_PERCENT

        percent = max(
            0.01,
            min(1.0, percent)
        )

        screen_width = self.parent.winfo_screenwidth()
        screen_height = self.parent.winfo_screenheight()

        aspect_ratio = (c.TOP_RIGHT_CUT_WIDTH / c.TOP_RIGHT_CUT_HEIGHT)

        total_area = (screen_width * screen_height)

        target_area = (total_area * percent)

        capture_height = math.sqrt(target_area / aspect_ratio)

        capture_width = (capture_height * aspect_ratio)

        capture_width = int(capture_width)
        capture_height = int(capture_height)

        capture_width = min(screen_width, capture_width)

        capture_height = min(screen_height, capture_height)

        x = screen_width - capture_width
        y = 0

        try:
            if self.settings_window and self.settings_window.winfo_exists():
                self.settings_window.grab_release()
        except Exception:
            pass

        preview = ctk.CTkToplevel(
            self.parent
        )

        self.top_right_target_capture_preview_window = preview

        preview.overrideredirect(True)

        preview.attributes("-topmost", True)

        try:
            preview.attributes("-alpha", 0.72)
        except Exception:
            pass

        preview.geometry(
            f"{capture_width}x{capture_height}+{x}+{y}"
        )

        # One consistent background color.
        capture_bg = "#300000"

        preview.configure(fg_color=capture_bg)

        border = ctk.CTkFrame(
            preview,
            fg_color=capture_bg,
            border_width=3,
            border_color="#FF4040",
            corner_radius=0
        )

        border.pack(fill="both", expand=True)

        title_label = ctk.CTkLabel(
            border,
            text="Layout Capture Area",
            font=make_font(
                12,
                "bold"
            ),
            text_color="#FFFFFF",
            fg_color=capture_bg
        )

        title_label.place(relx=0.5, rely=0.27, anchor="center")

        size_label = ctk.CTkLabel(
            border,
            text=(
                f"{percent * 100:.1f}%"
                f"  •  "
                f"{capture_width}×{capture_height}px"
            ),
            font=make_font(
                10,
                "bold"
            ),
            text_color="#FFFFFF",
            fg_color=capture_bg
        )

        size_label.place(relx=0.5, rely=0.52, anchor="center")

        close_label = ctk.CTkLabel(border, text="Click here to close", font=make_font(9), text_color="#D0D0D0",
                                   fg_color=capture_bg, cursor="hand2")

        close_label.place(relx=0.5, rely=0.75, anchor="center")

        def close_preview(_event=None):
            self._hide_top_right_capture_area()

        preview.bind("<Button-1>", close_preview)

        border.bind("<Button-1>", close_preview)

        title_label.bind("<Button-1>", close_preview)

        size_label.bind("<Button-1>", close_preview)

        close_label.bind("<Button-1>", close_preview)

        preview.lift()

        try:
            preview.focus_force()
        except Exception:
            pass

    def _hide_top_right_capture_area(self):
        preview = self.top_right_target_capture_preview_window

        self.top_right_target_capture_preview_window = None

        if preview:
            try:
                if preview.winfo_exists():
                    preview.destroy()
            except Exception:
                pass

        try:
            if self.settings_window and self.settings_window.winfo_exists():
                self.settings_window.lift()
                self.settings_window.grab_set()
                self.settings_window.focus_force()
        except Exception:
            pass


# -------------------------------
# Helper Functions
# -------------------------------
def switch_mode(mode=c.DEFAULT_THEME_MODE):
    apply_theme(mode=mode)


def show_settings_popup(parent, tracker, theme_manager, tree_manager):
    SettingsPopup(parent, tracker, theme_manager, tree_manager)
