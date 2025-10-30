import customtkinter as ctk

from gui import keybinds_popup
from gui.about_popup import CustomAboutPopup
from gui.settings_popup import show_settings_popup
from update_checker import check_for_updates


def create_settings_menu(root, tracker, theme_manager, tree_manager, update_info_callback):
    menu_frame = ctk.CTkFrame(root, corner_radius=0)

    try:
        uses_grid = len(root.grid_slaves()) > 0
    except Exception:
        uses_grid = False

    if uses_grid:
        menu_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5)
    else:
        menu_frame.pack(fill="x")

    def handle_selection(choice):
        if choice == "Keybinds":
            keybinds_popup.show_keybind_popup(root, update_labels_callback=update_info_callback)
        elif choice == "About":
            CustomAboutPopup(root)
        elif choice == "Settings":
            show_settings_popup(root, tracker, theme_manager, tree_manager)
        elif choice == "Check for Updates":
            check_for_updates(root)
        elif choice == "Exit":
            root.destroy()

        menu_dropdown.set("File")

    file_menu_items = [
        "Keybinds",
        "About",
        "Settings",
        "Check for Updates",
        "Exit"
    ]

    menu_dropdown = ctk.CTkOptionMenu(
        master=menu_frame,
        values=file_menu_items,
        command=handle_selection,
        width=100,
        anchor="w",
    )

    menu_dropdown.set("File")
    menu_dropdown.pack(side="left")

    return menu_frame
