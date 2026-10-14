# AI Workspace Atlas: dizajn (Faza 1, lokalni katalog)

**Datum:** 2026-10-13
**Status:** pregledano i korigovano na zahtjev korisnika; spremno za plan implementacije. Implementacija i završne provjere još nisu obavljene.
**Odnos prema `plan-izrade-ai-workspace-atlas.md`:** taj dokument ostaje referenca za kasnije faze (bilješke, Archify mape). Za Fazu 1 važi ovaj spec. Razlike su navedene u sekciji 11. Ova faza isporučuje katalog; Archify renderer i projektne mape nisu dio njenog prihvatanja.

## 1. Cilj i uspjeh

Korisnik dvoklikom otvori `output/index.html` i za manje od 10 sekundi nađe:

1. gdje je skill X, u kojem profilu je pronađen i da li je samostalan ili dolazi iz plugina;
2. gdje je deklarisan MCP server Y (profil, scope, transport);
3. koji plugin je instaliran u kojem profilu i koja verzija;
4. koji projekat postoji u radnom folderu, koji nazivi komandi su deklarisani i gdje mu je README;
5. koje stavke postoje na više mjesta (duplikati i linkovi).

Cilj od 10 sekundi provjeriti ručno na pet navedenih zadataka nakon upoznavanja s interfejsom; trajanja i konkretne tražene stavke zapisati u `verification.md`. To je cilj upotrebljivosti, ne garancija za svakog korisnika.

Katalog je snimak diska u trenutku skeniranja. Ne tvrdi da je MCP server pokrenut, da je skill učitan u sesiji ni da se projekat koristi.

**Završeno znači:** svi kriterijumi iz sekcije 10 su ispunjeni i zapisani u `output/verification.md`, sa komandama i rezultatima.

## 2. Ograničenja

- Sav kod i izlaz ostaju u `Projects\Archify`. Skenirani fajlovi se samo čitaju.
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
| Projekti | direktni podfolderi `Projects` sa markerom + eksplicitni `extraProjects` | `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `*.sln`, `*.csproj` |
| Skillovi | `~\.agents\skills` (132), `~\.claude\skills` (97, 9 linkova), `~\.claude-max\skills` (111, 3 linka), `~\.claude-pro\skills` (link na `.claude-max\skills`) | `<folder>\SKILL.md` sa YAML frontmatterom |
| Pluginovi | `~\.claude*\plugins\installed_plugins.json` (10 / 13 / 13) | `{version, plugins: {"ime@marketplace": [ {scope, installPath, version, installedAt, lastUpdated, gitCommitSha} ]}}` |
| Plugin skillovi | `<installPath>\skills\<ime>\SKILL.md` | isto kao skillovi |
| MCP, Claude | `~\.claude.json`, `~\.claude-max\.claude.json`, `~\.claude-pro\.claude.json`, `~\.claude*\settings.json` | `mcpServers` na vrhu (scope `user`) i `projects[<putanja>].mcpServers` (scope `project`) |
| MCP, projekat | `.mcp.json` u korijenu projekta, ako postoji | `mcpServers` (scope `project`) |
| MCP, Codex | `~\.codex\config.toml` (11 servera) | `[mcp_servers.<ime>]` sa `command`/`args`/`env`/`env_vars` ili `url` |
| Dokumenti | eksplicitna lista + README/AGENTS/CLAUDE u korijenu svakog projekta | putanja i naslov (prvi `# ` red ili ime fajla) |

Brojevi u tabeli su snimak zabilježen pri pisanju specifikacije, ne konstante za implementaciju. Skener mora izračunati trenutno stanje.

`skill-evals` nema marker, pa ulazi preko `extraProjects`. Folderi poput `drafts`, `ruben` ili `raw` nisu projekti i ne skeniraju se.

## 4. Konfiguracija

`config/sources.example.json` je u gitu, sa generičkim putanjama. `atlas init` iz njega pravi `config/sources.local.json` sa korisnikovim stvarnim putanjama, samo ako taj fajl ne postoji. Lokalni fajl je u `.gitignore`.

