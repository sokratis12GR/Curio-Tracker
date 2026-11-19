"""Collapsible session summary panel shown to the right of the tree."""

import threading
from datetime import datetime, timedelta
from tkinter import Canvas, TclError

import customtkinter
from customtkinter import (CTkButton, CTkFrame, CTkImage, CTkLabel, CTkOptionMenu,
                           CTkScrollableFrame)
from PIL import Image

import currency_utils
import summary_stats as ss
from fonts import make_font
from img_utils import get_cached_icon, get_icon
from gui.palette import (ACCENT_COLOR, CARD_COLOR, MUTED_TEXT, POE_PALETTE, SEPARATOR_COLOR,
                         themed)
from gui.tree.filtering import row_chaos_value
from settings import get_setting, set_setting

PANEL_WIDTH = 270
REFRESH_DEBOUNCE_MS = 200
TICK_MS = 30_000
SPARK_HEIGHT = 46
# Readable text for buttons in every theme (muted text was near-invisible).
TEXT_COLOR = themed(("#1f2328", "#dcddde"), POE_PALETTE["gold_bright"])
ARROW_STYLE = dict(
    width=30, height=24, corner_radius=6,
    fg_color=SEPARATOR_COLOR, hover_color=ACCENT_COLOR,
    text_color=TEXT_COLOR, text_color_disabled=MUTED_TEXT,
)
TABLE_LIMIT = 5       # rows shown before "Show all"
DROPS_PER_PAGE = 6
DROP_ICON = (24, 24)
PICKED_VALUES = ("True", "TRUE", "true", True)


def _mode_color(pair):
    # Canvas needs a plain colour; pick the slot for the current appearance mode.
    if isinstance(pair, (tuple, list)):
        return pair[1] if customtkinter.get_appearance_mode() == "Dark" else pair[0]
    return pair


