"""Jedan samostalan HTML katalog sa ugrađenim inventarom."""
from __future__ import annotations

import json

from atlas.model import Inventory, inventory_from_dict, inventory_hash, inventory_to_dict
from atlas.paths import UI_DIR
from atlas.overlay import Overlay, overlay_to_dict, overlay_from_dict
from atlas.maps import validate_catalog_maps

DATA_OPEN = '<script type="application/json" id="atlas-data">'
CSP = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:"


def embed_json(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def render_catalog(inv: Inventory, inv_hash: str, overlay: Overlay | None = None, maps: list[dict] | None = None) -> str:
    template = (UI_DIR / "template.html").read_text(encoding="utf-8")
    css = (UI_DIR / "styles.css").read_text(encoding="utf-8")
    js = (UI_DIR / "app.js").read_text(encoding="utf-8")
    if "</style" in css.lower() or "</script" in js.lower():
        raise ValueError("UI izvori ne smiju zatvarati style/script element")
    html = (
        template.replace("{{CSP}}", CSP)
        .replace("{{HASH}}", inv_hash)
        .replace("{{STYLES}}", css)
        .replace("{{SCRIPT}}", js)
    )
    # Replace data last so user text cannot be treated as a template placeholder.
    return _embed_payloads(html, inv, overlay, maps or [])


def _embed_payloads(html: str, inv: Inventory, overlay: Overlay | None, maps: list[dict]) -> str:
    inventory_payload = embed_json(inventory_to_dict(inv))
    overlay_payload = embed_json(overlay_to_dict(overlay if overlay is not None else Overlay({})))
    map_payload = embed_json(validate_catalog_maps(maps))
    # Both placeholders replaced in a single pass: text containing placeholders stays literal.
    import re
    payloads = {'DATA':inventory_payload, 'OVERLAY':overlay_payload, 'MAPS':map_payload}
    return re.sub(r'\{\{(DATA|OVERLAY|MAPS)\}\}', lambda m: payloads[m[1]], html)


def validate_catalog(html: str, inv_hash: str) -> None:
    if f'<meta name="atlas-inventory-hash" content="{inv_hash}">' not in html:
        raise ValueError("katalog nema očekivani hash inventara")
    start = html.find(DATA_OPEN)
    if start == -1:
        raise ValueError("katalog nema ugrađen inventar")
    start += len(DATA_OPEN)
    end = html.find("</script>", start)
    inv = inventory_from_dict(json.loads(html[start:end]))
    if inventory_hash(inv) != inv_hash:
        raise ValueError("ugrađeni inventar ne odgovara hashu")
    marker = '<script type="application/json" id="atlas-overlay">'
    start = html.find(marker)
    if start == -1:
        raise ValueError('katalog nema biljeske')
    start += len(marker)
    end = html.find('</script>', start)
    overlay_from_dict(json.loads(html[start:end]))
    marker = '<script type="application/json" id="atlas-maps">'
    start = html.find(marker)
    if start == -1:
        raise ValueError('katalog nema map registar')
    start += len(marker)
    end = html.find('</script>', start)
    validate_catalog_maps(json.loads(html[start:end]))
