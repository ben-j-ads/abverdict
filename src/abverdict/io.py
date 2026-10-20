"""Input parsing: `--arm name=conv/n` strings and CSV exports."""
from __future__ import annotations

import csv
import math
from collections import OrderedDict
from typing import Optional

from .verdict import Arm

_NAME = ("variant", "arm", "name", "group")
_VISITORS = ("visitors", "n", "users", "sessions", "sends", "impressions", "recipients")
_CONVERSIONS = ("conversions", "successes", "orders", "clicks", "signups", "opens")
_VALUE = ("value", "revenue", "metric", "amount")


def parse_arm(text: str) -> Arm:
    """Parse 'name=conversions/visitors', e.g. 'B=560/10000'."""
    try:
        name, rest = text.split("=", 1)
        conv, n = rest.replace(",", "").split("/", 1)
        return Arm(name.strip(), int(n), conversions=int(conv))
    except ValueError:
        raise ValueError(f"can't parse arm '{text}'. Expected name=conversions/visitors, e.g. B=560/10000") from None


def _column(header: list, options: tuple, what: str) -> str:
    lowered = {h.strip().lower(): h for h in header}
    for o in options:
        if o in lowered:
            return lowered[o]
    raise ValueError(f"CSV needs a {what} column (one of: {', '.join(options)}). Found: {', '.join(header)}")


def _order(groups: "OrderedDict", control: Optional[str]) -> list:
    names = list(groups)
    if control is not None:
        if control not in groups:
            raise ValueError(f"control '{control}' not found. Variants in file: {', '.join(names)}")
        names.remove(control)
        names.insert(0, control)
    return names


def read_counts_csv(path: str, control: Optional[str] = None):
    """Aggregate rows (e.g. one per day) by variant. Returns (arms, days_or_None)."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        name_c = _column(header, _NAME, "variant")
        n_c = _column(header, _VISITORS, "visitors")
        conv_c = _column(header, _CONVERSIONS, "conversions")
        date_c = next((h for h in header if h.strip().lower() == "date"), None)
        groups, dates = OrderedDict(), set()
        for row in reader:
            g = groups.setdefault(row[name_c].strip(), [0, 0])
            g[0] += int(float(row[n_c]))
            g[1] += int(float(row[conv_c]))
            if date_c:
                dates.add(row[date_c])
    arms = [Arm(name, groups[name][0], conversions=groups[name][1]) for name in _order(groups, control)]
    return arms, (len(dates) or None)


def _moments(values: list):
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        raise ValueError("each variant needs at least 2 observations")
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    sd = math.sqrt(var)
    skew = None
    if sd > 0:
        skew = sum(((x - mean) / sd) ** 3 for x in values) * n / ((n - 1) * (n - 2)) if n > 2 else None
    return mean, sd, skew


def read_values_csv(path: str, control: Optional[str] = None):
    """One row per user/order with a numeric value. Returns (arms, days_or_None)."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        name_c = _column(header, _NAME, "variant")
        val_c = _column(header, _VALUE, "value")
        date_c = next((h for h in header if h.strip().lower() == "date"), None)
        groups, dates = OrderedDict(), set()
        for row in reader:
            groups.setdefault(row[name_c].strip(), []).append(float(row[val_c]))
            if date_c:
                dates.add(row[date_c])
    arms = []
    for name in _order(groups, control):
        mean, sd, skew = _moments(groups[name])
        arms.append(Arm(name, len(groups[name]), mean=mean, sd=sd, skew=skew))
    return arms, (len(dates) or None)
