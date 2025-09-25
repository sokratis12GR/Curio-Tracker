from tkinter import ttk

def create_layout(root):
    # --- Column & row configs ---
    root.grid_columnconfigure(0, weight=0, minsize=280)  # Left panel
    root.grid_columnconfigure(1, weight=1)  # Right panel
    root.grid_columnconfigure(2, weight=1)  # Extra column
    root.grid_rowconfigure(0, weight=1)  # Main row grows
    root.grid_rowconfigure(1, weight=0)  # Bottom console row fixed

    # --- Left Frame ---
    left_frame = ttk.Frame(root)
    left_frame.grid(row=0, column=0, padx=(5, 10), pady=10, sticky="nw")

    # --- Right Frame ---
    right_frame = ttk.Frame(root)
    right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    right_frame.grid_rowconfigure(0, weight=1)  # tree_frame grows
    right_frame.grid_rowconfigure(1, weight=0)  # toggle_frame fixed
    right_frame.grid_columnconfigure(0, weight=1)

    # Tree Frame
    tree_frame = ttk.Frame(right_frame)
    tree_frame.grid(row=0, column=0, sticky="nsew")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)

    # Toggle Buttons Frame below tree_frame
    toggle_frame = ttk.Frame(right_frame)
    toggle_frame.grid(row=1, column=0, sticky="sew", pady=(5, 0))
    # Ensure it does not expand vertically
    right_frame.grid_rowconfigure(1, weight=0)

    # --- Console Frame ---
    console_frame = ttk.Frame(root)
    console_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="ew")

    return {
        "left_frame": left_frame,
        "right_frame": right_frame,
        "tree_frame": tree_frame,
        "toggle_frame": toggle_frame,
        "console_frame": console_frame,
    }