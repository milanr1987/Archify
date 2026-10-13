import json
import os
import time
from pathlib import Path
from unittest import mock

from helpers import TempDirTestCase, write

from atlas import writeout
from atlas.paths import AppPaths
from atlas.writeout import LockBusy, Target, atlas_lock, publish, recover_if_needed


class _Crash(BaseException):
    """Simulira smrt procesa: ne hvata se kao obična greška."""


def ok(_text):
    return None


class PublishTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.paths = AppPaths(self.tmp / "app")
        self.a = self.paths.inventory
        self.b = self.paths.report
        self.c = self.paths.catalog

    def leftovers(self):
        found = []
        for folder in (self.paths.data_dir, self.paths.output_dir):
            if folder.exists():
                found += [p.name for p in folder.iterdir() if p.name.endswith((".staged", ".bak"))]
        if self.paths.journal.exists():
            found.append(self.paths.journal.name)
        return found

    def old_set(self):
        for path, text in ((self.a, "A-old"), (self.b, "B-old"), (self.c, "C-old")):
            write(path, text)

    def contents(self):
        return [p.read_text(encoding="utf-8") if p.exists() else None for p in (self.a, self.b, self.c)]

    def test_publish_writes_all_and_cleans_up(self):
        publish(self.paths, [Target(self.a, "A", ok), Target(self.c, "C", ok)])
        self.assertEqual(self.a.read_text(encoding="utf-8"), "A")
        self.assertEqual(self.c.read_text(encoding="utf-8"), "C")
        self.assertEqual(self.leftovers(), [])

    def test_validation_failure_changes_nothing(self):
        self.old_set()

        def reject(_text):
            raise ValueError("neispravno")

        with self.assertRaises(ValueError):
            publish(self.paths, [Target(self.a, "A", ok), Target(self.b, "B", reject)])
        self.assertEqual(self.contents(), ["A-old", "B-old", "C-old"])
        self.assertEqual(self.leftovers(), [])

    def test_second_replace_failure_restores_previous_set(self):
        write(self.a, "A-old")
        write(self.b, "B-old")
        calls = {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("disk")
            os.replace(src, dst)

        with self.assertRaises(OSError):
            publish(self.paths, [Target(self.a, "A", ok), Target(self.b, "B", ok), Target(self.c, "C", ok)],
                    replace=flaky)
        self.assertEqual(self.contents(), ["A-old", "B-old", None])
        self.assertEqual(self.leftovers(), [])

    def test_recover_after_crash_during_replace(self):
        self.old_set()
        calls = {"n": 0}

        def dying(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:
                raise _Crash()
            os.replace(src, dst)

        with mock.patch.object(writeout, "_rollback", side_effect=_Crash()):
            with self.assertRaises(_Crash):
                publish(self.paths, [Target(self.a, "A", ok), Target(self.b, "B", ok), Target(self.c, "C", ok)],
                        replace=dying)
        self.assertTrue(self.paths.journal.exists())
        self.assertEqual(self.a.read_text(encoding="utf-8"), "A")
        self.assertTrue(recover_if_needed(self.paths))
        self.assertEqual(self.contents(), ["A-old", "B-old", "C-old"])
        self.assertEqual(self.leftovers(), [])

    def test_recover_in_backup_phase_keeps_targets(self):
        self.old_set()
        staged = write(self.a.with_name("inventory.json.x1.staged"), "A-new")
        partial_bak = write(self.a.with_name("inventory.json.x1.bak"), "A-o")
        write(self.paths.journal, json.dumps({"phase": "backup", "entries": [
            {"target": str(self.a), "staged": str(staged), "backup": str(partial_bak)}]}))
        self.assertTrue(recover_if_needed(self.paths))
        self.assertEqual(self.contents(), ["A-old", "B-old", "C-old"])
        self.assertEqual(self.leftovers(), [])

    def test_no_journal_means_no_recovery(self):
        self.assertFalse(recover_if_needed(self.paths))


    def test_committed_cleanup_interruption_keeps_all_new_outputs(self):
        self.old_set()
        entries = []
        for n, path in enumerate((self.a, self.b, self.c)):
            backup = path.with_name(path.name + ".x1.bak")
            if n != 0:
                write(backup, path.read_text(encoding="utf-8"))
            write(path, "NEW")
            entries.append({"target": str(path), "staged": str(path.with_name(path.name + ".x1.staged")),
                            "backup": str(backup)})
        write(self.paths.journal, json.dumps({"phase": "committed", "entries": entries}))
        self.assertTrue(recover_if_needed(self.paths))
        self.assertEqual(self.contents(), ["NEW", "NEW", "NEW"])
        self.assertEqual(self.leftovers(), [])

    def test_replace_recovery_is_repeatable_after_interruption(self):
        self.old_set()
        entries = []
        for path in (self.a, self.b, self.c):
            backup = write(path.with_name(path.name + ".x1.bak"), path.read_text(encoding="utf-8"))
            write(path, "NEW")
            entries.append({"target": str(path), "staged": str(path.with_name(path.name + ".x1.staged")),
                            "backup": str(backup)})
        write(self.paths.journal, json.dumps({"phase": "replace", "entries": entries}))
        rollback = writeout._rollback
        def interrupted(current):
            rollback(current[:1])
            raise _Crash()
        with mock.patch.object(writeout, "_rollback", side_effect=interrupted):
            with self.assertRaises(_Crash):
                recover_if_needed(self.paths)
        self.assertTrue(Path(entries[0]["backup"]).exists())
        self.assertTrue(recover_if_needed(self.paths))
        self.assertEqual(self.contents(), ["A-old", "B-old", "C-old"])
        self.assertEqual(self.leftovers(), [])


class LockTests(TempDirTestCase):
    def test_second_lock_is_refused(self):
        paths = AppPaths(self.tmp / "app")
        with atlas_lock(paths):
            with self.assertRaises(LockBusy):
                with atlas_lock(paths):
                    pass
        self.assertTrue(paths.lock.exists())
        with atlas_lock(paths):
            pass  # isti persistent lock fajl ponovo se zaključava

    def test_old_active_lock_is_not_stolen(self):
        paths = AppPaths(self.tmp / "app")
        with atlas_lock(paths):
            old = time.time() - 24 * 60 * 60
            os.utime(paths.lock, (old, old))
            with self.assertRaises(LockBusy):
                with atlas_lock(paths):
                    pass

    def test_existing_file_without_os_lock_is_reusable(self):
        paths = AppPaths(self.tmp / "app")
        write(paths.lock, "0")
        with atlas_lock(paths):
            self.assertTrue(paths.lock.exists())
