# AI Workspace Atlas: dizajn (Faza 1, kompletna aplikacija)

**Datum:** 2026-10-13
**Status:** dizajn odobren u razgovoru; čeka pregled ovog dokumenta.
**Odnos prema `plan-izrade-ai-workspace-atlas.md`:** taj dokument ostaje referenca za kasnije faze (bilješke, Archify mape). Za Fazu 1 važi ovaj spec. Razlike su navedene u sekciji 11.

## 1. Cilj i uspjeh

Milan dvoklikom otvori `output/index.html` i za manje od 10 sekundi nađe:

1. gdje je skill X, u kojem profilu je dostupan i da li je samostalan ili dolazi iz plugina;
2. gdje je deklarisan MCP server Y (profil, scope, transport);
3. koji plugin je instaliran u kojem profilu i koja verzija;
4. koji projekat postoji u radnom folderu, kako se zove njegova komanda i gdje mu je README;
5. koje stavke postoje na više mjesta (duplikati i linkovi).

Katalog je snimak diska u trenutku skeniranja. Ne tvrdi da je MCP server pokrenut, da je skill učitan u sesiji ni da se projekat koristi.

**Završeno znači:** svi kriterijumi iz sekcije 10 su ispunjeni i zapisani u `output/verification.md`, sa komandama i rezultatima.

## 2. Ograničenja

- Sav kod i izlaz ostaju u `Twiter_claude\Archify`. Skenirani fajlovi se samo čitaju.
- Python 3.12+ (lokalno 3.13.3), standardna biblioteka + PyYAML (`yaml.safe_load`). TOML preko ugrađenog `tomllib`.
- Bez mreže pri radu. Katalog ne učitava ništa izvana.
- Ništa iz skeniranih izvora se ne izvršava.
- Windows putanje s razmacima i dijakritikom moraju raditi.
- UI i README na BCS-u.
- Bez tajni u izlazu (sekcija 6).
- `Archify/` dobija vlastiti git repo; roditeljski repo se ne dira.

## 3. Izvori (stanje na disku 2026-10-13)

| Izvor | Lokacija | Format |
|---|---|---|
| Projekti | direktni podfolderi `Twiter_claude` sa markerom + eksplicitni `extraProjects` | `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `*.sln`, `*.csproj` |
| Skillovi | `~\.agents\skills` (132), `~\.claude\skills` (97, 9 linkova), `~\.claude-max\skills` (111, 3 linka), `~\.claude-pro\skills` (link na `.claude-max\skills`) | `<folder>\SKILL.md` sa YAML frontmatterom |
| Pluginovi | `~\.claude*\plugins\installed_plugins.json` (10 / 13 / 13) | `{version, plugins: {"ime@marketplace": [ {scope, installPath, version, installedAt, lastUpdated, gitCommitSha} ]}}` |
| Plugin skillovi | `<installPath>\skills\<ime>\SKILL.md` | isto kao skillovi |
| MCP, Claude | `~\.claude.json`, `~\.claude-max\.claude.json`, `~\.claude-pro\.claude.json`, `~\.claude*\settings.json` | `mcpServers` na vrhu (scope `user`) i `projects[<putanja>].mcpServers` (scope `project`) |
| MCP, projekat | `.mcp.json` u korijenu projekta, ako postoji | `mcpServers` (scope `project`) |
| MCP, Codex | `~\.codex\config.toml` (11 servera) | `[mcp_servers.<ime>]` sa `command`/`args`/`env`/`env_vars` ili `url` |
| Dokumenti | eksplicitna lista + README/AGENTS/CLAUDE u korijenu svakog projekta | putanja i naslov (prvi `# ` red ili ime fajla) |

`skill-evals` nema marker, pa ulazi preko `extraProjects`. Folderi poput `drafts`, `ruben` ili `raw` nisu projekti i ne skeniraju se.

## 4. Konfiguracija

`config/sources.example.json` je u gitu, sa generičkim putanjama. `atlas init` iz njega pravi `config/sources.local.json` sa Milanovim stvarnim putanjama, samo ako taj fajl ne postoji. Lokalni fajl je u `.gitignore`.

