import io
import queue
import re
import threading
import webbrowser

import customtkinter as ctk
import requests
from PIL import Image

from fonts import make_font

MAX_IMAGE_WIDTH = 420
MAX_IMAGE_HEIGHT = 300
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_TIMEOUT = 8

_IMAGE_DOWNLOAD_LIMIT = threading.BoundedSemaphore(4)


def render_markdown_to_frame(parent, markdown_text):
    for child in parent.winfo_children():
        try:
            child.destroy()
        except Exception:
            pass

    generation = getattr(
        parent,
        "_markdown_generation",
        0
    ) + 1

    parent._markdown_generation = generation
    parent._markdown_image_queue = queue.Queue()
    parent._markdown_pending_images = 0
    parent._markdown_image_refs = []

    if not markdown_text or not markdown_text.strip():
        _add_text(
            parent,
            "No release notes were provided."
        )
        return

    lines = markdown_text.splitlines()
    in_code_block = False
    code_lines = []

    for raw_line in lines:
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            if in_code_block:
                if code_lines:
                    _add_code_block(
                        parent,
                        "\n".join(code_lines)
                    )

                code_lines = []

            in_code_block = not in_code_block
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not line.strip():
            continue

        markdown_image = re.fullmatch(
            r"\s*!\[(.*?)\]\((https?://.*?)\)\s*",
            line,
            flags=re.IGNORECASE
        )

        if markdown_image:
            _add_remote_image(
                parent,
                url=markdown_image.group(2),
                alt_text=markdown_image.group(1),
                generation=generation
            )
            continue

        html_image = parse_html_img(line)

        if html_image:
            _add_remote_image(
                parent,
                url=html_image["src"],
                alt_text=html_image["alt"],
                width=html_image["width"],
                height=html_image["height"],
                generation=generation
            )
            continue

        if line.startswith("### "):
            _add_heading(
                parent,
                clean_inline_markdown(line[4:]),
                level=3
            )
            continue

        if line.startswith("## "):
            _add_heading(
                parent,
                clean_inline_markdown(line[3:]),
                level=2
            )
            continue

        if line.startswith("# "):
            _add_heading(
                parent,
                clean_inline_markdown(line[2:]),
                level=1
            )
            continue

        if line.strip() in (
                "---",
                "***",
                "___"
        ):
            _add_separator(parent)
            continue

        if (
                line.startswith("- ")
                or line.startswith("* ")
        ):
            _add_text(
                parent,
                "• " + clean_inline_markdown(
                    line[2:]
                ),
                left_padding=10
            )
            continue

        numbered = re.match(
            r"^(\d+)\.\s+(.*)$",
            line
        )

        if numbered:
            _add_text(
                parent,
                (
                        f"{numbered.group(1)}. "
                        + clean_inline_markdown(
                    numbered.group(2)
                )
                ),
                left_padding=10
            )
            continue

        if line.startswith("> "):
            _add_text(
                parent,
                "│ " + clean_inline_markdown(
                    line[2:]
                ),
                left_padding=8
            )
            continue

        _add_text(
            parent,
            clean_inline_markdown(line),
            url=extract_link(line)
        )

    if code_lines:
        _add_code_block(
            parent,
            "\n".join(code_lines)
        )

    if parent._markdown_pending_images > 0:
        parent.after(
            50,
            lambda: _poll_image_queue(
                parent,
                generation
            )
        )


def _add_heading(
        parent,
        text,
        level=1
):
    if level == 1:
        display_text = text.upper()
        font = ("Segoe UI", 16, "bold")
        pady = (10, 4)

    elif level == 2:
        display_text = text.upper()
        font = ("Segoe UI", 14, "bold")
        pady = (8, 3)

    else:
        display_text = f"▸ {text}"
        font = ("Segoe UI", 12, "bold")
        pady = (6, 2)

    ctk.CTkLabel(
        parent,
        text=display_text,
        font=font,
        anchor="w",
        justify="left",
        wraplength=420
    ).pack(
        fill="x",
        padx=6,
        pady=pady
    )


