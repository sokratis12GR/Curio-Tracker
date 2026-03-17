import tempfile
from pathlib import Path
import threading
import requests
from PIL import Image, ImageTk
from customtkinter import CTkImage

from load_utils import get_datasets

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

    def _download_icon(name, url):
        if not url or name in _img_refs:
            return
        get_icon(name=name, url=url, size=size, placeholder=placeholder, parent=parent)

    threads = []
    for name, type_name in terms.items():
        if type_name.lower() in ["replica", "replacement"]:
            url = tiers.get(name, {}).get("img")
            if url:
                t = threading.Thread(target=_download_icon, args=(name, url), daemon=True)
                t.start()
                threads.append(t)

    # Wait for all threads to finish
    for t in threads:
        t.join()
