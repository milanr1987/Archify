"""Tri izlaza aplikacije kao Target objekti sa validacijom."""
from __future__ import annotations

import json

from atlas.catalog import render_catalog, validate_catalog
from atlas.inventory import ScanOutcome
from atlas.model import Inventory, canonical_json, inventory_from_dict, inventory_hash
from atlas.paths import AppPaths
from atlas.report import render_report
from atlas.writeout import Target


def inventory_target(paths: AppPaths, inv: Inventory) -> Target:
    expected = inventory_hash(inv)

    def check(text: str) -> None:
        if inventory_hash(inventory_from_dict(json.loads(text))) != expected:
            raise ValueError("inventar se promijenio pri serijalizaciji")

    return Target(paths.inventory, canonical_json(inv) + "\n", check)


def report_target(paths: AppPaths, outcome: ScanOutcome, inv_hash: str) -> Target:
    def check(text: str) -> None:
        if f"Hash inventara: `{inv_hash}`" not in text:
            raise ValueError("izvještaj nema hash inventara")

    return Target(paths.report, render_report(outcome, inv_hash), check)


def catalog_target(paths: AppPaths, inv: Inventory, inv_hash: str) -> Target:
    return Target(paths.catalog, render_catalog(inv, inv_hash), lambda text: validate_catalog(text, inv_hash))
