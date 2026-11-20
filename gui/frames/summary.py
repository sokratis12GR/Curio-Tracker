"""Session summary page.

Lives as its own page next to the tracker (switched from the page bar) and can
be popped out into a separate window and attached back again.
"""

import threading
from datetime import datetime, timedelta
from tkinter import Canvas, TclError

import customtkinter
from customtkinter import (CTkButton, CTkEntry, CTkFrame, CTkImage, CTkLabel, CTkOptionMenu,
                           CTkProgressBar, CTkScrollableFrame, CTkSegmentedButton, CTkSwitch, CTkToplevel,
                           ThemeManager)
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
SPARK_SLOT_MAX = 20
SPARK_BAR_MAX = 14
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
    1: [["session", "trend", "wing_time", "value", "drops", "tiers", "types", "blueprints",
         "levels", "all"]],
    2: [["session", "wing_time", "value", "tiers", "all"],
        ["trend", "drops", "types", "blueprints", "levels"]],
    3: [["session", "wing_time", "value", "all"],
        ["trend", "drops", "tiers"],
        ["types", "blueprints", "levels"]],
}
TREND_HEIGHT = 130
BEST_NAME_MAX = 26


DT_FORMAT = "%Y-%m-%d %H:%M"
UP_COLOR = ("#1a7f37", "#3ba55d")
DOWN_COLOR = ("#c62828", "#ed4245")


DATE_LABEL = "%d %b %Y %H:%M"
FILTER_DIMS = (("league", "League"), ("year", "Year"), ("blueprint", "Blueprint"),
               ("area_level", "Area level"), ("item_type", "Type"), ("tier", "Tier"))
TABLE_FILTERS = {"blueprints": "blueprint", "levels": "area_level",
                 "types": "item_type", "tiers": "tier"}


def _any(label):
    return f"Any {label.lower()}"


def _natural_key(value):
    text = str(value)
    try:
        return (0, float(text.lstrip("T")), text)
    except ValueError:
        return (1, 0.0, text.lower())