```json
{
  "workspaceRoot": "C:\\Users\\Example\\Projects",
  "projectRoots": ["."],
  "extraProjects": ["skill-evals"],
  "excludeNames": ["Archify", "node_modules", ".git", ".venv", "venv", "dist", "build", "output", "graphify-out", "__pycache__"],
  "skillRoots": [
    {"path": "C:\\Users\\Example\\.agents\\skills", "profile": "agents", "label": ".agents"},
    {"path": "C:\\Users\\Example\\.claude\\skills", "profile": "claude", "label": ".claude"},
    {"path": "C:\\Users\\Example\\.claude-max\\skills", "profile": "max", "label": ".claude-max"},
    {"path": "C:\\Users\\Example\\.claude-pro\\skills", "profile": "pro", "label": ".claude-pro"}
  ],
  "pluginRegistries": [
    {"path": "C:\\Users\\Example\\.claude\\plugins\\installed_plugins.json", "profile": "claude"},
    {"path": "C:\\Users\\Example\\.claude-max\\plugins\\installed_plugins.json", "profile": "max"},
    {"path": "C:\\Users\\Example\\.claude-pro\\plugins\\installed_plugins.json", "profile": "pro"}
  ],
  "mcpSources": [
    {"path": "C:\\Users\\Example\\.claude.json", "format": "claude-json", "profile": "claude"},
    {"path": "C:\\Users\\Example\\.claude\\settings.json", "format": "claude-json", "profile": "claude"},
    {"path": "C:\\Users\\Example\\.claude-max\\.claude.json", "format": "claude-json", "profile": "max"},
    {"path": "C:\\Users\\Example\\.claude-max\\settings.json", "format": "claude-json", "profile": "max"},
    {"path": "C:\\Users\\Example\\.claude-pro\\.claude.json", "format": "claude-json", "profile": "pro"},
    {"path": "C:\\Users\\Example\\.claude-pro\\settings.json", "format": "claude-json", "profile": "pro"},
    {"path": "C:\\Users\\Example\\.codex\\config.toml", "format": "codex-toml", "profile": "codex"}
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

- `workspaceRoot` je obavezna apsolutna putanja. Relativne putanje izvora računaju se od `workspaceRoot`, nikad od trenutnog foldera terminala.
- Podrazumijevani config i izlazi nalaze se u korijenu aplikacije, određenom lokacijom paketa. Relativni argument `--config PATH` računa se od tog korijena; apsolutni se koristi direktno.
- `projectRoots` su roditeljski folderi čiji direktni podfolderi ulaze u pregled; `extraProjects` su direktne putanje projekata. Isti projekat otkriven na oba načina spaja se.
- Validirati tipove, obavezna polja i dozvoljene vrijednosti prije skeniranja. Prazne liste izvora su dozvoljene; nepoznata polja i formati su greška.
- Plugin registri određuju profile; dozvoljeni `plugins` root za svaki profil je roditeljski folder njegovog konfigurisanog registra. Za isti profil ne prihvatati dva različita registry roota bez eksplicitnog proširenja specifikacije.
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
    link_target: str | None  # krajnji realpath, ako putanja ili njen predak prolazi kroz link
    origin: str | None       # skill: "standalone" ili "plugin:<plugin-item-id>"
    root_label: str | None   # naziv root izvora za tu lokaciju

@dataclass
class Item:
    id: str
    kind: Kind
    name: str
    description: str
    locations: list[Location]
    evidence: Evidence
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

**Identitet.** `id = sha256(UTF-8 JSON niza [kind, ...dijelovi_ključa])` (punih 64 hex znaka). Koristiti kanonsku JSON serijalizaciju, bez spajanja dijelova delimiterom koji se može pojaviti u nazivu. Putanje za identitet se razriješe u realpath, normalizuju na lowercase i `\` na Windowsu; originalna putanja ostaje za prikaz. Za odsutan/nečitljiv cilj koristi se normalizovana apsolutna putanja i upozorenje, bez prekida ostalih izvora.
- Ključ za skill i dokument je realpath fajla, normalizovan na lowercase i `\`.
- Za projekat je realpath foldera.
- Za plugin su dijelovi `profile`, `ime@marketplace`, `scope`, normalizovani `projectPath` (prazan string kada ne postoji) i realpath `installPath`. Projektni kontekst uzima se samo iz registra kada ga taj format sadrži; ne zaključuje se iz cache putanje. Za project scope bez projektnog konteksta prikazati „Projekat nije naveden u registru“. Različiti installPath-ovi ostaju različite instalacije; promjena installPath-a pri upgrade-u namjerno mijenja ID.
- Za MCP je `profile | realpath izvora | scope | projectPath | ime servera`.

ID je isti nakon promjene opisa i ponovnog skeniranja.

**Spajanje lokacija.** Skillovi i dokumenti sa istim realpath fajlom, odnosno projekti sa istim realpath folderom, jesu isti item sa više `locations`. Pluginovi i MCP stavke spajaju se prema njihovim kompletnim identitetima, ne samo prema realpathu. Primjeri: `.claude\skills\firecrawl` → `.agents\skills\firecrawl`, i cijeli `.claude-pro\skills` → `.claude-max\skills`. Profil i porijeklo iz svake lokacije se čuvaju. Jedinstvenost lokacije je `(normalizovana pronađena path, profile, origin, root_label)`; realpath ne smije ukloniti drugi profil. Jedan skill može imati i samostalnu lokaciju i plugin lokaciju; za svaku plugin instalaciju čuva se relacija `contains`.

**Duplikati.** Različiti itemi istog `kind` i istog `name.lower()` dobijaju zajednički `duplicate_group`. Primjer: samostalni `skill-creator` i onaj iz plugina. Ne spajaju se.

**Dozvoljeni metadata ključevi** (sve ostalo je greška validacije):

| kind | ključevi |
|---|---|
| project | `projectType`, `scriptNames`, `markers` |
| skill | nema; root naziv i porijeklo su u `Location` |
| plugin | `marketplace`, `version`, `scope`, `projectPath`, `installedAt`, `lastUpdated` |
| mcp | `transport`, `executableName`, `envNames`, `scope`, `projectPath`, `sourceFormat` |
| document | `referenceStatus` |

**Validacija inventara:** prije pisanja provjeriti Literal vrijednosti, tipove metadata vrijednosti, jedinstvene ID-jeve, postojanje source/target stavki svake relacije i navedenu allowlistu metadata ključeva. `dataclasses` same ne provjeravaju te uslove.

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
6. **Atomično pisanje:** za svaki cilj koristiti jedinstven temp fajl u istom folderu, validirati sadržaj, pa `os.replace`. Obična greška prije zamjene ostavlja prethodni cilj netaknut. `refresh` prvo napravi i validira inventory, report i HTML u stagingu, pa ih objavi uz backup i rollback ako bilo koja zamjena padne; `scan` isto radi za svoja dva izlaza. `build` mijenja samo HTML. Ne tvrditi da su tri pojedinačna `os.replace` operativno jedna atomska transakcija. Za prekid procesa tokom objave čuvati recovery zapis/backup u aplikaciji i izvršiti oporavak prije sljedeće komande koja čita/piše izlaze. Paralelne scan/build/refresh procese odbiti lockom. Sve canonical izlaze povezati istim hashom inventara (bez `scanned_at`) u reportu i HTML-u, da se nesaglasnost može otkriti. Privremeni fajlovi se uklanjaju poslije uspješne objave/oporavka; backup se ne briše prije potvrđenog oporavka.
7. **Sentinel test:** fixture MCP config sadrži jedinstvene stringove u `args`, `url`, `env` i `headers`. Test provjerava da se nijedan ne pojavljuje u `inventory.json`, `scan-report.md`, `index.html` ni u stderr-u CLI-ja.
8. Katalog sadrži privatne putanje. Ne objavljuje se i ne commituje (`output/` i `data/` su u `.gitignore`).

## 7. Skeniranje: pravila i limiti

- **Linkovi se prate.** Svaka lokacija bilježi `via_link` i `link_target`.
  - Zaštita od ciklusa koristi realpathove na **trenutnoj putanji rekurzije**, odvojeno za svaki root i profil. Ponovni nailazak na folder koji je već na toj putanji prekida tu granu uz `warn` `link-cycle`.
  - Globalni cache može izbjeći ponovno čitanje sadržaja fajla, ali ne smije preskočiti evidentiranje nove pronađene putanje, profila ili porijekla. Skeniranje `.claude-pro` mora dodati profil `pro` i kada je `.claude-max` već obrađen.
  - `via_link` je True ako sam fajl ili bilo koji predak pronađene putanje prolazi kroz symlink/junction. Čuvati logičku putanju kroz dati root za prikaz i krajnji cilj zasebno. Prekinut link daje `warn` `broken-link`.
  - Link čiji je cilj van svih konfigurisanih korijena (npr. `ab-*` u `ai-context-system`) se čita, uz `info` upozorenje `link-outside-roots`. `info` ne čini pregled djelimičnim.
- **Skill scan:** u svakom korijenu traži `SKILL.md` do dubine 4. Kad folder ima `SKILL.md`, ne ide dublje. Preskače `excludeNames`.
- **Plugin skillovi:** `installPath` se prihvata samo ako je realpath unutar dozvoljenog `plugins` roota istog profila; containment provjeriti komponentama putanje (`os.path.commonpath`), ne string prefiksom. Inače ide `warn` i plugin se prikazuje bez skillova.
- **Nevalidan frontmatter:** item sa imenom foldera, praznim opisom i `warn` upozorenjem `bad-frontmatter`.
- **Fajlovi preko 1 MiB:** frontmatter i manifest se ne parsiraju. Ide `warn` `file-too-large`, a item ostaje sa imenom foldera.
- **Plafon je 5.000 itema.** Iznad toga skeniranje staje, dobija se `warn` `item-limit` i `partial = true`.
- **Nedostupan izvor** (ne postoji, nema dozvole, nevalidan JSON/TOML) daje `warn` za taj izvor, a ostali se obrađuju normalno.
- **Sortiranje:** `kind`, pa `name.lower()`, pa `id`. Prije serijalizacije sortirati i `locations`, relacije, upozorenja i listovne metadata vrijednosti koje predstavljaju skupove; ukloniti identične relacije/upozorenja. Dva skeniranja istog diska daju identičan `inventory.json` (osim `scanned_at`). Trajanje ostaje samo u reportu.

## 8. Katalog (`output/index.html`)

Jedan samostalan fajl: CSS i JS se ugrađuju iz `src/atlas/ui/` pri izradi.

- **Zaglavlje:** naslov "Moje AI okruženje", datum skeniranja, brojači po tipu (klik filtrira) i traka "Djelimičan pregled: N upozorenja" kada je `partial`. Klik na traku otvara listu upozorenja.
- **Filteri (lijevo):**
  - tip;
  - profil (agents, claude, max, pro, codex);
  - porijeklo skilla (samostalan / plugin);
  - samo duplikati;
  - samo stavke iz linkova.

  Filteri se kombinuju (AND), a "Očisti filtere" vraća sve. Profil, porijeklo i uslov „iz linka“ moraju odgovarati **istoj lokaciji** kada su uključeni zajedno. Skill sa samostalnom lokacijom u profilu `claude` i plugin lokacijom u profilu `max` ne smije proći filter `claude + plugin`. Ostali filteri se primjenjuju na item; porijeklo je relevantno samo za skillove.
- **Pretraga:** nad imenom, opisom, svim putanjama i metadata vrijednostima. Ne pravi razliku između velikih i malih slova ni dijakritika (`č`, `ć` = `c`, `š` = `s`, `ž` = `z`; `đ` se mapira u `dj`). Rezultat se obnavlja dok se kuca.
- **Lista (sredina):** ime, tip, profili kao oznake i prvi red opisa. Prikazuje se broj rezultata, a prazno stanje ima jasnu poruku.
- **Detalji (desno):**
  - svaka lokacija: putanja, profil, porijeklo i root naziv, oznaka "preko linka → cilj", dugme "Kopiraj putanju" (Clipboard API, a ako je nedostupan, putanja se označi za ručno kopiranje);
  - status dokaza: "Pronađeno na disku" ili "Dokumentovano; trenutno stanje nije potvrđeno";
  - metadata u čitljivim nazivima;
  - povezane stavke kao linkovi;
  - ostale stavke iz iste grupe duplikata.

  MCP stavke nose napomenu "Deklarisan u konfiguraciji", bez zelenog statusa "Radi".
- **Tastatura:**
  - `/` fokusira pretragu, osim kada korisnik već kuca u input/textarea;
  - `↑` / `↓` prolaze kroz listu kada je fokus u listi; ne preuzimaju navigaciju u poljima za unos;
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

`python` u primjerima označava interpreter `Archify\.venv\Scripts\python.exe`. Direktne komande rade nakon aktivacije lokalnog `.venv` i instalacije paketa (`python -m pip install -e .`). `pyproject.toml` navodi `PyYAML` kao jedinu runtime zavisnost (`dependencies = ["PyYAML>=6"]`) i `playwright` kao opcionalnu `dev` zavisnost, da editable instalacija u prazan `.venv` povuče sve potrebno. Izlazi i podrazumijevani config uvijek su relativni korijenu aplikacije, ne terminalskom cwd-u.

`atlas.cmd` u korijenu eksplicitno koristi lokalni interpreter i putanju `%~dp0src`. Koristi `setlocal` da ne mijenja okruženje roditeljskog terminala. Ako `.venv` ne postoji, vraća 1 s jasnim uputstvom; ne pada automatski nazad na globalni Python.

```bat
@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Nedostaje lokalni .venv. Prati instalaciju u README.md. 1>&2
  exit /b 1
)
set "PYTHONPATH=%~dp0src"
"%~dp0.venv\Scripts\python.exe" -m atlas %*
exit /b %errorlevel%
```

Iz korijena projekta dovoljno je `.\atlas.cmd refresh`. Testirati i pozivanje punom putanjom iz drugog foldera s razmacima. Sve komande čuvaju exit kod Python CLI-ja.

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
    e2e/test_catalog_browser.py       # obavezna završna browser provjera
    e2e/__init__.py                   # omogućava eksplicitni unittest poziv
  data/  output/                      # gitignore
```

