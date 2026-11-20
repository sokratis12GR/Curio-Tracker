import functools
import os
import queue
import tempfile
import threading
import time
import traceback

from logger import log_message


def on_main_thread():
    return threading.current_thread() is threading.main_thread()


#############################################################
# Tkinter is not thread-safe: widgets must only be touched  #
# from the main thread. ui_call runs fn right away when     #
# already there, otherwise queues it on the Tk event loop.  #
#############################################################
def ui_call(root, fn, *args, **kwargs):
    if root is None or on_main_thread():
        return fn(*args, **kwargs)
    try:
        root.after(0, lambda: fn(*args, **kwargs))
    except Exception as e:  # root destroyed / shutting down
        log_message(f"[WARN] ui_call could not schedule {getattr(fn, '__name__', fn)}: {e}")
    return None


def ui_thread(func):
    # Decorator for functions whose first argument is the Tk root.
    @functools.wraps(func)
    def wrapper(root, *args, **kwargs):
        return ui_call(root, func, root, *args, **kwargs)
    return wrapper


#############################################################
# Runs submitted jobs one at a time on a single background  #
# thread. Used for hotkey handlers so the keyboard hook     #
# returns immediately and captures never overlap.           #
#############################################################
class SerialWorker:
    def __init__(self, name="worker"):
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def submit(self, fn, label=""):
        self._queue.put((fn, label))

    def _run(self):
        while True:
            fn, label = self._queue.get()
            try:
                fn()
            except Exception:
                log_message(f"[ERROR] Background job '{label}' failed:\n{traceback.format_exc()}")


_background_worker = None
_background_lock = threading.Lock()


def get_background_worker():
    # Shared worker for captures/OCR so they run strictly one at a time.
    global _background_worker
    with _background_lock:
        if _background_worker is None:
            _background_worker = SerialWorker("capture-worker")
        return _background_worker


#############################################################
# Writes via a temp file + os.replace so a crash mid-write  #
# never leaves a truncated file behind. writer(f) receives  #
# an open text file. Retries briefly on PermissionError,    #
# which Windows raises while antivirus/indexers hold the    #
# target; persistent errors (file open in Excel) propagate. #
#############################################################
def atomic_write(path, writer, encoding="utf-8", newline=None, retries=5):
    path = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=os.path.basename(path), dir=directory)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as f:
            writer(f)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(retries):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == retries - 1:
                    raise
                time.sleep(0.05)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
