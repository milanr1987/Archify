"""Jedan samostalan HTML katalog sa ugrađenim inventarom."""
from __future__ import annotations

import json

from atlas.model import Inventory, inventory_from_dict, inventory_hash, inventory_to_dict
from atlas.paths import UI_DIR

DATA_OPEN = '<script type="application/json" id="atlas-data">'
CSP = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:"


def embed_json(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def render_catalog(inv: Inventory, inv_hash: str) -> str:
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
    return html.replace("{{DATA}}", embed_json(inventory_to_dict(inv)))


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
