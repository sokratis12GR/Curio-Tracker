import customtkinter as ctk

import config
from csv_to_json import csv_to_nested_json
from gui import keybinds_popup
from gui.about_popup import CustomAboutPopup
from gui.data_tools_popup import show_data_tools_popup
from gui.settings_popup import show_settings_popup
from settings import get_setting, set_setting
from tree_manager import TreeManager
from update_checker import check_for_updates


def create_settings_menu(tabview, tracker, theme_manager, tree_manager: TreeManager, update_info_callback):
    menu_frame = ctk.CTkFrame(tabview, corner_radius=0)
    menu_frame.grid(row=0, column=0, sticky="nw", padx=5, pady=5)

    def handle_selection(choice):
        if choice == "Keybinds":
            keybinds_popup.show_keybind_popup(tabview, update_labels_callback=update_info_callback)
        elif choice == "About":
            CustomAboutPopup(tabview)
        elif choice == "Settings":
            show_settings_popup(tabview, tracker, theme_manager, tree_manager)
        elif choice == "Data Tools":
            show_data_tools_popup(tabview, tree_manager)
        elif choice == "Export to JSON":
            csv_to_nested_json(config.data_file_base + ".csv")
        elif choice == "Exit":
            tabview.winfo_toplevel().destroy()

        menu_dropdown.set("File")

    file_menu_items = ["Keybinds", "About", "Settings",
                       "Data Tools",
                       "Export to JSON",
                       "Exit"]

    menu_dropdown = ctk.CTkOptionMenu(
        master=menu_frame,
        values=file_menu_items,
        command=handle_selection,
        width=100,
        anchor="nw"
    )
    menu_dropdown.set("File")
    menu_dropdown.pack(side="left")

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