```json
{
  "workspaceRoot": "C:\\Users\\Milan\\Desktop\\desktop 2.4.2021\\Twiter_claude",
  "projectRoots": ["."],
  "extraProjects": ["skill-evals"],
  "excludeNames": ["Archify", "node_modules", ".git", ".venv", "venv", "dist", "build", "output", "graphify-out", "__pycache__"],
  "skillRoots": [
    {"path": "C:\\Users\\Milan\\.agents\\skills", "profile": "agents", "label": ".agents"},
    {"path": "C:\\Users\\Milan\\.claude\\skills", "profile": "claude", "label": ".claude"},
    {"path": "C:\\Users\\Milan\\.claude-max\\skills", "profile": "max", "label": ".claude-max"},
    {"path": "C:\\Users\\Milan\\.claude-pro\\skills", "profile": "pro", "label": ".claude-pro"}
  ],
  "pluginRegistries": [
    {"path": "C:\\Users\\Milan\\.claude\\plugins\\installed_plugins.json", "profile": "claude"},
    {"path": "C:\\Users\\Milan\\.claude-max\\plugins\\installed_plugins.json", "profile": "max"},
    {"path": "C:\\Users\\Milan\\.claude-pro\\plugins\\installed_plugins.json", "profile": "pro"}
  ],
  "mcpSources": [
    {"path": "C:\\Users\\Milan\\.claude.json", "format": "claude-json", "profile": "claude"},
    {"path": "C:\\Users\\Milan\\.claude\\settings.json", "format": "claude-json", "profile": "claude"},
    {"path": "C:\\Users\\Milan\\.claude-max\\.claude.json", "format": "claude-json", "profile": "max"},
    {"path": "C:\\Users\\Milan\\.claude-max\\settings.json", "format": "claude-json", "profile": "max"},
    {"path": "C:\\Users\\Milan\\.claude-pro\\.claude.json", "format": "claude-json", "profile": "pro"},
    {"path": "C:\\Users\\Milan\\.codex\\config.toml", "format": "codex-toml", "profile": "codex"}
  ],
  "documents": [
    {"path": "my-claude-system.md", "title": "Moj Claude sistem"},
    {"path": "claude-skillovi-i-plugini-inventar.md", "title": "Inventar skillova i pluginova (2026-09-07)"},
    {"path": "claude-ai-engineer-playbook.md", "title": "AI engineer playbook"},
    {"path": "MEDIUM_CLAUDE\\INDEX.md", "title": "Medium indeks"}
  ]
}
```

Pravila:
- Relativne putanje se računaju od `workspaceRoot`, nikad od trenutnog foldera terminala.
- Nepostojeći pojedinačni izvor daje upozorenje, a ne grešku.
- Nevalidan config (nije JSON, fali obavezno polje, nepoznat `format`) prekida rad sa exit kodom 1 prije bilo kakvog pisanja.
- `.mcp.json` projekata se ne navodi ručno. Skener projekata ga sam prijavljuje MCP skeneru.

## 5. Model podataka

`src/atlas/model.py`, `dataclasses`:

```python
Kind = Literal["project", "skill", "plugin", "mcp", "document"]
Evidence = Literal["observed", "documented"]

@dataclass
class Location:
    path: str            # putanja kako je pronađena (za prikaz)
    profile: str | None
    via_link: bool       # pronađeno kroz symlink/junction
    link_target: str | None

@dataclass
class Item:
    id: str
    kind: Kind
    name: str
    description: str
    locations: list[Location]
    evidence: Evidence
    origin: str | None        # skill: "standalone" ili "plugin:<ime@marketplace>"
    metadata: dict[str, str | list[str]]
    duplicate_group: str | None   # "skill:firecrawl" ako isto ime ima više različitih itema

@dataclass
class Relation:
    source: str; target: str
    type: Literal["contains", "documented-by", "configured-for"]

@dataclass
class Warning:
    severity: Literal["info", "warn"]
    code: str; source: str; message: str

@dataclass
class Inventory:
    schema_version: int   # 1
    scanned_at: str       # ISO 8601, lokalna zona
    items: list[Item]; relations: list[Relation]; warnings: list[Warning]
    partial: bool         # True ako postoji bar jedno upozorenje "warn" ili je dostignut limit
```