def _parse_dt(text):
    text = str(text or "").strip()
    if not text:
        return None
    for f in (DT_FORMAT, "%Y-%m-%d"):
        try:
            return datetime.strptime(text, f)
        except ValueError:
            pass
    return None


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
        self.filters = {dim: None for dim, _ in FILTER_DIMS}
        self.picked_only = False
        self._sort = {}  # table key -> (column, descending)
        self._copy_sections = []

        mode = get_setting("Summary", "session_mode", ss.SESSION_APP_START)
        self.session_mode = mode if mode in ss.SESSION_MODES else ss.SESSION_APP_START
        idle_min = get_setting("Summary", "idle_minutes", 15)
        self.idle = ss.DEFAULT_IDLE
        if isinstance(idle_min, (int, float)) and idle_min > 0:
            self.idle = timedelta(minutes=idle_min)
        self.custom_range = (_parse_dt(get_setting("Summary", "custom_from", "")),
                             _parse_dt(get_setting("Summary", "custom_to", "")))
        if self.session_mode == ss.SESSION_CUSTOM and self.custom_range[0] is None:
            self.session_mode = ss.SESSION_APP_START
        self._last_mode = self.session_mode
        self.min_wing = ss.DEFAULT_MIN_WING
        min_sec = get_setting("Summary", "min_wing_seconds", int(ss.DEFAULT_MIN_WING.total_seconds()))
        if isinstance(min_sec, (int, float)) and min_sec >= 0:
            self.min_wing = timedelta(seconds=min_sec)

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
        inner._title = title
        self._cards[key] = card
        return inner

    def _copy_rows(self, section):
        for name, rows in self._copy_sections:
            if name == section:
                return rows
        rows = []
        self._copy_sections.append((section, rows))
        return rows

    def _stat(self, inner, caption):
        row = inner.grid_size()[1]
        cap = CTkLabel(inner, text=caption, font=make_font(12), text_color=MUTED_TEXT,
                       anchor="w", height=22)
        cap.grid(row=row, column=0, sticky="w", padx=(10, 6))
        value = CTkLabel(inner, text="—", font=make_font(12, "bold"), anchor="e", height=22)
        value.grid(row=row, column=1, sticky="e", padx=(6, 10))
        self._bind_copy((cap, value), lambda: f"{caption}: {value.cget('text')}")
        self._copy_rows(inner._title).append((caption, value))
        return value

    def _kpi(self, parent, col, caption):
        tile = CTkFrame(parent, fg_color=CARD_COLOR, corner_radius=10)
        tile.grid(row=0, column=col, sticky="nsew", padx=4)
        cap = CTkLabel(tile, text=caption.upper(), font=make_font(10, "bold"), text_color=MUTED_TEXT,
                       anchor="w", height=14)
        cap.pack(fill="x", padx=12, pady=(10, 0))
        value = CTkLabel(tile, text="—", font=make_font(20, "bold"), anchor="w", height=28)
        value.pack(fill="x", padx=12, pady=0)
        value._delta = CTkLabel(tile, text="", font=make_font(10), text_color=MUTED_TEXT,
                                anchor="w", height=14)
        value._delta.pack(fill="x", padx=12, pady=(0, 8))

        def text():
            delta = value._delta.cget("text")
            return f"{caption}: {value.cget('text')}" + (f" ({delta})" if delta else "")

        self._bind_copy((tile, cap, value, value._delta), text)
        self._copy_rows("Overview").append((caption, value))
        return value

    @staticmethod
    def _set_delta(kpi, current, previous):
        """Show the change against the previous period under a KPI tile."""
        change = ss.pct_change(current, previous)
        if change is None:
            kpi._delta.configure(text="", text_color=MUTED_TEXT)
        elif abs(change) < 0.5:
            kpi._delta.configure(text="= vs prev. period", text_color=MUTED_TEXT)
        else:
            arrow, color = ("▲", UP_COLOR) if change > 0 else ("▼", DOWN_COLOR)
            kpi._delta.configure(text=f"{arrow} {abs(change):.0f}% vs prev. period",
                                 text_color=color)

    def _build(self):
        c = self.content
        self._cards = {}
        self._copy_sections = []

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
        self.copy_btn = CTkButton(controls, text="Copy", width=70, height=28, font=make_font(12),
                                  fg_color=SEPARATOR_COLOR, hover_color=ACCENT_COLOR,
                                  text_color=TEXT_COLOR, command=self.copy_summary)
        self.copy_btn.grid(row=0, column=2, padx=(6, 0))

        self._build_filter_bar(c)

        kpis = CTkFrame(c, fg_color="transparent")
        kpis.grid(row=2, column=0, sticky="we", pady=(10, 4))
        for i in range(6):
            kpis.grid_columnconfigure(i, weight=1, uniform="kpi")
        self.kpi_active = self._kpi(kpis, 0, "Active time")
        self.kpi_wings = self._kpi(kpis, 1, "Wings")
        self.kpi_wph = self._kpi(kpis, 2, "Wings / hour")
        self.kpi_value = self._kpi(kpis, 3, "Total value")
        self.kpi_vph = self._kpi(kpis, 4, "Value / hour")
        self.kpi_best = self._kpi(kpis, 5, "Best drop")
        self._best_ref = None
        tile = self.kpi_best.master
        for w in (tile, *tile.winfo_children()):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda _e: self._best_ref is not None
                   and self.jump_to_row(self._best_ref), add="+")

        self.body = CTkFrame(c, fg_color="transparent")
        self.body.grid(row=3, column=0, sticky="we", pady=(4, 4))
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
        self.lbl_p10 = self._stat(inner, "Fast (P10)")
        self.lbl_p90 = self._stat(inner, "Slow (P90)")
        self.lbl_fast = self._stat(inner, "Fastest")
        self.lbl_slow = self._stat(inner, "Slowest")
        self._build_min_wing_row(inner)
        self.spark = Canvas(inner, height=SPARK_HEIGHT, highlightthickness=0, bd=0)
        self.spark.grid(row=inner.grid_size()[1], column=0, columnspan=2, sticky="we",
                        padx=10, pady=(8, 0))
        self.spark.grid_remove()  # shown once there are wing times
        self.spark.bind("<Configure>", lambda _e: self._draw_sparkline())
        self.spark.bind("<Motion>", lambda e: self._draw_sparkline(e.x))
        self.spark.bind("<Leave>", lambda _e: self._draw_sparkline())
        self._spark_wings = []
        self._spark_band = None

        inner = self._card("trend", "Value over time")
        self.trend = Canvas(inner, height=TREND_HEIGHT, highlightthickness=0, bd=0)
        self.trend.grid(row=0, column=0, columnspan=2, sticky="we", padx=10, pady=(4, 0))
        self.trend.bind("<Configure>", lambda _e: self._draw_trend())
        self.trend.bind("<Motion>", lambda e: self._draw_trend(e.x))
        self.trend.bind("<Leave>", lambda _e: self._draw_trend())
        self._series = []

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

    # ---------- Filters ----------
    def _build_filter_bar(self, parent):
        """Dropdowns that narrow the whole page; table rows set them too."""
        bar = CTkFrame(parent, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="we", padx=8, pady=(8, 0))
        CTkLabel(bar, text="FILTER", font=make_font(10, "bold"), text_color=MUTED_TEXT,
                 height=24).grid(row=0, column=0, padx=(0, 8))
        self.filter_menus = {}
        for col, (dim, label) in enumerate(FILTER_DIMS, start=1):
            menu = CTkOptionMenu(bar, values=[_any(label)], width=116, height=24,
                                 font=make_font(11), dynamic_resizing=False,
                                 fg_color=SEPARATOR_COLOR, button_color=SEPARATOR_COLOR,
                                 button_hover_color=ACCENT_COLOR, text_color=TEXT_COLOR,
                                 command=lambda v, d=dim, lb=label: self.set_filter(
                                     d, None if v == _any(lb) else v))
            menu.set(_any(label))
            menu.grid(row=0, column=col, padx=(0, 6))
            menu._options = None
            self.filter_menus[dim] = menu
        self.picked_switch = CTkSwitch(bar, text="Picked only", font=make_font(11), height=24,
                                       command=self._on_picked_toggled)
        self.picked_switch.grid(row=0, column=len(FILTER_DIMS) + 1, padx=(4, 6))
        if self.picked_only:
            self.picked_switch.select()
        self.clear_filters_btn = CTkButton(
            bar, text="✕ Clear", width=70, height=24, font=make_font(11),
            fg_color="transparent", hover_color=SEPARATOR_COLOR, text_color=MUTED_TEXT,
            command=self.clear_filters)
        self.clear_filters_btn.grid(row=0, column=len(FILTER_DIMS) + 2)
        self._sync_filter_widgets()

    def set_filter(self, dim, value):
        self.filters[dim] = value
        self._sync_filter_widgets()
        self.schedule_refresh()

    def _toggle_filter(self, dim, value):
        self.set_filter(dim, None if self.filters.get(dim) == value else value)

    def _on_picked_toggled(self):
        self.picked_only = bool(self.picked_switch.get())
        self._sync_filter_widgets()
        self.schedule_refresh()

    def clear_filters(self):
        self.filters = dict.fromkeys(self.filters)
        self.picked_only = False
        self.picked_switch.deselect()
        self._sync_filter_widgets()
        self.schedule_refresh()

    def _sync_filter_widgets(self):
        for dim, label in FILTER_DIMS:
            value = self.filters.get(dim)
            self.filter_menus[dim].set(value if value is not None else _any(label))
        active = self.picked_only or any(v is not None for v in self.filters.values())
        if active:
            self.clear_filters_btn.grid()
        else:
            self.clear_filters_btn.grid_remove()

    def _update_filter_options(self, rewards):
        found = {dim: set() for dim, _ in FILTER_DIMS}
        for r in rewards:
            found["league"].add(r.league)
            found["year"].add(str(r.time.year))
            found["blueprint"].add(r.blueprint)
            found["area_level"].add(r.area_level)
            found["item_type"].add(r.item_type or "Unknown")
            if r.item_type in ss.UNIQUE_TYPES:
                found["tier"].add(ss.tier_label(r.tier))
        for dim, label in FILTER_DIMS:
            values = found[dim]
            if self.filters.get(dim) is not None:
                values.add(self.filters[dim])
            options = [_any(label)] + sorted(values, key=_natural_key)
            menu = self.filter_menus[dim]
            if options != menu._options:
                menu._options = options
                menu.configure(values=options)

    def _scoped(self, rewards):
        """Apply the league and year filters, which narrow rewards before wings are built."""
        league, year = self.filters.get("league"), self.filters.get("year")
        if league is None and year is None:
            return rewards
        return [r for r in rewards
                if (league is None or r.league == league)
                and (year is None or str(r.time.year) == year)]

    def _predicates(self):
        """(wing_keep, keep) for summarize(), or None where no filter applies."""
        f = self.filters
        bp, lvl, typ, tier = f["blueprint"], f["area_level"], f["item_type"], f["tier"]
        wing_keep = None
        if bp is not None or lvl is not None:
            def wing_keep(w):
                return (bp is None or w.blueprint == bp) and (lvl is None or w.area_level == lvl)
        keep = None
        if typ is not None or tier is not None or self.picked_only:
            def keep(r):
                if typ is not None and (r.item_type or "Unknown") != typ:
                    return False
                if tier is not None and not (r.item_type in ss.UNIQUE_TYPES
                                             and ss.tier_label(r.tier) == tier):
                    return False
                return r.picked or not self.picked_only
        return wing_keep, keep

    # ---------- Copy ----------
    def _bind_copy(self, widgets, text_func):
        for w in widgets:
            w.bind("<Button-3>", lambda _e: self._copy(text_func()), add="+")

    def _copy(self, text):
        try:
            self._root.clipboard_clear()
            self._root.clipboard_append(text)
        except TclError:
            pass

    def copy_summary(self):
        """Copy a plain-text snapshot of the visible numbers."""
        lines = [f"Curio Tracker summary · {self.session_mode} · {self.since_label.cget('text')}"]
        active = [f"{label}: {self.filters[d]}" for d, label in FILTER_DIMS if self.filters[d]]
        if self.picked_only:
            active.append("Picked only")
        if active:
            lines.append("Filters: " + ", ".join(active))
        for section, rows in self._copy_sections:
            lines.append("")
            lines.append(section)
            for caption, label in rows:
                lines.append(f"  {caption}: {label.cget('text')}")
        self._copy("\n".join(lines))
        self.copy_btn.configure(text="Copied ✓")
        self._after(1500, lambda: self.copy_btn.winfo_exists() and self.copy_btn.configure(text="Copy"))

    def _build_min_wing_row(self, inner):
        """Adjustable threshold: wings starting sooner than this after the previous one are merged."""
        row = inner.grid_size()[1]
        CTkLabel(inner, text="Ignore wings under", font=make_font(12), text_color=MUTED_TEXT,
                 anchor="w", height=22).grid(row=row, column=0, sticky="w", padx=(10, 6), pady=(4, 0))
        box = CTkFrame(inner, fg_color="transparent")
        box.grid(row=row, column=1, sticky="e", padx=(6, 10), pady=(4, 0))
        self.min_wing_entry = CTkEntry(box, width=48, height=22, font=make_font(12), justify="right")
        self.min_wing_entry.insert(0, str(int(self.min_wing.total_seconds())))
        self.min_wing_entry.grid(row=0, column=0)
        CTkLabel(box, text="s", font=make_font(12), text_color=MUTED_TEXT, height=22
                 ).grid(row=0, column=1, padx=(4, 0))
        for seq in ("<Return>", "<FocusOut>"):
            self.min_wing_entry.bind(seq, self._on_min_wing_changed, add="+")

    def _on_min_wing_changed(self, _event=None):
        current = int(self.min_wing.total_seconds())
        try:
            seconds = int(float(self.min_wing_entry.get().strip()))
        except ValueError:
            seconds = current
        seconds = max(0, min(seconds, 600))
        self.min_wing_entry.delete(0, "end")
        self.min_wing_entry.insert(0, str(seconds))
        if seconds != current:
            self.min_wing = timedelta(seconds=seconds)
            set_setting("Summary", "min_wing_seconds", seconds)
            self.schedule_refresh()

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
        if mode == ss.SESSION_CUSTOM:
            self._open_range_dialog()
            return
        self._apply_mode(mode)

    def _apply_mode(self, mode):
        self.session_mode = self._last_mode = mode
        self.mode_menu.set(mode)
        set_setting("Summary", "session_mode", mode)
        self.schedule_refresh()

    def _open_range_dialog(self):
        """Ask for a custom from/to range; cancelling keeps the previous mode."""
        dlg = CTkToplevel(self._root)
        dlg.title("Custom range")
        dlg.resizable(False, False)
        dlg.transient(self._window or self._root)
        dlg.grid_columnconfigure(1, weight=1)
        now = datetime.now()
        start, end = self.custom_range
        defaults = ((start or now.replace(hour=0, minute=0, second=0, microsecond=0))
                    .strftime(DT_FORMAT), end.strftime(DT_FORMAT) if end else "")
        entries = []
        for row, (caption, value, hint) in enumerate((
                ("From", defaults[0], "YYYY-MM-DD HH:MM"),
                ("To", defaults[1], "empty = now"))):
            CTkLabel(dlg, text=caption, font=make_font(12)).grid(
                row=row, column=0, sticky="w", padx=(14, 8), pady=(12 if row == 0 else 6, 0))
            entry = CTkEntry(dlg, width=170, font=make_font(12), placeholder_text=hint)
            if value:
                entry.insert(0, value)
            entry.grid(row=row, column=1, sticky="we", padx=(0, 14), pady=(12 if row == 0 else 6, 0))
            entries.append(entry)
        error = CTkLabel(dlg, text="", font=make_font(11), text_color=DOWN_COLOR, height=16)
        error.grid(row=2, column=0, columnspan=2, padx=14, pady=(4, 0))

        def close(apply):
            if apply:
                frm = _parse_dt(entries[0].get())
                to_text = entries[1].get().strip()
                to = _parse_dt(to_text) if to_text else None
                if frm is None or (to_text and to is None):
                    error.configure(text="Use YYYY-MM-DD HH:MM")
                    return
                if to is not None and to <= frm:
                    error.configure(text="'To' must be after 'From'")
                    return
                self.custom_range = (frm, to)
                set_setting("Summary", "custom_from", frm.strftime(DT_FORMAT))
                set_setting("Summary", "custom_to", to.strftime(DT_FORMAT) if to else "")
            dlg.destroy()
            if apply:
                self._apply_mode(ss.SESSION_CUSTOM)
            else:
                self.mode_menu.set(self._last_mode)

        buttons = CTkFrame(dlg, fg_color="transparent")
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", padx=14, pady=(6, 12))
        CTkButton(buttons, text="Cancel", width=80, fg_color=SEPARATOR_COLOR, hover_color=ACCENT_COLOR,
                  text_color=TEXT_COLOR, command=lambda: close(False)).grid(row=0, column=0, padx=(0, 6))
        CTkButton(buttons, text="Apply", width=80, command=lambda: close(True)).grid(row=0, column=1)
        dlg.protocol("WM_DELETE_WINDOW", lambda: close(False))
        dlg.bind("<Return>", lambda _e: close(True))
        dlg.bind("<Escape>", lambda _e: close(False))
        dlg.after(50, lambda: (dlg.grab_set(), entries[0].focus_set()))

    def reset_session(self):
        self.session_start = datetime.now()
        if self.session_mode != ss.SESSION_APP_START:
            self._apply_mode(ss.SESSION_APP_START)
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
                league=str(getattr(item, "league", "") or "Unknown"),
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

        session_start = self.session_start if self.session_mode == ss.SESSION_APP_START else None
        window = ss.session_window(self.session_mode, now, self.session_start, self.custom_range)
        if window is not None:
            session_rewards = ss.in_window(rewards, window)
        else:
            session_rewards = ss.select_session(rewards, self.session_mode, None, self.idle * 2)
        self._update_filter_options(session_rewards)
        session_rewards = self._scoped(session_rewards)
        wing_keep, keep = self._predicates()
        opts = dict(idle=self.idle, min_wing=self.min_wing, wing_keep=wing_keep, keep=keep)
        s = ss.summarize(session_rewards, now=now, session_start=session_start, **opts)
        prev = None
        if window is not None:
            prev_rewards = self._scoped(ss.in_window(rewards, ss.previous_window(window)))
            if prev_rewards:
                prev = ss.summarize(prev_rewards, now=now, **opts)

        if self.session_mode == ss.SESSION_CUSTOM and window is not None:
            end = "now" if self.custom_range[1] is None else window[1].strftime(DATE_LABEL)
            since = f"{window[0].strftime(DATE_LABEL)} → {end}"
        elif s.start:
            since = f"Started {s.start.strftime(DATE_LABEL)}"
        else:
            since = "No rewards yet"
        self.since_label.configure(text=since)
        self.kpi_active.configure(text=dur(s.active) if s.active else "—")
        self.kpi_wings.configure(text=str(s.wings))
        self.kpi_wph.configure(text=f"{s.wings_per_hour:.1f}" if s.wings_per_hour else "—")
        self.kpi_value.configure(text=fmt(s.chaos))
        self.kpi_vph.configure(text=fmt(s.chaos_per_hour))
        for kpi, attr in ((self.kpi_active, "active"), (self.kpi_wings, "wings"),
                          (self.kpi_wph, "wings_per_hour"), (self.kpi_value, "chaos"),
                          (self.kpi_vph, "chaos_per_hour")):
            cur = getattr(s, attr)
            old = getattr(prev, attr) if prev else None
            if isinstance(cur, timedelta):
                cur, old = cur.total_seconds(), old.total_seconds() if old else None
            self._set_delta(kpi, cur, old)
        self._fmt = fmt
        best = s.best
        self._best_ref = best.ref if best else None
        self.kpi_best.configure(text=fmt(best.chaos) if best else "—")
        best_name = self._drop_name(best) if best else ""
        if len(best_name) > BEST_NAME_MAX:
            best_name = best_name[:BEST_NAME_MAX - 1] + "…"
        self.kpi_best._delta.configure(text=best_name, text_color=MUTED_TEXT)
        self._series = s.value_series
        self._draw_trend()

        self.lbl_elapsed.configure(text=dur(s.elapsed) if s.start else "—")
        self.lbl_active.configure(text=dur(s.active) if s.active else "—")
        self.lbl_wings.configure(text=str(s.wings))
        self.lbl_rewards.configure(text=str(s.rewards))
        self.lbl_wph.configure(text=f"{s.wings_per_hour:.1f}" if s.wings_per_hour else "—")

        self.lbl_avg.configure(text=dur(s.avg_wing))
        self.lbl_median.configure(text=dur(s.median_wing))
        self.lbl_p10.configure(text=dur(s.p10_wing))
        self.lbl_p90.configure(text=dur(s.p90_wing))
        self.lbl_fast.configure(text=self._wing_text(s.fastest_wing))
        self.lbl_slow.configure(text=self._wing_text(s.slowest_wing))
        self._recent = s.recent_durations
        self._spark_wings = s.recent_wings
        recent_sorted = sorted(self._recent)
        self._spark_band = ((ss.percentile(recent_sorted, 10), ss.percentile(recent_sorted, 90))
                            if len(recent_sorted) >= 5 else None)
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

        def type_rows(groups):
            return [((k, str(g.count), str(g.picked), fmt(g.chaos)),
                     (_natural_key(k), g.count, g.picked, g.chaos), k) for k, g in groups]

        tiers = sorted(s.by_tier.items(), key=lambda kv: (kv[0] == "Untiered", _natural_key(kv[0])))
        footer = []
        for key, g in tiers:
            if key != "Untiered" and g.count and s.wings:
                footer.append(f"{key}: 1 per {s.wings / g.count:,.1f} wings")
        self._fill_table(self.tier_card, ("Tier", "Count", "Picked", "Value"), type_rows(tiers),
                         empty="No uniques yet", footer=footer)

        types = sorted(s.by_type.items(), key=lambda kv: -kv[1].chaos)
        self._fill_table(self.type_card, ("Type", "Count", "Picked", "Value"), type_rows(types),
                         empty="No rewards yet")

        def wing_rows(groups, key_fmt=str):
            ordered = sorted(groups.items(), key=lambda kv: (-kv[1].wings, str(kv[0])))
            return [((key_fmt(k), str(g.wings), dur(g.avg), fmt(g.chaos)),
                     (_natural_key(k), g.wings,
                      g.avg.total_seconds() if g.avg else float("inf"), g.chaos), k)
                    for k, g in ordered]

        self._fill_table(self.bp_card, ("Blueprint", "Wings", "Avg", "Value"),
                         wing_rows(s.by_blueprint))
        self._fill_table(self.lvl_card, ("Area", "Wings", "Avg", "Value"),
                         wing_rows(s.by_area_level, lambda k: f"Level {k}"))

        if self.session_mode == ss.SESSION_ALL:
            a = s
        else:
            a = ss.summarize(self._scoped(rewards), now=now, **opts)
        self.lbl_all_wings.configure(text=str(a.wings))
        self.lbl_all_avg.configure(text=dur(a.avg_wing))
        self.lbl_all_per_wing.configure(text=fmt(a.chaos_per_wing))

    @staticmethod
    def _wing_text(wing):
        if wing is None:
            return "—"
        return (f"{ss.format_duration(wing.duration)}  ·  {wing.blueprint} L{wing.area_level}"
                f"  ·  {wing.start.strftime('%H:%M')}")

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
        """Render `rows` of (cells, sort_keys, filter_value) into a card.

        Header clicks sort by that column; row clicks toggle the page filter
        for the row's value.
        """
        used = set()
        last = len(headers) - 1
        sort = self._sort.get(card._key)
        if sort is not None:
            col, desc = sort
            rows = sorted(rows, key=lambda r: r[1][col], reverse=desc)
        dim = TABLE_FILTERS.get(card._key)
        active_value = self.filters.get(dim) if dim else None
        card._row_values = {}
        total_value = sum(max(0.0, r[1][-1]) for r in rows)

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
                lbl = self._cell(card, ("h", col), lambda c=col: self._header_label(card, c), used)
                arrow = ""
                if sort is not None and sort[0] == col:
                    arrow = " ▼" if sort[1] else " ▲"
                lbl.configure(text=title.upper() + arrow)
                lbl.grid(row=0, column=col, sticky="e" if col else "w", padx=pad(col), pady=(0, 2))
            expanded = card._key in self._expanded
            shown = rows if expanded else rows[:TABLE_LIMIT]
            default_text = ThemeManager.theme["CTkLabel"]["text_color"]
            for row, (cells, _keys, value) in enumerate(shown, start=1):
                card._row_values[row] = value
                is_active = dim is not None and value == active_value
                for col, text in enumerate(cells):
                    lbl = self._cell(card, (row, col), lambda r=row, c=col: self._row_label(
                        card, r, c), used)
                    lbl.configure(text=text, text_color=ACCENT_COLOR if is_active else default_text)
                    lbl.grid(row=2 * row - 1, column=col, sticky="w" if col == 0 else "e",
                             padx=pad(col))
                if total_value > 0:
                    share = self._cell(card, ("bar", row), lambda: CTkProgressBar(
                        card, height=3, corner_radius=2, fg_color=SEPARATOR_COLOR,
                        progress_color=ACCENT_COLOR), used)
                    share.set(max(0.0, _keys[-1]) / total_value)
                    share.grid(row=2 * row, column=0, columnspan=len(headers), sticky="we",
                               padx=10, pady=(0, 3))
            row = 2 * len(shown) + 1
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

    def _header_label(self, card, col):
        lbl = CTkLabel(card, font=make_font(10, "bold"), text_color=MUTED_TEXT, height=16,
                       cursor="hand2")
        lbl.bind("<Button-1>", lambda _e: self._sort_table(card, col))
        return lbl

    def _row_label(self, card, row, col):
        clickable = card._key in TABLE_FILTERS
        lbl = CTkLabel(card, font=make_font(12, "bold" if col == 0 else "normal"), height=22,
                       anchor="w" if col == 0 else "e", cursor="hand2" if clickable else "")
        if clickable:
            lbl.bind("<Button-1>", lambda _e: self._on_table_row(card, row))
        return lbl

    def _sort_table(self, card, col):
        current = self._sort.get(card._key)
        if current is not None and current[0] == col:
            self._sort[card._key] = (col, not current[1])
        else:
            self._sort[card._key] = (col, col != 0)  # numbers start high-to-low
        self.schedule_refresh()

    def _on_table_row(self, card, row):
        value = card._row_values.get(row)
        dim = TABLE_FILTERS.get(card._key)
        if dim and value is not None:
            self._toggle_filter(dim, value)

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
            for w in (icon, text_box, name, meta, value):
                w.configure(cursor="hand2")
                w.bind("<Button-1>", lambda _e, idx=i: self._on_drop_clicked(idx), add="+")

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
                    r.item_type, r.time.strftime(DATE_LABEL)]
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

    def _on_drop_clicked(self, idx):
        i = self._drop_page * DROPS_PER_PAGE + idx
        if i < len(self._drops):
            self.jump_to_row(self._drops[i].ref)

    def jump_to_row(self, iid):
        """Show the tracker and select `iid`, clearing tracker filters that hide it."""
        tm = self.tm
        tree = tm.tree
        try:
            if not tree.exists(iid):
                return
            if iid not in tree.get_children(""):
                tm.search_var.set("")
                tm.time_filter_var.set("All")
                tm.apply_filters("")
            if not self.detached and self.view != PAGE_TRACKER:
                self._on_page_selected(PAGE_TRACKER)
            else:
                self._root.deiconify()
                self._root.lift()
            tree.selection_set(iid)
            tree.focus(iid)
            tree.see(iid)
            tree.focus_set()
        except TclError:
            pass

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

    @staticmethod
    def _tooltip(c, x, y, lines, width):
        """Draw a small tooltip beside x, vertically centred on y, kept inside the canvas."""
        font = make_font(10)
        ink = _mode_color(ThemeManager.theme["CTkLabel"]["text_color"])
        text = c.create_text(0, 0, text="\n".join(lines), anchor="nw", fill=ink, font=font)
        x0, y0, x1, y1 = c.bbox(text)
        w, h = x1 - x0 + 12, y1 - y0 + 8
        tx = x + 10 if x + 10 + w <= width else x - 10 - w
        tx = max(0, tx)
        ty = max(0, min(y - h / 2, int(c.cget("height")) - h))
        c.coords(text, tx + 6, ty + 4)
        box = c.create_rectangle(tx, ty, tx + w, ty + h, fill=_mode_color(SEPARATOR_COLOR),
                                 outline=_mode_color(MUTED_TEXT), width=1)
        c.tag_raise(text, box)

    def _draw_sparkline(self, hover_x=None):
        """Recent wing times as bars, with the P10-P90 band and the average."""
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
        usable = SPARK_HEIGHT - 4

        def y_of(seconds):
            return SPARK_HEIGHT - (seconds / peak) * usable

        if self._spark_band:
            lo, hi = (d.total_seconds() for d in self._spark_band)
            c.create_rectangle(0, y_of(hi), width, y_of(lo), fill=_mode_color(SEPARATOR_COLOR),
                               width=0)
        avg = sum(values) / len(values)
        slot = min(width / len(values), SPARK_SLOT_MAX)
        bar = max(2.0, min(slot * 0.7, SPARK_BAR_MAX))
        accent = _mode_color(ACCENT_COLOR)
        muted = _mode_color(MUTED_TEXT)
        ink = _mode_color(ThemeManager.theme["CTkLabel"]["text_color"])
        hovered = None
        if hover_x is not None and 0 <= hover_x < slot * len(values):
            hovered = int(hover_x // slot)
        for i, v in enumerate(values):
            h = max(2.0, (v / peak) * usable)
            x = i * slot + (slot - bar) / 2
            c.create_rectangle(x, SPARK_HEIGHT - h, x + bar, SPARK_HEIGHT,
                               fill=ink if i == hovered else accent, width=0)
        c.create_line(0, y_of(avg), width, y_of(avg), fill=muted, dash=(3, 3))
        if hovered is not None and hovered < len(self._spark_wings):
            w = self._spark_wings[hovered]
            self._tooltip(c, hovered * slot + slot / 2, 0, [
                f"{ss.format_duration(w.duration)} · {w.blueprint} L{w.area_level}",
                w.start.strftime(DATE_LABEL)], width)

    def _draw_trend(self, hover_x=None):
        """Cumulative value over time as a 2px line, with a hover crosshair."""
        c = self.trend
        try:
            c.delete("all")
            c.configure(bg=_mode_color(CARD_COLOR))
            width = c.winfo_width()
        except TclError:
            return
        if width <= 1:
            return
        muted = _mode_color(MUTED_TEXT)
        grid = _mode_color(SEPARATOR_COLOR)
        font = make_font(10)
        series = self._series
        if len(series) < 2:
            c.create_text(width / 2, TREND_HEIGHT / 2, text="Not enough priced rewards yet",
                          fill=muted, font=font)
            return
        top, bottom, left, right = 16, TREND_HEIGHT - 16, 4, width - 6
        t0, t1 = series[0][0], series[-1][0]
        span = max((t1 - t0).total_seconds(), 1.0)
        vmax = series[-1][1] or 1.0

        def xy(t, v):
            return (left + (t - t0).total_seconds() / span * (right - left),
                    bottom - v / vmax * (bottom - top))

        for frac in (0.0, 0.5, 1.0):
            y = bottom - frac * (bottom - top)
            c.create_line(left, y, right, y, fill=grid, width=1)
        c.create_text(left, top - 2, text=self._fmt(vmax), anchor="sw", fill=muted, font=font)
        time_fmt = "%d %b %Y" if span > 86400 else "%H:%M"
        c.create_text(left, TREND_HEIGHT - 1, text=t0.strftime(time_fmt), anchor="sw",
                      fill=muted, font=font)
        c.create_text(right, TREND_HEIGHT - 1, text=t1.strftime(time_fmt), anchor="se",
                      fill=muted, font=font)

        points = [xy(t0, 0.0)] + [xy(t, v) for t, v in series]
        c.create_line(*[p for pt in points for p in pt], fill=_mode_color(ACCENT_COLOR), width=2)
        surface = _mode_color(CARD_COLOR)
        accent = _mode_color(ACCENT_COLOR)
        ex, ey = points[-1]
        c.create_oval(ex - 4, ey - 4, ex + 4, ey + 4, fill=accent, outline=surface, width=2)

        if hover_x is not None and left <= hover_x <= right:
            xs = [p[0] for p in points[1:]]
            i = min(range(len(xs)), key=lambda k: abs(xs[k] - hover_x))
            px, py = points[i + 1]
            c.create_line(px, top, px, bottom, fill=muted, dash=(2, 2))
            c.create_oval(px - 4, py - 4, px + 4, py + 4, fill=accent, outline=surface, width=2)
            t, v = series[i]
            self._tooltip(c, px, 0, [t.strftime(DATE_LABEL), f"Total {self._fmt(v)}"], width)
