import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

from helpers import TempDirTestCase, write

_SPEC = importlib.util.spec_from_file_location(
    "install_archify", Path(__file__).resolve().parents[1] / "tools/install_archify.py")
install_archify = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(install_archify)


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("archify-abc/archify/bin/archify.mjs", "console.log('ok')\n")
    return buffer.getvalue()


class InstallArchifyTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "app"
        self.payload = _zip_bytes()

    def spec(self, sha):
        write(self.root / "config/archify-upstream.json", json.dumps(
            {"repository": "x", "commit": "abc", "version": "1", "license": "MIT", "archiveSha256": sha}))

    def fetch(self, url, destination):
        Path(destination).write_bytes(self.payload)

    def test_matching_hash_installs(self):
        self.spec(hashlib.sha256(self.payload).hexdigest())
        install_archify.install(self.root, fetch=self.fetch)
        self.assertTrue((self.root / "vendor/archify/archify/bin/archify.mjs").is_file())

    def test_hash_mismatch_installs_nothing(self):
        self.spec("0" * 64)
        with self.assertRaises(ValueError):
            install_archify.install(self.root, fetch=self.fetch)
        self.assertFalse((self.root / "vendor/archify").exists())

    def test_missing_hash_is_rejected_before_download(self):
        self.spec(None)
        calls = []
        with self.assertRaises(ValueError):
            install_archify.install(self.root, fetch=lambda *a: calls.append(a))
        self.assertEqual(calls, [])
