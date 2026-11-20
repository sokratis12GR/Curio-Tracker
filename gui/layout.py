from customtkinter import CTkFrame

MARGIN = 8  # Outer window margin shared by all panels
GAP = 6     # Spacing between neighbouring panels


def create_layout(root):
    root.grid_columnconfigure(0, weight=0, minsize=280)  # Left panel
    root.grid_columnconfigure(1, weight=1)  # Right panel
    root.grid_columnconfigure(2, weight=1)  # Extra column
    root.grid_rowconfigure(0, weight=0)  # Top frame (menu/toolbar)
    root.grid_rowconfigure(1, weight=1)  # Main row grows (left + right frames)

    # --- Top Frame (menu/toolbar) ---
    top_frame = CTkFrame(root, height=0, corner_radius=6)
    top_frame.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=MARGIN, pady=(MARGIN, GAP))

    # --- Left Frame ---
    left_frame = CTkFrame(root)
    left_frame.grid(row=1, column=0, padx=(MARGIN, GAP), pady=(0, MARGIN), sticky="nsw")

    # --- Right Frame: page switch on top, active page below ---
    right_frame = CTkFrame(root)
    right_frame.grid(row=1, column=1, columnspan=2, padx=(0, MARGIN), pady=(0, MARGIN), sticky="nsew")
    right_frame.grid_rowconfigure(0, weight=0)
    right_frame.grid_rowconfigure(1, weight=1)
    right_frame.grid_columnconfigure(0, weight=1)

    page_bar = CTkFrame(right_frame, fg_color="transparent")
    page_bar.grid(row=0, column=0, sticky="we", pady=(0, GAP))
    page_bar.grid_columnconfigure(1, weight=1)

    # Tracker page (tree + actions + toggles + totals)
    tracker_page = CTkFrame(right_frame, fg_color="transparent", corner_radius=0)
    tracker_page.grid(row=1, column=0, sticky="nsew")
    tracker_page.grid_rowconfigure(0, weight=1)
    tracker_page.grid_rowconfigure(1, weight=0)
    tracker_page.grid_columnconfigure(0, weight=0)
    tracker_page.grid_columnconfigure(1, weight=1)

    tree_frame = CTkFrame(tracker_page, corner_radius=0)
    tree_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)
    tree_frame.configure(width=600, height=400)

    actions_frame = CTkFrame(tracker_page)
    actions_frame.grid(row=1, column=0, columnspan=2, sticky="sw", pady=(5, 0))
    actions_frame.grid_columnconfigure(0, weight=1)

    toggle_frame = CTkFrame(tracker_page, corner_radius=8)
    toggle_frame.grid(row=2, column=0, sticky="nsew", pady=(GAP, 0), padx=(0, GAP))

    total_frame = CTkFrame(tracker_page, corner_radius=8)
    total_frame.grid(row=2, column=1, sticky="nsew", pady=(GAP, 0))

    # Summary page shares the cell; only one page is gridded at a time.
    summary_page = CTkFrame(right_frame, fg_color="transparent", corner_radius=0)
    summary_page.grid_rowconfigure(0, weight=1)
    summary_page.grid_columnconfigure(0, weight=1)

    return {
        "page_bar": page_bar,
        "tracker_page": tracker_page,
        "summary_page": summary_page,
        "top_frame": top_frame,
        "left_frame": left_frame,
        "right_frame": right_frame,
        "tree_frame": tree_frame,
        "actions_frame": actions_frame,
        "toggle_frame": toggle_frame,
        "total_frame": total_frame
    }
