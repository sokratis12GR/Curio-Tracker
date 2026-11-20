import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import summary_stats as ss  # noqa: E402

T0 = datetime(2026, 11, 20, 12, 0, 0)


def wing(start_min, bp="Bunker", lvl="83", n=5, chaos=10.0, first_record=1):
    base = T0 + timedelta(minutes=start_min)
    return [ss.Reward(base + timedelta(seconds=i), first_record + i, bp, lvl, chaos, i == 0)
            for i in range(n)]


class GroupWingsTests(unittest.TestCase):
    def test_every_five_rewards_is_a_wing(self):
        rewards = wing(0) + wing(3, first_record=6)
        wings = ss.group_wings(rewards)
        self.assertEqual([len(w.rewards) for w in wings], [5, 5])
        self.assertEqual(wings[0].duration, timedelta(minutes=3))
        self.assertIsNone(wings[1].duration)

    def test_blueprint_change_starts_new_wing(self):
        rewards = wing(0, n=3) + wing(1, bp="Mansion", first_record=4)
        wings = ss.group_wings(rewards)
        self.assertEqual([(w.blueprint, len(w.rewards)) for w in wings],
                         [("Bunker", 3), ("Mansion", 5)])

    def test_area_level_change_starts_new_wing(self):
        rewards = wing(0, n=2) + wing(1, lvl="81", n=2, first_record=3)
        self.assertEqual(len(ss.group_wings(rewards)), 2)

    def test_long_gap_splits_partial_wing(self):
        rewards = wing(0, n=2) + wing(10, n=3, first_record=3)
        self.assertEqual(len(ss.group_wings(rewards)), 2)

    def test_wing_under_min_is_merged(self):
        rewards = wing(0) + wing(0.1, n=2, first_record=6) + wing(6, first_record=8)
        wings = ss.group_wings(rewards, min_wing=timedelta(seconds=10))
        self.assertEqual([len(w.rewards) for w in wings], [7, 5])
        self.assertEqual(wings[0].duration, timedelta(minutes=6))

    def test_min_wing_zero_keeps_split(self):
        rewards = wing(0) + wing(0.1, n=2, first_record=6)
        self.assertEqual(len(ss.group_wings(rewards, min_wing=timedelta())), 2)

    def test_idle_gap_excluded_from_duration(self):
        rewards = wing(0) + wing(60, first_record=6)
        self.assertIsNone(ss.group_wings(rewards)[0].duration)


