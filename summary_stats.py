"""Session summary statistics (no Tk): wings, timings, values.

A *wing* is a group of consecutive rewards (sorted by time, then record #).
A new wing starts when the current one already has REWARDS_PER_WING rewards,
when the blueprint type or area level changes, or when the gap since the
previous reward exceeds WING_BREAK.

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

SESSION_APP_START = "Since app start"
SESSION_LAST_BREAK = "Since last break"
SESSION_ALL = "All loaded"
SESSION_MODES = (SESSION_APP_START, SESSION_LAST_BREAK, SESSION_ALL)


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


def group_wings(rewards, idle=DEFAULT_IDLE):
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


def summarize(rewards, now=None, session_start=None, idle=DEFAULT_IDLE, sparkline_len=30):
    now = now or datetime.now()
    s = Summary()
    if not rewards and session_start is None:
        return s

    wings = group_wings(rewards, idle)
    durations = [w.duration for w in wings if w.duration is not None]

    s.rewards = len(rewards)
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
        s.fastest = min(durations)
        s.slowest = max(durations)
    s.recent_durations = durations[-sparkline_len:]

    for r in rewards:
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

    s.top_drops = sorted((r for r in rewards if r.chaos), key=lambda r: r.chaos, reverse=True)[:TOP_DROPS]
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
            g.rewards += len(wing.rewards)
            g.chaos += wing.chaos
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
