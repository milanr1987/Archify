# Archify

**AI Workspace Atlas** je lokalni katalog projekata, skillova, pluginova, MCP konfiguracija, slash komandi, agenata, hookova i dokumenata, sa privatnim bilješkama i projektnim mapama.
Otvori `output/index.html` dvoklikom: pretraga, filteri, detalji i kopiranje putanja rade bez servera i interneta.

Repo sadrži kod, testove, setup i dokumentaciju. Svaki računar pravi svoj inventar; privatni podaci i lokalno okruženje se ne preuzimaju iz Gita. Za korištenje nisu potrebni pretplata, hosting ili API ključ. Internet je potreban za početno preuzimanje besplatnih zavisnosti.

## Svakodnevna upotreba

Najlakše: **dvoklik na prečicu „AI Atlas“ na Desktopu**. Ona osvježi katalog i otvori ga u browseru, bez terminala; ako nešto pođe po zlu, greška se pokaže u prozoru. Setup pravi prečicu sam; ručno: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\create_shortcut.ps1`.

Iz terminala, u folderu Archify:

```powershell
.\atlas.cmd refresh
.\atlas.cmd open
```

`refresh` osvježava `data/inventory.json`, `data/scan-report.md` i `output/index.html`.
`scan` pravi samo JSON i izvještaj; `build` obnavlja HTML iz postojećeg JSON-a.
`open` prvo oporavlja eventualno prekinutu objavu, zatim otvara katalog.
Exit kod 0 znači uspjeh, 2 djelimičan pregled sa upozorenjima, 1 grešku.
`scan` i `refresh` na početku ispisuju `Config: ...`, putanju configa koji je stvarno korišten.

Na vrhu kataloga izaberi tip, profil ili pretraži ime/opis/putanju.
Pronađeni skill može imati više lokacija i profila; detalji pokazuju samostalno ili plugin porijeklo po lokaciji.
`/` fokusira pretragu, strelice prolaze kroz fokusiranu listu, Enter otvara detalje, Esc zatvara detalje/briše pretragu.
Za pronalaženje putanje koristi „Kopiraj putanju“; browser fallback označava tekst za Ctrl+C.

## Instalacija na drugom računaru

Potreban je **Python 3.12+**, preporučeno **Python 3.13**, i browser. Git je potreban samo za kloniranje; možeš koristiti GitHub **Code → Download ZIP**, pa raspakovati folder.

Iz PowerShella:

```powershell
git clone https://github.com/milanr1987/Archify.git
cd Archify
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\atlas.cmd open
```

Ako koristiš ZIP, otvori PowerShell u raspakovanom folderu i pokreni posljednje dvije komande. ExecutionPolicy važi za taj poziv; skripta ne mijenja trajnu sistemsku politiku.

Setup pravi lokalni `.venv`, instalira paket, pravi config i generiše prvi katalog. Ako je Python na posebnoj lokaciji:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -PythonExe "C:\putanja\do\python.exe"
```

