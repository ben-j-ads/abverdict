import math
import unittest

from abverdict import stats


class StatsReferenceValues(unittest.TestCase):
    def test_norm_ppf_975(self):
        self.assertAlmostEqual(stats.norm_ppf(0.975), 1.959964, places=5)

    def test_norm_cdf_symmetry(self):
        self.assertAlmostEqual(stats.norm_cdf(1.2) + stats.norm_cdf(-1.2), 1.0, places=12)

    def test_t_cdf_known_critical_values(self):
        # Two-sided 5% critical values from standard t tables.
        self.assertAlmostEqual(stats.t_cdf(2.228139, 10), 0.975, places=5)
        self.assertAlmostEqual(stats.t_cdf(2.042272, 30), 0.975, places=5)
        self.assertAlmostEqual(stats.t_cdf(-2.228139, 10), 0.025, places=5)

    def test_t_ppf_round_trip(self):
        self.assertAlmostEqual(stats.t_ppf(0.975, 10), 2.228139, places=4)

    def test_t_approaches_normal(self):
        self.assertAlmostEqual(stats.t_cdf(1.96, 1e6), stats.norm_cdf(1.96), places=5)

    def test_chi2_sf_known_values(self):
        self.assertAlmostEqual(stats.chi2_sf(3.841459, 1), 0.05, places=5)
        self.assertAlmostEqual(stats.chi2_sf(5.991465, 2), 0.05, places=5)
        self.assertAlmostEqual(stats.chi2_sf(0.0, 3), 1.0, places=12)

    def test_holm(self):
        adj = stats.holm_adjust([0.01, 0.04, 0.03])
        self.assertAlmostEqual(adj[0], 0.03)
        self.assertAlmostEqual(adj[2], 0.06)
        self.assertAlmostEqual(adj[1], 0.06)  # monotone: not below the previous

    def test_norm_ppf_rejects_bounds(self):
        with self.assertRaises(ValueError):
            stats.norm_ppf(1.0)


if __name__ == "__main__":
    unittest.main()
