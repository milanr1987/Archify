"""Transactional output publishing with repeatable process-crash recovery."""
from __future__ import annotations
import json
import os
import secrets
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Iterator
from atlas.paths import AppPaths
from atlas.maps import map_output_allowed

class LockBusy(Exception): pass
class RecoveryError(Exception): pass

@dataclass
class Target:
    path: Path
    content: str
    validate: Callable[[str], None]

@contextmanager
def atlas_lock(paths: AppPaths) -> Iterator[None]:
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    handle = open(paths.lock, "a+b")
    try:
        if paths.lock.stat().st_size == 0:
            handle.write(b"0"); handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise LockBusy(f"drugi atlas proces radi (lock: {paths.lock})") from None
        yield
    finally:
        handle.close()  # OS releases lock; retain the shared lock file.

def _write_journal(paths: AppPaths, phase: str, entries: list[dict]) -> None:
    tmp = paths.journal.with_name(paths.journal.name + ".tmp")
    tmp.write_text(json.dumps({"phase": phase, "entries": entries}), encoding="utf-8")
    os.replace(tmp, paths.journal)

def _clear_journal(paths: AppPaths) -> None:
    paths.journal.unlink(missing_ok=True)

def _rollback(entries: list[dict]) -> None:
    # Verify the complete rollback set before changing even its first target.
    for entry in entries:
        if entry["backup"] and not Path(entry["backup"]).is_file():
            raise RecoveryError(f"nedostaje backup za {entry['target']}")
    for entry in entries:
        target = Path(entry["target"])
        backup = entry["backup"]
        if backup:
            if not Path(backup).is_file():
                raise RecoveryError(f"nedostaje backup za {target}")
            restore = target.with_name(target.name + ".restore.tmp")
            shutil.copy2(backup, restore)
            os.replace(restore, target)
        else:
            target.unlink(missing_ok=True)

def _discard(entries: list[dict]) -> None:
    for entry in entries:
        Path(entry["staged"]).unlink(missing_ok=True)
        if entry["backup"]:
            Path(entry["backup"]).unlink(missing_ok=True)

def publish(paths: AppPaths, targets: list[Target], *, replace: Callable = os.replace) -> None:
    for t in targets: t.validate(t.content)
    token = secrets.token_hex(4)
    entries = []
    try:
        for t in targets:
            t.path.parent.mkdir(parents=True, exist_ok=True)
            stage = t.path.with_name(f"{t.path.name}.{token}.staged")
            entry = {"target": str(t.path), "staged": str(stage),
                     "backup": str(t.path.with_name(f"{t.path.name}.{token}.bak")) if t.path.exists() else None}
            entries.append(entry)
            stage.write_text(t.content, encoding="utf-8", newline="\n")
            t.validate(stage.read_text(encoding="utf-8"))
    except Exception:
        _discard(entries); raise
    _write_journal(paths, "backup", entries)
    try:
        for entry in entries:
            if entry["backup"]: shutil.copy2(entry["target"], entry["backup"])
    except Exception:
        _discard(entries); _clear_journal(paths); raise
    _write_journal(paths, "replace", entries)
    try:
        for entry in entries: replace(entry["staged"], entry["target"])
        _write_journal(paths, "committed", entries)
    except Exception:
        _rollback(entries)
        _write_journal(paths, "rolled-back", entries)
        _discard(entries); _clear_journal(paths)
        raise
    try:
        _discard(entries); _clear_journal(paths)
    except OSError:
        # Canonical set committed; journal enables later cleanup.
        pass

def _validated_journal(paths: AppPaths) -> tuple[str, list[dict]]:
    try:
        data = json.loads(paths.journal.read_text(encoding="utf-8"))
        if set(data) != {"phase", "entries"}: raise ValueError()
        phase, entries = data["phase"], data["entries"]
        if phase not in ("backup", "replace", "committed", "rolled-back") or not isinstance(entries, list):
            raise ValueError()
        allowed = {p.resolve() for p in (paths.inventory, paths.report, paths.catalog, paths.overrides)}
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"target", "staged", "backup"}: raise ValueError()
            t = Path(entry["target"])
            if (t.resolve() not in allowed and not map_output_allowed(paths, t)) or t.resolve() in seen: raise ValueError()
            seen.add(t.resolve())
            for field, suffix in (("staged", ".staged"), ("backup", ".bak")):
                if field == "backup" and entry[field] is None: continue
                p = Path(entry[field])
                if p.resolve().parent != t.resolve().parent or not p.name.startswith(t.name + ".") or not p.name.endswith(suffix):
                    raise ValueError()
        return phase, entries
    except (ValueError, TypeError, KeyError, OSError):
        raise RecoveryError(f"nevalidan journal: {paths.journal}; fajlovi nisu mijenjani") from None

def recover_if_needed(paths: AppPaths) -> bool:
    if not paths.journal.exists(): return False
    phase, entries = _validated_journal(paths)
    if phase == "replace":
        _rollback(entries)
        _write_journal(paths, "rolled-back", entries)
    _discard(entries)
    _clear_journal(paths)
    return True
