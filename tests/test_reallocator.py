"""Tests for the scenario reallocator — the bus-moving logic.

These pin the two defects found on 2026-10-24:

1. A donor was checked for over-capacity *before* the move, so taking a trip
   from a 3-trip hour running at 83% left it at 125% with passengers behind.
   The move created the queue it was meant to shorten.
2. The greedy loop could undo its own move on a later pass and log the
   reversal as a second improvement, so `trips_moved` counted work that did
   not happen.

Run with:  .venv/bin/python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard" / "build"))

from build_data import DONOR_CEILING_PCT, net_moves, reallocate  # noqa: E402


SEATS = 72


def _row(route, hour, trips, demand):
    return {
        "route_code": route,
        "hour": hour,
        "trips_in_hour": float(trips),
        "seated_capacity": SEATS,
        "demand_pax_est": float(demand),
    }


def _df(*rows):
    return pd.DataFrame([_row(*r) for r in rows])


def _all_rows(_d):
    return pd.Series(True, index=_d.index)


class TestDonorGuard:
    """A move may never create a new over-capacity hour."""

    def test_refuses_donor_that_would_overflow(self):
        # R1 12: 3 trips, 216 seats, 179.5 pax = 83%. Losing a trip -> 124.7%.
        gap = _df(("R1", 12, 3, 179.5), ("R1", 16, 4, 416.0))
        _, moves = reallocate(gap, _all_rows, _all_rows, n_moves=5)
        assert moves == [], "a donor that would exceed 100% must not be used"

    def test_accepts_donor_that_stays_within_ceiling(self):
        # R4 19: 2 trips, 144 seats, 37.3 pax = 25.9%. Losing a trip -> 51.8%.
        gap = _df(("R4", 19, 2, 37.3), ("R1", 16, 4, 416.0))
        _, moves = reallocate(
            gap,
            lambda d: d.route_code == "R4",
            lambda d: d.route_code == "R1",
            n_moves=1,
        )
        assert len(moves) == 1
        assert moves[0]["donor_load_after_pct"] <= DONOR_CEILING_PCT

    def test_ceiling_is_enforced_after_every_step_not_just_the_first(self):
        gap = _df(
            ("R4", 18, 2, 58.8),   # 40.8% -> 81.6% after, allowed
            ("R4", 14, 2, 100.5),  # 69.8% -> 139.6% after, must be refused
            ("R1", 16, 4, 416.0),
        )
        _, moves = reallocate(
            gap,
            lambda d: d.route_code == "R4",
            lambda d: d.route_code == "R1",
            n_moves=5,
        )
        assert all(m["donor_load_after_pct"] <= DONOR_CEILING_PCT for m in moves)
        assert not any(m["from_hour"] == 14 for m in moves)

    def test_never_deletes_service(self):
        gap = _df(("R4", 19, 2, 5.0), ("R1", 16, 4, 416.0))
        out, moves = reallocate(
            gap,
            lambda d: d.route_code == "R4",
            lambda d: d.route_code == "R1",
            n_moves=10,
        )
        assert len(moves) == 1, "a 2-trip hour may donate at most one trip"
        assert out.loc[out.route_code == "R4", "trips_in_hour"].iloc[0] == 1

    def test_does_not_move_into_an_hour_that_is_not_over_capacity(self):
        gap = _df(("R4", 19, 2, 37.3), ("R1", 12, 3, 100.0))  # R1 12 only 46%
        _, moves = reallocate(
            gap,
            lambda d: d.route_code == "R4",
            lambda d: d.route_code == "R1",
            n_moves=5,
        )
        assert moves == []


class TestReverseNetting:
    """Moves that cancel each other must not be counted."""

    def test_cancelling_pair_is_dropped(self):
        a = {"from_route": "R1", "from_hour": 12, "to_route": "R2", "to_hour": 22}
        b = {"from_route": "R2", "from_hour": 22, "to_route": "R1", "to_hour": 12}
        assert net_moves([a, b]) == []

    def test_non_cancelling_moves_survive(self):
        a = {"from_route": "R4", "from_hour": 19, "to_route": "R1", "to_hour": 16}
        b = {"from_route": "R4", "from_hour": 20, "to_route": "R1", "to_hour": 20}
        assert net_moves([a, b]) == [a, b]

    def test_only_the_pair_is_removed(self):
        a = {"from_route": "R4", "from_hour": 19, "to_route": "R1", "to_hour": 16}
        b = {"from_route": "R1", "from_hour": 12, "to_route": "R2", "to_hour": 22}
        c = {"from_route": "R2", "from_hour": 22, "to_route": "R1", "to_hour": 12}
        assert net_moves([a, b, c]) == [a]

    def test_repeated_cycles_all_cancel(self):
        pair = [
            {"from_route": "R1", "from_hour": 12, "to_route": "R2", "to_hour": 22},
            {"from_route": "R2", "from_hour": 22, "to_route": "R1", "to_hour": 12},
        ]
        assert net_moves(pair * 4) == []

    def test_reallocation_never_returns_a_reverse_pair(self):
        gap = _df(
            ("R4", 16, 2, 51.3),
            ("R4", 17, 2, 47.2),
            ("R1", 16, 4, 416.0),
            ("R1", 20, 3, 320.0),
        )
        _, moves = reallocate(
            gap,
            lambda d: d.route_code == "R4",
            lambda d: d.route_code == "R1",
            n_moves=10,
        )
        keys = {(m["from_route"], m["from_hour"], m["to_route"], m["to_hour"]) for m in moves}
        assert not any((b, d, a, c) in keys for a, c, b, d in keys)


class TestFleetNeutrality:
    """Moving trips must conserve the fleet."""

    @pytest.mark.parametrize("n_moves", [1, 3, 8, 20])
    def test_total_trips_are_conserved(self, n_moves):
        gap = _df(
            ("R4", 16, 2, 51.3),
            ("R4", 17, 2, 47.2),
            ("R4", 19, 2, 37.3),
            ("R1", 16, 4, 416.0),
            ("R1", 20, 3, 320.0),
        )
        before = gap["trips_in_hour"].sum()
        out, _ = reallocate(
            gap,
            lambda d: d.route_code == "R4",
            lambda d: d.route_code == "R1",
            n_moves=n_moves,
        )
        assert out["trips_in_hour"].sum() == before

    def test_every_move_relieves_its_receiver(self):
        gap = _df(
            ("R4", 16, 2, 51.3),
            ("R4", 17, 2, 47.2),
            ("R1", 16, 4, 416.0),
            ("R1", 20, 3, 320.0),
        )
        _, moves = reallocate(
            gap,
            lambda d: d.route_code == "R4",
            lambda d: d.route_code == "R1",
            n_moves=10,
        )
        assert moves
        for m in moves:
            assert m["receiver_unmet_after"] < m["receiver_unmet_before"]
