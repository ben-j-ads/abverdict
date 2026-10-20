import random
import unittest

from abverdict import planning, verdict
from abverdict.verdict import Arm


def conv(name, c, n):
    return Arm(name, n, conversions=c)


class Planning(unittest.TestCase):
    def test_matches_published_calculator(self):
        # 5% baseline, +10% relative, alpha .05, power .8 -> 31,234 per arm (Evan Miller's calculator).
        self.assertEqual(planning.conversion_n_per_arm(0.05, 0.10), 31234)

    def test_absolute_mde(self):
        self.assertEqual(planning.conversion_n_per_arm(0.05, 0.005, relative=False), 31234)

    def test_more_variants_need_more_traffic(self):
        self.assertGreater(planning.conversion_n_per_arm(0.05, 0.1, comparisons=2),
                           planning.conversion_n_per_arm(0.05, 0.1))

    def test_continuous(self):
        # sd 10, detect 2 units: 2*((1.96+0.8416)*5)^2 = 392.4 -> 393
        self.assertEqual(planning.continuous_n_per_arm(10, 2), 393)

    def test_days_round_up_to_whole_weeks(self):
        p = planning.make_plan(31234, "conversion", daily_traffic=2000)
        self.assertEqual((p.raw_days, p.days), (32, 35))
        self.assertEqual(planning.make_plan(100, "conversion", daily_traffic=1000).days, 7)

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            planning.conversion_n_per_arm(1.2, 0.1)
        with self.assertRaises(ValueError):
            planning.conversion_n_per_arm(0.95, 0.2)


class Verdicts(unittest.TestCase):
    def test_clear_winner(self):
        r = verdict.analyze([conv("A", 5000, 100000), conv("B", 5400, 100000)], planned_n=100000, days=14)
        self.assertEqual(r.overall, verdict.WINNER)

    def test_early_significance_is_not_called(self):
        r = verdict.analyze([conv("A", 500, 10000), conv("B", 580, 10000)], planned_n=31234, days=5)
        self.assertEqual(r.overall, verdict.KEEP_RUNNING)
        self.assertTrue(any("5 day" in w for w in r.warnings))

    def test_srm_invalidates(self):
        r = verdict.analyze([conv("A", 500, 10000), conv("B", 500, 13000)])
        self.assertEqual(r.overall, verdict.INVALID)
        self.assertLess(r.srm_p, 0.001)

    def test_srm_respects_intended_split(self):
        ok = verdict.analyze([conv("A", 800, 80000), conv("B", 210, 20000)], split=[80, 20])
        self.assertNotEqual(ok.overall, verdict.INVALID)

    def test_loser(self):
        r = verdict.analyze([conv("A", 5400, 100000), conv("B", 5000, 100000)], planned_n=100000)
        self.assertEqual(r.overall, verdict.LOSER)

    def test_inconclusive_vs_no_difference(self):
        arms = [conv("A", 5000, 100000), conv("B", 5010, 100000)]
        self.assertEqual(verdict.analyze(arms, planned_n=100000).overall, verdict.INCONCLUSIVE)
        # CI is about +/-0.14 pts; an MDE of 0.5 pts is ruled out.
        self.assertEqual(verdict.analyze(arms, planned_n=100000, mde=0.005).overall, verdict.NO_DIFFERENCE)

    def test_peeking_tightens_threshold(self):
        # p ~ 0.033: significant for one look, not after three looks (Pocock 0.0221).
        arms = [conv("A", 1000, 20000), conv("B", 1095, 20000)]
        once = verdict.analyze(arms, planned_n=20000, looks=1)
        thrice = verdict.analyze(arms, planned_n=20000, looks=3)
        self.assertTrue(0.0221 < once.comparisons[0].p_value < 0.05)
        self.assertEqual(once.overall, verdict.WINNER)
        self.assertEqual(thrice.overall, verdict.INCONCLUSIVE)

    def test_multiple_variants_are_corrected(self):
        arms = [conv("A", 1000, 20000), conv("B", 1095, 20000), conv("C", 1000, 20000)]
        r = verdict.analyze(arms, planned_n=20000)
        self.assertGreater(r.comparisons[0].p_adjusted, r.comparisons[0].p_value)
        self.assertEqual(r.overall, verdict.INCONCLUSIVE)

    def test_welch_detects_real_difference(self):
        a = Arm("A", 500, mean=20.0, sd=10.0)
        b = Arm("B", 500, mean=22.0, sd=10.0)
        r = verdict.analyze([a, b], planned_n=500)
        self.assertEqual(r.overall, verdict.WINNER)
        self.assertAlmostEqual(r.comparisons[0].effect, 2.0)

    def test_heavy_tail_warning(self):
        a = Arm("A", 500, mean=20.0, sd=10.0, skew=4.0)
        b = Arm("B", 500, mean=20.0, sd=10.0, skew=1.0)
        r = verdict.analyze([a, b], planned_n=500)
        self.assertTrue(any("Heavy-tailed" in w for w in r.warnings))

    def test_validation(self):
        with self.assertRaises(ValueError):
            verdict.analyze([conv("A", 1, 10)])
        with self.assertRaises(ValueError):
            verdict.analyze([conv("A", 11, 10), conv("B", 1, 10)])
        with self.assertRaises(ValueError):
            verdict.analyze([conv("A", 1, 10), conv("A", 1, 10)])

    def test_false_positive_rate_with_correction_is_controlled(self):
        # A/A tests with 4 looks at alpha .05: Pocock should keep false positives near 5%.
        rng = random.Random(7)
        trials, hits = 400, 0
        for _ in range(trials):
            ca = cb = 0
            called = False
            for look in range(1, 5):
                ca += sum(rng.random() < 0.1 for _ in range(500))
                cb += sum(rng.random() < 0.1 for _ in range(500))
                n = 500 * look
                r = verdict.analyze([conv("A", ca, n), conv("B", cb, n)], looks=4, planned_n=n)
                if r.overall in (verdict.WINNER, verdict.LOSER):
                    called = True
            hits += called
        self.assertLess(hits / trials, 0.08)


if __name__ == "__main__":
    unittest.main()