def _add_text(
        parent,
        text,
        url=None,
        left_padding=0
):
    label = ctk.CTkLabel(
        parent,
        text=text,
        font=make_font(10),
        anchor="w",
        justify="left",
        wraplength=420
    )

    label.pack(
        fill="x",
        padx=(
            6 + left_padding,
            6
        ),
        pady=(0, 3)
    )

    if url:
        try:
            label.configure(
                cursor="hand2"
            )
        except Exception:
            pass

        label.bind(
            "<Button-1>",
            lambda event, link=url:
            webbrowser.open_new(link)
        )


def _add_code_block(
        parent,
        text
):
    frame = ctk.CTkFrame(parent)

    frame.pack(
        fill="x",
        padx=6,
        pady=(3, 6)
    )

    ctk.CTkLabel(
        frame,
        text=text,
        font=make_font(9),
        anchor="w",
        justify="left",
        wraplength=400
    ).pack(
        fill="x",
        padx=10,
        pady=8
    )


def _add_separator(parent):
    ctk.CTkLabel(
        parent,
        text="────────────────────────────",
        font=make_font(10),
        anchor="w"
    ).pack(
        fill="x",
        padx=6,
        pady=(4, 6)
    )


def _add_remote_image(
        parent,
        url,
        alt_text="",
        width=None,
        height=None,
        generation=None
):
    display_alt = (
        alt_text.strip()
        if alt_text
        else "image"
    )

    placeholder = ctk.CTkLabel(
        parent,
        text=f"Loading {display_alt}...",
        font=make_font(9),
        anchor="center",
        justify="center",
        wraplength=420
    )

    placeholder.pack(
        fill="x",
        padx=6,
        pady=(4, 6)
    )

    parent._markdown_pending_images += 1

    threading.Thread(
        target=_download_image_worker,
        args=(
            parent._markdown_image_queue,
            generation,
            placeholder,
            url,
            alt_text,
            width,
            height
        ),
        daemon=True
    ).start()


def _download_image_worker(
        result_queue,
        generation,
        placeholder,
        url,
        alt_text,
        width,
        height
):
    try:
        with _IMAGE_DOWNLOAD_LIMIT:
            with requests.get(
                    url,
                    timeout=IMAGE_TIMEOUT,
                    stream=True,
                    headers={
                        "User-Agent": "Curio-Tracker"
                    }
            ) as response:

                response.raise_for_status()

                content_length = response.headers.get(
                    "Content-Length"
                )

                if content_length:
                    try:
                        declared_size = int(
                            content_length
                        )

                    except (
                            TypeError,
                            ValueError
                    ):
                        declared_size = None

                    if (
                            declared_size is not None
                            and declared_size
                            > MAX_IMAGE_BYTES
                    ):
                        raise ValueError(
                            "Image exceeds maximum allowed size"
                        )

                data = bytearray()

                for chunk in response.iter_content(
                        chunk_size=64 * 1024
                ):
                    if not chunk:
                        continue

                    data.extend(chunk)

                    if len(data) > MAX_IMAGE_BYTES:
                        raise ValueError(
                            "Image exceeds maximum allowed size"
                        )

        with Image.open(
                io.BytesIO(data)
        ) as source:
            image = source.convert("RGBA")

        requested_width = parse_dimension(width)
        requested_height = parse_dimension(height)

        max_width = MAX_IMAGE_WIDTH
        max_height = MAX_IMAGE_HEIGHT

        if requested_width is not None:
            max_width = min(
                requested_width,
                MAX_IMAGE_WIDTH
            )

        if requested_height is not None:
            max_height = min(
                requested_height,
                MAX_IMAGE_HEIGHT
            )

        image.thumbnail(
            (
                max_width,
                max_height
            ),
            Image.Resampling.LANCZOS
        )

        image = image.copy()

        result_queue.put(
            (
                "success",
                generation,
                placeholder,
                image,
                alt_text,
                url
            )
        )

    except Exception as exc:
        result_queue.put(
            (
                "error",
                generation,
                placeholder,
                exc,
                alt_text,
                url
            )
        )


