import contextlib
import io
import json
import os
import tempfile
import unittest

from abverdict.cli import main


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def write(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    f.write(text)
    f.close()
    return f.name


class Cli(unittest.TestCase):
    def test_plan_text_and_json(self):
        code, out, _ = run("plan", "--baseline", "5%", "--mde", "10%", "--daily-traffic", "2000")
        self.assertEqual(code, 0)
        self.assertIn("31,234", out)
        _, js, _ = run("plan", "--baseline", "0.05", "--mde", "0.1", "--json")
        self.assertEqual(json.loads(js)["n_per_arm"], 31234)

    def test_plan_continuous(self):
        code, out, _ = run("plan", "--sd", "10", "--mde", "2")
        self.assertEqual(code, 0)
        self.assertIn("393", out)

    def test_test_arms_json(self):
        code, out, _ = run("test", "--arm", "A=5000/100000", "--arm", "B=5400/100000", "--planned-n", "100000", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["overall"], "WINNER")

    def test_counts_csv_sums_days_and_counts_dates(self):
        rows = ["variant,visitors,conversions,date"]
        for day in range(1, 8):
            rows += [f"A,10000,500,2026-01-0{day}", f"B,10000,580,2026-01-0{day}"]
        path = write("\n".join(rows))
        try:
            code, out, _ = run("test", "--csv", path, "--planned-n", "70000")
            self.assertEqual(code, 0)
            self.assertIn("WINNER", out)
            self.assertNotIn("Test ran", out)  # 7 days from the date column
        finally:
            os.unlink(path)

    def test_control_override(self):
        path = write("variant,visitors,conversions\nB,100000,5400\nA,100000,5000\n")
        try:
            _, out, _ = run("test", "--csv", path, "--control", "A", "--planned-n", "100000")
            self.assertIn("B vs A: WINNER", out)
        finally:
            os.unlink(path)

    def test_values_csv(self):
        lines = ["variant,value"] + [f"A,{10 + (i % 5)}" for i in range(200)] + [f"B,{13 + (i % 5)}" for i in range(200)]
        path = write("\n".join(lines))
        try:
            code, out, _ = run("test", "--values-csv", path, "--planned-n", "200")
            self.assertEqual(code, 0)
            self.assertIn("B vs A: WINNER", out)
        finally:
            os.unlink(path)

    def test_errors_exit_2_without_traceback(self):
        for argv in (["test"], ["test", "--arm", "nonsense"], ["plan", "--mde", "10%"],
                     ["test", "--csv", "/no/such/file.csv"]):
            code, _, err = run(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn("abverdict: error:", err)


if __name__ == "__main__":
    unittest.main()
