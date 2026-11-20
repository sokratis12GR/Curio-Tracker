import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from img_utils import get_item_icon_url
from load_utils import load_currency_dataset

HEADER = "Category,Name,Chaos Value,Exalted Value,Divine Value,five_link_value,six_link_value,League"


def test_tier_icon_preferred_over_ninja_icon():
    assert get_item_icon_url({"img": "tier.png"}, {"img": "ninja.png"}) == "tier.png"


def test_falls_back_to_ninja_icon():
    assert get_item_icon_url({}, {"img": "ninja.png"}) == "ninja.png"
    assert get_item_icon_url({"img": ""}, {"img": "ninja.png"}) == "ninja.png"


def test_no_icon_anywhere():
    assert get_item_icon_url(None, None) == ""


def test_loader_reads_icon_column(tmp_path):
    path = tmp_path / "currency.csv"
    path.write_text(HEADER + ",Icon\nCurrency,Divine Orb,200,N/A,1,N/A,N/A,Covens,https://x/divine.png\n",
                    encoding="utf-8")
    data = load_currency_dataset(str(path))
    assert data["Covens"]["Divine Orb"]["img"] == "https://x/divine.png"


def test_loader_handles_old_csv_without_icon_column(tmp_path):
    path = tmp_path / "currency.csv"
    path.write_text(HEADER + "\nCurrency,Divine Orb,200,N/A,1,N/A,N/A,Covens\n", encoding="utf-8")
    data = load_currency_dataset(str(path))
    assert data["Covens"]["Divine Orb"]["img"] == ""
    assert data["Covens"]["Divine Orb"]["chaos"] == "200"
