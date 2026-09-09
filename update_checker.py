import queue
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import customtkinter as ctk
import requests

from fonts import make_font
from markdown_utils import render_markdown_to_frame
from version_utils import VERSION


GITHUB_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/"
    "sokratis12GR/Curio-Tracker/releases/latest"
)

UPDATE_POPUP_WIDTH = 520
UPDATE_POPUP_HEIGHT = 680

CHECK_POPUP_WIDTH = 360
CHECK_POPUP_HEIGHT = 180


def version_tuple(version: str):
    version = version.strip().lower().lstrip("v")

    parts = []

    for part in version.split("."):
        digits = ""

        for char in part:
            if char.isdigit():
                digits += char
            else:
                break

        parts.append(
            int(digits) if digits else 0
        )

    return tuple(parts)


def get_parent_window(root):
    try:
        return root.winfo_toplevel()
    except Exception:
        return root


def center_popup_on_parent(
    popup,
    parent,
    width,
    height
):
    try:
        parent.update_idletasks()
        popup.update_idletasks()
    except Exception:
        pass

    try:
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        if parent_width <= 1:
            parent_width = popup.winfo_screenwidth()

        if parent_height <= 1:
            parent_height = popup.winfo_screenheight()

    except Exception:
        parent_x = 0
        parent_y = 0
        parent_width = popup.winfo_screenwidth()
        parent_height = popup.winfo_screenheight()

    x = (
        parent_x
        + (parent_width - width) // 2
    )

    y = (
        parent_y
        + (parent_height - height) // 2
    )

    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()

    x = max(
        0,
        min(
            x,
            screen_width - width
        )
    )

    y = max(
        0,
        min(
            y,
            screen_height - height
        )
    )

    popup.geometry(
        f"{width}x{height}+{x}+{y}"
    )


def show_popup_window(
    popup,
    parent,
    width,
    height
):
    try:
        if not popup.winfo_exists():
            return
    except Exception:
        return

    center_popup_on_parent(
        popup,
        parent,
        width,
        height
    )

    try:
        popup.update_idletasks()
    except Exception:
        pass

    try:
        popup.attributes(
            "-topmost",
            True
        )
    except Exception:
        pass

    try:
        popup.attributes(
            "-alpha",
            1.0
        )
    except Exception:
        pass


def close_popup(
    popup,
    root=None
):
    try:
        popup.attributes(
            "-topmost",
            False
        )
    except Exception:
        pass

    if root is not None:
        try:
            root._update_popup = None
        except Exception:
            pass

    try:
        popup.destroy()
    except Exception:
        pass


def check_for_updates(
    root,
    show_uptodate_popup=False,
    blocking=False
):
    result_queue = queue.Queue()

    def worker():
        try:
            response = requests.get(
                GITHUB_LATEST_RELEASE_URL,
                timeout=5,
                headers={
                    "User-Agent": "Curio-Tracker"
                }
            )

            response.raise_for_status()
            data = response.json()

            latest = (
                data.get(
                    "tag_name",
                    ""
                )
                .strip()
            )

            if not latest:
                result_queue.put(
                    (
                        "error",
                        "Latest release did not "
                        "contain a tag name."
                    )
                )
                return

            print(
                "[UPDATE] Current version:",
                VERSION
            )

            print(
                "[UPDATE] Latest version:",
                latest
            )

            if (
                version_tuple(latest)
                > version_tuple(VERSION)
            ):
                result_queue.put(
                    (
                        "update",
                        latest,
                        data.get(
                            "html_url",
                            ""
                        ),
                        data.get(
                            "body",
                            ""
                        )
                    )
                )

            else:
                result_queue.put(
                    (
                        "current",
                        latest
                    )
                )

        except Exception as exc:
            result_queue.put(
                (
                    "error",
                    str(exc)
                )
            )

    def process_result():
        try:
            result = result_queue.get_nowait()

        except queue.Empty:
            try:
                root.after(
                    100,
                    process_result
                )
            except Exception:
                pass

            return

        status = result[0]

        if status == "update":
            try:
                show_update_popup(
                    root,
                    result[1],
                    result[2],
                    result[3]
                )

            except Exception as exc:
                print(
                    "[UPDATE] Failed to show "
                    f"update popup: {exc}"
                )

        elif status == "current":
            if show_uptodate_popup:
                try:
                    show_up_to_date_popup(
                        root,
                        result[1]
                    )

                except Exception as exc:
                    print(
                        "[UPDATE] Failed to show "
                        f"up-to-date popup: {exc}"
                    )

        elif status == "error":
            print(
                "[UPDATE] Update check failed:",
                result[1]
            )

            if show_uptodate_popup:
                try:
                    show_up_to_date_popup(
                        root,
                        error=True
                    )

                except Exception as exc:
                    print(
                        "[UPDATE] Failed to show "
                        f"error popup: {exc}"
                    )

    if blocking:
        worker()
        process_result()

    else:
        root.after(
            50,
            process_result
        )

        threading.Thread(
            target=worker,
            daemon=True
        ).start()


