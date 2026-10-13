"""Čitljiv Markdown izvještaj o skeniranju."""
from __future__ import annotations

from collections import Counter, defaultdict

from atlas.inventory import ScanOutcome
from atlas.model import KINDS

SOURCE_STATUS = {"read": "pročitan", "missing": "nedostaje", "error": "greška"}


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_report(outcome: ScanOutcome, inv_hash: str) -> str:
    inv = outcome.inventory
    lines = [
        "# Izvještaj skeniranja",
        "",
        f"- Vrijeme: {inv.scanned_at}",
        f"- Trajanje: {outcome.duration_s:.1f} s",
        f"- Status: {'djelimičan pregled' if inv.partial else 'kompletan pregled'}",
        f"- Hash inventara: `{inv_hash}`",
        "",
        "## Po tipu",
        "",
        "| Tip | Broj |",
        "|---|---|",
    ]
    counts = Counter(i.kind for i in inv.items)
    lines += [f"| {kind} | {counts.get(kind, 0)} |" for kind in KINDS]
    profile_counts: Counter[str] = Counter()
    for item in inv.items:
        for profile in {l.profile for l in item.locations if l.profile}:
            profile_counts[profile] += 1
    lines += ["", "## Po profilu", "", "| Profil | Stavki |", "|---|---|"]
    lines += [f"| {p} | {n} |" for p, n in sorted(profile_counts.items())]
    lines += ["", "## Izvori", "", "| Vrsta | Putanja | Status |", "|---|---|---|"]
    lines += [f"| {s.kind} | {_cell(s.path)} | {SOURCE_STATUS.get(s.status, s.status)} |" for s in outcome.sources]
    lines += ["", "## Upozorenja", ""]
    if not inv.warnings:
        lines.append("Nema upozorenja.")
    by_code: dict[str, list] = defaultdict(list)
    for warning in inv.warnings:
        by_code[warning.code].append(warning)
    for code in sorted(by_code):
        lines += [f"### {code} ({len(by_code[code])})", ""]
        lines += [f"- [{w.severity}] {w.source}: {w.message}" for w in by_code[code]]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
