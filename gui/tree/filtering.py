import re
from datetime import datetime, timedelta
from tkinter import TclError

import currency_utils
from gui.popups.custom_hours import CustomHoursPopup
from settings import get_setting


PICKED_CELL_VALUES = ("☑", "True", "true", "YES", "yes")


def _get_row_tag(index):
    return "odd" if index % 2 == 0 else "even"


def row_chaos_value(item):
    # Chaos value of a row including its stack size; 0.0 if unpriced.
    chaos_value = currency_utils.convert_to_float(getattr(item, "chaos_value", 0))
    if not chaos_value:
        return 0.0
    stack_size, _ = currency_utils.get_stack_size(item)
    return chaos_value * stack_size


class TreeFilteringMixin:
    #############################################################
    # Per-row caches (value, search text, stripe tag) avoid one #
    # Tk call per row on every total, filter and sort. Rows are #
    # invalidated by TreeManager's hook on tree.set/delete, so  #
    # any cell edit is picked up on the next read.              #
    #############################################################
    def _row_totals_entry(self, iid):
        entry = self._row_totals.get(iid)
        if entry is not None:
            return entry

        item = self.csv_row_map.get(iid)
        if not item:
            return None
        chaos_value = row_chaos_value(item)
        picked = False
        if chaos_value:
            try:
                picked = str(self.tree.set(iid, "picked")).strip() in PICKED_CELL_VALUES
            except TclError:
                return None  # row no longer exists in the tree
        entry = (chaos_value, picked)
        self._row_totals[iid] = entry
        return entry

    def _set_row_tag(self, iid, tag):
        if self._row_tags.get(iid) != tag:
            self.tree.item(iid, tags=(tag,))
            self._row_tags[iid] = tag

    def _restripe(self, ordered_iids):
        # Direct Tk call: same as tree.item(iid, tags=(tag,)) without
        # ttk's per-call option formatting, which dominates on big lists.
        call = self.tree.tk.call
        widget = self.tree._w
        row_tags = self._row_tags
        for index, iid in enumerate(ordered_iids):
            tag = "odd" if index % 2 == 0 else "even"
            if row_tags.get(iid) != tag:
                call(widget, "item", iid, "-tags", tag)
                row_tags[iid] = tag

    def calculate_totals(self):
        total_chaos = 0.0
        total_divine = 0.0
        picked_chaos = 0.0
        picked_divine = 0.0

        league_divine_equiv = currency_utils.convert_to_float(
            get_setting("Application", "divine_equivalent", 0)
        )

        for iid in self.all_item_iids:
            entry = self._row_totals_entry(iid)
            if entry is None:
                continue
            chaos_value, picked = entry
            if not chaos_value:
                continue

            divine_value = chaos_value / league_divine_equiv if league_divine_equiv > 0 else 0

            total_chaos += chaos_value
            total_divine += divine_value

            if picked:
                picked_chaos += chaos_value
                picked_divine += divine_value

        return total_chaos, total_divine, picked_chaos, picked_divine

    # @pyinstrument.profile()
    def update_total_labels(self):
        if not hasattr(self, "total_frame") or not self.total_frame:
            return

        total_chaos, total_divine, picked_chaos, picked_divine = self.calculate_totals()

        mode = self.total_frame.value_mode.get()
        if mode == "Divine":
            total_value = total_divine
            total_picked_value = picked_divine
            suffix = " Divines"
        else:
            total_value = total_chaos
            total_picked_value = picked_chaos
            suffix = " Chaos"

        total_text = f"Total Value: {total_value:.2f}{suffix}" if total_value else ""
        picked_text = f"Picked Value: {total_picked_value:.2f}{suffix}" if total_picked_value else ""

        self.total_frame.total_value_label.configure(text=total_text)
        self.total_frame.total_picked_label.configure(text=picked_text)

    # ---------- Sorting ----------
    # @pyinstrument.profile()
    def sort_tree(self, column):
        children = self.tree.get_children()
        reverse = self.sort_reverse.get(column, False)

        missing = float('inf') if not reverse else float('-inf')

        # record/time come from data already in memory (kept in sync with
        # the cells), avoiding one Tk read per row. Same keys as below.
        def record_key(iid):
            text = str(getattr(self.csv_row_map.get(iid), "record_number", "") or "").strip()
            return int(text) if text.isdigit() else missing

        def time_key(iid):
            # (group, datetime): inf can't be compared with datetimes, so
            # the group puts rows without a time last in either direction.
            dt = self.item_time_map.get(iid)
            if dt is None:
                return (0 if reverse else 1, datetime.min)
            return (1 if reverse else 0, dt)

        def sort_key(iid):
            val = self.tree.set(iid, column)
            if val in ("", None):
                # Place empty/None values at the end
                return float('inf') if not reverse else float('-inf')

            if column == "value":
                return float(self.tree.set(iid, "numeric_value") or 0.0)
            elif column == "time":
                dt = self.item_time_map.get(iid)
                if dt is None:
                    return float('inf') if not reverse else float('-inf')
                return dt
            elif column == "record":
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return float('inf') if not reverse else float('-inf')
            elif column == "tier" or column == "stack_size":
                s = str(val).strip() if val else ""
                if s == "":
                    numeric = 999
                else:
                    try:
                        numeric = int(s)
                    except ValueError:
                        m = re.search(r"\d+", s)
                        numeric = int(m.group()) if m else 999
                return numeric
            else:
                return str(val).lower()

        # Sort all iids by the key
        key = {"record": record_key, "time": time_key}.get(column, sort_key)
        sorted_iids = sorted(children, key=key, reverse=reverse)

        # Reinsert in sorted order (one Tk call instead of one per row)
        self.tree.set_children("", *sorted_iids)
        self._restripe(sorted_iids)

        # Toggle sort direction for next click
        self.sort_reverse[column] = not reverse

    # ---------- Filtering ----------
    # @pyinstrument.profile()
    def apply_filters(self, search_query=None, *args):
        if search_query is None:
            search_query = self.search_var.get()
        search_query = search_query.lower().strip()

        selected_time = self.time_filter_var.get()
        now = datetime.now()

        # Collect iids that should be visible
        visible_iids = []

        # all_item_iids only holds existing top-level rows (deletes go
        # through TreeManager's hook), so no per-row exists/parent checks.
        for iid in self.all_item_iids:
            # Search match; row text is read from Tk once, then cached
            # until one of the row's cells changes.
            matches_search = True
            if search_query:
                text = self._search_text.get(iid)
                if text is None:
                    try:
                        values = self.tree.item(iid, "values")
                    except TclError:
                        continue
                    text = " ".join(str(v).lower() for v in values)
                    self._search_text[iid] = text
                matches_search = search_query in text

            # Time match
            dt = self.item_time_map.get(iid)
            matches_time = False
            if dt is None:
                matches_time = False
            else:
                delta = now - dt
                if selected_time == "All":
                    matches_time = True
                elif selected_time == "Today":
                    matches_time = dt.date() == now.date()
                elif selected_time == "Last hour":
                    matches_time = dt >= now - timedelta(hours=1)
                elif selected_time == "Last 2 hours":
                    matches_time = dt >= now - timedelta(hours=2)
                elif selected_time == "Last 12 hours":
                    matches_time = dt >= now - timedelta(hours=12)
                elif selected_time == "Last 24 hours":
                    matches_time = dt >= now - timedelta(hours=24)
                elif selected_time == "Last week":
                    matches_time = dt >= now - timedelta(weeks=1)
                elif selected_time == "Last 2 weeks":
                    matches_time = dt >= now - timedelta(weeks=2)
                elif selected_time == "Last month":
                    matches_time = dt >= now - timedelta(days=30)
                elif selected_time == "Last year":
                    matches_time = dt >= now - timedelta(days=365)
                elif selected_time == "Custom...":
                    if not getattr(self, "_custom_popup_open", False):
                        self.open_custom_hours_popup()
                    return

            if matches_search and matches_time:
                visible_iids.append((dt or datetime.min, iid))

        # Sort visible rows by timestamp descending
        visible_iids.sort(key=lambda x: x[0], reverse=True)

        # One call reattaches the visible rows in order and detaches
        # every other row (detached rows still exist).
        ordered = [iid for _, iid in visible_iids]
        self.tree.set_children("", *ordered)
        self._restripe(ordered)

    # @pyinstrument.profile()
    def open_custom_hours_popup(self):
        if getattr(self, "_custom_popup_open", False):
            return  # already open
        self._custom_popup_open = True

        def on_apply(hours):
            self.custom_hours_var.set(hours)
            self.time_filter_var.set("Custom")
            self.filter_tree_by_time()
            self._custom_popup_open = False

        CustomHoursPopup(
            parent=self.tree.winfo_toplevel(),
            initial_hours=self.custom_hours_var.get(),
            callback=on_apply
        )

    def _close_custom_popup(self, popup):
        self._custom_popup_open = False
        popup.destroy()

    # @pyinstrument.profile()
    def filter_tree_by_time(self, *args):
        current_search = self.search_var.get()
        self.apply_filters(search_query=current_search)