**Testovi:**

- Unit/integration: `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`, iz korijena aplikacije poslije lokalne editable instalacije.
- Browser: `.\.venv\Scripts\python.exe -m unittest discover -s tests/e2e -p "test_*.py" -v`. Playwright se instalira lokalnim interpreterom: `.\.venv\Scripts\python.exe -m pip install playwright`; Chromium: `.\.venv\Scripts\python.exe -m playwright install chromium`. Za browser binarne fajlove podesiti `PLAYWRIGHT_BROWSERS_PATH` na apsolutni `Archify\.playwright-browsers` tokom instalacije i testova; `.venv/` i `.playwright-browsers/` su u `.gitignore`.
- Tokom razvoja nedostajući Playwright može dati jasno označen skip. Za završno prihvatanje zahtijeva se stvarno pokrenut browser test bez skipa. Nedostajuća zavisnost znači „browser provjera nije obavljena“, ne „sve prolazi“.
- Fixturei prave linkove u privremenom folderu. Ako symlink nije dozvoljen, Windows junction kreirati test helperom; `_winapi.CreateJunction` koristiti samo ako je dostupan, jer je privatni API. Ako nijedna metoda nije dostupna, integration test prijavljuje skip. Logika rekurzije i očuvanja lokacija dodatno se provjerava fake filesystem testovima bez privilegija. Završna provjera obuhvata stvarne postojeće linkove; njihovo ponašanje ne smije ostati neprovjereno.
- Testovi identiteta obuhvataju dvije projektne instalacije istog plugina, isti skill preko više profila i samostalno/plugin porijeklo istog realpatha. Browser test provjerava da filter `profil + porijeklo` odgovara istoj lokaciji.
- Performance provjera koristi deterministički fixture od 2.000 stavki i 20 upita; izmjeriti vrijeme od input događaja do sljedećeg prikaza rezultata, navesti medijan i p95. Cilj p95 je ispod 50 ms na lokalnom računaru, uz zapis verzije browsera i uslova mjerenja. Pri 5.000 stavki interfejs i paginacija moraju ostati funkcionalni.

