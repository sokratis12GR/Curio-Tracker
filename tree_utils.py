# ---------- Add Item ----------
from PIL import Image

item_counters = {}  # global dict to track counts per item name

def get_item_name_str(item):
    name = getattr(item, 'itemName', 'Unknown')
    if hasattr(name, 'lines'):
        return "_".join([str(line) for line in name.lines])
    elif isinstance(name, str):
        return name
    else:
        return str(name)


def generate_item_id(item):
    item_name = getattr(item, "itemName", "Unknown")

    item_name_str = str(item_name)

    count = item_counters.get(item_name_str, 0) + 1
    item_counters[item_name_str] = count

    return f"{item_name_str}_{count}"


def pad_image(img, left_pad=0, top_pad=0, target_width=200, target_height=40):
    new_img = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    new_img.paste(img, (0, 0))
    return new_img
