"""Session summary statistics (no Tk): wings, timings, values.

A *wing* is a group of consecutive rewards (sorted by time, then record #).
A new wing starts when the current one already has REWARDS_PER_WING rewards,
when the blueprint type or area level changes, or when the gap since the
previous reward exceeds WING_BREAK.

A wing that starts less than the minimum wing time after the previous wing
is merged into it (split captures, not a real wing).

A wing's duration is the time from its first reward to the first reward of
the next wing. Durations longer than the idle threshold are treated as
breaks and excluded from timing stats.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median
from typing import Optional

REWARDS_PER_WING = 5
WING_BREAK = timedelta(minutes=5)
DEFAULT_IDLE = timedelta(minutes=15)
DEFAULT_MIN_WING = timedelta(seconds=10)

SESSION_APP_START = "Since app start"
SESSION_LAST_BREAK = "Since last break"
SESSION_TODAY = "Today"
SESSION_24H = "Last 24 hours"
SESSION_7D = "Last 7 days"
SESSION_CUSTOM = "Custom range…"
SESSION_ALL = "All loaded"
SESSION_MODES = (SESSION_APP_START, SESSION_LAST_BREAK, SESSION_TODAY, SESSION_24H,
                 SESSION_7D, SESSION_CUSTOM, SESSION_ALL)


def session_window(mode, now, app_start=None, custom=None):
    """(start, end) for time-window modes, or None for modes not bounded by a window.

    `custom` is a (start, end) pair; a missing end means "until now".
    """
    if mode == SESSION_APP_START and app_start is not None:
        return app_start, now
    if mode == SESSION_TODAY:
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    if mode == SESSION_24H:
        return now - timedelta(hours=24), now
    if mode == SESSION_7D:
        return now - timedelta(days=7), now
    if mode == SESSION_CUSTOM and custom and custom[0] is not None:
        return custom[0], custom[1] or now
    return None


def previous_window(window):
    """The equally long window right before `window`."""
    start, end = window
    return start - (end - start), start


def in_window(rewards, window):
    start, end = window
    return [r for r in rewards if start <= r.time <= end]


def pct_change(current, previous):
    if current is None or not previous:
        return None
    return (current - previous) / previous * 100


@dataclass
class Reward:
    time: datetime
    record: int
    blueprint: str
    area_level: str
    chaos: float
    picked: bool
    ref: object = None  # caller's handle (e.g. tree iid)
    item_type: str = ""
    tier: str = ""
    name: str = ""
    img: str = ""
    league: str = ""


UNIQUE_TYPES = ("Replica", "Replacement")
TOP_DROPS = 50


def tier_label(tier):
    text = str(tier or "").strip()
    if not text:
        return "Untiered"
    try:
        return f"T{int(float(text))}"
    except ValueError:
        return text


@dataclass
class TypeStats:
    count: int = 0
    picked: int = 0
    chaos: float = 0.0
    best: Optional[Reward] = None


@dataclass
class Wing:
    rewards: list
    duration: Optional[timedelta] = None

    @property
    def start(self):
        return self.rewards[0].time

    @property
    def blueprint(self):
        return self.rewards[0].blueprint

    @property
    def area_level(self):
        return self.rewards[0].area_level

    @property
    def chaos(self):
        return sum(r.chaos for r in self.rewards)


@dataclass
class GroupStats:
    wings: int = 0
    rewards: int = 0
    chaos: float = 0.0
    durations: list = field(default_factory=list)

    @property
    def avg(self):
        if not self.durations:
            return None
        return sum(self.durations, timedelta()) / len(self.durations)


@dataclass
class Summary:
    rewards: int = 0
    wings: int = 0
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    elapsed: timedelta = timedelta()
    active: timedelta = timedelta()
    avg_wing: Optional[timedelta] = None
    median_wing: Optional[timedelta] = None
    fastest: Optional[timedelta] = None
    slowest: Optional[timedelta] = None
    p10_wing: Optional[timedelta] = None
    p90_wing: Optional[timedelta] = None
    fastest_wing: Optional[Wing] = None
    slowest_wing: Optional[Wing] = None
    wings_per_hour: Optional[float] = None
    chaos: float = 0.0
    picked_chaos: float = 0.0
    picked_count: int = 0
    chaos_per_wing: Optional[float] = None
    chaos_per_hour: Optional[float] = None
    best: Optional[Reward] = None
    by_blueprint: dict = field(default_factory=dict)
    by_area_level: dict = field(default_factory=dict)
    by_type: dict = field(default_factory=dict)
    by_tier: dict = field(default_factory=dict)
    top_drops: list = field(default_factory=list)
    recent_durations: list = field(default_factory=list)
    recent_wings: list = field(default_factory=list)
    value_series: list = field(default_factory=list)  # (time, cumulative chaos)


def percentile(values, pct):
    """Linear-interpolated percentile of sorted-able timedeltas (pct in 0..100)."""
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * pct / 100
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def group_wings(rewards, idle=DEFAULT_IDLE, min_wing=DEFAULT_MIN_WING):
    ordered = sorted(rewards, key=lambda r: (r.time, r.record))
    wings = []
    current = []
    for reward in ordered:
        if current:
            prev = current[-1]
            if (len(current) >= REWARDS_PER_WING
                    or reward.blueprint != prev.blueprint
                    or reward.area_level != prev.area_level
                    or reward.time - prev.time > WING_BREAK):
                wings.append(Wing(current))
                current = []
        current.append(reward)
    if current:
        wings.append(Wing(current))

    if min_wing and min_wing > timedelta():
        merged = []
        for wing in wings:
            if merged and wing.start - merged[-1].start < min_wing:
                merged[-1].rewards.extend(wing.rewards)
            else:
                merged.append(wing)
        wings = merged

    for wing, nxt in zip(wings, wings[1:]):
        gap = nxt.start - wing.start
        if gap <= idle:
            wing.duration = gap
    return wings


def select_session(rewards, mode, app_start=None, session_gap=DEFAULT_IDLE * 2):
    if mode == SESSION_ALL or not rewards:
        return list(rewards)
    if mode == SESSION_APP_START:
        if app_start is None:
            return list(rewards)
        return [r for r in rewards if r.time >= app_start]
    # SESSION_LAST_BREAK: walk back from the newest reward until a long gap.
    ordered = sorted(rewards, key=lambda r: (r.time, r.record))
    start_index = 0
    for i in range(len(ordered) - 1, 0, -1):
        if ordered[i].time - ordered[i - 1].time > session_gap:
            start_index = i
            break
    return ordered[start_index:]


def summarize(rewards, now=None, session_start=None, idle=DEFAULT_IDLE, sparkline_len=30,
              min_wing=DEFAULT_MIN_WING, keep=None, wing_keep=None):
    """Summarise `rewards`.

    Wings are always built from every reward so timings stay correct.
    `wing_keep` (a wing predicate) then drops whole wings, e.g. other
    blueprints. `keep` (a reward predicate) narrows only the reward-based
    stats: value, counts, drops, type/tier tables and the value columns of
    the wing tables.
    """
    now = now or datetime.now()
    s = Summary()
    if not rewards and session_start is None:
        return s

    wings = group_wings(rewards, idle, min_wing)
    if wing_keep:
        wings = [w for w in wings if wing_keep(w)]
        rewards = [r for w in wings for r in w.rewards]
    timed = [w for w in wings if w.duration is not None]
    durations = [w.duration for w in timed]

    kept = [r for r in rewards if keep(r)] if keep else list(rewards)
    kept_ids = {id(r) for r in kept}
    s.rewards = len(kept)
    s.wings = len(wings)
    if wings:
        s.start = session_start or wings[0].start
        s.end = wings[-1].rewards[-1].time
    else:
        s.start = session_start
    if s.start:
        # Keep the clock running while still active, freeze it after a break.
        live = s.end is None or now - s.end <= idle
        end = now if live else s.end
        s.elapsed = max(end - s.start, timedelta())

    if durations:
        s.active = sum(durations, timedelta())
        s.avg_wing = s.active / len(durations)
        s.median_wing = median(durations)
        s.fastest_wing = min(timed, key=lambda w: w.duration)
        s.slowest_wing = max(timed, key=lambda w: w.duration)
        s.fastest = s.fastest_wing.duration
        s.slowest = s.slowest_wing.duration
        s.p10_wing = percentile(durations, 10)
        s.p90_wing = percentile(durations, 90)
    s.recent_durations = durations[-sparkline_len:]
    s.recent_wings = timed[-sparkline_len:]

    for r in kept:
        s.chaos += r.chaos
        if r.picked:
            s.picked_count += 1
            s.picked_chaos += r.chaos
        if r.chaos and (s.best is None or r.chaos > s.best.chaos):
            s.best = r

        groups = [s.by_type.setdefault(r.item_type or "Unknown", TypeStats())]
        if r.item_type in UNIQUE_TYPES:
            groups.append(s.by_tier.setdefault(tier_label(r.tier), TypeStats()))
        for g in groups:
            g.count += 1
            g.chaos += r.chaos
            g.picked += 1 if r.picked else 0
            if r.chaos and (g.best is None or r.chaos > g.best.chaos):
                g.best = r

    running = 0.0
    for r in sorted(kept, key=lambda r: (r.time, r.record)):
        running += r.chaos
        s.value_series.append((r.time, running))
    s.top_drops = sorted((r for r in kept if r.chaos), key=lambda r: r.chaos, reverse=True)[:TOP_DROPS]
    if s.wings:
        s.chaos_per_wing = s.chaos / s.wings
    # Rates use active time (counted wing times) so breaks and multi-day
    # spans don't dilute them.
    hours = s.active.total_seconds() / 3600
    if hours > 0:
        s.wings_per_hour = len(durations) / hours
        s.chaos_per_hour = s.chaos_per_wing * s.wings_per_hour if s.chaos_per_wing else None

    for wing in wings:
        for key, table in ((wing.blueprint, s.by_blueprint), (wing.area_level, s.by_area_level)):
            g = table.setdefault(key or "Unknown", GroupStats())
            g.wings += 1
            wing_kept = [r for r in wing.rewards if id(r) in kept_ids]
            g.rewards += len(wing_kept)
            g.chaos += sum(r.chaos for r in wing_kept)
            if wing.duration is not None:
                g.durations.append(wing.duration)
    return s


def format_duration(td):
    if td is None:
        return "—"
    total = int(td.total_seconds())
    h, rem = divmod(total, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"
