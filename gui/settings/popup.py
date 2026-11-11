import json

import customtkinter as ctk

import config as c
import curio_collection_fetch
import toasts
from fonts import make_font, init_font_var
from load_utils import get_datasets
from logger import log_message
from settings import get_setting, set_setting
from themes import apply_theme
from tree_manager import TreeManager
from win_utils import center_window_on_parent, prepare_popup

from gui.settings.common import CollapsibleSection, _safe_combo_values, _safe_json_dict_setting, _safe_float_setting
from gui.settings.general import GeneralSettingsMixin
from gui.settings.player import PlayerSettingsMixin
from gui.settings.capture import CaptureSettingsMixin
from gui.settings.toasts import ToastSettingsMixin
from gui.settings.records import RecordsSettingsMixin


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
        prepare_popup(self.popup)
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


# -------------------------------
# Unified Settings
# -------------------------------
class UnifiedSettingsSection(
    GeneralSettingsMixin,
    PlayerSettingsMixin,
    CaptureSettingsMixin,
    ToastSettingsMixin,
    RecordsSettingsMixin,
):
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
        self.toast_fade_out_var = ctk.BooleanVar(value=toasts.TOAST_FADE_OUT)
        self.toast_monitor_choices = toasts.get_monitor_choices()
        saved_monitor = toasts.TOAST_MONITOR
        if saved_monitor not in self.toast_monitor_choices:
            # Match by monitor number in case the resolution changed.
            prefix = saved_monitor.split(":")[0] + ":"
            saved_monitor = next(
                (m for m in self.toast_monitor_choices if m.startswith(prefix)),
                "Primary",
            )
        self.toast_monitor_var = ctk.StringVar(value=saved_monitor)

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
# Helper Functions
# -------------------------------
def switch_mode(mode=c.DEFAULT_THEME_MODE):
    apply_theme(mode=mode)


def show_settings_popup(parent, tracker, theme_manager, tree_manager):
    SettingsPopup(parent, tracker, theme_manager, tree_manager)
