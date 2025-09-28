from datetime import datetime

from config import ENABLE_LOGGING
from load_utils import LOG_FILE


def log_message(*messages, log_file: str = LOG_FILE, sep: str = " ", end: str = "\n"):
    if not ENABLE_LOGGING:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = sep.join(str(m) for m in messages)
    log = f"[{timestamp}] {line}{end}"

    print(log, end="")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log)
