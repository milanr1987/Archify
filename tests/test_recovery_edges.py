import json, os, subprocess, sys, unittest
from pathlib import Path
from helpers import TempDirTestCase, write
from atlas.paths import AppPaths
from atlas.writeout import atlas_lock, recover_if_needed, RecoveryError

class RecoveryEdgeTests(TempDirTestCase):
    def test_malformed_journal_has_no_side_effects(self):
        paths=AppPaths(self.tmp/'app')
        outside=write(self.tmp/'outside', 'KEEP')
        for phase in ('unknown', 'replace'):
            write(paths.journal,json.dumps({'phase':phase,'entries':[{'target':str(outside),
                        'staged':str(outside)+'.x.staged','backup':None}]}))
            with self.assertRaises(RecoveryError):recover_if_needed(paths)
            self.assertEqual(outside.read_text(),'KEEP')

    def test_missing_second_backup_does_not_partially_restore(self):
        paths=AppPaths(self.tmp/'app')
        entries=[]
        for n,p in enumerate((paths.inventory, paths.report)):
            write(p,'NEW')
            b=p.with_name(p.name+'.x.bak')
            if n==0:write(b,'OLD')
            entries.append({'target':str(p),'staged':str(p)+'.x.staged','backup':str(b)})
        write(paths.journal,json.dumps({'phase':'replace','entries':entries}))
        with self.assertRaises(RecoveryError):recover_if_needed(paths)
        self.assertEqual(paths.inventory.read_text(),'NEW')
        self.assertEqual(paths.report.read_text(),'NEW')

    def test_process_lock_survives_age_and_releases_on_termination(self):
        paths=AppPaths(self.tmp/'app')
        code="from pathlib import Path; from atlas.paths import AppPaths; from atlas.writeout import atlas_lock; import sys; p=AppPaths(Path(sys.argv[1])); ctx=atlas_lock(p); ctx.__enter__(); print('ready',flush=True); sys.stdin.read()"
        executable=getattr(sys, '_base_executable', sys.executable)
        env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
        child=subprocess.Popen([executable,'-c',code,str(paths.root)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'ready')
            probe="from pathlib import Path; from atlas.paths import AppPaths; from atlas.writeout import atlas_lock,LockBusy; import sys; p=AppPaths(Path(sys.argv[1])); ctx=atlas_lock(p); ctx.__enter__()"
            result=subprocess.run([executable,'-c',probe,str(paths.root)],env=env,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('LockBusy',result.stderr)
            child.terminate(); child.wait(timeout=10)
            with atlas_lock(paths):pass
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=10)
            for h in (child.stdin,child.stdout,child.stderr):h.close()
