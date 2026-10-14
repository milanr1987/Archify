"""Komandna linija: init, scan, build, refresh, open."""
from __future__ import annotations

import argparse
import contextlib
import io
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
from atlas.overlay import OverlayError, load_overlay, update_note, orphan_note_ids
from atlas.outputs import overlay_target
from atlas.maps import MapError, catalog_maps
from atlas.mapops import publish_map

KIND_LABELS = {"project": "projekti", "skill": "skillovi", "plugin": "pluginovi",
               "mcp": "MCP", "document": "dokumenti",
               "command": "komande", "agent": "agenti", "hook": "hookovi"}


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
    selected = paths.resolve_config(config_arg)
    print(f"Config: {selected}")
    return build_inventory(load_config(selected), hash_cache_path=paths.data_dir / "skill-hash-cache.json")


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
    overlay = load_overlay(paths.overrides)
    publish(paths, [catalog_target(paths, inv, inventory_hash(inv), overlay, catalog_maps(paths))])
    _orphan_summary(inv, overlay)
    print(f"Katalog: {paths.catalog}")
    return 0


def _cmd_refresh(paths: AppPaths, config_arg: str | None) -> int:
    overlay = load_overlay(paths.overrides)
    outcome = _scan(paths, config_arg)
    inv = outcome.inventory
    h = inventory_hash(inv)
    publish(paths, [inventory_target(paths, inv), report_target(paths, outcome, h), catalog_target(paths, inv, h, overlay, catalog_maps(paths))])
    _orphan_summary(inv, overlay)
    _summary(paths, outcome, wrote_catalog=True)
    return 2 if inv.partial else 0


def _orphan_summary(inv, overlay) -> None:
    count = len(orphan_note_ids(inv, overlay))
    if count:
        print(f'Bilješke nestalih stavki: {count}. Sačuvane su u lokalnom overlay-u.')


def _cmd_note(paths: AppPaths, item_id: str, *, text: str | None,
              tags: list[str] | None, delete: bool) -> int:
    if not paths.inventory.exists():
        _err('Nema inventara. Pokreni atlas scan ili atlas refresh.')
        return 1
    inv = inventory_from_dict(json.loads(paths.inventory.read_text(encoding='utf-8')))
    overlay = load_overlay(paths.overrides)
    updated = update_note(overlay, item_id, text=text, tags=tags, delete=delete)
    if not delete and item_id.lower() not in {item.id for item in inv.items}:
        raise OverlayError('note-unknown-item')
    publish(paths, [overlay_target(paths, updated),
                    catalog_target(paths, inv, inventory_hash(inv), updated, catalog_maps(paths))])
    _orphan_summary(inv, updated)
    print('Bilješka sačuvana; katalog obnovljen.')
    return 0


def _open_catalog(paths: AppPaths) -> None:
    if os.name == "nt":
        os.startfile(str(paths.catalog))  # bez shella
    else:
        webbrowser.open(paths.catalog.as_uri())


def _cmd_open(paths: AppPaths) -> int:
    if not paths.catalog.exists():
        _err(f"Greška: nema {paths.catalog}. Pokreni prvo: atlas refresh")
        return 1
    _open_catalog(paths)
    return 0


def _show_error(message: str) -> None:
    """launch radi bez konzole (pythonw), pa grešku prikazuje u Windows prozoru."""
    if os.name == "nt":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "AI Atlas", 0x10)
    else:
        _err(message)


def _cmd_launch(app_root: Path | None) -> int:
    errors = io.StringIO()
    with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
        code = main(["refresh"], app_root=app_root)
    if code == 1:
        _show_error("Osvježavanje kataloga nije uspjelo.\n\n" + (errors.getvalue().strip() or "Nepoznata greška."))
        return 1
    _open_catalog(AppPaths(app_root))
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
        ("launch", "refresh pa open, bez terminala; greška u prozoru (za prečicu na Desktopu)"),
    ):
        command = sub.add_parser(name, help=help_text)
        if name in ("init", "scan", "refresh"):
            command.add_argument("--config", help="putanja do configa (relativna od korijena aplikacije)")
    note = sub.add_parser('note', help='dodaj, izmijeni ili izbriši lokalnu bilješku')
    note.add_argument('item_id')
    note.add_argument('--text')
    note.add_argument('--tag', action='append', dest='tags')
    note.add_argument('--clear-tags', action='store_true')
    note.add_argument('--delete', action='store_true')
    mapping = sub.add_parser('map', help='valideraj i objavi lokalnu Archify mapu')
    mapping.add_argument('project_id')
    mapping.add_argument('--analysis', required=True)
    mapping.add_argument('--input', required=True)
    mapping.add_argument('--slug', required=True)
    mapping.add_argument('--type', choices=['workflow','architecture'], default='workflow')
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    paths = AppPaths(app_root)
    if args.command == "launch":
        return _cmd_launch(app_root)
    try:
        if args.command == 'note':
            if (args.clear_tags and args.tags is not None) or (args.delete and
                    (args.text is not None or args.tags is not None or args.clear_tags)):
                raise OverlayError('note-conflicting-options')
            if not args.delete and args.text is None and args.tags is None and not args.clear_tags:
                raise OverlayError('note-missing-options')
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
            elif args.command == 'note':
                return _cmd_note(paths, args.item_id, text=args.text,
                                 tags=[] if args.clear_tags else args.tags, delete=args.delete)
            elif args.command == 'map':
                return publish_map(paths,args.project_id,args.analysis,args.input,args.slug,args.type)
        return _cmd_open(paths)
    except (ConfigError, LockBusy, RecoveryError, InventoryError, OverlayError, MapError) as exc:
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
