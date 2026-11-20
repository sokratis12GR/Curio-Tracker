"""Session summary page.

Lives as its own page next to the tracker (switched from the page bar) and can
be popped out into a separate window and attached back again.
"""

import threading
from datetime import datetime, timedelta
from tkinter import Canvas, TclError

import customtkinter
from customtkinter import (CTkButton, CTkFrame, CTkImage, CTkLabel, CTkOptionMenu,
                           CTkScrollableFrame, CTkSegmentedButton, CTkToplevel)
from PIL import Image

import currency_utils
import summary_stats as ss
from fonts import make_font
from img_utils import get_cached_icon, get_icon
from gui.palette import (ACCENT_COLOR, CARD_COLOR, MUTED_TEXT, POE_PALETTE, SEPARATOR_COLOR,
                         themed)
from gui.tree.filtering import row_chaos_value
from settings import get_setting, set_setting

REFRESH_DEBOUNCE_MS = 200
RELAYOUT_DEBOUNCE_MS = 120
TICK_MS = 30_000
SPARK_HEIGHT = 64
# Readable text for buttons in every theme (muted text was near-invisible).
TEXT_COLOR = themed(("#1f2328", "#dcddde"), POE_PALETTE["gold_bright"])
ARROW_STYLE = dict(
    width=30, height=24, corner_radius=6,
    fg_color=SEPARATOR_COLOR, hover_color=ACCENT_COLOR,
    text_color=TEXT_COLOR, text_color_disabled=MUTED_TEXT,
)
TABLE_LIMIT = 6       # rows shown before "Show all"
DROPS_PER_PAGE = 8
DROP_ICON = (28, 28)
PICKED_VALUES = ("True", "TRUE", "true", True)
NAME_MAX = 38

PAGE_TRACKER = "Tracker"
PAGE_SUMMARY = "Summary"
# Content width at which the dashboard uses 2 / 3 columns.
TWO_COL_WIDTH = 620
THREE_COL_WIDTH = 960
DEFAULT_WINDOW_GEOMETRY = "980x720"

# Card placement per column count (keys of self._cards).
COLUMN_PLANS = {
    1: [["session", "wing_time", "value", "drops", "tiers", "types", "blueprints", "levels", "all"]],
    2: [["session", "wing_time", "value", "tiers", "all"],
        ["drops", "types", "blueprints", "levels"]],
    3: [["session", "wing_time", "value", "all"],
        ["drops", "tiers"],
        ["types", "blueprints", "levels"]],
}


def _mode_color(pair):
    # Canvas needs a plain colour; pick the slot for the current appearance mode.
    if isinstance(pair, (tuple, list)):
        return pair[1] if customtkinter.get_appearance_mode() == "Dark" else pair[0]
    return pair


