from customtkinter import CTkFrame


def create_layout(root):
    root.grid_columnconfigure(0, weight=0, minsize=280)  # Left panel
    root.grid_columnconfigure(1, weight=1)  # Right panel
    root.grid_columnconfigure(2, weight=1)  # Extra column
    root.grid_rowconfigure(0, weight=0)  # Top frame (menu/toolbar)
    root.grid_rowconfigure(1, weight=1)  # Main row grows (left + right frames)

    # --- Top Frame (menu/toolbar) ---
    top_frame = CTkFrame(root, height=0, corner_radius=0)
    top_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5)

    # --- Left Frame ---
    left_frame = CTkFrame(root)
    left_frame.grid(row=1, column=0, padx=(5, 10), pady=10, sticky="nw")

    # --- Right Frame ---
    right_frame = CTkFrame(root)
    right_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
    right_frame.grid_rowconfigure(0, weight=1)
    right_frame.grid_rowconfigure(1, weight=0)
    right_frame.grid_columnconfigure(0, weight=0)
    right_frame.grid_columnconfigure(1, weight=1)

    # Tree Frame
    tree_frame = CTkFrame(right_frame)
    tree_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)
    tree_frame.configure(width=600, height=400)

    # Toggle Buttons Frame below tree_frame
    toggle_frame = CTkFrame(right_frame)
    toggle_frame.grid(row=1, column=0, sticky="sw", pady=(5, 0))

    total_frame = CTkFrame(right_frame)
    total_frame.grid(row=1, column=1, sticky="w", pady=(5, 0))

    return {
        "top_frame": top_frame,
        "left_frame": left_frame,
        "right_frame": right_frame,
        "tree_frame": tree_frame,
        "toggle_frame": toggle_frame,
        "total_frame": total_frame
    }
