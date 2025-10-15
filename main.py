import threading
from sys import platform

import customtkinter
from customtkinter import *

from gui.item_overview_frame import ItemOverviewFrame
from logger import log_message

_original_destroy = customtkinter.CTkButton.destroy


def _safe_destroy(self, *args, **kwargs):
    try:
        _original_destroy(self, *args, **kwargs)
    except AttributeError:
        pass


from load_utils import get_datasets

import customtkinter
from customtkinter import CTk, CTkToplevel
from PIL.ImageTk import PhotoImage
from load_utils import get_resource_path

# Lazy globals
_GLOBAL_ICON = None
_GLOBAL_ICO = None


def _ensure_icons(widget):
    global _GLOBAL_ICON, _GLOBAL_ICO
    if _GLOBAL_ICON is None:
        try:
            _GLOBAL_ICON = PhotoImage(master=widget, file=get_resource_path("assets/icon.png"))
        except Exception as e:
            print(f"[WARN] Could not load PNG icon: {e}")
    if _GLOBAL_ICO is None:
        try:
            _GLOBAL_ICO = get_resource_path("assets/icon.ico")
        except Exception:
            _GLOBAL_ICO = None


def _apply_icon(widget):
    try:
        if _GLOBAL_ICON:
            widget.iconphoto(True, _GLOBAL_ICON)
        if _GLOBAL_ICO:
            widget.iconbitmap(_GLOBAL_ICO)
    except Exception:
        pass


# Save original constructors
_original_ctk_init = CTk.__init__
_original_toplevel_init = CTkToplevel.__init__


def _patched_ctk_init(self, *args, **kwargs):
    _original_ctk_init(self, *args, **kwargs)
    _ensure_icons(self)
    _apply_icon(self)
    # Reapply on idle: this helps override resets
    self.after_idle(lambda: _apply_icon(self))


def _patched_toplevel_init(self, *args, **kwargs):
    _original_toplevel_init(self, *args, **kwargs)
    _ensure_icons(self)
    _apply_icon(self)
    # For Toplevel, use a small delay to ensure icon sticks
    self.after(200, lambda: _apply_icon(self))


CTk.__init__ = _patched_ctk_init
CTkToplevel.__init__ = _patched_toplevel_init

customtkinter.CTkButton.destroy = _safe_destroy

import curio_currency_fetch as fetch_currency
import curio_keybinds
import curio_tiers_fetch as fetch_tiers
import curio_collection_fetch as fetch_collection
import curio_tracker as tracker
from config import DEBUGGING, initialize_settings, LEAGUE, TREE_COLUMNS, IS_SSF
from gui.controls import LeftFrameControls
from gui.layout import create_layout
from gui.menus import create_settings_menu
from gui.toggles import TreeToggles
from gui.treeview import CustomTreeview
from keybinds_handlers import register_handlers
from set_tesseract_path import set_tesseract_path
from settings import get_setting
from themes import CTkThemes, apply_theme
from tree_manager import TreeManager