Alternativa bez setup skripte:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\atlas.cmd init
.\atlas.cmd refresh
.\atlas.cmd open
```

`init` kreira `config/sources.local.json` i ne prepisuje postojeći fajl. `atlas.cmd` uvijek koristi lokalni `.venv`.
Paket koristi editable instalaciju i namijenjen je radu iz ovog projektnog foldera; nije prenosiva wheel aplikacija.
Ne kopiraj `.venv` sa drugog računara: pokreni setup na svakom novom računaru. Nepostojeći Claude profili mogu dati upozorenja; uredi izvore koje stvarno koristiš, pa ponovi refresh.

## Lokalne bilješke (Faza 2)

U detaljima stavke katalog prikazuje njen ID. Koristi taj ID kroz CLI:

```powershell
.\atlas.cmd note ITEM_ID --text "Moja bilješka" --tag "korisno"
.\atlas.cmd note ITEM_ID --text "Novi tekst"
.\atlas.cmd note ITEM_ID --clear-tags
.\atlas.cmd note ITEM_ID --delete
```

`ITEM_ID` zamijeni stvarnim ID-jem stavke. `--tag` se može ponoviti i zamjenjuje oznake; bez tog argumenta postojeće oznake ostaju. `--clear-tags` ih uklanja. Brisanje se ne kombinuje sa drugim opcijama bilješke.

Bilješke su u privatnom `config/overrides.json`, izuzetom iz Gita. Komanda koristi postojeći inventar i objavljuje bilješke i novi katalog zajedno, uz lock i oporavak. Prethodno pokreni scan ili refresh. Tekst je ograničen na 10.000 znakova, oznake na 20 jedinstvenih vrijednosti po 100 znakova, fajl na 1 MiB.

Refresh čuva bilješke. Ako stavka nestane, bilješka ostaje sačuvana i CLI prijavljuje broj nepovezanih bilješki; ona ne predstavlja instalirani alat. Povratak istog ID-ja ponovo je povezuje. Browser samo prikazuje i pretražuje bilješke; ne uređuje ih niti ih čuva u localStorage. Ne stavljaj tajne u bilješke jer se njihov sadržaj ugrađuje u lokalni HTML.

## Dodavanje izvora

Uredi `config/sources.local.json`: `workspaceRoot` je apsolutan; relativni izvori se računaju od njega.

- `projectRoots`: folderi u kojima se traže projekti.
- `projectDepth`: koliko nivoa ispod njih (1–5; bez polja 1). Projekat je folder sa manifestom (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `.sln`, `.csproj`) ili sa `.git`, `CLAUDE.md`, `AGENTS.md`. U manifest projekat se ne ulazi dublje; u git/CLAUDE projekat se ulazi i nalaze se projekti u njemu.
- `extraProjects`: dodatni projekti bez ijednog markera.
- `skillRoots`: putanja, profil, label.
- `pluginRegistries`: installed_plugins.json putanja i profil.
- `mcpSources`: putanja, profil i format claude-json / mcp-json / codex-toml.
- `documents`: putanja i naslov dokumenta.

Config argument možeš zadati sa `refresh --config PATH`; relativni PATH se računa od Archify roota, ne cwd-a. Bez `--config` koristi se `config/sources.local.json`. Privatne config fajlove praviš ponovo na novom računaru.
Podrazumijevani izvori uključuju `.agents`, tri Claude profila i `.codex/config.toml`. `init` sam upisuje postojeće uobičajene foldere sa projektima (Desktop, Documents, OneDrive, WebstormProjects, source\repos i slične) sa `projectDepth: 3`, pa na novom računaru projekti dolaze bez ručnog upisivanja. Ako je nešto suvišno (npr. privremeni folder), dodaj njegovo ime u `excludeNames`.

U katalogu je „Grupiši isto ime“ uključeno: isti plugin, skill ili hook u više profila je jedan red sa svim profilima i oznakom ×N, a detalji pokazuju sve instance. Isključi ga za listu svake instance posebno.
Brojevi se računaju pri skeniranju. Ako YAML frontmatter nije strogo ispravan (npr. `Argumenti opciono: x` bez navodnika u `description`), Atlas ga čita blaže, kao Claude Code, i daje samo `info` upozorenje `lenient-frontmatter`. Tek kad ni to ne uspije, item dobija naziv foldera, prazan opis i `warn` upozorenje.

## Komande, agenti i hookovi (Faza 4)

Za svaki skill root koji se zove `skills` Atlas čita susjedne `commands/` i `agents/` (npr. `~\.claude\commands`), a iz pluginova `commands/`, `agents/` i `hooks/hooks.json`. Hookovi se čitaju iz `hooks` ključa u `claude-json` izvorima (`settings.json`). Novi config nije potreban.

Komanda iz podfoldera dobija namespace (`git/commit.md` → `git:commit`). Hook se prikazuje kao `Događaj · matcher`, sa brojem i tipom hookova. Sadržaj hooka (`command`, `prompt`, `url`, `headers`, `env`) se nikad ne čita u izlaz. Spec: `docs/specs/2026-10-14-atlas-faza4-komande-agenti-hookovi-design.md`.

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
$env:PYTHONUTF8 = "1"
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
.\.venv\Scripts\python.exe -m playwright install chromium
$env:ATLAS_E2E = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests/e2e -p "test_*.py" -v
```

Testovi koriste lažne konfiguracije sa sentinel tajnama; browser test otvara file:// katalog i provjerava odsustvo mrežnih zahtjeva.
Screenshoti i performanse su u `output/e2e/`, stvarna verifikacija u `output/verification.md`.

## Obim

Faza 1 pravi katalog; Faza 2 dodaje lokalne bilješke; Faza 3 lokalne Archify mape i praćenje njihove zastarjelosti; Faza 4 slash komande, agente i hookove. Server, cloud i browser uređivanje nisu uključeni.

## Lokalne mape (Faza 3)

