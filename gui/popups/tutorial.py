import json
import urllib.request
from pathlib import Path

from customtkinter import *

import curio_keybinds
import config as c
from config import data_file_base
from fonts import make_font
from load_utils import get_data_path, get_resource_path
from logger import log_message
from win_utils import center_window_on_parent, prepare_popup


def is_first_run():
    """A user is new if they have no saved matches file in either format."""
    base = Path(data_file_base)
    return not (base.with_suffix(".csv").exists() or base.with_suffix(".json").exists())


TUTORIAL_FILE = "assets/tutorial.json"

KEY_DEFAULTS = {
    "capture_key": "f2",
    "exit_key": "f3",
    "snippet_key": "f4",
    "layout_capture_key": "f5",
    "duplicate_latest_key": "alt+1",
    "delete_latest_key": "alt+2",
    "show_highest_value_key": "alt+s",
    "cycle_bp_enchantment_key": "alt+4",
}

FALLBACK_PAGES = [(
    "Welcome to Heist Curio Tracker!",
    "The tutorial content could not be loaded.\n\n"
    "See the README on GitHub for setup and usage instructions.",
)]


class _KeyMap(dict):
    # Leave unknown placeholders untouched instead of raising.
    def __missing__(self, key):
        return "{" + key + "}"


def _current_keys():
    return _KeyMap({
        name: str(getattr(curio_keybinds, name, None) or default).upper()
        for name, default in KEY_DEFAULTS.items()
    })


def _is_valid(data):
    return isinstance(data, dict) and isinstance(data.get("pages"), list) and bool(data["pages"])


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if _is_valid(data) else None
    except Exception:
        return None


def refresh_tutorial(timeout=3):
    """Fetch the site copy into the local cache. Safe to call from a worker thread."""
    try:
        with urllib.request.urlopen(c.tutorial_url, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log_message(f"[INFO] Tutorial remote fetch failed: {e}")
        return None

    if not _is_valid(data):
        log_message("[WARN] Remote tutorial.json has an unexpected format; ignoring.")
        return None

    try:
        with open(get_data_path(c.tutorial_cache_file_name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_message(f"[WARN] Could not cache tutorial.json: {e}")
    return data


def _build_pages():
    # Load order: cached site copy -> bundled copy -> fallback page.
    data = (_read_json(get_data_path(c.tutorial_cache_file_name))
            or _read_json(get_resource_path(TUTORIAL_FILE)))
    if not data:
        log_message("[ERROR] No valid tutorial.json found; showing fallback page.")
        return FALLBACK_PAGES

    keys = _current_keys()
    pages = []
    for p in data["pages"]:
        if not isinstance(p, dict):
            continue
        try:
            pages.append((str(p.get("title", "")).format_map(keys),
                          str(p.get("body", "")).format_map(keys)))
        except (ValueError, IndexError) as e:
            log_message(f"[WARN] Bad placeholder in tutorial page: {e}")
            pages.append((str(p.get("title", "")), str(p.get("body", ""))))
    return pages or FALLBACK_PAGES


class TutorialPopup:
    def __init__(self, parent):
        self.parent = parent
        self.pages = _build_pages()
        self.index = 0

        self.popup = CTkToplevel(parent)
        prepare_popup(self.popup)
        self.popup.title("Getting Started")
        self.popup.resizable(False, False)
        self.popup.transient(parent.winfo_toplevel())
        self.popup.protocol("WM_DELETE_WINDOW", self._close)
        self.popup.bind("<Escape>", lambda e: self._close())

        frame = CTkFrame(self.popup)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.title_label = CTkLabel(frame, text="", font=make_font(16, "bold"), anchor="w")
        self.title_label.pack(fill="x", padx=15, pady=(15, 5))

        self.body_label = CTkLabel(frame, text="", font=make_font(12), justify="left",
                                   anchor="nw", wraplength=440, width=460, height=200)
        self.body_label.pack(fill="both", expand=True, padx=15, pady=5)

        nav = CTkFrame(frame, fg_color="transparent")
        nav.pack(fill="x", padx=15, pady=(5, 15))

        self.skip_btn = CTkButton(nav, text="Skip", width=80, fg_color="transparent",
                                  border_width=1, command=self._close)
        self.skip_btn.pack(side="left")

        self.step_label = CTkLabel(nav, text="")
        self.step_label.pack(side="left", expand=True)

        self.next_btn = CTkButton(nav, text="Next", width=80, command=self._next)
        self.next_btn.pack(side="right")
        self.back_btn = CTkButton(nav, text="Back", width=80, command=self._back)
        self.back_btn.pack(side="right", padx=(0, 5))

        self._render()
        center_window_on_parent(self.popup, parent)
        self.popup.focus_force()

    def _render(self):
        title, body = self.pages[self.index]
        last = self.index == len(self.pages) - 1
        self.title_label.configure(text=title)
        self.body_label.configure(text=body)
        self.step_label.configure(text=f"Step {self.index + 1} of {len(self.pages)}")
        self.back_btn.configure(state="normal" if self.index > 0 else "disabled")
        self.next_btn.configure(text="Finish" if last else "Next")

    def _next(self):
        if self.index >= len(self.pages) - 1:
            self._close()
            return
        self.index += 1
        self._render()

    def _back(self):
        if self.index > 0:
            self.index -= 1
            self._render()

    def _close(self):
        self.popup.destroy()


def show_tutorial_popup(parent):
    return TutorialPopup(parent)
