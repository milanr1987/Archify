# AI Workspace Atlas

Lokalni katalog projekata, skillova, pluginova, MCP konfiguracija i dokumenata.
Otvori `output/index.html` dvoklikom: pretraga, filteri, detalji i kopiranje putanja rade bez servera i interneta.

## Svakodnevna upotreba

Iz foldera Archify u PowerShellu:

```powershell
.\atlas.cmd refresh
.\atlas.cmd open
```

`refresh` osvježava `data/inventory.json`, `data/scan-report.md` i `output/index.html`.
`scan` pravi samo JSON i izvještaj; `build` obnavlja HTML iz postojećeg JSON-a.
`open` prvo oporavlja eventualno prekinutu objavu, zatim otvara katalog.
Exit kod 0 znači uspjeh, 2 djelimičan pregled sa upozorenjima, 1 grešku.

Na vrhu kataloga izaberi tip, profil ili pretraži ime/opis/putanju.
Pronađeni skill može imati više lokacija i profila; detalji pokazuju samostalno ili plugin porijeklo po lokaciji.
`/` fokusira pretragu, strelice prolaze kroz fokusiranu listu, Enter otvara detalje, Esc zatvara detalje/briše pretragu.
Za pronalaženje putanje koristi „Kopiraj putanju“; browser fallback označava tekst za Ctrl+C.

## Instalacija na drugom računaru

Potreban je Python 3.12+. Ako `python` nije dostupan, koristi punu putanju instaliranog interpretera.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\atlas.cmd init
.\atlas.cmd refresh
```

`init` kreira `config/sources.local.json` i ne prepisuje postojeći fajl. `atlas.cmd` uvijek koristi lokalni `.venv`.
Paket koristi editable instalaciju i namijenjen je radu iz ovog projektnog foldera; nije prenosiva wheel aplikacija.

## Dodavanje izvora

Uredi `config/sources.local.json`: `workspaceRoot` je apsolutan; relativni izvori se računaju od njega.

- `projectRoots`: roditeljski folderi čije direktne podfoldere treba pregledati.
- `extraProjects`: dodatni projekti bez manifesta.
- `skillRoots`: putanja, profil, label.
- `pluginRegistries`: installed_plugins.json putanja i profil.
- `mcpSources`: putanja, profil i format claude-json / mcp-json / codex-toml.
- `documents`: putanja i naslov dokumenta.

Config argument možeš zadati sa `refresh --config PATH`; relativni PATH se računa od Archify roota, ne cwd-a.
Podrazumijevani izvori uključuju `.agents`, tri Claude profila i `.codex/config.toml`.
Brojevi se računaju pri skeniranju. Nevalidan YAML frontmatter daje fallback naziv foldera i upozorenje, ali item ostaje u katalogu.

## Tačnost i privatnost

MCP „deklarisan u konfiguraciji“ ne znači da server radi. Skill na disku ne znači da je učitan u sesiji.
Skillovi se ne povezuju automatski sa projektima. Linkovi zadržavaju logičku putanju, cilj i profil.
Iz MCP objekata izvoze se samo dozvoljena opisna polja, bez args/env vrijednosti/URL/header sadržaja.
Skener ne izvršava projekte, skillove ili komande. Izvorni fajlovi se ne mijenjaju.
Katalog sadrži privatne putanje: output, data i sources.local.json se ne objavljuju i nisu u Gitu.

Izlazi se pripremaju u stagingu; journal i backupi omogućavaju oporavak poslije prekida procesa.
Lock fajl može ostati na disku i poslije završetka: vlasništvo određuje OS lock, ne postojanje fajla.
Oporavak ne garantuje disk durability poslije nestanka struje. Ne uklanjaj ručno recovery backup/journal tokom rada.

## Testovi

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Browser provjera:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
.\.venv\Scripts\python.exe -m playwright install chromium
$env:ATLAS_E2E = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests/e2e -p "test_*.py" -v
```

Testovi koriste lažne konfiguracije sa sentinel tajnama; browser test otvara file:// katalog i provjerava odsustvo mrežnih zahtjeva.
Screenshoti i performanse su u `output/e2e/`, stvarna verifikacija u `output/verification.md`.

## Obim

Faza 1 pravi katalog. Archify mape projekata, bilješke, server i cloud su odloženi.
Specifikacija: `docs/specs/2026-10-13-atlas-design.md`.
Plan: `docs/plans/2026-10-13-atlas-faza1.md`.

Ažurirano: 2026-10-13.
