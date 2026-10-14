# Faza 5: pronalaženje projekata, grupisanje, pokretanje bez terminala

**Datum:** 2026-10-14
**Status:** odobreno u razgovoru ("uradi sve do 7").

## Pronalaženje projekata

- Novo opciono polje `projectDepth` (1–5, podrazumijevano 1 radi kompatibilnosti). Skener ide toliko nivoa ispod svakog `projectRoots` foldera; skriveni folderi i `excludeNames` se preskaču, uz zaštitu od ciklusa linkova.
- Folder sa manifestom (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `.sln`, `.csproj`) je projekat i skener ne ide dublje (workspace paketi nisu zasebni projekti).
- Folder sa `.git`, `CLAUDE.md` ili `AGENTS.md` je projekat, a skener nastavlja unutra: tako radni repo i projekti u njemu dolaze zajedno. Unutar takvog projekta samo `.git` ili manifest označava novi projekat; `CLAUDE.md` u podfolderu je dokumentacija.
- `init` pravi config sa postojećim uobičajenim folderima (Desktop, Documents, OneDrive, WebstormProjects, PycharmProjects, IdeaProjects, source/repos, Projects, code, dev, repos, GitHub) i `projectDepth: 3`. Folder iznad Archify ide kao `.` samo ako nije već unutar nekog od njih.
- Revizija 2026-10-14 (javni repo): `init` ne pretpostavlja ničije profile. Upisuje samo izvore koji postoje: `~/.agents/skills`, svaki `~/.claude` i `~/.claude-<ime>` folder kao profil `claude` odnosno `<ime>` (skills, plugin registar, `settings.json`, `.claude.json`; za `claude` profil `~/.claude.json`) i `~/.codex/config.toml`. `extraProjects` i `documents` su prazni. Postojeći lokalni config se ne prepisuje.
- `config/sources.current.json` se više ne čita; jedini podrazumijevani config je `sources.local.json`.

## Grupisanje u katalogu

Samo prikaz; ID-jevi, inventar i bilješke se ne mijenjaju. Prekidač „Grupiši isto ime“ (uključen) spaja stavke iste `duplicate_group` u jedan red sa unijom profila i oznakom `×N`. Detalji pokazuju „Sve instance (N)“ sa profilom, verzijom/scope/matcherom i porijeklom svake instance. „Očisti filtere“ ne dira prekidač jer je to izbor prikaza, ne filter.

## Pokretanje bez terminala

`atlas launch` radi refresh pa otvara katalog. Pokreće se kroz `pythonw.exe` (bez konzole); greška se prikazuje u Windows prozoru sa porukom refresh-a. `tools/create_shortcut.ps1` pravi prečicu „AI Atlas“ na Desktopu; `setup.ps1` je pravi podrazumijevano (`-NoShortcut` za preskakanje).

## Mape

`src/atlas/mapspec.py` pretvara opis mape u analysis i native Archify JSON; linije i SHA-256 računa iz stvarnih izvora, uz postojeća pravila (`..`, skriveni i „secret/token/auth/credentials“ putanje odbijene). Opisi su u `config/maps/<slug>.json`, van Gita jer je repo javan; `tools/make_map.py <slug>|--all` objavljuje i pokreće upstream `finalize`.

## CI

`.github/workflows/ci.yml`: Windows, Python 3.13, pun suite sa browser testovima. Granica p95 pretrage na CI-ju je `ATLAS_PERF_P95_MS=200`; spec cilj od 50 ms ostaje za lokalni računar.
