import sys

import platform_compat

DEV_VERSION_FILE = "version.txt"


def _parse_product_version(path) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("StringStruct('ProductVersion'"):
                    start = line.rfind("'")
                    end = line.rfind("'", 0, start)
                    if start > end:
                        return line[end + 1: start]
    except FileNotFoundError:
        return "0.0.0.0"
    return "0.0.0.0"


def get_dev_version() -> str:
    return _parse_product_version(DEV_VERSION_FILE)


def get_version():
    dev_version = get_dev_version()
    if getattr(sys, "frozen", False):
        # Try the bundled version.txt resource first (works on every platform).
        from load_utils import get_resource_path
        bundled_version_file = get_resource_path(DEV_VERSION_FILE)
        bundled_version = _parse_product_version(bundled_version_file)
        if bundled_version != "0.0.0.0":
            return bundled_version

        # Fall back to reading the PE version resource directly (Windows only).
        product_version = platform_compat.get_frozen_product_version(sys.executable)
        return product_version or dev_version
    else:
        return dev_version


VERSION = get_version()