def main():
    root = CTk()
    root.withdraw()

    loading = CTkToplevel(root)
    loading.title("Loading...")
    loading.geometry("300x120")
    loading.resizable(False, False)

    CTkLabel(loading, text="Initializing, please wait...", font=('Segoe UI', 11)).pack(pady=20)
    progress = CTkProgressBar(loading, mode='indeterminate')
    progress.pack(fill="x", padx=20)
    progress.start()

    # Center the popup
    loading.update_idletasks()
    w = loading.winfo_width()
    h = loading.winfo_height()
    x = (loading.winfo_screenwidth() // 2) - (w // 2)
    y = (loading.winfo_screenheight() // 2) - (h // 2)
    loading.geometry(f"{w}x{h}+{x}+{y}")

    def initialize_app():
        try:
            player = get_setting("User", "poe_user", tracker.poe_user)
            fetch_tiers.run_fetch_curios()
            fetch_collection.run_fetch_curios_threaded(player)
            load_data()
            schedule_auto_update(root, player)
            set_tesseract_path()
            tracker.init_csv()
            initialize_settings()
        finally:
            root.after(0, finish_loading)

    def finish_loading():
        progress.stop()
        loading.destroy()
        root.deiconify()
        theme_mode = get_setting('Application', 'theme_mode', "DARK")
        theme_manager = CTkThemes()
        apply_theme(theme_mode)
        start_main_app(root, theme_mode, theme_manager)

    threading.Thread(target=initialize_app, daemon=True).start()
    root.mainloop()


def start_main_app(root, theme_mode, theme_manager):
    root.title("Heist Curio Tracker")
    root.geometry("1020x650")
    root.resizable(True, True)

    if platform.startswith("win"):
        root.after(200, lambda: root.iconbitmap(get_resource_path("assets/icon.ico")))

    tracker.poe_user = get_setting("User", "poe_user", tracker.poe_user)
    tracker.league_version = get_setting("User", "poe_league", tracker.league_version)
    tracker.blueprint_layout = get_setting("Blueprint", "layout", tracker.blueprint_layout)
    tracker.blueprint_area_level = get_setting("Blueprint", "area_level", tracker.blueprint_area_level)
    tracker.on_league_change()

    layout = create_layout(root)
    treeview = CustomTreeview(layout['tree_frame'], theme_mode, TREE_COLUMNS)
    tree = treeview.tree
    left_frame = layout['left_frame']
    right_frame = layout['right_frame']
    tree_manager = TreeManager(tree, theme_mode)

    for col in tree_manager.tree_columns:
        tree.heading(col["id"], command=lambda c=col["id"]: tree_manager.sort_tree(c))

    toggle_frame = layout['toggle_frame']
    tree_toggles = TreeToggles(toggle_frame, tree, tree_manager)
    tree_toggles.frame.grid(row=0, column=0, sticky="e", padx=5)

    left_controls = LeftFrameControls(
        parent=left_frame,
        tracker=tracker,
        tree_manager=tree_manager,
        tree=tree,
    )
    left_controls.refresh_ui()

    row_index = left_controls.get_current_row()
    # info_panel = InfoPanel(parent=left_frame, row_index_start=row_index)
    # row_index = info_panel.get_current_row()
    item_overview = ItemOverviewFrame(left_frame, row_index_start=row_index)
    tree_manager.bind_overview(item_overview)

    menu_bar = create_settings_menu(
        root,
        tracker=tracker,
        theme_manager=theme_manager,
        tree_manager=tree_manager,
        update_info_callback=None,
    )

    handlers = register_handlers(root, tree_manager, controls=left_controls)
    curio_keybinds.handlers = handlers

    curio_keybinds.init_from_settings()
    curio_keybinds.start_global_listener()

    try:
        import inputs
        if inputs.devices.gamepads:
            curio_keybinds.start_controller_thread()
        else:
            if DEBUGGING:
                print("[INFO] No controller detected. Skipping controller thread.")
    except Exception as e:
        if DEBUGGING:
            print(f"[WARN] Could not initialize controller thread: {e}")

    root.mainloop()


UPDATE_INTERVAL_MS = 30 * 60 * 1000  # 30 minutes in milliseconds

def schedule_auto_update(root, player):

    def auto_fetch():
        threading.Thread(target=fetch_collection.run_fetch_curios_threaded, args=(player,), daemon=True).start()
        root.after(UPDATE_INTERVAL_MS, auto_fetch)

    # Start the first update
    root.after(0, auto_fetch)


def load_data(force_refresh=False):
    try:
        log_message("[INFO] Starting data load...")

        if not fetch_currency.IS_FETCHING:
            fetch_currency.run_fetch(force=force_refresh)

        if fetch_currency.IS_FETCHING:
            log_message("[INFO] Waiting for currency fetch to finish...")
            fetch_currency.FETCH_DONE.wait()

        datasets = get_datasets(force_reload=True)
        tracker.full_currency = datasets.get("currency", {})
        tracker.collection_dataset = datasets.get("collection", {})
        tracker.on_league_change()

        log_message("[INFO] Data load complete.")

        return datasets

    except Exception as e:
        log_message(f"[ERROR] Data load failed: {e}")
        return None


if __name__ == "__main__":
    main()
