"""The three dry runs documented in docs/, pinned against the sample data."""
from pathlib import Path

from migrate import config as config_io
from migrate import pipeline, reconcile

CONFIG = Path(__file__).resolve().parent.parent / "config"


def dry_run(version):
    result = pipeline.run(config_io.load(CONFIG / f"{version}.yaml"))
    return result, reconcile.reconcile(result)


def test_dry_run_1_fails_on_reject_rate():
    _, rec = dry_run("v1")
    assert rec.reject_rate > 0.25
    assert not rec.go


def test_dry_run_2_balances_every_row_but_not_every_euro():
    _, rec = dry_run("v2")
    assert all(b.balanced for b in rec.balances)
    assert rec.reject_rate < rec.max_reject_rate
    assert rec.control_totals[0].unexplained > 90_000
    assert rec.blockers == [rec.blockers[0]] and "unexplained" in rec.blockers[0]


def test_dry_run_3_is_go():
    _, rec = dry_run("v3")
    assert rec.go, rec.blockers
    assert rec.control_totals[0].unexplained == 0