def _poll_image_queue(
        parent,
        generation
):
    try:
        if not parent.winfo_exists():
            return
    except Exception:
        return

    if getattr(
            parent,
            "_markdown_generation",
            None
    ) != generation:
        return

    result_queue = getattr(
        parent,
        "_markdown_image_queue",
        None
    )

    if result_queue is None:
        return

    while True:
        try:
            result = result_queue.get_nowait()
        except queue.Empty:
            break

        status = result[0]
        result_generation = result[1]
        placeholder = result[2]

        if result_generation != generation:
            continue

        parent._markdown_pending_images = max(
            0,
            parent._markdown_pending_images - 1
        )

        try:
            if not placeholder.winfo_exists():
                continue
        except Exception:
            continue

        if status == "success":
            image = result[3]
            alt_text = result[4]
            url = result[5]

            try:
                ctk_image = ctk.CTkImage(
                    light_image=image,
                    dark_image=image,
                    size=(
                        image.width,
                        image.height
                    )
                )

                placeholder.configure(
                    text="",
                    image=ctk_image,
                    cursor="hand2"
                )

                placeholder._markdown_image = ctk_image

                parent._markdown_image_refs.append(
                    ctk_image
                )

                placeholder.bind(
                    "<Button-1>",
                    lambda event, link=url:
                    webbrowser.open_new(link)
                )

            except Exception as exc:
                placeholder.configure(
                    text=(
                        f"[{alt_text or 'image'} unavailable]"
                    ),
                    image=None
                )

                print(
                    "[MARKDOWN] Failed to display "
                    f"image {url!r}: {exc}"
                )

        else:
            exc = result[3]
            alt_text = result[4]
            url = result[5]

            try:
                placeholder.configure(
                    text=(
                        f"[{alt_text or 'image'} unavailable]"
                    )
                )
            except Exception:
                pass

            print(
                "[MARKDOWN] Failed to load "
                f"image {url!r}: {exc}"
            )

    if getattr(
            parent,
            "_markdown_pending_images",
            0
    ) > 0:
        try:
            parent.after(
                75,
                lambda: _poll_image_queue(
                    parent,
                    generation
                )
            )
        except Exception:
            pass


def parse_html_img(line):
    match = re.fullmatch(
        r"\s*<img\b([^>]*)/?>\s*",
        line,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    attrs = {}

    for key, value in re.findall(
            r'''([\w:-]+)\s*=\s*["']([^"']*)["']''',
            match.group(1)
    ):
        attrs[key.lower()] = value

    src = attrs.get("src")

    if not src:
        return None

    return {
        "src": src,
        "alt": attrs.get("alt", ""),
        "width": attrs.get("width"),
        "height": attrs.get("height"),
    }


def clean_inline_markdown(text):
    text = re.sub(
        r"\*\*(.*?)\*\*",
        r"\1",
        text
    )

    text = re.sub(
        r"`(.*?)`",
        r"\1",
        text
    )

    text = re.sub(
        r"\[(.*?)\]\((https?://.*?)\)",
        r"\1",
        text
    )

    return text


def extract_link(text):
    markdown_link = re.search(
        r"\[(.*?)\]\((https?://.*?)\)",
        text
    )

    if markdown_link:
        return markdown_link.group(2)

    raw_link = re.search(
        r"https?://[^\s]+",
        text
    )

    if raw_link:
        return raw_link.group(0).rstrip(
            ".,)]}"
        )

    return None


def parse_dimension(value):
    if value is None:
        return None

    value = str(value).strip()

    match = re.fullmatch(
        r"(\d+)(?:px)?",
        value,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    dimension = int(
        match.group(1)
    )

    if dimension <= 0:
        return None

    return dimension
