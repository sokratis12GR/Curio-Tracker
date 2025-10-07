import tkinter as tk

from gui import about_popup, keybinds_popup  # your popup modules
from gui.settings_popup import show_settings_popup
from update_checker import check_for_updates


def create_settings_menu(root, theme_manager, tracker, toggle_theme_callback, update_info_callback, reload_tree_for_league=None):
    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)

    settings_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="File", menu=settings_menu)

    settings_menu.add_command(
        label="Keybinds",
        command=lambda: keybinds_popup.show_keybind_popup(root, update_labels_callback=update_info_callback)
    )


    settings_menu.add_command(label="Toggle Theme (Light/Dark)", command=toggle_theme_callback)
    settings_menu.add_command(
        label="About",
        command=lambda: about_popup.show_about_popup(root, theme_manager)
    )
    settings_menu.add_separator()
    settings_menu.add_command(
        label="Settings",
        command=lambda: show_settings_popup(root, tracker=tracker, on_league_change_callback=reload_tree_for_league)
    )
    settings_menu.add_separator()
    settings_menu.add_command(
        label="Check for Updates",
        command=lambda: check_for_updates(root, theme_manager)
    )
    settings_menu.add_separator()
    settings_menu.add_command(label="Exit", command=root.destroy)

    return menu_bar
