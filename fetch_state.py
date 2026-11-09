from logger import log_message
from shared_lock import is_recent_run


def should_skip_recent_run(lock_identifier, min_duration, force, skip_message):
    """Shared recent-run guard used by threaded fetch modules before starting a fetch."""
    if not force and is_recent_run(lock_identifier, min_duration):
        log_message(skip_message)
        return True
    return False
