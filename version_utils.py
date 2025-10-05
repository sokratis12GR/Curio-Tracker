import sys

DEV_VERSION_FILE = "version.txt"

def get_dev_version() -> str:
    try:
        with open(DEV_VERSION_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("StringStruct('ProductVersion'"):
                    start = line.rfind("'")
                    end = line.rfind("'", 0, start)
                    if start > end:
                        return line[end + 1 : start]
    except FileNotFoundError:
        return "0.0.0.0"
    return "0.0.0.0"


def get_version():
    dev_version = get_dev_version()
    if getattr(sys, "frozen", False):
        exe_path = sys.executable
        try:
            import win32api
            info = win32api.GetFileVersionInfo(exe_path, "\\")

            lang, codepage = win32api.GetFileVersionInfo(exe_path, "\\VarFileInfo\\Translation")[0]
            str_info_path = f"\\StringFileInfo\\{lang:04X}{codepage:04X}\\ProductVersion"

            product_version = win32api.GetFileVersionInfo(exe_path, str_info_path)
            return product_version
        except Exception:
            return dev_version
    else:
        return dev_version


VERSION = get_version()