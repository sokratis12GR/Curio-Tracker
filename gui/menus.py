import threading

import customtkinter as ctk
import requests

import config
from csv_to_json import csv_to_nested_json
from gui import keybinds_popup
from gui.about_popup import CustomAboutPopup
from gui.settings_popup import show_settings_popup
from settings import get_setting, set_setting
from tree_manager import TreeManager
from update_checker import check_for_updates, show_update_popup, version_tuple
from version_utils import VERSION

def create_settings_menu(tabview, tracker, theme_manager, tree_manager: TreeManager, update_info_callback):
    menu_frame = ctk.CTkFrame(tabview, corner_radius=0)
    menu_frame.grid(row=0, column=0, sticky="w", padx=5)

    def handle_selection(choice):
        if choice == "Keybinds":
            keybinds_popup.show_keybind_popup(tabview, update_labels_callback=update_info_callback)
        elif choice == "About":
            CustomAboutPopup(tabview)
        elif choice == "Settings":
            show_settings_popup(tabview, tracker, theme_manager, tree_manager)
        elif choice == "Export to JSON":
            csv_to_nested_json(config.data_file_base + ".csv")
        elif choice == "Exit":
            tabview.winfo_toplevel().destroy() # close main window

        menu_dropdown.set("File")

    file_menu_items = ["Keybinds", "About", "Settings",
                       "Export to JSON",
                       "Exit"]

    menu_dropdown = ctk.CTkOptionMenu(
        master=menu_frame,
        values=file_menu_items,
        command=handle_selection,
        width=100,
        anchor="w"
    )
    menu_dropdown.set("File")
    menu_dropdown.pack(side="left")

    # def check_updates():
    #     original_text = update_button.cget("text")
    #     update_button.configure(text="Checking...", state="disabled")
    #
    #     def worker():
    #         try:
    #             url = "https://api.github.com/repos/sokratis12GR/Curio-Tracker/releases/latest"
    #             response = requests.get(url, timeout=5)
    #             response.raise_for_status()
    #             data = response.json()
    #
    #             latest = data.get("tag_name", "").strip()
    #             if not latest:
    #                 tabview.after(0, lambda: update_button.configure(text="No version info", state="normal"))
    #                 return
    #
    #             if version_tuple(latest) > version_tuple(VERSION):
    #                 # update found
    #                 tabview.after(0, lambda: update_button.configure(text=f"Update {latest}!", state="normal"))
    #                 # also show popup
    #                 tabview.after(0, lambda: show_update_popup(tabview, latest, data.get("html_url", "")))
    #             else:
    #                 # already latest
    #                 tabview.after(0, lambda: update_button.configure(text="Up to date ✔", state="normal"))
    #
    #         except Exception:
    #             tabview.after(0, lambda: update_button.configure(text="Check Failed", state="normal"))
    #
    #     threading.Thread(target=worker, daemon=True).start()

    buttons_frame = ctk.CTkFrame(menu_frame, fg_color="transparent")
    buttons_frame.pack(side="left", padx=(5, 0))

    update_button = ctk.CTkButton(
        buttons_frame,
        text="Check for Updates",
        width=100,
        command=lambda: check_for_updates(tabview, show_uptodate_popup=True)
    )
    update_button.pack(side="left", padx=(0, 5))

    saved_mode = get_setting("Application", "export_mode", default="CSV")
    csv_json_mode = {"mode": saved_mode}

    def toggle_csv_json():
        if csv_json_mode["mode"] == "CSV":
            csv_json_mode["mode"] = "JSON"
        else:
            csv_json_mode["mode"] = "CSV"

        csv_json_button.configure(text=f"Data: {csv_json_mode['mode']}")
        set_setting("Application", "export_mode", csv_json_mode["mode"])

        from curio_tracker import reload_data_manager
        _data_mgr = reload_data_manager()
        tree_manager.switch_data_manager(_data_mgr)

    csv_json_button = ctk.CTkButton(
        buttons_frame,
        text=f"Data: {csv_json_mode['mode']}",
        command=toggle_csv_json,
        width=80
    )
    csv_json_button.pack(side="left")

    return menu_frame