Mape koriste zaseban open-source [Archify renderer](https://github.com/tt-a1i/archify), MIT licenca. Za mapiranje treba **Node.js 18+** na PATH-u ili Node iz lokalnog Playwright drivera.

Pinovana verzija je u `config/archify-upstream.json`, zajedno sa SHA-256 hashom ZIP arhive; instaler odbija arhivu čiji hash ne odgovara i tada ništa ne instalira. Lokalni vendor nije u Gitu. Na novom računaru ga pripremi:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -WithMaps
```

Za kompletne razvojne/browser zavisnosti i lokalni Node iz Playwrighta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -WithMaps -Development
```

Nema globalne instalacije skillova, npm instalacije ili API ključa. Potrebna su dva lokalna JSON fajla: analysis sa projektnim ID-jem/rootom, komponentama, vezama, relativnim source putanjama, linijama i SHA-256 hashovima; i native Archify JSON prema shemi iz vendor/archify/archify/schemas/. Demo inputs nastaju tek poslije pripreme demonstracije, ne dolaze iz privatnog data foldera.

U detaljima projekta vidiš naslov mape, relativni link i status: Aktuelna, Zastarjela ili Neprovjerena. Status poredi lokalne SHA-256 hashove relevantnih source fajlova sa sačuvanom analizom. Promjena ili brisanje fajla daje Zastarjela; nepotpuna/nečitljiva evidencija daje Neprovjerena. To nije provjera javnog Git commita.

```powershell
.\atlas.cmd map PROJECT_ID --analysis data/moja-analiza.json --input data/moja-mapa.json --slug moj-projekat --type workflow
```

PROJECT_ID je ID projektnog itema iz detalja kataloga. Analiza mora navesti isti ID i stvarnu projektnu lokaciju. Native JSON mora pratiti lokalnu upstream Archify shemu. Podržani tipovi su workflow i architecture. Komanda validira i renderuje u stagingu; tek nakon uspjeha objavljuje HTML, oba JSON izvora, registar i katalog zajedno. Greška čuva stare izlaze.

Upstream je lokalno u vendor/archify, sa verzijom/commitom u data/archify-version.json i MIT licencom. Koristi se postojeći lokalni Node iz Playwright drivera ili Node na PATH-u. Nema globalne instalacije ili update provjere. Upstream može zahtijevati dodatnu sandbox dozvolu da provjeri Windows putanje; nikad ne zaobilaziti njegovu provjeru.

Mapa projekta se opisuje u `config/maps/<slug>.json` (privatno, van Gita jer je repo javan): projekt iz kataloga, naslov, trake (lanes) i komponente sa fajlom i tekstom koji označava liniju dokaza. Pravi se i obnavlja iz Archify foldera, poslije `refresh`:

```powershell
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe tools\make_map.py creative-forge
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe tools\make_map.py --all
```

Alat čita izvore projekta, upisuje linije i SHA-256 hashove u `data/map-input/<slug>/analysis.json`, objavljuje mapu i pokreće upstream `finalize`. Kad se projekat promijeni, mapa u katalogu postaje „Zastarjela“; ponovi komandu. Polja opisa i primjer su u `docs/specs/2026-10-14-atlas-faza5-pronalazenje-grupisanje-pokretanje-design.md` i `tests/test_mapspec.py`. Isporučena mapa atlas-demo ostaje lokalna demonstracija toka Atlasa. Viewer kontrole upstream mape koriste engleski fallback; naslovi našeg kataloga i mapa su na BCS-u.

## Struktura projekta

- src/atlas/: CLI, skeneri, bilješke, mape i offline UI.
- tests/: unit, integration i browser testovi.
- docs/specs/ i docs/plans/: specifikacije i planovi faza 1–5.
- .github/workflows/ci.yml: testovi na svaki push (Windows, uključujući browser testove).
- config/sources.example.json: primjer izvora za vlastiti računar.
- setup.ps1 i atlas.cmd: instalacija i svakodnevni rad.
- tools/: lokalna instalacija renderera i provjere.

## Privatnost i prenos

U Git ne ulaze privatni configi, bilješke, data/, output/, .venv/, browseri, vendor/ ili .tools/. Svaki računar pravi svoj inventar. Bilješke prenesi zasebno ako želiš; identitet stavke zavisi od lokalne putanje.

## Ako nešto ne radi

- Python nije pronađen: koristi -PythonExe sa punom putanjom do instaliranog Pythona.
- Prazan katalog/upozorenja: podesi stvarne izvore u lokalnom configu.
- Nema .venv: pokreni setup, bez kopiranja starog okruženja.
- Mape: provjeri Node i lokalni vendor; ne uklanjaj upstream path-safety provjere.
- GitHub prijava je potrebna za push/privatni clone, ne za lokalno korištenje.

Za novo skeniranje pokreni atlas.cmd refresh, a za otvaranje atlas.cmd open.
