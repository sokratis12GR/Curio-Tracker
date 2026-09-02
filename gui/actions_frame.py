from tkinter import StringVar

from customtkinter import (
    CTkFrame,
    CTkLabel,
    CTkButton,
    CTkComboBox,
)

import curio_tracker
from fonts import make_font
from logger import log_message
from tree_manager import TreeManager


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

        self._create_widgets()
        self._populate_types()

        self.selected_term.trace_add("write", self._on_term_typed)

    def _term_sort_key(self, term):
        lower = term.lower()

        return (lower)

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

        # -----------------------------------------------------
        # Insert
        # -----------------------------------------------------
        self.insert_button = CTkButton(self.frame, text="Insert Item", font=make_font(12, "bold"), width=120,
                                       command=self._insert_item)

        self.insert_button.grid(row=0, column=3, padx=(5, 5), pady=5)

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
            text_color="gray"
        )

    def _hide_item_placeholder(self):
        if not self._showing_item_placeholder:
            return

        self._showing_item_placeholder = False
        self._set_term("")

        self.item_combo.configure(
            text_color=("black", "white")
        )

    def _on_item_focus_in(self, _event=None):
        self._hide_item_placeholder()

    def _on_item_focus_out(self, _event=None):
        if not self.selected_term.get().strip():
            self._show_item_placeholder()

    def _on_item_selected(self, selected_term):
        if not selected_term:
            return

        self._showing_item_placeholder = False

        self.item_combo.configure(
            text_color=("black", "white")
        )

        self._set_term(selected_term)

        actual_type = self.term_types.get(selected_term)

        if actual_type:
            self.selected_type.set(actual_type)

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
        self._populate_terms(
            selected_type,
            select_first=False
        )

        self._set_term("")
        self._show_item_placeholder()

    def _on_term_typed(self, *_args):
        if self._updating_term or self._showing_item_placeholder:
            return

        typed = self.selected_term.get()

        search = typed.strip().lower()

        selected_type = (
            self.selected_type.get().strip()
        )

        if not search:
            terms = self._get_terms_for_type(
                selected_type
            )

            self.item_combo.configure(
                values=terms
            )

            return

        type_terms = self._get_terms_for_type(
            selected_type
        )

        matches = [
            term
            for term in type_terms
            if search in term.lower()
        ]

        if not matches:
            matches = [
                term
                for term in self.term_types
                if search in term.lower()
            ]

        # Starts-with matches should appear before contains.
        matches.sort(
            key=lambda term: (
                not term.lower().startswith(search),
                term.lower()
            )
        )

        self.item_combo.configure(
            values=matches
        )

        exact_term = next(
            (
                term
                for term in self.term_types
                if term.lower() == search
            ),
            None
        )

        if exact_term:
            actual_type = self.term_types.get(exact_term)

            if (actual_type and actual_type != selected_type):
                self.selected_type.set(actual_type)

    def _insert_item(self):
        term = self.selected_term.get().strip()

        if not term or self._showing_item_placeholder or term == self.item_placeholder:
            log_message("[WARN] Manual insert attempted without selecting an item.")
            return

        actual_term = next(
            (
                known_term
                for known_term in self.term_types
                if known_term.lower() == term.lower()
            ),
            None
        )

        if not actual_term:
            log_message(f"[WARN] Manual insert rejected: unknown item '{term}'")
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
            return

        if item is None:
            return

        self.tm.add_item_to_tree(item, insert_at_top=True)

        log_message(f"[INFO] Manual item inserted into tree: {actual_type}: {actual_term}")
