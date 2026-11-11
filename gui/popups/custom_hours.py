import math

from customtkinter import *

from win_utils import center_window_on_parent, prepare_popup

# Unit name -> (hours per unit, short suffix used in the filter label)
TIME_UNITS = {
    "Minutes": (1 / 60, "m"),
    "Hours": (1, "h"),
    "Days": (24, "d"),
    "Weeks": (168, "w"),
}
DEFAULT_UNIT = "Hours"


def range_to_hours(amount, unit):
    hours_per_unit, _ = TIME_UNITS.get(unit, TIME_UNITS[DEFAULT_UNIT])
    return amount * hours_per_unit


def format_range_label(amount, unit):
    _, suffix = TIME_UNITS.get(unit, TIME_UNITS[DEFAULT_UNIT])
    return f"Custom ({amount:g}{suffix})"


class CustomHoursPopup:
    """Asks for a time range (amount + unit).

    on_apply(amount, unit) is called on a valid Apply; on_cancel() is called
    when the popup is closed any other way (Cancel, X, Escape).
    """

    def __init__(self, parent, initial_amount=1, initial_unit=DEFAULT_UNIT, on_apply=None, on_cancel=None):
        self.parent = parent
        self.on_apply = on_apply
        self.on_cancel = on_cancel
        self._closed = False

        self.popup = CTkToplevel(self.parent)
        prepare_popup(self.popup)
        self.popup.title("Custom Time Filter")
        self.popup.resizable(False, False)
        self.popup.transient(self.parent.winfo_toplevel())

        self.popup.protocol("WM_DELETE_WINDOW", self._cancel)
        self.popup.bind("<Escape>", lambda e: self._cancel())

        frame = CTkFrame(self.popup)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        CTkLabel(frame, text="Show items from the last:").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))

        self.amount_var = StringVar(value=f"{initial_amount:g}")
        entry = CTkEntry(frame, textvariable=self.amount_var, width=90)
        entry.grid(row=1, column=0, sticky="ew", padx=(10, 5), pady=5)
        entry.bind("<Return>", lambda e: self._apply())
        entry.focus()
        entry.select_range(0, "end")

        if initial_unit not in TIME_UNITS:
            initial_unit = DEFAULT_UNIT
        self.unit_var = StringVar(value=initial_unit)
        CTkOptionMenu(frame, variable=self.unit_var, values=list(TIME_UNITS), width=110).grid(
            row=1, column=1, sticky="ew", padx=(5, 10), pady=5)

        self.error_label = CTkLabel(frame, text="", text_color="#e05252")
        self.error_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=10)

        CTkButton(frame, text="Apply", command=self._apply, width=90).grid(
            row=3, column=0, sticky="ew", padx=(10, 5), pady=(5, 10))
        CTkButton(frame, text="Cancel", command=self._cancel, width=110, fg_color="transparent",
                  border_width=1).grid(row=3, column=1, sticky="ew", padx=(5, 10), pady=(5, 10))

        center_window_on_parent(self.popup, self.parent)

        self.popup.grab_set()
        self.popup.focus_force()

    def _apply(self):
        try:
            amount = float(self.amount_var.get().strip().replace(",", "."))
        except ValueError:
            amount = None
        if amount is None or not math.isfinite(amount) or amount <= 0:
            self.error_label.configure(text="Enter a number greater than 0.")
            return

        unit = self.unit_var.get()
        self._close()
        if self.on_apply:
            self.on_apply(amount, unit)

    def _cancel(self):
        if self._closed:
            return
        self._close()
        if self.on_cancel:
            self.on_cancel()

    def _close(self):
        self._closed = True
        try:
            self.popup.grab_release()
        except Exception:
            pass
        self.popup.destroy()