def show_up_to_date_popup(
    root,
    latest_version=None,
    error=False
):
    parent = get_parent_window(root)

    popup = ctk.CTkToplevel(parent)

    try:
        popup.attributes(
            "-alpha",
            0.0
        )
    except Exception:
        pass

    popup.title(
        "Update Check"
    )

    popup.geometry(
        f"{CHECK_POPUP_WIDTH}"
        f"x{CHECK_POPUP_HEIGHT}"
    )

    popup.resizable(
        False,
        False
    )

    if error:
        text = "Failed to check for updates."

    else:
        text = (
            "You are up to date!\n\n"
            f"Current version: {VERSION}"
        )

    frame = ctk.CTkFrame(popup)

    frame.pack(
        padx=20,
        pady=20,
        fill="both",
        expand=True
    )

    ctk.CTkLabel(
        frame,
        text=text,
        font=make_font(12),
        justify="center"
    ).pack(
        expand=True,
        pady=(5, 15)
    )

    ctk.CTkButton(
        frame,
        text="OK",
        command=lambda: close_popup(
            popup
        ),
        width=120
    ).pack()

    popup.protocol(
        "WM_DELETE_WINDOW",
        lambda: close_popup(
            popup
        )
    )

    popup.after(
        10,
        lambda: show_popup_window(
            popup,
            parent,
            CHECK_POPUP_WIDTH,
            CHECK_POPUP_HEIGHT
        )
    )


def deploy_updater():
    from load_utils import get_resource_path

    source = Path(
        get_resource_path(
            "updater.exe"
        )
    )

    if not source.exists():
        raise FileNotFoundError(
            f"Updater was not found: {source}"
        )

    if getattr(
        sys,
        "frozen",
        False
    ):
        app_dir = Path(
            sys.executable
        ).parent

    else:
        app_dir = Path(
            __file__
        ).resolve().parent

    target = app_dir / "updater.exe"

    if source.resolve() != target.resolve():
        shutil.copy2(
            source,
            target
        )

    return target


