import pytest

from migrate import config as config_io
from migrate import loader, pipeline, reconcile
from migrate.target import TargetPlatform

NO_SLEEP = lambda _: None  # noqa: E731


def test_row_counts_balance_but_control_total_catches_misparsed_amounts(project):
    """The dry run 2 incident in miniature: nothing rejected, still wrong."""
    result = pipeline.run(config_io.load(project(amount="amount_naive")))
    rec = reconcile.reconcile(result)
    assert all(b.balanced for b in rec.balances)
    check = rec.control_totals[0]
    assert check.unexplained == pytest.approx(2400 - 2.40)
    assert not rec.go
    assert any("unexplained" in b for b in rec.blockers)


def test_correct_parser_reconciles_to_the_cent(project):
    result = pipeline.run(config_io.load(project()))
    check = reconcile.reconcile(result).control_totals[0]
    assert check.migrated == pytest.approx(2400 + 1250.50)
    assert check.on_hold == pytest.approx(189.90)  # the rejected contract with the impossible date
    assert check.unexplained == 0
    assert check.matches


def test_reject_rate_above_threshold_blocks_go_live(project):
    result = pipeline.run(config_io.load(project(max_reject=0.01)))
    rec = reconcile.reconcile(result)
    assert not rec.go
    assert any("reject rate" in b for b in rec.blockers)


def test_load_then_reconcile_against_target(project, tmp_path):
    result = pipeline.run(config_io.load(project()))
    target = TargetPlatform(tmp_path / "t.db")
    report = loader.load(result, target, "run-1", sleep=NO_SLEEP)
    rec = reconcile.reconcile(result, target, "run-1")
    assert report.loaded == {"accounts": 3, "contacts": 2, "contracts": 2}
    assert all(b.target_matches for b in rec.balances)
    assert rec.go, rec.blockers


def test_rerunning_a_load_is_idempotent(project, tmp_path):
    result = pipeline.run(config_io.load(project()))
    target = TargetPlatform(tmp_path / "t.db")
    loader.load(result, target, "run-1", sleep=NO_SLEEP)
    loader.load(result, target, "run-2", sleep=NO_SLEEP)
    assert target.count("accounts") == 3
    assert target.count("accounts", "run-2") == 3
    assert reconcile.reconcile(result, target, "run-2").go


def test_transient_failures_are_retried_with_backoff(project, tmp_path):
    result = pipeline.run(config_io.load(project()))
    target = TargetPlatform(tmp_path / "t.db", fail_first_attempt_every=1)
    delays = []
    report = loader.load(result, target, "run-1", batch_size=1, sleep=delays.append)
    assert report.retries == 7  # every batch failed once
    assert delays == [0.5] * 7
    assert target.count("contracts") == 2


def test_persistent_failure_marks_the_run_failed(project, tmp_path, monkeypatch):
    from migrate.target import RateLimited

    result = pipeline.run(config_io.load(project()))
    target = TargetPlatform(tmp_path / "t.db")

    def always_limited(*args, **kwargs):
        raise RateLimited("429")

    monkeypatch.setattr(target, "upsert_batch", always_limited)
    with pytest.raises(loader.LoadFailed):
        loader.load(result, target, "run-1", max_retries=2, sleep=NO_SLEEP)
    assert target.runs()[-1]["status"] == "failed"


def test_rollback_removes_everything_the_run_wrote(project, tmp_path):
    result = pipeline.run(config_io.load(project()))
    target = TargetPlatform(tmp_path / "t.db")
    loader.load(result, target, "run-1", sleep=NO_SLEEP)
    removed = target.rollback("run-1", ["contracts", "contacts", "accounts"])
    assert removed == {"contracts": 2, "contacts": 2, "accounts": 3}
    assert target.count("accounts") == 0
    assert target.runs()[-1]["status"] == "rolled_back"


def test_rows_left_over_from_an_earlier_run_block_go_live(project, tmp_path):
    result = pipeline.run(config_io.load(project()))
    target = TargetPlatform(tmp_path / "t.db")
    loader.load(result, target, "run-1", sleep=NO_SLEEP)
    target.conn.execute(
        "INSERT INTO accounts (external_id, name, migration_run_id) VALUES ('CL777', 'Old test row', 'run-0')"
    )
    target.conn.commit()
    rec = reconcile.reconcile(result, target, "run-1")
    assert not rec.go
    assert any("earlier run" in b for b in rec.blockers)