class SummaryFrame:
    def __init__(self, page_bar, summary_page, tracker_page, tree_manager):
        self.tm = tree_manager
        self.page_bar = page_bar
        self.summary_page = summary_page
        self.tracker_page = tracker_page
        self.app_start = datetime.now()
        self.session_start = self.app_start
        self._refresh_job = None
        self._tick_job = None
        self._relayout_job = None
        self._columns = 0
        self._window = None
        self.content = None
        self._host = None
        self._expanded = set()  # table keys showing all rows
        self._drops = []
        self._drop_page = 0
        self._drop_token = 0
        self._drops_sig = None
        self._recent = []
        self._fmt = str

        mode = get_setting("Summary", "session_mode", ss.SESSION_APP_START)
        self.session_mode = mode if mode in ss.SESSION_MODES else ss.SESSION_APP_START
        idle_min = get_setting("Summary", "idle_minutes", 15)
        self.idle = ss.DEFAULT_IDLE
        if isinstance(idle_min, (int, float)) and idle_min > 0:
            self.idle = timedelta(minutes=idle_min)

        view = get_setting("Summary", "view", PAGE_TRACKER)
        self.view = view if view in (PAGE_TRACKER, PAGE_SUMMARY) else PAGE_TRACKER
        self.detached = bool(get_setting("Summary", "detached", False))

        # Callbacks go through the toplevel so main's on_closing (which
        # cancels every pending `after` via root) unregisters them cleanly.
        self._root = page_bar.winfo_toplevel()
        self._alive = True
        self._root.bind("<Destroy>", self._on_root_destroy, add="+")

        self._build_page_bar()
        if self.detached:
            self.view = PAGE_TRACKER
            self._after(0, self._open_window)
        self._show_view()

    # ---------- Lifetime ----------
    def _on_root_destroy(self, event):
        if event.widget is self._root:
            self._alive = False

    def _after(self, ms, func):
        return self._root.after(ms, func) if self._alive else None

    def _cancel(self, job):
        if job is not None:
            try:
                self._root.after_cancel(job)
            except (TclError, ValueError):
                pass

    @property
    def visible(self):
        return self._alive and (self.detached or self.view == PAGE_SUMMARY)

    # ---------- Page bar / attach & detach ----------
    def _build_page_bar(self):
        self.page_switch = CTkSegmentedButton(
            self.page_bar, values=[PAGE_TRACKER, PAGE_SUMMARY], height=28,
            font=make_font(12, "bold"), command=self._on_page_selected,
        )
        self.page_switch.grid(row=0, column=0, sticky="w")
        self.detach_btn = CTkButton(
            self.page_bar, height=28, width=120, font=make_font(11),
            fg_color=SEPARATOR_COLOR, hover_color=ACCENT_COLOR, text_color=TEXT_COLOR,
            command=self.toggle_detached,
        )
        self.detach_btn.grid(row=0, column=2, sticky="e")

    def _on_page_selected(self, value):
        if value == PAGE_SUMMARY and self.detached:
            # The summary already has its own window; bring it forward instead.
            self.page_switch.set(PAGE_TRACKER)
            if self._window is not None:
                self._window.deiconify()
                self._window.lift()
                self._window.focus_force()
            return
        self.view = value
        set_setting("Summary", "view", value)
        self._show_view()

    def _show_view(self):
        self.page_switch.set(self.view)
        self.detach_btn.configure(text="⇲ Attach summary" if self.detached else "⧉ Pop out summary")
        if self.view == PAGE_SUMMARY and not self.detached:
            self.tracker_page.grid_remove()
            self.summary_page.grid(row=1, column=0, sticky="nsew")
            if self.content is None or self._host is not self.summary_page:
                self._mount(self.summary_page)
        else:
            self.summary_page.grid_remove()
            self.tracker_page.grid(row=1, column=0, sticky="nsew")
        if self.visible:
            self.schedule_refresh()
            self._schedule_tick()

    def toggle_detached(self):
        if self.detached:
            self.attach()
        else:
            self.detach()

    def detach(self):
        if self.detached:
            return
        self.detached = True
        set_setting("Summary", "detached", True)
        self.view = PAGE_TRACKER
        set_setting("Summary", "view", PAGE_TRACKER)
        self._open_window()
        self._show_view()

    def _open_window(self):
        if self._window is not None or not self._alive:
            return
        win = CTkToplevel(self._root)
        win.title("Session Summary")
        win.geometry(get_setting("Summary", "window_geometry", DEFAULT_WINDOW_GEOMETRY)
                     or DEFAULT_WINDOW_GEOMETRY)
        win.minsize(360, 320)
        win.grid_rowconfigure(0, weight=1)
        win.grid_columnconfigure(0, weight=1)
        win.protocol("WM_DELETE_WINDOW", self.attach)
        self._window = win
        self._geom_job = None

        def save_geometry():
            self._geom_job = None
            if self._window is win:
                try:
                    set_setting("Summary", "window_geometry", win.geometry())
                except TclError:
                    pass

        def on_configure(event):
            # Debounced so dragging the window doesn't write settings constantly.
            if event.widget is win:
                self._cancel(self._geom_job)
                self._geom_job = self._after(600, save_geometry)

        win.bind("<Configure>", on_configure, add="+")
        self._mount(win)
        self.schedule_refresh()
        self._schedule_tick()

    def attach(self):
        if not self.detached:
            return
        self.detached = False
        set_setting("Summary", "detached", False)
        win, self._window = self._window, None
        if win is not None:
            try:
                set_setting("Summary", "window_geometry", win.geometry())
            except TclError:
                pass
            self.content = None
            win.destroy()
        self.view = PAGE_SUMMARY
        set_setting("Summary", "view", PAGE_SUMMARY)
        self._show_view()

    # ---------- Building ----------
    def _mount(self, host):
        """(Re)build the dashboard inside `host` (the page or the pop-out window)."""
        if self.content is not None:
            try:
                self.content.destroy()
            except TclError:
                pass
        self._columns = 0
        self._drops_sig = None
        self._host = host
        self.content = CTkScrollableFrame(host, corner_radius=8, fg_color="transparent")
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self._build()
        self.content.bind("<Configure>", self._on_content_configure, add="+")
        self._relayout()

    def _card(self, key, title):
        card = CTkFrame(self.body, fg_color=CARD_COLOR, corner_radius=10)
        card.grid_columnconfigure(0, weight=1)
        head = CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="we", padx=12, pady=(10, 4))
        CTkFrame(head, width=4, height=16, corner_radius=2, fg_color=ACCENT_COLOR
                 ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        CTkLabel(head, text=title, font=make_font(13, "bold"), anchor="w", height=18
                 ).grid(row=0, column=1, sticky="w")
        inner = CTkFrame(card, fg_color="transparent")
        inner.grid(row=1, column=0, sticky="we", padx=4, pady=(0, 10))
        inner.grid_columnconfigure(1, weight=1)
        inner._cells = {}
        self._cards[key] = card
        return inner

    def _stat(self, inner, caption):
        row = inner.grid_size()[1]
        CTkLabel(inner, text=caption, font=make_font(12), text_color=MUTED_TEXT,
                 anchor="w", height=22).grid(row=row, column=0, sticky="w", padx=(10, 6))
        value = CTkLabel(inner, text="—", font=make_font(12, "bold"), anchor="e", height=22)
        value.grid(row=row, column=1, sticky="e", padx=(6, 10))
        return value

    def _kpi(self, parent, col, caption):
        tile = CTkFrame(parent, fg_color=CARD_COLOR, corner_radius=10)
        tile.grid(row=0, column=col, sticky="nsew", padx=4)
        CTkLabel(tile, text=caption.upper(), font=make_font(10, "bold"), text_color=MUTED_TEXT,
                 anchor="w", height=14).pack(fill="x", padx=12, pady=(10, 0))
        value = CTkLabel(tile, text="—", font=make_font(20, "bold"), anchor="w", height=28)
        value.pack(fill="x", padx=12, pady=(0, 10))
        return value

    def _build(self):
        c = self.content
        self._cards = {}

        header = CTkFrame(c, fg_color="transparent")
        header.grid(row=0, column=0, sticky="we", padx=4, pady=(4, 0))
        header.grid_columnconfigure(1, weight=1)
        title_box = CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w", padx=4)
        CTkLabel(title_box, text="Session Summary", font=make_font(18, "bold"), anchor="w",
                 height=24).grid(row=0, column=0, sticky="w")
        self.since_label = CTkLabel(title_box, text="", font=make_font(11), text_color=MUTED_TEXT,
                                    anchor="w", height=16)
        self.since_label.grid(row=1, column=0, sticky="w")
        controls = CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=2, sticky="e", padx=4)
        self.mode_menu = CTkOptionMenu(
            controls, values=list(ss.SESSION_MODES), width=160, height=28,
            font=make_font(12), command=self._on_mode_changed,
        )
        self.mode_menu.set(self.session_mode)
        self.mode_menu.grid(row=0, column=0, padx=(0, 6))
        CTkButton(controls, text="Reset", width=70, height=28, font=make_font(12),
                  command=self.reset_session).grid(row=0, column=1)

        kpis = CTkFrame(c, fg_color="transparent")
        kpis.grid(row=1, column=0, sticky="we", pady=(10, 4))
        for i in range(5):
            kpis.grid_columnconfigure(i, weight=1, uniform="kpi")
        self.kpi_active = self._kpi(kpis, 0, "Active time")
        self.kpi_wings = self._kpi(kpis, 1, "Wings")
        self.kpi_wph = self._kpi(kpis, 2, "Wings / hour")
        self.kpi_value = self._kpi(kpis, 3, "Total value")
        self.kpi_vph = self._kpi(kpis, 4, "Value / hour")

        self.body = CTkFrame(c, fg_color="transparent")
        self.body.grid(row=2, column=0, sticky="we", pady=(4, 4))
        self._column_frames = [CTkFrame(self.body, fg_color="transparent") for _ in range(3)]

        inner = self._card("session", "Session")
        self.lbl_elapsed = self._stat(inner, "Duration")
        self.lbl_active = self._stat(inner, "Active time")
        self.lbl_wings = self._stat(inner, "Wings")
        self.lbl_rewards = self._stat(inner, "Rewards")
        self.lbl_wph = self._stat(inner, "Wings / hour")

        inner = self._card("wing_time", "Wing time")
        self.lbl_avg = self._stat(inner, "Average")
        self.lbl_median = self._stat(inner, "Median")
        self.lbl_fast = self._stat(inner, "Fastest")
        self.lbl_slow = self._stat(inner, "Slowest")
        self.spark = Canvas(inner, height=SPARK_HEIGHT, highlightthickness=0, bd=0)
        self.spark.grid(row=inner.grid_size()[1], column=0, columnspan=2, sticky="we",
                        padx=10, pady=(8, 0))
        self.spark.grid_remove()  # shown once there are wing times
        self.spark.bind("<Configure>", lambda _e: self._draw_sparkline())

        inner = self._card("value", "Value")
        self.lbl_value = self._stat(inner, "Total")
        self.lbl_picked = self._stat(inner, "Picked")
        self.lbl_per_wing = self._stat(inner, "Per wing")
        self.lbl_per_hour = self._stat(inner, "Per active hour")

        self._build_top_drops()

        self.tier_card = self._card("tiers", "Unique tiers")
        self.tier_card._key = "tiers"
        self.type_card = self._card("types", "By item type")
        self.type_card._key = "types"
        self.bp_card = self._card("blueprints", "By blueprint")
        self.bp_card._key = "blueprints"
        self.lvl_card = self._card("levels", "By area level")
        self.lvl_card._key = "levels"

        inner = self._card("all", "All loaded (comparison)")
        self.lbl_all_wings = self._stat(inner, "Wings")
        self.lbl_all_avg = self._stat(inner, "Avg wing time")
        self.lbl_all_per_wing = self._stat(inner, "Value / wing")

    # ---------- Responsive columns ----------
    def _on_content_configure(self, event):
        if event.widget is not self.content:
            return
        self._cancel(self._relayout_job)
        self._relayout_job = self._after(RELAYOUT_DEBOUNCE_MS, self._relayout)

    def _relayout(self):
        self._relayout_job = None
        if self.content is None:
            return
        try:
            width = self.content.winfo_width()
        except TclError:
            return
        if width <= 1:
            width = THREE_COL_WIDTH  # not mapped yet; settle on the next Configure
        n = 3 if width >= THREE_COL_WIDTH else 2 if width >= TWO_COL_WIDTH else 1
        if n == self._columns:
            return  # nothing to move: avoids re-packing every card on each resize step
        self._columns = n
        for i, col in enumerate(self._column_frames):
            if i < n:
                self.body.grid_columnconfigure(i, weight=1, uniform="col")
                col.grid(row=0, column=i, sticky="new", padx=4)
            else:
                self.body.grid_columnconfigure(i, weight=0, uniform="")
                col.grid_remove()
        for i, keys in enumerate(COLUMN_PLANS[n]):
            for key in keys:
                card = self._cards[key]
                card.pack_forget()
                card.pack(in_=self._column_frames[i], fill="x", pady=(0, 8))

    # ---------- Events ----------
    def _on_mode_changed(self, mode):
        self.session_mode = mode
        set_setting("Summary", "session_mode", mode)
        self.schedule_refresh()

    def reset_session(self):
        self.session_start = datetime.now()
        if self.session_mode != ss.SESSION_APP_START:
            self.mode_menu.set(ss.SESSION_APP_START)
            self._on_mode_changed(ss.SESSION_APP_START)
        else:
            self.schedule_refresh()

    def schedule_refresh(self):
        if not self.visible or self.content is None:
            return
        self._cancel(self._refresh_job)
        self._refresh_job = self._after(REFRESH_DEBOUNCE_MS, self.refresh)

    def _schedule_tick(self):
        if self._tick_job is not None:
            return

        def tick():
            self._tick_job = None
            if self.visible:
                self.refresh()
                self._schedule_tick()

        self._tick_job = self._after(TICK_MS, tick)

    # ---------- Data ----------
    def _collect(self):
        rewards = []
        tm = self.tm
        for iid in list(tm.all_item_iids):
            t = tm.item_time_map.get(iid)
            item = tm.csv_row_map.get(iid)
            if t is None or item is None:
                continue
            entry = tm._row_totals_entry(iid)
            if entry is not None:
                chaos, picked = entry
            else:
                chaos = row_chaos_value(item)
                picked = getattr(item, "picked", False) in PICKED_VALUES
            try:
                record = int(str(getattr(item, "record_number", 0) or 0))
            except ValueError:
                record = 0
            rewards.append(ss.Reward(
                time=t, record=record,
                blueprint=str(getattr(item, "blueprint_type", "") or "Unknown"),
                area_level=str(getattr(item, "area_level", "") or "?"),
                chaos=chaos or 0.0, picked=bool(picked), ref=iid,
                item_type=str(getattr(item, "type", "") or ""),
                tier=str(getattr(item, "tier", "") or ""),
                img=str(getattr(item, "img", "") or ""),
            ))
        return rewards

    def _value_fmt(self):
        total_frame = getattr(self.tm, "total_frame", None)
        mode = total_frame.value_mode.get() if total_frame else "Chaos"
        divine = currency_utils.convert_to_float(get_setting("Application", "divine_equivalent", 0))
        if mode == "Divine" and divine > 0:
            return lambda c: "—" if not c else f"{c / divine:,.2f} div"
        return lambda c: "—" if not c else f"{c:,.0f} c"

    def refresh(self):
        self._refresh_job = None
        if not self.visible or self.content is None:
            return
        try:
            self._refresh()
        except TclError:
            pass  # widget destroyed during shutdown / re-mount

    def _refresh(self):
        rewards = self._collect()
        now = datetime.now()
        fmt = self._value_fmt()
        dur = ss.format_duration

        session_start = None
        if self.session_mode == ss.SESSION_APP_START:
            session_start = self.session_start
            session_rewards = ss.select_session(rewards, self.session_mode, self.session_start,
                                                self.idle * 2)
        else:
            session_rewards = ss.select_session(rewards, self.session_mode, None, self.idle * 2)
        s = ss.summarize(session_rewards, now=now, session_start=session_start, idle=self.idle)

        self.since_label.configure(
            text=f"Started {s.start.strftime('%d %b %H:%M')}" if s.start else "No rewards yet")
        self.kpi_active.configure(text=dur(s.active) if s.active else "—")
        self.kpi_wings.configure(text=str(s.wings))
        self.kpi_wph.configure(text=f"{s.wings_per_hour:.1f}" if s.wings_per_hour else "—")
        self.kpi_value.configure(text=fmt(s.chaos))
        self.kpi_vph.configure(text=fmt(s.chaos_per_hour))

        self.lbl_elapsed.configure(text=dur(s.elapsed) if s.start else "—")
        self.lbl_active.configure(text=dur(s.active) if s.active else "—")
        self.lbl_wings.configure(text=str(s.wings))
        self.lbl_rewards.configure(text=str(s.rewards))
        self.lbl_wph.configure(text=f"{s.wings_per_hour:.1f}" if s.wings_per_hour else "—")

        self.lbl_avg.configure(text=dur(s.avg_wing))
        self.lbl_median.configure(text=dur(s.median_wing))
        self.lbl_fast.configure(text=dur(s.fastest))
        self.lbl_slow.configure(text=dur(s.slowest))
        self._recent = s.recent_durations
        if self._recent:
            self.spark.grid()
        else:
            self.spark.grid_remove()
        self._draw_sparkline()

        self.lbl_value.configure(text=fmt(s.chaos))
        self.lbl_picked.configure(text=f"{fmt(s.picked_chaos)} ({s.picked_count})"
                                  if s.picked_count else "—")
        self.lbl_per_wing.configure(text=fmt(s.chaos_per_wing))
        self.lbl_per_hour.configure(text=fmt(s.chaos_per_hour))

        self._fmt = fmt
        self._drops = s.top_drops
        pages = max(1, -(-len(self._drops) // DROPS_PER_PAGE))
        self._drop_page = min(self._drop_page, pages - 1)  # keep the page while browsing
        self._render_drops()

        tiers = sorted(s.by_tier.items(), key=lambda kv: (kv[0] == "Untiered", kv[0]))
        tier_rows = [(k, str(g.count), str(g.picked), fmt(g.chaos)) for k, g in tiers]
        footer = []
        for key, g in tiers:
            if key != "Untiered" and g.count and s.wings:
                footer.append(f"{key}: 1 per {s.wings / g.count:,.1f} wings")
        self._fill_table(self.tier_card, ("Tier", "Count", "Picked", "Value"), tier_rows,
                         empty="No uniques yet", footer=footer)

        types = sorted(s.by_type.items(), key=lambda kv: -kv[1].chaos)
        self._fill_table(self.type_card, ("Type", "Count", "Picked", "Value"),
                         [(k, str(g.count), str(g.picked), fmt(g.chaos)) for k, g in types],
                         empty="No rewards yet")

        def wing_rows(groups, key_fmt=str):
            ordered = sorted(groups.items(), key=lambda kv: (-kv[1].wings, str(kv[0])))
            return [(key_fmt(k), str(g.wings), dur(g.avg), fmt(g.chaos)) for k, g in ordered]

        self._fill_table(self.bp_card, ("Blueprint", "Wings", "Avg", "Value"),
                         wing_rows(s.by_blueprint))
        self._fill_table(self.lvl_card, ("Area", "Wings", "Avg", "Value"),
                         wing_rows(s.by_area_level, lambda k: f"Level {k}"))

        if self.session_mode == ss.SESSION_ALL:
            a = s
        else:
            a = ss.summarize(rewards, now=now, idle=self.idle)
        self.lbl_all_wings.configure(text=str(a.wings))
        self.lbl_all_avg.configure(text=dur(a.avg_wing))
        self.lbl_all_per_wing.configure(text=fmt(a.chaos_per_wing))

    # ---------- Tables (widgets are reused between refreshes) ----------
    @staticmethod
    def _cell(card, key, factory, used):
        widget = card._cells.get(key)
        if widget is None:
            widget = factory()
            card._cells[key] = widget
        used.add(key)
        return widget

    def _fill_table(self, card, headers, rows, empty="No wings yet", footer=()):
        used = set()
        last = len(headers) - 1

        def pad(col):
            return (10 if col == 0 else 6, 10 if col == last else 6)

        if not rows:
            lbl = self._cell(card, "empty", lambda: CTkLabel(
                card, font=make_font(12), text_color=MUTED_TEXT, height=22), used)
            lbl.configure(text=empty)
            lbl.grid(row=0, column=0, columnspan=4, padx=10, pady=2)
        else:
            card.grid_columnconfigure(0, weight=1)
            card.grid_columnconfigure(1, weight=0)
            for col, title in enumerate(headers):
                lbl = self._cell(card, ("h", col), lambda: CTkLabel(
                    card, font=make_font(10, "bold"), text_color=MUTED_TEXT, height=16), used)
                lbl.configure(text=title.upper())
                lbl.grid(row=0, column=col, sticky="e" if col else "w", padx=pad(col), pady=(0, 2))
            expanded = card._key in self._expanded
            shown = rows if expanded else rows[:TABLE_LIMIT]
            for row, cells in enumerate(shown, start=1):
                for col, text in enumerate(cells):
                    lbl = self._cell(card, (row, col), lambda c=col: CTkLabel(
                        card, font=make_font(12, "bold" if c == 0 else "normal"), height=22,
                        anchor="w" if c == 0 else "e"), used)
                    lbl.configure(text=text)
                    lbl.grid(row=row, column=col, sticky="w" if col == 0 else "e", padx=pad(col))
            row = len(shown) + 1
            for i, line in enumerate(footer):
                lbl = self._cell(card, ("f", i), lambda: CTkLabel(
                    card, font=make_font(11), text_color=MUTED_TEXT, height=16, anchor="w"), used)
                lbl.configure(text=line)
                lbl.grid(row=row, column=0, columnspan=len(headers), sticky="w", padx=10)
                row += 1
            if len(rows) > TABLE_LIMIT:
                btn = self._cell(card, "more", lambda: CTkButton(
                    card, height=22, font=make_font(11), fg_color="transparent",
                    text_color=MUTED_TEXT, hover_color=SEPARATOR_COLOR,
                    command=lambda c=card: self._toggle_table(c)), used)
                btn.configure(text="Show less" if expanded else f"Show all ({len(rows)})")
                btn.grid(row=row, column=0, columnspan=len(headers), sticky="we", padx=6, pady=(4, 0))

        for key, widget in card._cells.items():
            if key not in used:
                widget.grid_remove()

    def _toggle_table(self, card):
        self._expanded.symmetric_difference_update({card._key})
        self.schedule_refresh()

    # ---------- Top drops ----------
    def _build_top_drops(self):
        inner = self._card("drops", "Top drops")
        inner.grid_columnconfigure(0, weight=1)
        self.drops_list = CTkFrame(inner, fg_color="transparent")
        self.drops_list.grid(row=0, column=0, columnspan=2, sticky="we")
        self.drops_list.grid_columnconfigure(1, weight=1)

        self.drops_empty = CTkLabel(self.drops_list, text="No priced drops yet", font=make_font(12),
                                    text_color=MUTED_TEXT, height=22)
        self._drop_rows = []
        for i in range(DROPS_PER_PAGE):
            icon = CTkLabel(self.drops_list, text="", width=DROP_ICON[0], height=DROP_ICON[1])
            text_box = CTkFrame(self.drops_list, fg_color="transparent")
            name = CTkLabel(text_box, text="", font=make_font(12, "bold"), anchor="w", height=17)
            name.grid(row=0, column=0, sticky="w")
            meta = CTkLabel(text_box, text="", font=make_font(10), text_color=MUTED_TEXT,
                            anchor="w", height=14)
            meta.grid(row=1, column=0, sticky="w")
            value = CTkLabel(self.drops_list, text="", font=make_font(12, "bold"), anchor="e",
                             height=22)
            self._drop_rows.append((icon, text_box, name, meta, value))

        nav = CTkFrame(inner, fg_color="transparent")
        nav.grid(row=1, column=0, columnspan=2, sticky="we", padx=6, pady=(6, 0))
        nav.grid_columnconfigure(1, weight=1)
        self.drops_prev = CTkButton(nav, text="◀", command=lambda: self._page_drops(-1),
                                    font=make_font(12, "bold"), **ARROW_STYLE)
        self.drops_prev.grid(row=0, column=0)
        self.drops_pos = CTkLabel(nav, text="", font=make_font(11), text_color=MUTED_TEXT, height=16)
        self.drops_pos.grid(row=0, column=1)
        self.drops_next = CTkButton(nav, text="▶", command=lambda: self._page_drops(1),
                                    font=make_font(12, "bold"), **ARROW_STYLE)
        self.drops_next.grid(row=0, column=2)
        self._wheel_targets(self._cards["drops"])

    def _wheel_targets(self, widget):
        # Wheel over the drops list pages through it instead of scrolling the page.
        def on_wheel(event):
            step = -1 if (getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4) else 1
            self._page_drops(step)
            return "break"

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            widget.bind(seq, on_wheel)
        for child in widget.winfo_children():
            self._wheel_targets(child)

    def _page_drops(self, step):
        pages = max(1, -(-len(self._drops) // DROPS_PER_PAGE))
        new_page = min(max(self._drop_page + step, 0), pages - 1)
        if new_page != self._drop_page:
            self._drop_page = new_page
            self._render_drops()

    def _render_drops(self):
        fmt = self._fmt
        drops = self._drops
        start = self._drop_page * DROPS_PER_PAGE
        page = drops[start:start + DROPS_PER_PAGE]
        sig = (start, len(drops), tuple((r.ref, r.chaos) for r in page), fmt(1.0))
        if sig == self._drops_sig:
            return  # same page as last time: skip touching the widgets
        self._drops_sig = sig
        self._drop_token += 1

        if not drops:
            self.drops_empty.grid(row=0, column=0, columnspan=3, padx=10, pady=4)
        else:
            self.drops_empty.grid_remove()
        for i, (icon, text_box, name_lbl, meta_lbl, value_lbl) in enumerate(self._drop_rows):
            if i >= len(page):
                icon.grid_remove()
                text_box.grid_remove()
                value_lbl.grid_remove()
                continue
            r = page[i]
            name = self._drop_name(r)
            if len(name) > NAME_MAX:
                name = name[:NAME_MAX - 1] + "…"
            meta = [ss.tier_label(r.tier) if r.item_type in ss.UNIQUE_TYPES and r.tier else "",
                    r.item_type, r.time.strftime("%d %b %H:%M")]
            name_lbl.configure(text=name)
            meta_lbl.configure(text=" · ".join(m for m in meta if m))
            value_lbl.configure(text=fmt(r.chaos))
            icon.configure(image=None)
            icon.grid(row=i, column=0, padx=(8, 8), pady=3)
            text_box.grid(row=i, column=1, sticky="we")
            value_lbl.grid(row=i, column=2, sticky="e", padx=(4, 10))
            self._load_drop_icon(icon, r)

        if drops:
            self.drops_pos.configure(text=f"{start + 1}–{start + len(page)} of {len(drops)}")
        else:
            self.drops_pos.configure(text="")
        self.drops_prev.configure(state="normal" if start > 0 else "disabled")
        self.drops_next.configure(state="normal" if start + len(page) < len(drops) else "disabled")

    def _drop_name(self, r):
        if not r.name:
            try:
                r.name = str(self.tm.tree.set(r.ref, "item"))
            except TclError:
                r.name = ""
        return r.name or r.item_type or "Unknown"

    def _load_drop_icon(self, label, r):
        if not r.img:
            return
        key = f"{r.name or r.ref} [summary]"
        cached = get_cached_icon(key, DROP_ICON)
        if cached is not None:
            self._set_icon(label, cached)
            return
        token = self._drop_token

        def load():
            pil = get_icon(name=key, url=r.img, size=DROP_ICON, return_pil=True)
            if isinstance(pil, Image.Image) and self._alive:
                self._after(0, lambda: token == self._drop_token and self._set_icon(label, pil))

        threading.Thread(target=load, daemon=True).start()

    @staticmethod
    def _set_icon(label, pil):
        try:
            label.configure(image=CTkImage(light_image=pil, dark_image=pil, size=DROP_ICON))
        except TclError:
            pass

    def _draw_sparkline(self):
        c = self.spark
        try:
            c.delete("all")
            c.configure(bg=_mode_color(CARD_COLOR))
            width = c.winfo_width()
        except TclError:
            return
        values = [d.total_seconds() for d in self._recent]
        if width <= 1 or not values:
            return
        peak = max(values) or 1
        avg = sum(values) / len(values)
        slot = width / len(values)
        bar = max(2.0, slot * 0.7)
        accent = _mode_color(ACCENT_COLOR)
        muted = _mode_color(MUTED_TEXT)
        for i, v in enumerate(values):
            h = max(2.0, (v / peak) * (SPARK_HEIGHT - 4))
            x = i * slot + (slot - bar) / 2
            c.create_rectangle(x, SPARK_HEIGHT - h, x + bar, SPARK_HEIGHT, fill=accent, width=0)
        y = SPARK_HEIGHT - (avg / peak) * (SPARK_HEIGHT - 4)
        c.create_line(0, y, width, y, fill=muted, dash=(3, 3))
