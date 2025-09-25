import sys
import tkinter as tk
from contextlib import contextmanager


class TextRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)

    def flush(self):
        pass


def setup_console(root):
    console_frame = tk.Frame(root)
    console_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="ew")

    console_output = tk.Text(console_frame, height=6, width=110, wrap="word", state="normal")
    console_output.pack(side="left", fill="both", expand=True)

    scrollbar = tk.Scrollbar(console_frame, command=console_output.yview)
    scrollbar.pack(side="right", fill="y")
    console_output['yscrollcommand'] = scrollbar.set

    # Redirect global stdout/stderr
    sys.stdout = TextRedirector(console_output)
    sys.stderr = TextRedirector(console_output)

    return console_output, console_frame


# Context manager for temporary stdout/stderr redirection
@contextmanager
def redirect_stdout_stderr(new_target):
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = new_target
    try:
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# Decorator to redirect stdout/stderr for a specific function
def redirect_to_capture_console(func):
    def wrapper(*args, **kwargs):
        # Create a temporary text widget for this capture
        temp_root = tk.Toplevel()
        temp_root.title("Captured Console")
        temp_text = tk.Text(temp_root, height=10, width=80, wrap="word", state="disabled")
        temp_text.pack(fill="both", expand=True)
        temp_scroll = tk.Scrollbar(temp_root, command=temp_text.yview)
        temp_scroll.pack(side="right", fill="y")
        temp_text['yscrollcommand'] = temp_scroll.set

        temp_redirector = TextRedirector(temp_text)
        with redirect_stdout_stderr(temp_redirector):
            result = func(*args, **kwargs)
        return result
    return wrapper
