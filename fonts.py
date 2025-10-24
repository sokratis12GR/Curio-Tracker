import customtkinter as ctk
from customtkinter import CTkFont
from settings import get_setting

font_family_var: ctk.StringVar = None

def init_font_var(master):
    global font_family_var
    font_family_var = ctk.StringVar(
        master=master,
        value=get_setting("Application", "font_family", "Segoe UI")
    )

def _ensure_font_var(master=None):
    global font_family_var
    if font_family_var is None:
        font_family_var = ctk.StringVar(
            master=master,
            value=get_setting("Application", "font_family", "Segoe UI")
        )

def make_font(size: int, weight: str = "normal", underline=False):
    _ensure_font_var()
    font_family = get_setting("Application", "font_family", "Segoe UI")
    return CTkFont(family=font_family, size=size, weight=weight, underline=underline)

def update_all_fonts(widget):
    try:
        current_font = widget.cget("font")
        if isinstance(current_font, CTkFont):
            size = current_font.cget("size")
            weight = current_font.cget("weight")
            underline = current_font.cget("underline")
        else:
            size = 12
            weight = "normal"
            underline = False

        widget.configure(font=make_font(size=size, weight=weight, underline=underline))
    except Exception:
        pass

    for child in widget.winfo_children():
        update_all_fonts(child)
