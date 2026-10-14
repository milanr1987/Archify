"""Čitljiv Markdown izvještaj o skeniranju."""
from __future__ import annotations

from collections import Counter, defaultdict

from atlas.inventory import ScanOutcome
from atlas.model import KINDS
from atlas.state import skill_groups, hook_matrix, activity_key

SOURCE_STATUS = {"read": "pročitan", "missing": "nedostaje", "error": "greška"}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace('\n',' ').replace('\r',' ')


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
    groups=[g for g in skill_groups(inv.items) if g['multiple']]
    statuses=Counter(g['status'] for g in groups)
    lines += ['', '## Neusklađenost skillova', '', '| Status | Grupa |','|---|---|']
    lines += [f'| {status} | {statuses[status]} |' for status in ('isti','razlikuje se','nepoznato')]
    lines += ['', '### Vlastiti skillovi različitog sadržaja', '']
    for group in groups:
        if group['ownDrift']:
            lines.append(f"- {_cell(group['name'])}")
            for cohort in group['variants']:
                if cohort['cohort'][0]=='own':
                    for loc in cohort['locations']:
                        lines.append(f"  - `{loc['hash'][:12]}` · {_cell(loc['profile'])} · {_cell(loc['path'])}")
    profiles=sorted(set(inv.profiles)|{l.profile for i in inv.items for l in i.locations if l.profile})
    lines += ['', '## Matrica hookova', '', 'Prazno znači da deklaracija nije pronađena u snimku; pogledaj upozorenja izvora.', '', '| Event / matcher | '+' | '.join(_cell(p) for p in profiles)+' |', '|---|'+'---|'*len(profiles)]
    for row in hook_matrix(inv.items,profiles):
        cells=[]
        for profile in profiles:
            entries=row['cells'][profile]
            cells.append('; '.join(f"{e['hookCount']} · {', '.join(e['hookTypes'])} · {e['origin']}" for e in entries) if entries else 'nema u ovom profilu')
        lines.append('| '+_cell(row['event']+' / '+row['matcher'])+' | '+' | '.join(_cell(c) for c in cells)+' |')
    lines += ['', '## Projekti po zadnjoj aktivnosti', '', '| Projekat | Commit | Sesija | Grana | Nekomitovano |','|---|---|---|---|---|']
    projects=sorted((i for i in inv.items if i.kind=='project'),key=lambda i:(-activity_key(i),i.name.lower(),i.id))
    for item in projects:
        lines.append('| '+' | '.join(_cell(str(v)) for v in [item.name,*[item.metadata.get(k,'unknown') for k in ('lastCommitAt','lastSessionAt','branch','dirtyCount')]])+' |')
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