class SessionTests(unittest.TestCase):
    def test_app_start_filters_older(self):
        rewards = wing(0) + wing(100, first_record=6)
        picked = ss.select_session(rewards, ss.SESSION_APP_START, T0 + timedelta(minutes=50))
        self.assertEqual(len(picked), 5)

    def test_last_break_mode(self):
        rewards = wing(0) + wing(100, first_record=6) + wing(103, first_record=11)
        picked = ss.select_session(rewards, ss.SESSION_LAST_BREAK)
        self.assertEqual(len(picked), 10)

    def test_summary_numbers(self):
        rewards = wing(0) + wing(3, first_record=6) + wing(7, bp="Mansion", chaos=20, first_record=11)
        s = ss.summarize(rewards, now=T0 + timedelta(minutes=8))
        self.assertEqual(s.wings, 3)
        self.assertEqual(s.avg_wing, timedelta(minutes=3, seconds=30))
        self.assertEqual(s.fastest, timedelta(minutes=3))
        self.assertEqual(s.slowest, timedelta(minutes=4))
        self.assertEqual(s.fastest_wing.blueprint, "Bunker")
        self.assertEqual(s.p10_wing, timedelta(minutes=3, seconds=6))
        self.assertEqual(s.p90_wing, timedelta(minutes=3, seconds=54))
        self.assertAlmostEqual(s.chaos, 200)
        self.assertEqual(s.picked_count, 3)
        self.assertEqual(s.by_blueprint["Bunker"].wings, 2)
        self.assertEqual(s.by_blueprint["Mansion"].chaos, 100)
        self.assertEqual(s.elapsed, timedelta(minutes=8))

    def test_rates_use_active_time(self):
        # Two wings 3 min apart, then a 2-day gap: rates must ignore the gap.
        rewards = wing(0) + wing(3, first_record=6) + wing(3000, first_record=11)
        s = ss.summarize(rewards, now=T0 + timedelta(minutes=3001))
        self.assertEqual(s.active, timedelta(minutes=3))
        self.assertAlmostEqual(s.wings_per_hour, 20.0)

    def test_tiers_and_types(self):
        rewards = wing(0, n=3)
        rewards[0].item_type, rewards[0].tier, rewards[0].chaos = "Replica", "1.0", 500
        rewards[1].item_type, rewards[1].tier = "Replacement", "3"
        rewards[2].item_type = "Currency"
        s = ss.summarize(rewards, now=T0)
        self.assertEqual(set(s.by_tier), {"T1", "T3"})
        self.assertEqual(s.by_tier["T1"].chaos, 500)
        self.assertEqual(s.by_type["Currency"].count, 1)
        self.assertIs(s.top_drops[0], rewards[0])

    def test_windows(self):
        now = T0 + timedelta(hours=3)
        self.assertEqual(ss.session_window(ss.SESSION_TODAY, now)[0], T0.replace(hour=0))
        self.assertEqual(ss.session_window(ss.SESSION_24H, now), (now - timedelta(days=1), now))
        self.assertEqual(ss.session_window(ss.SESSION_CUSTOM, now, custom=(T0, None)), (T0, now))
        self.assertIsNone(ss.session_window(ss.SESSION_CUSTOM, now, custom=(None, None)))
        self.assertIsNone(ss.session_window(ss.SESSION_ALL, now))
        self.assertEqual(ss.previous_window((T0, now)), (T0 - timedelta(hours=3), T0))

    def test_in_window_and_change(self):
        rewards = wing(0) + wing(100, first_record=6)
        picked = ss.in_window(rewards, (T0 + timedelta(minutes=50), T0 + timedelta(minutes=200)))
        self.assertEqual(len(picked), 5)
        self.assertAlmostEqual(ss.pct_change(120, 100), 20)
        self.assertIsNone(ss.pct_change(120, 0))

    def test_wing_filter_keeps_timings(self):
        rewards = wing(0) + wing(3, bp="Mansion", first_record=6) + wing(7, first_record=11)
        s = ss.summarize(rewards, now=T0 + timedelta(minutes=8),
                         wing_keep=lambda w: w.blueprint == "Mansion")
        self.assertEqual(s.wings, 1)
        self.assertEqual(s.avg_wing, timedelta(minutes=4))
        self.assertAlmostEqual(s.chaos, 50)

    def test_reward_filter_narrows_value_only(self):
        rewards = wing(0) + wing(3, first_record=6)
        s = ss.summarize(rewards, now=T0 + timedelta(minutes=4), keep=lambda r: r.picked)
        self.assertEqual(s.wings, 2)
        self.assertEqual(s.rewards, 2)
        self.assertAlmostEqual(s.chaos, 20)
        self.assertAlmostEqual(s.by_blueprint["Bunker"].chaos, 20)

    def test_value_series_and_recent_wings(self):
        rewards = wing(0, n=2) + wing(10, n=2, chaos=5, first_record=3)
        s = ss.summarize(rewards, now=T0 + timedelta(minutes=11))
        self.assertEqual([v for _, v in s.value_series], [10, 20, 25, 30])
        self.assertEqual(len(s.recent_wings), 1)
        self.assertEqual(s.recent_wings[0].duration, timedelta(minutes=10))

    def test_empty(self):
        s = ss.summarize([], now=T0, session_start=T0)
        self.assertEqual(s.wings, 0)
        self.assertEqual(ss.format_duration(None), "—")


if __name__ == "__main__":
    unittest.main()
