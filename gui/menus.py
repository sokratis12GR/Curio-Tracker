import customtkinter as ctk

from gui import keybinds_popup
from gui.about_popup import CustomAboutPopup
from gui.settings_popup import show_settings_popup
from update_checker import check_for_updates
# from csv_to_json import csv_to_json


def create_settings_menu(tabview, tracker, theme_manager, tree_manager, update_info_callback):
    menu_frame = ctk.CTkFrame(tabview, corner_radius=0)
    menu_frame.grid(row=0, column=0, sticky="w", padx=5)

    def handle_selection(choice):
        if choice == "Keybinds":
            keybinds_popup.show_keybind_popup(tabview, update_labels_callback=update_info_callback)
        elif choice == "About":
            CustomAboutPopup(tabview)
        elif choice == "Settings":
            show_settings_popup(tabview, tracker, theme_manager, tree_manager)
        # elif choice == "Check for Updates":
        #     check_for_updates(tabview)
        # elif choice == "Convert to JSON":
        #     csv_to_json("all_valid_heist_terms.csv")
        elif choice == "Exit":
            tabview.master.destroy()  # close main window

        menu_dropdown.set("File")

    file_menu_items = ["Keybinds", "About", "Settings",
                       # "Convert to JSON",
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

    def check_updates():
        check_for_updates(tabview)

    button = ctk.CTkButton(menu_frame, text="Check for Updates", command=check_updates)
    button.pack(side="left", padx=(5,0))

    return menu_frame