**Identitet.** `id = sha256(kind | ključ)[:16]`.
- Ključ za skill i dokument je realpath fajla, normalizovan na lowercase i `\`.
- Za projekat je realpath foldera.
- Za plugin je `profile | ime@marketplace | scope`.
- Za MCP je `profile | realpath izvora | scope | projectPath | ime servera`.

ID je isti nakon promjene opisa i ponovnog skeniranja.

**Spajanje lokacija.** Dva nalaza sa istim realpathom su isti item sa više `locations`. Primjeri: `.claude\skills\firecrawl` → `.agents\skills\firecrawl`, i cijeli `.claude-pro\skills` → `.claude-max\skills`. Profil iz svake lokacije se čuva.

**Duplikati.** Različiti itemi istog `kind` i istog `name.lower()` dobijaju zajednički `duplicate_group`. Primjer: samostalni `skill-creator` i onaj iz plugina. Ne spajaju se.

**Dozvoljeni metadata ključevi** (sve ostalo je greška validacije):

| kind | ključevi |
|---|---|
| project | `projectType`, `scriptNames`, `markers` |
| skill | `rootLabel` |
| plugin | `marketplace`, `version`, `scope`, `installedAt`, `lastUpdated` |
| mcp | `transport`, `executableName`, `envNames`, `scope`, `projectPath`, `sourceFormat` |
| document | `referenceStatus` |

**Relacije** (samo uz direktan dokaz iz izvora):
- `plugin contains skill`: skill je u `installPath` plugina.
- `project documented-by document`: README/AGENTS/CLAUDE u korijenu projekta.
- `mcp configured-for project`: `projects[<putanja>]` u `.claude.json` ili `.mcp.json` projekta, kad se putanja poklapa sa skeniranim projektom.

Instaliran skill ne dobija vezu ni sa jednim projektom.

## 6. Sigurnost i privatnost

1. **MCP izlaz** sadrži samo: ime, profil, scope, `projectPath`, transport (`stdio` / `http` / `sse` / `unknown`), `executableName` i `envNames`.
   - `executableName` je basename od `command`, propušten kroz `^[A-Za-z0-9._-]{1,64}$`, inače `unknown`.
   - `envNames` su ključevi od `env` i stavke `env_vars`, propušteni kroz `^[A-Za-z_][A-Za-z0-9_]{0,63}$`.
   - Nikad ne izlaze `args`, vrijednosti `env`, `url`, `headers` ni originalni objekat.
2. **Skillovi:** čitaju se samo `name` i `description` iz frontmattera, a opis se skraćuje na 500 znakova. Tijelo skilla ne ulazi u izlaz.
3. **Poruke upozorenja** sadrže putanju i kod greške, nikad sadržaj fajla. Za JSON grešku idu samo red i kolona.
4. **HTML:**
   - Inventar se ugrađuje kao `<script type="application/json">`, uz zamjenu `<`, `>` i `&` sa `\u003c`, `\u003e` i `\u0026`.
   - JS čita taj JSON preko `JSON.parse(textContent)`, a sav sadržaj ide u DOM samo preko `textContent`. Nema `innerHTML` sa podacima.
   - CSP meta: `default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:`. Browser tako sam blokira bilo kakav mrežni zahtjev.
5. **Bez izvršavanja:** skener ne pokreće komande iz configa. `open` koristi `os.startfile` (Windows), odnosno `webbrowser.open` sa `file://` URI-jem drugdje, bez shella.
6. **Atomično pisanje:** izlaz se prvo piše u `<ime>.tmp` u istom folderu, provjeri se (JSON se ponovo parsira, HTML sadrži marker), pa ide `os.replace`. Ako bilo šta padne, stari fajl ostaje, a `.tmp` se briše.
7. **Sentinel test:** fixture MCP config sadrži jedinstvene stringove u `args`, `url`, `env` i `headers`. Test provjerava da se nijedan ne pojavljuje u `inventory.json`, `scan-report.md`, `index.html` ni u stderr-u CLI-ja.
8. Katalog sadrži privatne putanje. Ne objavljuje se i ne commituje (`output/` i `data/` su u `.gitignore`).

## 7. Skeniranje: pravila i limiti

- **Linkovi se prate.** Svaka lokacija bilježi `via_link` i `link_target`.
  - Zaštita od ciklusa: skup posjećenih realpath foldera.
  - Link čiji je cilj van svih konfigurisanih korijena (npr. `ab-*` u `ai-context-system`) se čita, uz `info` upozorenje `link-outside-roots`. `info` ne čini pregled djelimičnim.
