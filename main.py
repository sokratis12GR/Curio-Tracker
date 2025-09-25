import tkinter as tk
from tkinter import ttk

import curio_keybinds
import curio_tracker as tracker
from config import ROW_HEIGHT
from gui.controls import LeftFrameControls
from gui.info_frame import InfoPanel
from gui.layout import create_layout
from gui.menus import create_settings_menu
from gui.toggles import TreeToggles, ToastsToggles
from gui.treeview import setup_tree
from keybinds_handlers import register_handlers
from load_utils import get_resource_path
from settings import get_setting, set_setting
from themes import Themes
from tree_manager import TreeManager
import curio_currency_fetch as fetch_currency
import curio_tiers_fetch as fetch_tiers
import ocr_utils as utils

import config as c

def main():
    fetch_currency.run_fetch()
    fetch_tiers.run_fetch_curios()
    utils.set_tesseract_path()
    tracker.init_csv()
    c.initialize_settings()

    root = tk.Tk()
    root.title("Heist Curio Tracker")

    icon_img = tk.PhotoImage(file=get_resource_path("assets/icon.png"))
    root.iconphoto(True, icon_img)
    root.geometry("1020x650")
    # root.protocol("WM_DELETE_WINDOW", handle_exit)
    root.resizable(True, True)

    is_dark_mode = get_setting('Application', 'is_dark_mode', True)  # default: dark mode enabled

    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    style.configure('TFrame', background='#f4f6f8')
    style.configure('TLabel', background='#f4f6f8', font=('Segoe UI', 10))
    style.configure('Header.TLabel', font=('Segoe UI', 11, 'bold'))
    style.configure('TButton', padding=6)
    style.configure('Small.TLabel', font=('Segoe UI', 9))
    style.configure("Treeview", rowheight=ROW_HEIGHT, padding=0)

    theme_manager = Themes(root, style)

    # GUI layout
    layout = create_layout(root)

    # Capture console setup
    # console_output = setup_console(layout['console_frame']) - Disabled for now, feels unnecessary.
    tree = setup_tree(layout['tree_frame'])
    left_frame = layout['left_frame']
    right_frame = layout['right_frame']
    tree_manager = TreeManager(tree, is_dark_mode)
    for col in tree_manager.tree_columns:
        tree.heading(col["id"], command=lambda c=col["id"]: tree_manager.sort_tree(c))

    toggle_frame = layout['toggle_frame']
    tree_toggles = TreeToggles(toggle_frame, tree, tree_manager)
    tree_toggles.frame.grid(row=0, column=0, sticky="w", padx=5)
    theme_manager.tree_toggles = tree_toggles

    toasts_toggles = ToastsToggles(toggle_frame)
    toasts_toggles.frame.grid(row=0, column=1, sticky="w", padx=5)
    theme_manager.register(toasts_toggles.toasts_checkbox, "buttons")
    theme_manager.register(toasts_toggles.toasts_duration_spinbox, "spinboxes")

    tracker.poe_user = get_setting("User", "poe_user", tracker.poe_user)
    tracker.league_version = get_setting("User", "poe_league", tracker.league_version)
    tracker.blueprint_layout = get_setting("Blueprint", "layout", tracker.blueprint_layout)
    tracker.blueprint_area_level = get_setting("Blueprint", "area_level", tracker.blueprint_area_level)

    def toggle_theme():
        nonlocal is_dark_mode
        is_dark_mode = not is_dark_mode
        set_setting('Application', 'is_dark_mode', is_dark_mode)
        tree_manager.reapply_row_formatting()
        theme_manager.apply_theme(is_dark_mode=is_dark_mode)

    left_controls = LeftFrameControls(
        parent=left_frame,
        theme_manager=theme_manager,
        tracker=tracker,
        tree_manager=tree_manager,
        tree=tree,
    )
    left_controls.refresh_ui()

    row_index = left_controls.get_current_row()
    info_panel = InfoPanel(parent=left_frame, theme_manager=theme_manager, row_index_start=row_index)
    theme_manager.register(info_panel.frame, "frames")
    for lbl in info_panel.labels.values():
        theme_manager.register(lbl, "labels")

    menu_bar = create_settings_menu(root, theme_manager, toggle_theme, info_panel)

    menu_bar = create_settings_menu(
        root,
        theme_manager,
        toggle_theme_callback=toggle_theme,
        update_info_callback=info_panel.update_labels
    )

    handlers = register_handlers(root, tree_manager, controls=left_controls)
    curio_keybinds.handlers = handlers

    curio_keybinds.init_from_settings()
    curio_keybinds.start_global_listener()

    theme_manager.apply_theme(is_dark_mode=is_dark_mode)

    root.mainloop()


if __name__ == "__main__":
    main()
