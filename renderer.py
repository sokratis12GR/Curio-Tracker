from PIL import Image, ImageDraw, ImageFont
import textwrap
import os
import sys
from types import SimpleNamespace


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    abs_path = os.path.join(base_path, relative_path)
    if not os.path.exists(abs_path):
        print(f"[resource_path] WARNING: {abs_path} does not exist!")
    return abs_path


NAME_BLOCK_OFFSET = 20
HEADER_MARGIN = 10
HORIZONTAL_MARGIN = 40
FONT_HEIGHT = 18
LINE_HEIGHT = 20
NAME_OFFSET = 18
NAME_FONT_HEIGHT = 23
SEPARATOR_WIDTH = 221
SEPARATOR_HEIGHT = 8
SEPARATOR_MARGIN_TOP = 4
SEPARATOR_MARGIN_BOTTOM = 7
NAME_Y_OFFSET = 13    # shift item name down
CLASS_Y_OFFSET = 10   # shift item class down

COLOR = {
    "grey": "#7f7f7f",
    "white": "#ffffff",
    "enchant": "#b4b4ff",
    "affix": "#8888ff",
    "corrupted": "#d20000",
    "currency": "#aa9e82",
    "normal": "#c8c8c8",
    "magic": "#8888ff",
    "rare": "#ffff77",
    "unique": "#af6025",
    "uniqueName": "#ee681d",
    "gem": "#1ba29b",
    "quest": "#4ae63a",
    "boon": "#b5a890",
    "affliction": "#a06dca",
}

def limit_text_lines(text, width_chars: int):
    return textwrap.wrap(text, width=width_chars)

def limit_text_array(texts, width_chars=88):
    lines = []
    for t in texts:
        if not t or len(t) <= width_chars:
            lines.append(t)
        else:
            lines.extend(textwrap.wrap(t, width=width_chars))
    return lines

def is_base_value_increased(item, name):
    not_scaling = ["Reduced Attribute Requirements", "Block Chance", "Charges"]
    if name not in not_scaling and getattr(item, "quality", 0) > 0:
        return True
    if name == "Radius":
        return False
    to_check = []
    for attr in ["affixes", "runes", "implicits", "enchants"]:
        to_check.extend(getattr(item, attr, []))
    name_lower = name.lower()
    return any(name_lower in stat.lower() for stat in to_check)

