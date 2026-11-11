from tkinter import StringVar

from customtkinter import (
    CTkFrame,
    CTkLabel,
    CTkButton,
    CTkComboBox,
    ThemeManager,
)

import curio_tracker
from fonts import make_font
from logger import log_message
from tree_manager import TreeManager

STATUS_COLORS = {
    "success": ("#2e7d32", "#388e3c"),
    "error": ("#c62828", "#c62828"),
}

STATUS_CLEAR_MS = 2000
HINT_MAX_NAMES = 2
HINT_MAX_CHARS = 60


def _theme_color(widget, key, fallback):
    try:
        return ThemeManager.theme[widget][key]
    except (KeyError, TypeError):
        return fallback


class ActionsFrame:
    def __init__(self, parent, tree_manager: TreeManager, theme_manager=None):
        self.tm = tree_manager
        self.theme_manager = theme_manager

        self.frame = CTkFrame(
            parent,
            corner_radius=15,
            fg_color="transparent",
            bg_color="transparent"
        )

        self.frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # Let item field expand.
        self.frame.grid_columnconfigure(2, weight=1)

        self.selected_type = StringVar(value="")

        self.selected_term = StringVar(value="")

        # term -> type
        self.term_types = curio_tracker.term_types

        self.item_placeholder = "i.e. Abyssus"
        self._showing_item_placeholder = False

        self._updating_term = False

        self._status_after_id = None

        self._create_widgets()
        self._populate_types()

        self.selected_term.trace_add("write", self._on_term_typed)

        self._update_insert_state()

    def _term_sort_key(self, term):
        lower = term.lower()

        return (lower)

    # ---------------------------------------------------------
    # Theme-aware colors
    # ---------------------------------------------------------
    def _text_color(self):
        return _theme_color("CTkEntry", "text_color", ("black", "white"))

    def _placeholder_color(self):
        return _theme_color("CTkEntry", "placeholder_text_color", "gray")

    def _create_widgets(self):

        # -----------------------------------------------------
        # Type
        # -----------------------------------------------------
        self.type_label = CTkLabel(self.frame, text="Type:", font=make_font(12, "bold"))

        self.type_label.grid(row=0, column=0, padx=(5, 5), pady=5)

        self.type_combo = CTkComboBox(self.frame, variable=self.selected_type, values=[], state="readonly", width=180,
                                      command=self._on_type_changed)

        self.type_combo.grid(row=0, column=1, padx=(0, 5), pady=5)

        self.item_combo = CTkComboBox(self.frame, variable=self.selected_term, values=[], width=400,
                                      command=self._on_item_selected)

        self.item_combo.grid(row=0, column=2, sticky="ew", padx=5, pady=5)

        self.item_combo.bind("<FocusIn>", self._on_item_focus_in)

        self.item_combo.bind("<FocusOut>", self._on_item_focus_out)

        # Press Enter while typing to insert.
        self.item_combo.bind("<Return>", lambda event: self._insert_item())

        # Escape clears the field.
        self.item_combo.bind("<Escape>", self._on_escape)

        # -----------------------------------------------------
        # Insert
        # -----------------------------------------------------
        self.insert_button = CTkButton(self.frame, text="Insert Item", font=make_font(12, "bold"), width=120,
                                       command=self._insert_item)

        self.insert_button.grid(row=0, column=3, padx=(5, 5), pady=5)

        # Thin "did you mean" line under the field.
        self.hint_label = CTkLabel(self.frame, text="", font=make_font(10), anchor="w", height=14,
                                   text_color=("gray40", "gray65"))

        self.hint_label.grid(row=1, column=2, columnspan=2, sticky="w", padx=8, pady=(0, 2))

        for widget in (self.type_label, self.type_combo, self.item_combo, self.insert_button):
            widget.grid_configure(pady=(5, 0))

        self._button_text = self.insert_button.cget("text")
        self._button_color = self.insert_button.cget("fg_color")

    # ---------------------------------------------------------
    # Feedback (flashed on the Insert button, keeps the row compact)
    # ---------------------------------------------------------
    def _set_status(self, text, kind="error"):
        if self._status_after_id is not None:
            self.frame.after_cancel(self._status_after_id)

        self.insert_button.configure(text=text, fg_color=STATUS_COLORS[kind])
        self._status_after_id = self.frame.after(STATUS_CLEAR_MS, self._clear_status)

    def _clear_status(self):
        if self._status_after_id is not None:
            self.frame.after_cancel(self._status_after_id)
            self._status_after_id = None

        self.insert_button.configure(text=self._button_text, fg_color=self._button_color)

    def _set_hint(self, matches=None, no_match=False):
        if no_match:
            text = "No match"
        elif matches:
            text = "Did you mean " + " / ".join(matches[:HINT_MAX_NAMES])
            extra = len(matches) - HINT_MAX_NAMES
            if extra > 0:
                text += f" +{extra}"
            text += "?"
        else:
            text = ""

        if len(text) > HINT_MAX_CHARS:
            text = text[:HINT_MAX_CHARS - 1] + "…"

        self.hint_label.configure(text=text)

    # ---------------------------------------------------------
    # Matching helpers
    # ---------------------------------------------------------
    def _find_matches(self, search, item_type=None):
        """Return matches for `search`, preferring the given type, starts-with first."""
        search = search.strip().lower()

        if not search:
            return []

        pool = self._get_terms_for_type(item_type) if item_type else []

        matches = [term for term in pool if search in term.lower()]

        if not matches:
            matches = [term for term in self.term_types if search in term.lower()]

        matches.sort(
            key=lambda term: (
                not term.lower().startswith(search),
                term.lower()
            )
        )

        return matches

    def _exact_term(self, text):
        lower = text.strip().lower()

        return next(
            (term for term in self.term_types if term.lower() == lower),
            None
        )

    def _current_text(self):
        if self._showing_item_placeholder:
            return ""

        return self.selected_term.get().strip()

    def _update_insert_state(self):
        text = self._current_text()

        valid = bool(text) and (self._exact_term(text) or self._find_matches(text, self.selected_type.get()))

        self.insert_button.configure(state="normal" if valid else "disabled")

    def _populate_types(self):
        types = sorted({
            item_type
            for item_type in self.term_types.values()
            if item_type
        })

        self.type_combo.configure(values=types)

        if not types:
            self.selected_type.set("")
            self._set_term("")
            return

        default_type = "Replica" if "Replica" in types else types[0]

        self.selected_type.set(default_type)

        self._populate_terms(
            default_type,
            select_first=False
        )

        self._show_item_placeholder()

    def _show_item_placeholder(self):
        if self.selected_term.get().strip():
            return

        self._showing_item_placeholder = True
        self._set_term(self.item_placeholder)

        self.item_combo.configure(
            text_color=self._placeholder_color()
        )

    def _hide_item_placeholder(self):
        if not self._showing_item_placeholder:
            return

        self._showing_item_placeholder = False
        self._set_term("")

        self.item_combo.configure(
            text_color=self._text_color()
        )

    def _on_item_focus_in(self, _event=None):
        self._hide_item_placeholder()

    def _on_item_focus_out(self, _event=None):
        if not self.selected_term.get().strip():
            self._show_item_placeholder()

    def _on_escape(self, _event=None):
        self._set_term("")
        self._populate_terms(self.selected_type.get(), select_first=False)
        self._clear_status()
        self._set_hint()
        self._update_insert_state()
        return "break"

    def _on_item_selected(self, selected_term):
        if not selected_term:
            return

        self._showing_item_placeholder = False

        self.item_combo.configure(
            text_color=self._text_color()
        )

        self._set_term(selected_term)

        actual_type = self.term_types.get(selected_term)

        if actual_type:
            self.selected_type.set(actual_type)

        self._clear_status()
        self._set_hint()
        self._update_insert_state()

    def _get_terms_for_type(self, item_type):
        return sorted(
            (
                term
                for term, term_type
                in self.term_types.items()
                if term_type == item_type
            ),
            key=self._term_sort_key
        )

    def _populate_terms(self, item_type, select_first=True):
        terms = self._get_terms_for_type(
            item_type
        )

        self.item_combo.configure(
            values=terms
        )

        if select_first:
            if terms:
                self._set_term(terms[0])
            else:
                self._set_term("")

    def _set_term(self, value):
        self._updating_term = True

        try:
            self.selected_term.set(value)
        finally:
            self._updating_term = False

    def _on_type_changed(self, selected_type):
        typed = self._current_text()

        self._populate_terms(
            selected_type,
            select_first=False
        )

        if typed and any(typed.lower() in term.lower() for term in self._get_terms_for_type(selected_type)):
            self._on_term_typed()
            return

        self._set_term("")
        self._clear_status()
        self._set_hint()

        if self.frame.focus_get() is not self.item_combo._entry:
            self._show_item_placeholder()

        self._update_insert_state()

    def _on_term_typed(self, *_args):
        if self._updating_term or self._showing_item_placeholder:
            return

        typed = self.selected_term.get()

        search = typed.strip().lower()

        selected_type = (
            self.selected_type.get().strip()
        )

        if not search:
            self.item_combo.configure(
                values=self._get_terms_for_type(selected_type)
            )

            self._clear_status()
            self._set_hint()
            self._update_insert_state()
            return

        matches = self._find_matches(search, selected_type)

        self.item_combo.configure(
            values=matches
        )

        exact_term = self._exact_term(search)

        if exact_term:
            actual_type = self.term_types.get(exact_term)

            if (actual_type and actual_type != selected_type):
                self.selected_type.set(actual_type)

            self._set_hint()
        else:
            self._set_hint(matches, no_match=not matches)

        self._clear_status()
        self._update_insert_state()

    def _resolve_term(self, text):
        exact = self._exact_term(text)

        if exact:
            return exact, None

        matches = self._find_matches(text, self.selected_type.get())

        if not matches:
            return None, "Not found"

        search = text.lower()
        starts = [m for m in matches if m.lower().startswith(search)]

        # Unique, or a single starts-with candidate -> take it.
        if len(matches) == 1 or len(starts) == 1:
            return (starts or matches)[0], None

        # Ambiguous: candidates are already in the dropdown.
        return None, "Pick one ▾"

    def _insert_item(self):
        term = self._current_text()

        if not term or term == self.item_placeholder:
            log_message("[WARN] Manual insert attempted without selecting an item.")
            self._set_status("Pick an item")
            return

        actual_term, problem = self._resolve_term(term)

        if not actual_term:
            log_message(f"[WARN] Manual insert rejected for '{term}': {problem}")
            self._set_status(problem)
            return

        actual_type = self.term_types[actual_term]

        self.selected_type.set(actual_type)

        self._set_term(actual_term)

        try:
            item = curio_tracker.insert_item(
                root=self.frame.winfo_toplevel(),
                term_title=actual_term,
                item_type=actual_type,
                data_manager=self.tm.data_mgr
            )

        except Exception as e:
            log_message(f"[ERROR] Failed manually inserting '{actual_term}': {e}")
            self._set_status("Failed")
            return

        if item is None:
            self._set_status("Not inserted")
            return

        self.tm.add_item_to_tree(item, insert_at_top=True)

        log_message(f"[INFO] Manual item inserted into tree: {actual_type}: {actual_term}")

        self._set_status("✓ Inserted", "success")
        self._set_hint()

        # Keep the term for quick repeats, but select it so typing replaces it.
        self._populate_terms(actual_type, select_first=False)
        entry = self.item_combo._entry
        entry.focus_set()
        entry.select_range(0, "end")
        entry.icursor("end")

        self._update_insert_state()
