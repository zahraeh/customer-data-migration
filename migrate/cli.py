"""Command line entry point: python -m migrate <command> ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config as config_io
from . import loader, pipeline, profile, reconcile, report, suggest
from . import source as source_io
from .target import TargetPlatform

ROOT = Path(__file__).resolve().parent.parent


def cmd_profile(args):
    text = profile.profile(args.files, args.out)
    print(text if not args.out else f"Profile written to {args.out}")


def cmd_suggest(args):
    src = source_io.read(args.file)
    samples = suggest.collect_samples(src, mask=args.mask)
    if args.ai:
        suggestions = suggest.ai(args.entity, src.headers, samples)
    else:
        suggestions = suggest.heuristic(args.entity, src.headers, samples)
    print(suggest.to_yaml(args.entity, args.file, suggestions))


def _run_pipeline(args):
    cfg = config_io.load(args.config)
    result = pipeline.run(cfg)
    out_dir = Path(args.out) if args.out else ROOT / "reports" / cfg.version
    return cfg, result, out_dir


def _print_decision(rec, path):
    print(f"{'GO' if rec.go else 'NO-GO'}: report written to {path}")
    for b in rec.blockers:
        print(f"  - {b}")


def cmd_dry_run(args):
    cfg, result, out_dir = _run_pipeline(args)
    rec = reconcile.reconcile(result)
    _print_decision(rec, report.write(result, rec, out_dir))
    return 0 if rec.go else 1


def cmd_load(args):
    cfg, result, out_dir = _run_pipeline(args)
    pre = reconcile.reconcile(result)
    if not pre.go and not args.force:
        _print_decision(pre, report.write(result, pre, out_dir))
        print("Refusing to load: dry-run checks fail. Fix them, or pass --force for a test environment.")
        return 1
    target = TargetPlatform(args.db, fail_first_attempt_every=args.simulate_rate_limit)
    run_id = loader.new_run_id(cfg.version)
    load_report = loader.load(result, target, run_id)
    rec = reconcile.reconcile(result, target, run_id)
    _print_decision(rec, report.write(result, rec, out_dir, load_report))
    print(f"Run ID: {run_id}  (roll back with: python -m migrate rollback --db {args.db} --run-id {run_id})")
    return 0 if rec.go else 1


def cmd_rollback(args):
    target = TargetPlatform(args.db)
    removed = target.rollback(args.run_id, ["contracts", "contacts", "accounts"])
    for entity, n in removed.items():
        print(f"{entity}: {n} rows removed")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="migrate", description="Customer data migration toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("profile", help="profile legacy export files")
    sp.add_argument("files", nargs="+")
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_profile)

    sp = sub.add_parser("suggest-mapping", help="draft a column mapping for a legacy file")
    sp.add_argument("file")
    sp.add_argument("--entity", required=True, choices=list(suggest.TARGET_SCHEMA))
    sp.add_argument("--ai", action="store_true", help="ask Claude (needs ANTHROPIC_API_KEY)")
    sp.add_argument("--mask", action="store_true", help="send value shapes, not real values")
    sp.set_defaults(func=cmd_suggest)

    for name, func in (("dry-run", cmd_dry_run), ("load", cmd_load)):
        sp = sub.add_parser(name)
        sp.add_argument("--config", required=True)
        sp.add_argument("--out", help="report folder (default reports/<version>)")
        if name == "load":
            sp.add_argument("--db", default="target.db")
            sp.add_argument("--force", action="store_true")
            sp.add_argument("--simulate-rate-limit", type=int, metavar="N",
                            help="fail the first attempt of every Nth batch with a 429")
        sp.set_defaults(func=func)

    sp = sub.add_parser("rollback")
    sp.add_argument("--db", default="target.db")
    sp.add_argument("--run-id", required=True)
    sp.set_defaults(func=cmd_rollback)

    args = p.parse_args(argv)
    try:
        return args.func(args) or 0
    except pipeline.ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2
