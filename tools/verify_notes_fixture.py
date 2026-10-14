"""Generate a controlled notes fixture without scanning real configuration."""
from pathlib import Path
from atlas.catalog import render_catalog
from atlas.identity import make_id
from atlas.model import Inventory, Item, Location, SCHEMA_VERSION, inventory_hash
from atlas.overlay import Overlay, Note

root = Path(__file__).resolve().parents[1]
identity = make_id('skill', 'notes-fixture')
inv = Inventory(SCHEMA_VERSION, '2026-10-13T12:00:00+02:00', [
    Item(identity, 'skill', 'fixture-tool', 'Test', [Location('C:\\fixture\\tool')])
], [], [], False)
overlay = Overlay({identity: Note('</script><img src=x onerror=alert(1)> moja bilješka', ['Đurđevak'])})
output = root / 'output' / 'notes-verification.html'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(render_catalog(inv, inventory_hash(inv), overlay), encoding='utf-8')
print(output)
