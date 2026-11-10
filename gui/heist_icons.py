"""
Icon URLs for Heist reference UIs (Blueprint Encyclopedia / Blueprint Info).

Images are Path of Exile game art owned by Grinding Gear Games. They are not
bundled with this tool; they're downloaded at runtime from GGG's CDN (or the
tool's existing blueprint icon host) and cached locally, like item icons.
"""

from gui.popups.trade import BLUEPRINT_ICONS

CDN = "https://web.poecdn.com/image/Art/2DItems"

CONTRACT_ICON = ("Heist Contract", f"{CDN}/Currency/Heist/ContractItem.png")
ROGUES_MARKER_ICON = ("Rogue's Marker", f"{CDN}/Currency/Heist/HeistCoinCurrency.png")
CHAOS_ICON = ("Chaos Orb", f"{CDN}/Currency/CurrencyRerollRare.png")


def location_icon(location_name):
    """(cache name, url) for a blueprint location such as 'Bunker'."""
    key = f"Blueprint: {location_name}"
    url = BLUEPRINT_ICONS.get(key)
    return (key, url) if url else None


# Representative in-game item for each reward chest type.
CHEST_TYPE_ICONS = {
    "Currency": CHAOS_ICON,
    "Divination Cards": ("Stacked Deck", f"{CDN}/Divination/Deck.png"),
    "Maps": ("Strand Map", f"{CDN}/Maps/Atlas2Maps/New/Strand.png"),
    "Map Fragments": ("Sacrifice at Dawn", f"{CDN}/Maps/Vaal01.png"),
    "Gems": ("Gemcutter's Prism", f"{CDN}/Currency/CurrencyGemQuality.png"),
    "Uniques": ("Orb of Chance", f"{CDN}/Currency/CurrencyUpgradeRandomly.png"),
    "Jewellery": ("Agate Amulet", f"{CDN}/Amulets/AgateAmulet.png"),
    "Armour": ("Armourer's Scrap", f"{CDN}/Currency/CurrencyArmourQuality.png"),
    "Weapons": ("Blacksmith's Whetstone", f"{CDN}/Currency/CurrencyWeaponQuality.png"),
    "Delirium": ("Simulacrum Splinter", f"{CDN}/Maps/DeliriumSplinter.png"),
    "Gold": ("Gold", f"{CDN}/Currency/Ruthless/CoinPileTier3.png"),
    "Blight": ("Golden Oil", f"{CDN}/Currency/Oils/GoldenOil.png"),
    "Essences": ("Essence of Greed", f"{CDN}/Currency/Essence/Greed7.png"),
    "Random": ("Orb of Alchemy", f"{CDN}/Currency/CurrencyUpgradeToRare.png"),
}

# Icon shown on each encyclopedia category heading.
CATEGORY_ICONS = {
    "Blueprint Locations": CONTRACT_ICON,
    "Heist Jobs": ROGUES_MARKER_ICON,
    "Reward Chest Types": CHAOS_ICON,
    "Mechanics": CONTRACT_ICON,
}

# Blueprint enchantment -> icon of the guaranteed target type.
BP_ENCHANTMENT_ICONS = {
    "Heist Targets are always Currency or Scarabs": CHAOS_ICON,
    "Heist Targets are always Replica Unique Items": CHEST_TYPE_ICONS["Uniques"],
    "Heist Targets are always Enchanted Armaments": CHEST_TYPE_ICONS["Armour"],
    "Heist Targets are always Thieves' Trinkets": ROGUES_MARKER_ICON,
    "Heist Targets are always Experimented Items": CHEST_TYPE_ICONS["Weapons"],
}