## 10. Kriterijumi prihvatanja

- [ ] `.\atlas refresh` nad stvarnim izvorima završava sa exit kodom 0 ili 2 i pravi sva tri izlaza.
- [ ] Brojevi u katalogu odgovaraju disku: provjera nad 5 slučajnih skillova, 2 plugina, 2 MCP servera i 3 projekta, zapisana u `verification.md`.
- [ ] `firecrawl` (`.claude` → `.agents`) je jedan item sa dvije lokacije, a skill iz `.claude-max` nosi i profil `pro`.
- [ ] Skillovi iz pluginova (npr. `brainstorming` iz `superpowers`) su pronađeni, sa vezom prema konkretnoj instalaciji plugina.
- [ ] Dvije projektne instalacije istog plugina s različitim installPath/projectPath imaju različite ID-jeve. Isti realpath skilla kroz samostalnu i plugin lokaciju čuva oba porijekla.
- [ ] Filter `profil + porijeklo + link` koristi jednu odgovarajuću lokaciju, bez spajanja uslova iz različitih lokacija.
- [ ] Codex MCP serveri su prikazani, i nijedna vrijednost iz `args`/`env`/`url`/`headers` nije u izlazima (sentinel test + grep stvarnih izlaza po uzorcima tokena: `sk-`, `ghp_`, `Bearer`, `token=`, `key=`).
- [ ] Naslov `</script><img src=x onerror=alert(1)>` u fixtureu se prikazuje kao tekst, a alert se ne javlja.
- [ ] `index.html` otvoren preko `file://` ne pravi nijedan mrežni zahtjev (Playwright prati zahtjeve).
- [ ] Pretraga, filter profil + tip, detalji, kopiranje putanje i tastatura rade u browser testu.
- [ ] Screenshot na 1440×900 i 390×844 je čitljiv i bez horizontalnog scrolla.
- [ ] Nedostupan izvor daje upozorenje, a ostatak kataloga je tu. Pokvaren config ostavlja stari katalog netaknut.
- [ ] Dva uzastopna skeniranja daju isti `inventory.json` (osim vremena).
- [ ] SHA-256 svih izvornih config fajlova je isti prije i poslije rada.
- [ ] Svi unit testovi prolaze; browser test je stvarno izvršen i prolazi bez skipa. Svi eventualno preskočeni platform integration testovi su navedeni, uz stvarnu provjeru linkova na disku.
- [ ] `.\atlas.cmd refresh` radi i kada se pozove punom putanjom iz drugog foldera; koristi lokalni interpreter i piše u Archify izlaze.
- [ ] Simulirana greška druge/treće zamjene tokom refresh-a vraća prethodni komplet izlaza. Recovery test potvrđuje oporavak poslije prekinute objave; paralelno pisanje se odbija.
- [ ] Performance rezultati za 2.000 stavki i ručna provjera cilja pronalaženja u 10 sekundi zapisani su s uslovima mjerenja.
- [ ] README opisuje instalaciju, komande, dodavanje izvora i granice detekcije.