class SummaryFrame:
    def __init__(self, parent, tree_manager):
        self.tm = tree_manager
        self.parent = parent
        self.app_start = datetime.now()
        self.session_start = self.app_start
        self._refresh_job = None
        self._tick_job = None

        mode = get_setting("Summary", "session_mode", ss.SESSION_APP_START)
        self.session_mode = mode if mode in ss.SESSION_MODES else ss.SESSION_APP_START
        self.is_open = bool(get_setting("Summary", "open", True))
        idle_min = get_setting("Summary", "idle_minutes", 15)
        self.idle = ss.DEFAULT_IDLE
        if isinstance(idle_min, (int, float)) and idle_min > 0:
            self.idle = timedelta(minutes=idle_min)

        self.frame = CTkFrame(parent, fg_color="transparent")
        self.frame.grid(row=0, column=0, sticky="ns")
        self.frame.grid_rowconfigure(0, weight=1)

        # Callbacks go through the toplevel so main's on_closing (which
        # cancels every pending `after` via root) unregisters them cleanly.
        self._root = parent.winfo_toplevel()
        self._alive = True
        self.frame.bind("<Destroy>", self._on_destroy, add="+")

        # Small outlined tab shown only while collapsed.
        self.open_tab = CTkButton(
            self.frame, width=24, height=110, text="«\n\nS\nU\nM\nM\nA\nR\nY",
            font=make_font(11, "bold"), fg_color=CARD_COLOR, text_color=TEXT_COLOR,
            border_width=1, border_color=SEPARATOR_COLOR, hover_color=SEPARATOR_COLOR,
            corner_radius=6, command=self.toggle,
        )

        self.content = CTkScrollableFrame(self.frame, width=PANEL_WIDTH, corner_radius=8)
        self.content.grid_columnconfigure(0, weight=1)
        self._build()
        self._apply_open_state()

    def _on_destroy(self, event):
        if event.widget is self.frame:
            self._alive = False

    def _after(self, ms, func):
        return self._root.after(ms, func) if self._alive else None

    # ---------- Layout ----------
    def _apply_open_state(self):
        if self.is_open:
            self.open_tab.grid_remove()
            self.content.grid(row=0, column=0, sticky="ns")
            self.schedule_refresh()
            self._schedule_tick()
        else:
            self.content.grid_remove()
            self.open_tab.grid(row=0, column=0, sticky="n")

    def toggle(self):
        self.is_open = not self.is_open
        set_setting("Summary", "open", self.is_open)
        self._apply_open_state()

    def _section(self, title):
        row = self.content.grid_size()[1]
        CTkLabel(self.content, text=title.upper(), font=make_font(10, "bold"),
                 text_color=MUTED_TEXT, anchor="w", height=16
                 ).grid(row=row, column=0, sticky="we", padx=8, pady=(10, 2))
        card = CTkFrame(self.content, fg_color=CARD_COLOR, corner_radius=8)
        card.grid(row=row + 1, column=0, sticky="we", padx=4, ipady=4)
        card.grid_columnconfigure(1, weight=1)
        return card

    def _stat(self, card, caption):
        row = card.grid_size()[1]
        CTkLabel(card, text=caption, font=make_font(11), text_color=MUTED_TEXT,
                 anchor="w", height=18).grid(row=row, column=0, sticky="w", padx=(10, 6), pady=1)
        value = CTkLabel(card, text="—", font=make_font(11, "bold"), anchor="e", height=18)
        value.grid(row=row, column=1, sticky="e", padx=(6, 10), pady=1)
        return value

    def _build(self):
        header = CTkFrame(self.content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="we", padx=4, pady=(2, 0))
        header.grid_columnconfigure(0, weight=1)
        CTkLabel(header, text="Session Summary", font=make_font(14, "bold"), anchor="w"
                 ).grid(row=0, column=0, sticky="w", padx=4)
        CTkButton(header, text="»", command=self.toggle, font=make_font(12, "bold"), **ARROW_STYLE
                  ).grid(row=0, column=1, sticky="e", padx=4)
        self.mode_menu = CTkOptionMenu(
            header, values=list(ss.SESSION_MODES), width=150, height=24,
            font=make_font(11), command=self._on_mode_changed,
        )
        self.mode_menu.set(self.session_mode)
        self.mode_menu.grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))
        self.reset_btn = CTkButton(header, text="Reset", width=60, height=24,
                                   font=make_font(11), command=self.reset_session)
        self.reset_btn.grid(row=1, column=1, sticky="e", padx=4, pady=(4, 0))
        self.since_label = CTkLabel(header, text="", font=make_font(10), text_color=MUTED_TEXT,
                                    anchor="w", height=14)
        self.since_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=4)

        card = self._section("Session")
        self.lbl_elapsed = self._stat(card, "Duration")
        self.lbl_active = self._stat(card, "Active time")
        self.lbl_wings = self._stat(card, "Wings")
        self.lbl_rewards = self._stat(card, "Rewards")
        self.lbl_wph = self._stat(card, "Wings / hour")

        card = self._section("Wing time")
        self.lbl_avg = self._stat(card, "Average")
        self.lbl_median = self._stat(card, "Median")
        self.lbl_fast = self._stat(card, "Fastest")
        self.lbl_slow = self._stat(card, "Slowest")
        self.spark = Canvas(card, height=SPARK_HEIGHT, highlightthickness=0, bd=0)
        self.spark.grid(row=card.grid_size()[1], column=0, columnspan=2, sticky="we", padx=10, pady=(6, 2))
        self.spark.grid_remove()  # shown once there are wing times
        self.spark.bind("<Configure>", lambda _e: self._draw_sparkline())

        card = self._section("Value")
        self.lbl_value = self._stat(card, "Total")
        self.lbl_picked = self._stat(card, "Picked")
        self.lbl_per_wing = self._stat(card, "Per wing")
        self.lbl_per_hour = self._stat(card, "Per active hour")

        self._build_top_drops()

        self.tier_card = self._section("Unique tiers")
        self.type_card = self._section("By item type")
        self.bp_card = self._section("By blueprint")
        self.lvl_card = self._section("By area level")
        self._expanded = set()  # tables showing all rows

        card = self._section("All loaded (comparison)")
        self.lbl_all_wings = self._stat(card, "Wings")
        self.lbl_all_avg = self._stat(card, "Avg wing time")
        self.lbl_all_per_wing = self._stat(card, "Value / wing")

        self._recent = []

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
        if not self.is_open or not self._alive:
            return
        if self._refresh_job is not None:
            try:
                self._root.after_cancel(self._refresh_job)
            except (TclError, ValueError):
                pass
        self._refresh_job = self._after(REFRESH_DEBOUNCE_MS, self.refresh)

    def _schedule_tick(self):
        if self._tick_job is not None:
            return

        def tick():
            self._tick_job = None
            if self.is_open and self._alive:
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
        if not self.is_open or not self._alive:
            return
        try:
            self._refresh()
        except TclError:
            pass  # widget destroyed during shutdown

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

        self._fill_table(self.bp_card, ("", "Wings", "Avg", "Value"), wing_rows(s.by_blueprint))
        self._fill_table(self.lvl_card, ("", "Wings", "Avg", "Value"),
                         wing_rows(s.by_area_level, lambda k: f"Level {k}"))

        if self.session_mode == ss.SESSION_ALL:
            a = s
        else:
            a = ss.summarize(rewards, now=now, idle=self.idle)
        self.lbl_all_wings.configure(text=str(a.wings))
        self.lbl_all_avg.configure(text=dur(a.avg_wing))
        self.lbl_all_per_wing.configure(text=fmt(a.chaos_per_wing))

    def _fill_table(self, card, headers, rows, empty="No wings yet", footer=()):
        for child in card.winfo_children():
            child.destroy()
        if not rows:
            CTkLabel(card, text=empty, font=make_font(11), text_color=MUTED_TEXT,
                     height=18).grid(row=0, column=0, columnspan=4, padx=10, pady=2)
            return
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)
        last = len(headers) - 1

        def pad(col):
            return (10 if col == 0 else 4, 10 if col == last else 4)

        for col, title in enumerate(headers):
            CTkLabel(card, text=title, font=make_font(9, "bold"), text_color=MUTED_TEXT,
                     height=14).grid(row=0, column=col, sticky="e" if col else "w", padx=pad(col))
        expanded = card in self._expanded
        shown = rows if expanded else rows[:TABLE_LIMIT]
        for row, cells in enumerate(shown, start=1):
            for col, text in enumerate(cells):
                CTkLabel(card, text=text, font=make_font(11, "bold" if col == 0 else "normal"),
                         height=18, anchor="w" if col == 0 else "e"
                         ).grid(row=row, column=col, sticky="w" if col == 0 else "e",
                                padx=pad(col), pady=1)
        row = len(shown) + 1
        for line in footer:
            CTkLabel(card, text=line, font=make_font(10), text_color=MUTED_TEXT, height=14,
                     anchor="w").grid(row=row, column=0, columnspan=len(headers), sticky="w", padx=10)
            row += 1
        if len(rows) > TABLE_LIMIT:
            text = "Show less" if expanded else f"Show all ({len(rows)})"
            CTkButton(card, text=text, height=20, font=make_font(10), fg_color="transparent",
                      text_color=MUTED_TEXT, hover_color=SEPARATOR_COLOR,
                      command=lambda c=card: self._toggle_table(c)
                      ).grid(row=row, column=0, columnspan=len(headers), sticky="we", padx=6, pady=(2, 0))

    def _toggle_table(self, card):
        self._expanded.symmetric_difference_update({card})
        self.schedule_refresh()

    # ---------- Top drops ----------
    def _build_top_drops(self):
        self.drops_card = self._section("Top drops")
        self.drops_card.grid_columnconfigure(0, weight=1)
        self.drops_list = CTkFrame(self.drops_card, fg_color="transparent")
        self.drops_list.grid(row=0, column=0, sticky="we")
        self.drops_list.grid_columnconfigure(1, weight=1)

        nav = CTkFrame(self.drops_card, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="we", padx=6, pady=(2, 0))
        nav.grid_columnconfigure(1, weight=1)
        self.drops_prev = CTkButton(nav, text="◀", command=lambda: self._page_drops(-1), font=make_font(12, "bold"), **ARROW_STYLE)
        self.drops_prev.grid(row=0, column=0)
        self.drops_pos = CTkLabel(nav, text="", font=make_font(10), text_color=MUTED_TEXT, height=16)
        self.drops_pos.grid(row=0, column=1)
        self.drops_next = CTkButton(nav, text="▶", command=lambda: self._page_drops(1), font=make_font(12, "bold"), **ARROW_STYLE)
        self.drops_next.grid(row=0, column=2)
        self._drops = []
        self._drop_page = 0
        self._drop_token = 0
        self._wheel_targets(self.drops_card)

    def _wheel_targets(self, widget):
        # Wheel over the drops list pages through it instead of scrolling the panel.
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
        for child in self.drops_list.winfo_children():
            child.destroy()
        self._drop_token += 1
        fmt = getattr(self, "_fmt", str)
        drops = self._drops
        if not drops:
            CTkLabel(self.drops_list, text="No priced drops yet", font=make_font(11),
                     text_color=MUTED_TEXT, height=18).grid(row=0, column=0, columnspan=3, padx=10, pady=2)
            self.drops_pos.configure(text="")
            self.drops_prev.configure(state="disabled")
            self.drops_next.configure(state="disabled")
            return

        start = self._drop_page * DROPS_PER_PAGE
        page = drops[start:start + DROPS_PER_PAGE]
        for i, r in enumerate(page):
            name = self._drop_name(r)
            icon = CTkLabel(self.drops_list, text="", width=DROP_ICON[0], height=DROP_ICON[1])
            icon.grid(row=i, column=0, padx=(8, 6), pady=2)
            self._load_drop_icon(icon, r)

            text_box = CTkFrame(self.drops_list, fg_color="transparent")
            text_box.grid(row=i, column=1, sticky="we")
            if len(name) > 26:
                name = name[:25] + "…"
            CTkLabel(text_box, text=name, font=make_font(11, "bold"), anchor="w", height=15
                     ).grid(row=0, column=0, sticky="w")
            meta = [ss.tier_label(r.tier) if r.item_type in ss.UNIQUE_TYPES and r.tier else "",
                    r.item_type, r.time.strftime("%d %b %H:%M")]
            CTkLabel(text_box, text=" · ".join(m for m in meta if m), font=make_font(9),
                     text_color=MUTED_TEXT, anchor="w", height=12).grid(row=1, column=0, sticky="w")
            CTkLabel(self.drops_list, text=fmt(r.chaos), font=make_font(11, "bold"), anchor="e",
                     height=18).grid(row=i, column=2, sticky="e", padx=(4, 10))

        end = start + len(page)
        self.drops_pos.configure(text=f"{start + 1}–{end} of {len(drops)}")
        self.drops_prev.configure(state="normal" if start > 0 else "disabled")
        self.drops_next.configure(state="normal" if end < len(drops) else "disabled")
        self._wheel_targets(self.drops_list)

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
        c.delete("all")
        c.configure(bg=_mode_color(CARD_COLOR))
        width = c.winfo_width()
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
