"""Komandna linija: init, scan, build, refresh, open."""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from collections import Counter
from pathlib import Path

from atlas.config import ConfigError, default_config, load_config
from atlas.inventory import ScanOutcome, build_inventory
from atlas.model import KINDS, InventoryError, inventory_from_dict, inventory_hash
from atlas.outputs import catalog_target, inventory_target, report_target
from atlas.paths import AppPaths
from atlas.writeout import LockBusy, RecoveryError, atlas_lock, publish, recover_if_needed

KIND_LABELS = {"project": "projekti", "skill": "skillovi", "plugin": "pluginovi",
               "mcp": "MCP", "document": "dokumenti"}


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def _summary(paths: AppPaths, outcome: ScanOutcome, wrote_catalog: bool) -> None:
    inv = outcome.inventory
    counts = Counter(i.kind for i in inv.items)
    parts = ", ".join(f"{KIND_LABELS[k]} {counts.get(k, 0)}" for k in KINDS)
    print(f"Skenirano {len(inv.items)} stavki ({parts}) za {outcome.duration_s:.1f} s.")
    if inv.partial:
        warn_count = sum(1 for w in inv.warnings if w.severity == "warn")
        print(f"Djelimičan pregled: {warn_count} upozorenja. Detalji su u izvještaju.")
    print(f"Izvještaj: {paths.report}")
    if wrote_catalog:
        print(f"Katalog: {paths.catalog}")


def _cmd_init(paths: AppPaths, config_arg: str | None) -> int:
    target = paths.resolve_config(config_arg)
    if target.exists():
        print(f"Config već postoji, ne mijenjam ga: {target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    data = default_config(Path.home(), paths.root.parent)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Napravljen config: {target}")
    return 0


def _scan(paths: AppPaths, config_arg: str | None) -> ScanOutcome:
    return build_inventory(load_config(paths.resolve_config(config_arg)))


def _cmd_scan(paths: AppPaths, config_arg: str | None) -> int:
    outcome = _scan(paths, config_arg)
    h = inventory_hash(outcome.inventory)
    publish(paths, [inventory_target(paths, outcome.inventory), report_target(paths, outcome, h)])
    _summary(paths, outcome, wrote_catalog=False)
    return 2 if outcome.inventory.partial else 0


def _cmd_build(paths: AppPaths) -> int:
    if not paths.inventory.exists():
        _err(f"Greška: nema {paths.inventory}. Pokreni prvo: atlas scan")
        return 1
    inv = inventory_from_dict(json.loads(paths.inventory.read_text(encoding="utf-8")))
    publish(paths, [catalog_target(paths, inv, inventory_hash(inv))])
    print(f"Katalog: {paths.catalog}")
    return 0


def _cmd_refresh(paths: AppPaths, config_arg: str | None) -> int:
    outcome = _scan(paths, config_arg)
    inv = outcome.inventory
    h = inventory_hash(inv)
    publish(paths, [inventory_target(paths, inv), report_target(paths, outcome, h), catalog_target(paths, inv, h)])
    _summary(paths, outcome, wrote_catalog=True)
    return 2 if inv.partial else 0


def _cmd_open(paths: AppPaths) -> int:
    if not paths.catalog.exists():
        _err(f"Greška: nema {paths.catalog}. Pokreni prvo: atlas refresh")
        return 1
    if os.name == "nt":
        os.startfile(str(paths.catalog))  # bez shella
    else:
        webbrowser.open(paths.catalog.as_uri())
    return 0


def main(argv: list[str] | None = None, *, app_root: Path | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except AttributeError:
            pass
    parser = argparse.ArgumentParser(prog="atlas", description="Lokalni katalog AI okruženja")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("init", "napravi config/sources.local.json ako ne postoji"),
        ("scan", "skeniraj izvore u data/"),
        ("build", "napravi output/index.html iz data/inventory.json"),
        ("refresh", "scan + build"),
        ("open", "otvori output/index.html"),
    ):
        command = sub.add_parser(name, help=help_text)
        if name in ("init", "scan", "refresh"):
            command.add_argument("--config", help="putanja do configa (relativna od korijena aplikacije)")
    args = parser.parse_args(argv)
    paths = AppPaths(app_root)
    try:
        if args.command == "init":
            return _cmd_init(paths, args.config)
        with atlas_lock(paths):
            if recover_if_needed(paths):
                _err("Oporavljen prethodni komplet izlaza nakon prekinute objave.")
            if args.command == "open":
                pass
            elif args.command == "scan":
                return _cmd_scan(paths, args.config)
            elif args.command == "build":
                return _cmd_build(paths)
            elif args.command == "refresh":
                return _cmd_refresh(paths, args.config)
        return _cmd_open(paths)
    except (ConfigError, LockBusy, RecoveryError, InventoryError) as exc:
        _err(f"Greška: {exc}")
        return 1
    except ValueError as exc:
        _err(f"Greška: neispravan izlaz ili inventar ({type(exc).__name__}: {exc})")
        return 1
    except OSError as exc:
        _err(f"Greška pri radu sa fajlom: {exc.strerror or type(exc).__name__} ({exc.filename})")
        return 1


def main_entry() -> None:
    raise SystemExit(main())