## 11. Razlike u odnosu na originalni plan

| Original | Ovdje | Zašto |
|---|---|---|
| Node + TypeScript + Zod + esbuild | Python stdlib + PyYAML | isti obrazac kao `session-miner` i `skill-evals`, bez build koraka |
| Linkovi se ne prate | Prate se, uz zaštitu od ciklusa i oznaku | bez toga `.claude-pro` i `ab-*` skillovi nestaju |
| Pluginovi odloženi | Pluginovi i njihovi skillovi uključeni | većina korištenih skillova dolazi iz pluginova |
| Codex TOML `unsupported` | Parsira se preko `tomllib` | ugrađeno u Python, struktura provjerena na disku |
| Bilješke, Archify mape i fingerprint bili su uključeni u prvu verziju | Van ove faze | svjesno su odloženi radi manjeg obima prve faze; ovo mijenja originalni plan |
| Pisan za Codex | Primjenjiv za Codex i Claude Code | isti ugovor podataka, CLI i kriterijumi prihvatanja nezavisno od implementera |

## 12. Van obima

Bilješke i overlay, Archify mape, praćenje promjena u realnom vremenu, izmjena ili instalacija bilo čega, server, cloud i objavljivanje. Svaki od ovih dodataka dobija vlastiti spec kad se pokaže potreba.

## 13. Revizija specifikacije

Revizija 2026-10-13: precizirani identitet instalacije plugina, porijeklo po lokaciji, obrada linkova bez gubitka profila, lokalni interpreter, završna browser provjera, objava/oporavak izlaza i stvarna promjena obima u odnosu na originalni plan. Obim ostaje lokalni katalog bez Archify mapa i bilješki.