def show_update_popup(
    root,
    latest_version,
    release_url,
    changelog=""
):
    parent = get_parent_window(root)

    existing_popup = getattr(
        root,
        "_update_popup",
        None
    )

    if existing_popup is not None:
        try:
            if existing_popup.winfo_exists():
                try:
                    existing_popup.attributes(
                        "-topmost",
                        True
                    )
                except Exception:
                    pass

                return

        except Exception:
            root._update_popup = None

    popup = ctk.CTkToplevel(parent)

    root._update_popup = popup

    try:
        popup.attributes(
            "-alpha",
            0.0
        )
    except Exception:
        pass

    popup.title(
        "Update Available"
    )

    popup.geometry(
        f"{UPDATE_POPUP_WIDTH}"
        f"x{UPDATE_POPUP_HEIGHT}"
    )

    popup.minsize(
        UPDATE_POPUP_WIDTH,
        620
    )

    popup.resizable(
        False,
        True
    )

    def handle_close():
        close_popup(
            popup,
            root
        )

    popup.protocol(
        "WM_DELETE_WINDOW",
        handle_close
    )

    frm = ctk.CTkFrame(popup)

    frm.pack(
        padx=16,
        pady=16,
        fill="both",
        expand=True
    )

    ctk.CTkLabel(
        frm,
        text="Update Available",
        font=make_font(
            15,
            "bold"
        )
    ).pack(
        pady=(4, 2)
    )

    ctk.CTkLabel(
        frm,
        text=f"Your version: {VERSION}",
        font=make_font(10)
    ).pack()

    ctk.CTkLabel(
        frm,
        text=(
            f"Latest version: "
            f"{latest_version}"
        ),
        font=make_font(
            10,
            "bold"
        )
    ).pack(
        pady=(0, 10)
    )

    ctk.CTkLabel(
        frm,
        text="What's New",
        font=make_font(
            12,
            "bold"
        ),
        anchor="w"
    ).pack(
        fill="x",
        padx=6,
        pady=(2, 5)
    )

    changelog_frame = ctk.CTkScrollableFrame(
        frm,
        width=460,
        height=390
    )

    changelog_frame.pack(
        fill="both",
        expand=True,
        padx=4,
        pady=(0, 10)
    )

    try:
        render_markdown_to_frame(
            changelog_frame,
            changelog
        )

    except Exception as exc:
        print(
            "[UPDATE] Markdown rendering failed:",
            exc
        )

        for child in changelog_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        ctk.CTkLabel(
            changelog_frame,
            text=(
                changelog
                or
                "No release notes were provided."
            ),
            justify="left",
            anchor="w",
            wraplength=420,
            font=make_font(10)
        ).pack(
            fill="x",
            padx=6,
            pady=6
        )

    def update_now():
        try:
            updater_path = deploy_updater()

            subprocess.Popen(
                [str(updater_path)],
                cwd=str(
                    updater_path.parent
                )
            )

            root.destroy()

        except Exception as exc:
            print(
                "[UPDATE] Failed to launch updater:",
                exc
            )

    button_width = 190

    ctk.CTkButton(
        frm,
        text="Update Now",
        command=update_now,
        width=button_width
    ).pack(
        pady=(2, 5)
    )

    def open_github():
        if release_url:
            webbrowser.open_new(
                release_url
            )

    try:
        from load_utils import get_resource_path
        from PIL import Image

        icon_path = get_resource_path(
            "assets/github-icon.png"
        )

        with Image.open(
            icon_path
        ) as source:
            img = (
                source
                .convert("RGBA")
                .resize(
                    (18, 18),
                    Image.Resampling.LANCZOS
                )
            )

        github_img = ctk.CTkImage(
            light_image=img,
            dark_image=img,
            size=(18, 18)
        )

        github_button = ctk.CTkButton(
            frm,
            image=github_img,
            text="Download from GitHub",
            compound="left",
            command=open_github,
            width=button_width
        )

        github_button._github_image = github_img

        github_button.pack(
            pady=(0, 5)
        )

    except Exception:
        ctk.CTkButton(
            frm,
            text="Download from GitHub",
            command=open_github,
            width=button_width
        ).pack(
            pady=(0, 5)
        )

    ctk.CTkButton(
        frm,
        text="Later",
        command=handle_close,
        width=button_width
    ).pack(
        pady=(5, 4)
    )

    popup.after(
        2000,
        lambda: show_popup_window(
            popup,
            parent,
            UPDATE_POPUP_WIDTH,
            UPDATE_POPUP_HEIGHT
        )
    )