def render_item(item):
    # Font loading
    font_path = resource_path(os.path.join("assets", "fontin-smallcaps-webfont.ttf"))
    small_font = ImageFont.truetype(font_path, FONT_HEIGHT)
    name_font = ImageFont.truetype(font_path, NAME_FONT_HEIGHT)

    # Load header/separator images
    rarity = item.itemRarity.lower()
    header_left = Image.open(resource_path(f"assets/header-{rarity}-left.png"))
    header_middle = Image.open(resource_path(f"assets/header-{rarity}-middle.png"))
    header_right = Image.open(resource_path(f"assets/header-{rarity}-right.png"))

    headerW, headerH = header_left.size
    canvas_h = headerH
    # Measure content width
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines_max_width = 0

    # Collect all text lines to measure
    flavor_lines = item.flavorText.get("lines", []) if item.flavorText else []
    measure_texts = (
        limit_text_array(item.affixes)
        + item.runes + item.implicits + item.enchants
        + flavor_lines
    )

    for line in measure_texts:
        bbox = draw.textbbox((0, 0), line, font=small_font)
        lines_max_width = max(lines_max_width, bbox[2] - bbox[0])

    for ln in item.itemName.lines:
        bbox = draw.textbbox((0, 0), ln, font=name_font)
        lines_max_width = max(lines_max_width, bbox[2] - bbox[0])

    canvas_w = int(lines_max_width + headerW * 2)

    # --- Compute dynamic height ---
    # Count how many content lines exist (defensive)
    content_lines = 0

    # Helper to check if a list of strings has non-empty lines
    def non_empty_lines(lst):
        return [line for line in lst if line and line.strip()]

    if getattr(item, "itemClass", ""):
        content_lines += 1

    if getattr(item, "quality", 0) > 0:
        content_lines += 1

    if hasattr(item, "baseStats") and item.baseStats:
        content_lines += len(non_empty_lines(item.baseStats))

    if getattr(item, "itemLevel", 0) > 0:
        content_lines += 1

    if hasattr(item, "requirements") and item.requirements:
        content_lines += len(non_empty_lines(item.requirements))

    if hasattr(item, "implicits") and item.implicits:
        content_lines += len(non_empty_lines(item.implicits))

    if hasattr(item, "enchants") and item.enchants:
        content_lines += len(non_empty_lines(item.enchants))

    if hasattr(item, "affixes") and item.affixes:
        content_lines += len(non_empty_lines(item.affixes))

    # if getattr(item, "stack_size", ""):
    #     content_lines += 1

    if getattr(item, "corrupted", False):
        content_lines += 1



    flavor_lines = non_empty_lines(item.flavorText.get("lines", [])) if item.flavorText else []
    content_lines += len(flavor_lines)

    # Compute total height for content
    if content_lines > 0:
        y_content = HEADER_MARGIN + content_lines * LINE_HEIGHT
        canvas_h = max(canvas_h, headerH + y_content)
    else:
        canvas_h = headerH


    # --- Create canvas ---
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, headerH, canvas_w, canvas_h], fill="black")

    center_x = canvas_w // 2
    y = headerH + HEADER_MARGIN

    # Draw item class
    if getattr(item, "itemClass", ""):
        draw.text((center_x, y), item.itemClass.rstrip("s"), font=small_font, fill=COLOR["grey"], anchor="mm")
        y += LINE_HEIGHT

    # Quality
    if getattr(item, "quality", 0) > 0:
        draw.text((center_x, y), f"Quality: +{item.quality}%", font=small_font, fill=COLOR["white"], anchor="mm")
        y += LINE_HEIGHT

    # Base stats
    if hasattr(item, "baseStats") and item.baseStats:
        for stat in item.baseStats:
            draw.text((center_x, y), stat, font=small_font, fill=COLOR["white"], anchor="mm")
            y += LINE_HEIGHT

    # Item level
    if getattr(item, "itemLevel", 0) > 0:
        draw.text((center_x, y), f"Item Level: {item.itemLevel}", font=small_font, fill=COLOR["white"], anchor="mm")
        y += LINE_HEIGHT

    # Requirements
    if hasattr(item, "requirements") and item.requirements:
        draw.text((center_x, y), "Requires: " + ", ".join(item.requirements), font=small_font, fill=COLOR["grey"], anchor="mm")
        y += LINE_HEIGHT
    
    # Implicits
    for implicit in getattr(item, "implicits", []):
        draw.text((center_x, y), implicit, font=small_font, fill=COLOR["affix"], anchor="mm")
        y += LINE_HEIGHT

    # Enchants
    for enchant in getattr(item, "enchants", []):
        draw.text((center_x, y), enchant, font=small_font, fill=COLOR["enchant"], anchor="mm")
        y += LINE_HEIGHT

    # Affixes
    for affix in getattr(item, "affixes", []):
        draw.text((center_x, y), affix, font=small_font, fill=COLOR["affix"], anchor="mm")
        y += LINE_HEIGHT

    # Stack Size
    # if getattr(item, "stack_size", ""):
    #     max_size = ""
    #     stack_current = item.stack_size
    #     stack_max = getattr(item, "stack_size_max", None)
    #     if stack_max and int(stack_max) >= int(stack_current):
    #         max_size = f"/{stack_max}"

    #     main_text = "Stack Size: "
    #     stack_text = f"{stack_current}{max_size}"

    #     # Measure widths
    #     main_width = draw.textlength(main_text, font=small_font)
    #     stack_width = draw.textlength(stack_text, font=small_font)
    #     total_width = main_width + stack_width

    #     # Draw both pieces centered
    #     canvas_center = canvas_w // 2
    #     draw.text((canvas_center - total_width/2, y), main_text, font=small_font, fill=COLOR["white"])
    #     draw.text((canvas_center - total_width/2 + main_width, y), stack_text, font=small_font, fill=COLOR["white"])

    #     y += LINE_HEIGHT

    # Corrupted flag
    if getattr(item, "corrupted", False):
        draw.text((center_x, y), "Corrupted", font=small_font, fill=COLOR["corrupted"], anchor="mm")
        y += LINE_HEIGHT

    # Tile headers across top
    x = 0
    while x < canvas_w:
        img.paste(header_middle, (x, 0))
        x += headerW - 1
    img.paste(header_left, (0, 0))
    img.paste(header_right, (canvas_w - headerW, 0))

    # Draw item name on top
    color_name = COLOR["uniqueName"] if item.itemRarity == "Unique" else COLOR.get(rarity, COLOR["white"])
    # Draw item name
    num_lines = len(item.itemName.lines)
    if num_lines == 1:
        # Center single-line name vertically in header area
        y_name = (headerH // 2) - 2  # shift up by 5 pixels
        draw.text((canvas_w // 2, y_name), item.itemName.lines[0], font=name_font, fill=color_name, anchor="mm")
    else:
        # Multi-line: draw normally stacked
        for idx, line in enumerate(item.itemName.lines):
            y_name = NAME_OFFSET + idx * NAME_FONT_HEIGHT
            draw.text((canvas_w // 2, y_name), line, font=name_font, fill=color_name, anchor="mm")

    return img

# render_item(SimpleNamespace(
#                 itemClass="",
#                 itemRarity="rare",
#                 itemName=SimpleNamespace(lines=["TESTING_NAME"]),
#                 flavorText={"lines": []},
#                 itemLevel=0,
#                 affixes=[],
#                 runes=[],
#                 implicits=[],
#                 enchants=[],
#                 quality=0,
#                 corrupted=False,
#                 duplicate=False
#             ))