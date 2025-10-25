from config import LEAGUE
from ocr_utils import is_currency_or_scarab, format_currency_value, parse_item_name
from settings import get_setting


def convert_to_float(val):
    try:
        result_float = float(val)
    except (ValueError, TypeError):
        result_float = 0
    return result_float


def convert_to_int(val):
    try:
        result_int = int(val)
    except (ValueError, TypeError):
        result_int = 1
    return result_int


def get_stack_size(item):
    item_type = getattr(item, "type", "N/A")

    stack_size = getattr(item, "stack_size", "")

    stack_size = convert_to_int(stack_size)

    stack_size_txt = (
        stack_size
        if stack_size > 0 and is_currency_or_scarab(item_type)
        else ""
    )
    return stack_size, stack_size_txt

def calculate_estimate_value(item):
    chaos_value = getattr(item, "chaos_value", "")
    divine_value = getattr(item, "divine_value", "")
    stack_size, _ = get_stack_size(item)

    chaos_float = convert_to_float(chaos_value)
    divine_float = convert_to_float(divine_value)

    if stack_size > 1:
        chaos_float *= stack_size
        divine_float *= stack_size

    league_divine_equiv = convert_to_float(get_setting("Application", "divine_equivalent", 183.5))

    # Only attempt conversion if league_divine_equiv > 0
    if league_divine_equiv > 0 and chaos_float >= league_divine_equiv * 0.99:
        display_value = f"{format_currency_value(chaos_float / league_divine_equiv)} Divines"
    elif divine_float >= 0.5:
        display_value = f"{format_currency_value(divine_float)} Divines"
    elif chaos_float > 0:
        display_value = f"{format_currency_value(chaos_float)} Chaos"
    else:
        display_value = ""

    return display_value
