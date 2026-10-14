"""Install the pinned MIT Archify package locally, without global settings."""
from __future__ import annotations
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path


def install(root: Path) -> None:
    spec = json.loads((root/'config/archify-upstream.json').read_text(encoding='utf-8'))
    target = root/'vendor/archify'
    if (target/'archify/bin/archify.mjs').exists():
        print('Lokalni Archify vec postoji; ne prepisujem ga.')
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    url = 'https://codeload.github.com/tt-a1i/archify/zip/'+spec['commit']
    with tempfile.TemporaryDirectory(prefix='archify-install-',dir=target.parent) as tmp:
        stage = Path(tmp)
        archive = stage/'source.zip'
        urllib.request.urlretrieve(url,archive)
        unpacked = stage/'unpacked'
        unpacked.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            prefix = bundle.namelist()[0].split('/')[0]+'/'
            for entry in bundle.infolist():
                relative = Path(entry.filename.removeprefix(prefix))
                destination = (unpacked/relative).resolve()
                if not destination.is_relative_to(unpacked.resolve()):
                    raise ValueError('Neispravna putanja u upstream arhivi')
                if entry.is_dir():
                    destination.mkdir(parents=True,exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    destination.write_bytes(bundle.read(entry))
        if not (unpacked/'archify/bin/archify.mjs').is_file():
            raise ValueError('Upstream arhiva nema ocekivani CLI')
        if target.exists():
            raise ValueError('vendor/archify postoji ali nema CLI; provjeri folder prije nastavka')
        shutil.move(str(unpacked),str(target))
    data = root/'data'
    data.mkdir(exist_ok=True)
    (data/'archify-version.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
    print('Instaliran lokalni Archify '+spec['version'])


if __name__ == '__main__':
    install(Path(__file__).resolve().parents[1])