- **Skill scan:** u svakom korijenu traži `SKILL.md` do dubine 4. Kad folder ima `SKILL.md`, ne ide dublje. Preskače `excludeNames`.
- **Plugin skillovi:** `installPath` se prihvata samo ako je realpath unutar `plugins` foldera istog profila. Inače ide `warn` i plugin se prikazuje bez skillova.
- **Nevalidan frontmatter:** item sa imenom foldera, praznim opisom i `warn` upozorenjem `bad-frontmatter`.
- **Fajlovi preko 1 MiB:** frontmatter i manifest se ne parsiraju. Ide `warn` `file-too-large`, a item ostaje sa imenom foldera.
- **Plafon je 5.000 itema.** Iznad toga skeniranje staje, dobija se `warn` `item-limit` i `partial = true`.
- **Nedostupan izvor** (ne postoji, nema dozvole, nevalidan JSON/TOML) daje `warn` za taj izvor, a ostali se obrađuju normalno.
- **Sortiranje:** `kind`, pa `name.lower()`, pa `id`. Dva skeniranja istog diska daju identičan `inventory.json` (osim `scanned_at`).

## 8. Katalog (`output/index.html`)

Jedan samostalan fajl: CSS i JS se ugrađuju iz `src/atlas/ui/` pri izradi.

- **Zaglavlje:** naslov "Moje AI okruženje", datum skeniranja, brojači po tipu (klik filtrira) i traka "Djelimičan pregled: N upozorenja" kada je `partial`. Klik na traku otvara listu upozorenja.
- **Filteri (lijevo):**
  - tip;
  - profil (agents, claude, max, pro, codex);
  - porijeklo skilla (samostalan / plugin);
  - samo duplikati;
  - samo stavke iz linkova.

  Filteri se kombinuju (AND), a "Očisti filtere" vraća sve.
- **Pretraga:** nad imenom, opisom, svim putanjama i metadata vrijednostima. Ne pravi razliku između velikih i malih slova ni dijakritika (`č` = `c`). Rezultat se obnavlja dok se kuca.
- **Lista (sredina):** ime, tip, profili kao oznake i prvi red opisa. Prikazuje se broj rezultata, a prazno stanje ima jasnu poruku.
- **Detalji (desno):**
  - svaka lokacija: putanja, profil, oznaka "preko linka → cilj", dugme "Kopiraj putanju" (Clipboard API, a ako je nedostupan, putanja se označi za ručno kopiranje);
  - status dokaza: "Pronađeno na disku" ili "Dokumentovano; trenutno stanje nije potvrđeno";
  - metadata u čitljivim nazivima;
  - povezane stavke kao linkovi;
  - ostale stavke iz iste grupe duplikata.

  MCP stavke nose napomenu "Deklarisan u konfiguraciji", bez zelenog statusa "Radi".
- **Tastatura:**
  - `/` fokusira pretragu;
  - `↑` / `↓` kroz listu;
  - `Enter` otvara detalje;
  - `Esc` zatvara detalje ili briše pretragu.

  Fokus je uvijek vidljiv. Izabrana stavka je u URL hashu (`#<id>`), pa osvježavanje stranice ostaje na njoj.
- **Izgled:** tri kolone od 1100 px naviše, dvije (filteri se sklapaju) između 700 i 1100 px, a jedna ispod 700 px, gdje se detalji otvaraju preko liste uz dugme "Nazad". Bez horizontalnog scrolla stranice. Svijetla i tamna tema prate sistem, `prefers-reduced-motion` se poštuje, kontrast je najmanje 4.5:1.
- **Performanse:** do 2.000 itema pretraga reaguje ispod 50 ms po pritisku tipke. Lista renderuje najviše 300 redova uz "Prikaži još".

## 9. CLI, izlazi, struktura

```text
python -m atlas init      [--config PATH]   # napravi config/sources.local.json ako ne postoji
python -m atlas scan      [--config PATH]   # data/inventory.json + data/scan-report.md
python -m atlas build                       # output/index.html iz data/inventory.json
python -m atlas refresh   [--config PATH]   # scan + build
python -m atlas open                        # otvori output/index.html
```

Uz to ide `atlas.cmd` u korijenu (`@python -m atlas %*`, uz `PYTHONPATH=src`), pa je dovoljno `.\atlas refresh`.

- **Exit kodovi:** 0 uspjeh, 1 fatalna greška (stari izlaz ostaje), 2 djelimičan rezultat (izlaz je napisan, uz upozorenja).
- **`scan-report.md`:** brojači po tipu i profilu, lista izvora sa statusom (pročitan / nedostaje / greška), upozorenja grupisana po kodu i trajanje.

