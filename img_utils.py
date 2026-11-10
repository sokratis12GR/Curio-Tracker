import hashlib
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image, ImageTk

import ocr_utils as utils
from load_utils import get_datasets, get_resource_path

# Temp folder for caching icons
ICON_CACHE_DIR = Path(tempfile.gettempdir()) / "curio_icons"
ICON_CACHE_DIR.mkdir(exist_ok=True)

# Parallel downloads when many icons are fetched at once.
ICON_DOWNLOAD_WORKERS = 8

# In-memory caches, keyed by (name, size) so callers asking for different
# sizes never receive an image scaled for someone else.
_img_refs = {}
_pil_cache = {}
_lock = threading.Lock()


def _normalize_size(size):
    if isinstance(size, int):
        return size, size
    return int(size[0]), int(size[1])


def fit_image(pil_img, size, align="center"):
    """
    Scale an image to fit inside `size` while keeping its aspect ratio, then
    pad it with transparency to exactly `size`. Prevents icons from being
    stretched when shown in fixed-size (often square) slots.
    """
    box_w, box_h = _normalize_size(size)
    img = pil_img.convert("RGBA")

    if img.width == 0 or img.height == 0:
        return Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))

    scale = min(box_w / img.width, box_h / img.height)
    new_w = max(1, round(img.width * scale))
    new_h = max(1, round(img.height * scale))

    if (new_w, new_h) != img.size:
        img = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    x = 0 if align == "left" else (box_w - new_w) // 2
    y = (box_h - new_h) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def _download_icon_file(name, url):
    safe_name = "".join(c if c not in r'<>:"/\|?*' else "_" for c in name)
    if url:
        # Include the URL in the file name so a changed icon URL is re-downloaded
        # instead of reusing the old image cached under the same name.
        safe_name += "_" + hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    local_file = ICON_CACHE_DIR / f"{safe_name}.png"

    if local_file.exists() and local_file.stat().st_size > 0:
        return local_file

    if not url:
        return None

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        tmp_file = local_file.with_suffix(".part")
        tmp_file.write_bytes(response.content)
        tmp_file.replace(local_file)
        return local_file
    except Exception:
        return None


def get_icon(name: str, url: str, size=(24, 24), placeholder=None, parent=None, return_pil=False):
    """
    Return an icon fitted (not stretched) into `size`.

    return_pil=True is safe to call from worker threads. Tk images
    (return_pil=False) must only be requested from the Tk main thread.
    """
    size = _normalize_size(size)
    key = (name, size)

    if return_pil:
        cached = _pil_cache.get(key)
        if cached is not None:
            return cached
    else:
        cached = _img_refs.get(key)
        if cached is not None:
            return cached

    pil_img = _pil_cache.get(key)

    if pil_img is None:
        local_file = _download_icon_file(name, url)
        if local_file is None:
            return placeholder

        try:
            with Image.open(local_file) as source:
                pil_img = fit_image(source, size)
        except Exception:
            return placeholder

        with _lock:
            _pil_cache[key] = pil_img

    if return_pil:
        return pil_img

    try:
        tk_img = ImageTk.PhotoImage(pil_img, master=parent)
        tk_img._pil_image = pil_img
        _img_refs[key] = tk_img
        return tk_img
    except Exception:
        return placeholder


def get_cached_icon(name, size=(24, 24)):
    """Return an already-loaded PIL icon from memory, or None. Never touches disk/network."""
    return _pil_cache.get((name, _normalize_size(size)))


def get_icons_parallel(requests_list, size=(24, 24)):
    """
    Fetch many icons concurrently. `requests_list` is an iterable of
    (name, url). Returns {name: PIL image} for icons that loaded.
    Safe to call from a worker thread.
    """
    results = {}
    items = [(n, u) for n, u in requests_list if u]

    if not items:
        return results

    def _fetch(entry):
        name, url = entry
        return name, get_icon(name=name, url=url, size=size, return_pil=True)

    with ThreadPoolExecutor(max_workers=ICON_DOWNLOAD_WORKERS) as pool:
        for name, pil_img in pool.map(_fetch, items):
            if isinstance(pil_img, Image.Image):
                results[name] = pil_img

    return results


def preload_all_icons(parent=None, size=(24, 24), placeholder=None):
    datasets = get_datasets(load_external=False)
    tiers = datasets.get("tiers", {})
    terms = datasets.get("terms", {})

    to_fetch = []
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
            to_fetch.append((display_name, url))

    # Downloads + decoding only; PIL results are cached per size and Tk
    # images are created lazily on the main thread by the caller.
    get_icons_parallel(to_fetch, size=size)


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
