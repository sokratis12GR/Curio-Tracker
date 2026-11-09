import tempfile
import threading
from pathlib import Path

import requests
from PIL import Image, ImageTk

import ocr_utils as utils
from load_utils import get_datasets, get_resource_path

# Temp folder for caching icons
ICON_CACHE_DIR = Path(tempfile.gettempdir()) / "curio_icons"
ICON_CACHE_DIR.mkdir(exist_ok=True)

# In-memory cache of PhotoImage objects
_img_refs = {}
_lock = threading.Lock()


def get_icon(name: str, url: str, size=(24, 24), placeholder=None, parent=None, return_pil=False):
    global _img_refs

    if name in _img_refs:
        img = _img_refs[name]
        return img if not return_pil else img._pil_image

    local_file = ICON_CACHE_DIR / f"{name}.png"

    if not local_file.exists():
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            local_file.write_bytes(response.content)
        except Exception:
            return placeholder

    try:
        pil_img = Image.open(local_file).convert("RGBA")
        pil_img.thumbnail(size, Image.LANCZOS)

        if return_pil:
            return pil_img
        else:
            tk_img = ImageTk.PhotoImage(pil_img, master=parent)
            tk_img._pil_image = pil_img
            _img_refs[name] = tk_img
            return tk_img
    except Exception:
        return placeholder


def preload_all_icons(parent=None, size=(24, 24), placeholder=None):
    datasets = get_datasets(load_external=False)
    tiers = datasets.get("tiers", {})
    terms = datasets.get("terms", {})

    pending = []
    pending_lock = threading.Lock()

    def _download_icon(name, url):
        if not url or name in _img_refs:
            return
        pil_img = get_icon(name=name, url=url, size=size, placeholder=placeholder, parent=parent, return_pil=True)
        if isinstance(pil_img, Image.Image):
            with pending_lock:
                pending.append((name, pil_img))

    threads = []
    for name, type_name in terms.items():
        if not utils.is_unique(type_name):
            continue

        display_name = (
            f"{name} (Replica)"
            if type_name and type_name.lower() == "replica"
            else name
        )

        url = tiers.get(name, {}).get("img")
        if url:
            t = threading.Thread(target=_download_icon, args=(display_name, url), daemon=True)
            t.start()
            threads.append(t)

    for t in threads:
        t.join()

    if parent is not None and pending:
        done = threading.Event()

        def _create_tk_images():
            for name, pil_img in pending:
                if name not in _img_refs:
                    tk_img = ImageTk.PhotoImage(pil_img, master=parent)
                    tk_img._pil_image = pil_img
                    _img_refs[name] = tk_img
            done.set()

        parent.after(0, _create_tk_images)
        done.wait()


def get_local_image(relative_path, mode="RGB"):
    path = get_resource_path(relative_path)

    print(
        f"[IMG] Loading local image: {path}"
    )

    if not Path(path).exists():
        print(
            f"[IMG] Local image not found: {path}"
        )
        return None

    try:
        with Image.open(path) as source_image:
            if mode:
                image = source_image.convert(mode)
            else:
                image = source_image.copy()

        print(
            f"[IMG] Loaded local image: "
            f"{path} ({image.width}x{image.height})"
        )

        return image

    except Exception as error:
        print(
            f"[IMG] Failed to load local image "
            f"{path}: {error}"
        )
        return None
