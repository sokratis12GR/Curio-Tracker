import re
from datetime import datetime, timedelta

import currency_utils
from gui.popups.custom_hours import CustomHoursPopup
from settings import get_setting


def _get_row_tag(index):
    return "odd" if index % 2 == 0 else "even"


class TreeFilteringMixin:
    def calculate_totals(self):
        total_chaos = 0.0
        total_divine = 0.0
        picked_chaos = 0.0
        picked_divine = 0.0

        league_divine_equiv = currency_utils.convert_to_float(
            get_setting("Application", "divine_equivalent", 0)
        )

        for iid in self.all_item_iids:
            if not self.tree.exists(iid):
                continue

            item = self.csv_row_map.get(iid)
            if not item:
                continue

            chaos_value = currency_utils.convert_to_float(getattr(item, "chaos_value", 0))
            stack_size, _ = currency_utils.get_stack_size(item)
            chaos_value *= stack_size

            divine_value = chaos_value / league_divine_equiv if league_divine_equiv > 0 else 0

            total_chaos += chaos_value
            total_divine += divine_value

            picked_value = self.tree.set(iid, "picked")
            if str(picked_value).strip() in ("☑", "True", "true", "YES", "yes"):
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
        sorted_iids = sorted(children, key=sort_key, reverse=reverse)

        # Reinsert in sorted order
        for index, iid in enumerate(sorted_iids):
            self.tree.move(iid, "", index)
            tag = _get_row_tag(index)
            self.tree.item(iid, tags=(tag,))

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

        for iid in self.all_item_iids:
            if not self.tree.exists(iid) or self.tree.parent(iid) != "":
                continue

            # Search match
            values = self.tree.item(iid, "values")
            text = " ".join(str(v).lower() for v in values)
            matches_search = search_query in text if search_query else True

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

        # Reattach in correct order
        for _, iid in visible_iids:
            self.tree.reattach(iid, "", "end")

        # Detach invisible rows
        invisible_iids = set(self.all_item_iids) - {iid for _, iid in visible_iids}
        for iid in invisible_iids:
            if self.tree.exists(iid):
                self.tree.detach(iid)

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