```text
Archify/
  plan-izrade-ai-workspace-atlas.md   # originalni plan, referenca
  README.md  AGENTS.md  CLAUDE.md     # CLAUDE.md samo upućuje na AGENTS.md
  pyproject.toml  atlas.cmd  .gitignore
  config/sources.example.json
  config/sources.local.json           # gitignore
  docs/specs/  docs/plans/
  src/atlas/
    __main__.py  cli.py  config.py  model.py  identity.py  fsutil.py
    scan/projects.py  scan/skills.py  scan/plugins.py  scan/mcp.py  scan/documents.py
    inventory.py  report.py  writeout.py  catalog.py
    ui/template.html  ui/app.js  ui/styles.css
  tests/
    fixtures/                         # lažni workspace i profili, uklj. link i ciklus
    test_identity.py  test_config.py  test_skills.py  test_plugins.py
    test_mcp.py  test_projects.py  test_inventory.py  test_catalog.py  test_cli.py
    e2e/test_catalog_browser.py       # Playwright, preskače se ako nije instaliran
  data/  output/                      # gitignore
```

**Testovi:**
- `python -m unittest discover -s tests -v`, uz `PYTHONPATH=src`.
- Fixturei prave linkove u `setUp` u privremenom folderu. Ako Windows ne dozvoli symlink bez Developer Mode, koristi se junction (`_winapi.CreateJunction`), a ako ni to ne uspije, test se preskače uz jasan razlog.
- Browser test traži Playwright u lokalnom `.venv` (`pip install playwright`, `playwright install chromium`). Instalacija ide samo u `Archify\.venv`, nikad globalno.

## 10. Kriterijumi prihvatanja

- [ ] `.\atlas refresh` nad stvarnim izvorima završava sa exit kodom 0 ili 2 i pravi sva tri izlaza.
- [ ] Brojevi u katalogu odgovaraju disku: provjera nad 5 slučajnih skillova, 2 plugina, 2 MCP servera i 3 projekta, zapisana u `verification.md`.
- [ ] `firecrawl` (`.claude` → `.agents`) je jedan item sa dvije lokacije, a skill iz `.claude-max` nosi i profil `pro`.
- [ ] Skillovi iz pluginova (npr. `brainstorming` iz `superpowers`) su pronađeni, sa vezom prema pluginu.
- [ ] Codex MCP serveri su prikazani, i nijedna vrijednost iz `args`/`env`/`url`/`headers` nije u izlazima (sentinel test + grep stvarnih izlaza po uzorcima tokena: `sk-`, `ghp_`, `Bearer`, `token=`, `key=`).
- [ ] Naslov `</script><img src=x onerror=alert(1)>` u fixtureu se prikazuje kao tekst, a alert se ne javlja.
- [ ] `index.html` otvoren preko `file://` ne pravi nijedan mrežni zahtjev (Playwright prati zahtjeve).
- [ ] Pretraga, filter profil + tip, detalji, kopiranje putanje i tastatura rade u browser testu.
- [ ] Screenshot na 1440×900 i 390×844 je čitljiv i bez horizontalnog scrolla.
- [ ] Nedostupan izvor daje upozorenje, a ostatak kataloga je tu. Pokvaren config ostavlja stari katalog netaknut.
- [ ] Dva uzastopna skeniranja daju isti `inventory.json` (osim vremena).
- [ ] SHA-256 svih izvornih config fajlova je isti prije i poslije rada.
- [ ] Svi unit testovi i e2e test prolaze.
- [ ] README opisuje instalaciju, komande, dodavanje izvora i granice detekcije.

## 11. Razlike u odnosu na originalni plan

| Original | Ovdje | Zašto |
|---|---|---|
| Node + TypeScript + Zod + esbuild | Python stdlib + PyYAML | isti obrazac kao `session-miner` i `skill-evals`, bez build koraka |
| Linkovi se ne prate | Prate se, uz zaštitu od ciklusa i oznaku | bez toga `.claude-pro` i `ab-*` skillovi nestaju |
| Pluginovi odloženi | Pluginovi i njihovi skillovi uključeni | većina korištenih skillova dolazi iz pluginova |
| Codex TOML `unsupported` | Parsira se preko `tomllib` | ugrađeno u Python, struktura provjerena na disku |
| Bilješke, Archify mape, fingerprint | Van ove faze | sekcija 15 originala: tek nakon stvarne upotrebe |
| Pisan za Codex | Pisan za Claude Code | radi se u ovoj sesiji |

## 12. Van obima

Bilješke i overlay, Archify mape, praćenje promjena u realnom vremenu, izmjena ili instalacija bilo čega, server, cloud i objavljivanje. Svaki od ovih dodataka dobija vlastiti spec kad se pokaže potreba.
