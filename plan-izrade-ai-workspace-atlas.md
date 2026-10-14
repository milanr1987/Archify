# AI Workspace Atlas uz Archify: specifikacija i plan izrade

> **For agentic workers:** Use `superpowers:executing-plans`, if available, to implement this document task by task. Track progress with checkboxes. This file contains both the specification and implementation plan. Do not assume permission to delegate to subagents.

**Goal:** Napraviti lokalni, pretraživ katalog korisnikovih projekata, AI skillova i MCP konfiguracija, sa interaktivnim Archify mapama odabranih projekata.

**Architecture:** Node CLI čita dozvoljene lokalne izvore i pravi normalizovan JSON inventar. Statični katalog prikazuje taj inventar i otvara zasebne Archify HTML mape. Codex analizira odabrani projekat i priprema mapu iz provjerenih izvora; skener sam ne zaključuje arhitekturu proizvoljnog koda.

**Tech Stack:** Node.js aktivni LTS u vrijeme implementacije, TypeScript, npm, Zod za validaciju, esbuild za mali browser bundle, Node test runner i Playwright za browser provjere. Archify je izdvojena, verzionisana zavisnost za generisanje mapa. Bez Reacta, baze podataka, cloud backenda i dodatnog LLM API-ja u prvoj verziji.

**Spec:** Ovaj dokument, sekcije 1–12. Plan implementacije je u sekciji 13.

**Status:** Spremno za implementaciju; softver još nije napravljen ovim dokumentom.

**Datum:** 2026-10-13.

## Globalna ograničenja

- Projekat i svi generisani izlazi ostaju u `C:\Users\Example\Projects\Archify`.
- Izvorni projekti, instrukcije, konfiguracije i korpusi čitaju se bez izmjena.
- Lokalni Windows rad, uključujući putanje s razmacima i slovima č, ć, š, ž, đ.
- Interfejs i uputstva su na BCS-u; promptovi za kopiranje su na engleskom.
- Dokazana konfiguracija, dokumentovana tvrdnja i nepoznato stanje moraju biti odvojeni.
- Ne unositi tajne, tokene, kompletne komande MCP servera ili sadržaj sesija u inventar/HTML.
- Skener ne izvršava pronađene projekte, skripte, skillove ili MCP servere.
- Ne instalirati skill globalno kao sporedni efekat izrade kataloga. Archify koristiti lokalno.
- Nakon inicijalnog pribavljanja zavisnosti katalog i postojeće mape rade bez mreže.
- Ne dirati roditeljski knowledge base niti pokretati njegove projekte radi ove izrade.

## Fokus provjere

1. Windows putanje s razmacima i dijakritikom: skeniranje, osvježavanje i otvaranje izlaza rade.
2. Nedostupan profil ili nečitljiv JSON: nastaje jasno upozorenje, ostali izvori se obrađuju.
3. Token u konfiguraciji ili zlonamjeran tekst u naslovu: ništa osjetljivo ne izlazi i tekst se ne izvršava u browseru.
4. Dva profila sa istoimenim skillom/MCP serverom: nastaju odvojene instance, uz vidljivu grupu duplikata.
5. Neuspješno generisanje mape ili osvježavanje: prethodni ispravan izlaz ostaje dostupan.

## 1. Šta korisnik dobija

Jedan fajl `output/index.html`, koji korisnik otvara dvoklikom. U njemu nalazi:

- projekte u svom radnom folderu;
- skillove otkrivene u eksplicitno navedenim lokacijama;
- MCP servere deklarisane u podržanim konfiguracijama;
- dokumente koji objašnjavaju radno okruženje;
- provjerene veze između ovih stavki;
- odvojene interaktivne mape odabranih projekata.

Primjeri pitanja koja katalog treba da olakša:

1. Gdje se nalazi skill koji sam koristio i u kojem profilu postoji?
2. Gdje je konfigurisan određeni MCP server?
3. Koji dokument objašnjava moj projekat i kako ga pokrenuti?
4. Kako podaci prolaze kroz odabranu aplikaciju?
5. Koje stavke postoje u više lokacija, a koje su samo pomenute u starim bilješkama?

Katalog pokazuje snimak pronađenih izvora. Ne tvrdi da je MCP server pokrenut, da je skill učitan u aktivnoj sesiji ili da je pronađeni projekat trenutno u upotrebi.

## 2. Šta Archify radi u ovom projektu

Archify je renderer i skup pravila za interaktivne mape. Prema provjerenom upstream README-u, izlaz je samostalan HTML, izvor mape je tipizirani JSON, a podržani su architecture, workflow, sequence, data flow i lifecycle prikazi. Upstream navodi CLI validaciju i isporuku artefakta.

Izvor: [Archify README](https://github.com/tt-a1i/archify/blob/main/README_EN.md), provjeren 2026-10-13. Inspiracija: `MEDIUM_CLAUDE/medium-posts-raw.md`, POST 10.

Naš katalog, skener, klasifikacija profila, dokazi, pretraga i lične bilješke su funkcionalnosti koje ovim projektom treba izgraditi. Nemoj pripisivati te mogućnosti samom Archifyju.

**Važna odluka:** Ne pretvarati cijeli inventar u jedan ogroman arhitekturni graf. Skill instaliran u korisničkom profilu nije dokaz da ga neki projekat koristi. Početni katalog je lista/kartice s filterima; Archify mapa jednog projekta prikazuje 8–15 važnih komponenti i stvarno utvrđene veze.

## 3. Granice prve verzije

### Uključeno

- Eksplicitno podešavanje izvora.
- Skeniranje projekata, lokalnih skillova i podržanih MCP konfiguracija.
- Dokumenti kao reference, bez indeksiranja punog korpusa.
- Pretraga, filteri, detalji stavke i duplikati.
- Ručne bilješke koje preživljavaju osvježavanje.
- JSON inventar i čitljiv izvještaj o skeniranju.
- Jedna stvarna Archify mapa projekta `creative-forge`, ako je folder dostupan.
- Druga mapa tek poslije uspješne provjere prve; prirodan kandidat je `session-miner`.
- Offline katalog i komanda za osvježavanje.

### Odloženo

- RAG, vektorska baza i chat nad cijelim korpusom.
- Automatska analiza svih projekata pomoću modela.
- Troškovi i kvote modela, monitoring procesa i automatsko pokretanje MCP servera.
- Cloud sinhronizacija, nalog, više korisnika i javno objavljivanje.
- Automatska instalacija/deinstalacija pluginova i izmjena konfiguracija.
- Otvaranje proizvoljnog foldera kroz backend ili izvršavanje komandi iz HTML-a.
- Automatsko praćenje promjena u realnom vremenu.

## 4. Izvori i pravila skeniranja

Korijenski radni folder je:

```text
C:\Users\Example\Projects
```

Početna konfiguracija sadrži `workspaceRoot`, `projectRoots`, `skillRoots`, `mcpSources`, `documents` i `excludeNames`. Sve putanje se normalizuju u apsolutne putanje pri učitavanju konfiguracije. Relativne putanje računaju se od konfiguracionog fajla, nikada od slučajnog trenutnog terminalskog foldera.

### Projekti

Skenirati direktne podfoldere workspacea. Kandidat za kodni projekat ima najmanje jedan marker: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `.sln` ili `.csproj`. Folder označen samo dokumentima dobija tip `knowledge-base`, uz eksplicitnu dozvolu iz konfiguracije. `Archify` isključiti iz inventara kojim sam sebe skenira.

Početni kandidati su `creative-forge`, `session-miner` i `skill-evals`. Provjeriti stvarne markere i instrukcije prije klasifikacije. Prisustvo markera nije dokaz da je aplikacija ispravna.

Iz `package.json` uzeti ime, opis, workspace strukturu i **nazive** scripts komandi. Ne izvršavati scripts i ne prepisivati njihove vrijednosti u izlaz. Za ostale manifeste uzeti ime/opis dostupne kroz odgovarajući parser ili dati ograničeni rezultat i upozorenje.

### Skillovi

Početne lokacije za provjeru postojanja:

```text
C:\Users\Example\.agents\skills
C:\Users\Example\.claude\skills
C:\Users\Example\.claude-max\skills
C:\Users\Example\.claude-pro\skills
```

Dodatne lokacije unijeti eksplicitno. Ne pretpostaviti da neki alat traži baš ove foldere niti da pronalaženje fajla znači da je skill aktivan.

Svaki `SKILL.md` predstavlja instancu skilla u datom rootu/profilu. Izvući `name` i `description` iz frontmattera kroz YAML parser, te putanju. Ne kopirati ostatak tijela skilla u katalog. Za neispravan frontmatter zadržati karticu s nazivom foldera i upozorenjem.

Ne pratiti symlink/junction foldere. Ako je sam `SKILL.md` symlink, koristiti sadržaj samo kada realna ciljna putanja ostaje unutar eksplicitno dozvoljenih izvora; inače prijaviti preskočenu stavku.

### MCP konfiguracije

U prvoj verziji obavezno podržati `.mcp.json` projekata i korisnički JSON koji ima objekat `mcpServers`. Svaki izvor konfiguracije navesti kroz `mcpSources` sa poljima `path`, `format: "mcp-json"` i `profile`.

Codex TOML, plugin marketplace i instalacioni registri nisu obavezni parseri prve verzije. Ako stvarna konfiguracija to koristi, evidentirati je kao referencu s oznakom `unsupported-format`, uz mogućnost kasnijeg adaptera. Ne izmišljati strukturu TOML/JSON registra niti zaključivati instalaciju iz cache foldera.

Iz konfiguracije izvesti isključivo: ime servera, profil, scope, transport (`stdio`, `http`, `sse`, `unknown`), basename executable-a i **imena** env varijabli. Ne izvesti `args`, vrijednosti env varijabli, URL, headers ili cijelu originalnu stavku. HTTP prikazuje transport i izvor; endpoint je izostavljen jer URL može nositi token.

U browseru koristiti status „Deklarisan u konfiguraciji“, bez zelenog indikatora „Radi“.

### Dokumenti

Eksplicitno dodati reference za `my-claude-system.md`, `claude-skillovi-i-plugini-inventar.md`, `claude-ai-engineer-playbook.md`, README/AGENTS/CLAUDE dokumente projekta i Medium INDEX. Čuvati putanju i naslov, bez kopiranja cijelog sadržaja.

Stari inventar može objasniti kontekst, ali svaka tvrdnja iz njega ima oznaku „Dokumentovano; trenutno stanje nije potvrđeno“.

### Limiti

- Ne pratiti folder junctions/symlinks; registracija dozvoljenih korijena ide kroz realpath.
- Maksimalna dubina za skill skeniranje: 4; projekti se otkrivaju u direktnim podfolderima.
- Isključiti `node_modules`, `.git`, `.venv`, `venv`, `dist`, `build`, `output`, cache, backup i raw korpuse.
- Maksimalna veličina tekstualnog fajla za automatski parser: 1 MiB. Veći dokument ostaje referenca bez sadržaja.
- Maksimalno 2.000 stavki po skeniranju; prekoračenje završava s upozorenjem i jasnim djelimičnim statusom.
- Greška jednog izvora ne prekida ostale. Potpuno nevalidna početna konfiguracija prekida rad prije pisanja izlaza.

## 5. Model podataka

U `src/domain/schema.ts` definisati Zod sheme, pa TypeScript tipove izvesti iz njih. Ovo je ugovor našeg kataloga, ne Archify JSON shema.

`ScanConfig` ima `workspaceRoot: string`, `projectRoots: string[]`, `skillRoots: { path: string; profile: string; label: string }[]`, `mcpSources: { path: string; format: 'mcp-json' | 'unsupported'; profile: string; scope: 'user' | 'project'; projectPath?: string }[]`, `documents: { path: string; title: string; projectPath?: string }[]` i `excludeNames: string[]`. Limitima upravlja implementacija prema sekciji 4. `projectRoots` su roditeljski folderi čiji se direktni podfolderi pregledaju. Nedostajući pojedinačni izvor nije nevalidan config.

```typescript
type ItemKind = 'project' | 'skill' | 'mcp' | 'document';
type EvidenceStatus = 'observed' | 'documented' | 'unknown';
type Warning = { code: string; sourcePath: string; message: string };
type Evidence = {
  sourcePath: string;
  locator?: string; // npr. JSON pointer; bez vrijednosti tajnih polja
  status: EvidenceStatus;
  observedAt: string;
};
type Item = {
  id: string;
  kind: ItemKind;
  name: string;
  description: string;
  sourcePath: string;
  profile?: string;
  tags: string[];
  evidence: Evidence[];
  metadata: Record<string, string | string[]>; // allowlist ključeva po tipu
};
type Relation = {
  id: string;
  from: string;
  to: string;
  type: 'contains' | 'configured-for' | 'documented-by';
  evidence: Evidence[];
};
type Overlay = {
  notes: Record<string, { text: string; tags: string[] }>;
};
type MapEntry = {
  projectId: string;
  title: string;
  htmlPath: string; // relativno od output/index.html, npr. maps/creative-forge.html
  generatedAt: string;
  sourceFingerprint: string;
  status: 'current' | 'stale' | 'unverified';
};
type Inventory = {
  schemaVersion: 1;
  scannedAt: string;
  items: Item[];
  relations: Relation[];
  maps: MapEntry[];
  warnings: Warning[];
};
```

ID je SHA-256 od `kind + profile + normalizovana apsolutna sourcePath + podkljuc`. Podključ je ime MCP servera ili prazan string za ostale. Na Windowsu putanja za identitet ide u lowercase, uz normalizovane separatore; original za prikaz ostaje sačuvan. ID ostaje isti poslije promjene opisa i osvježavanja.

Za metadata dozvoliti unaprijed definisane ključeve: project (`projectType`, `scriptNames`), skill (`rootLabel`), mcp (`transport`, `executableName`, `envNames`, `scope`), document (`referenceStatus`). Zod shema mora odbiti neočekivane ključeve.

Grupe duplikata izvode se iz `kind + name.toLowerCase()` za prikaz. Instance se ne spajaju. Isto ime u dva profila nije greška, ali korisnik mora vidjeti obje lokacije.

Relacije dodavati samo kad izvor podržava baš tu tvrdnju. Root skill foldera ne stvara automatski vezu `uses` sa svakim projektom. Referenca u README-u dokazuje dokumentovanu vezu, ne runtime poziv.

## 6. Analiza odabranog projekta i Archify adapter

Automatski inventar i arhitektura projekta su dvije odvojene stvari. Za mapu jednog projekta Codex:

1. Pročita lokalne AGENTS/CLAUDE/README instrukcije.
2. Pregleda manifeste, ulazne tačke, relevantne importe i pozive.
3. Izdvoji 8–15 važnih komponenti i jedan konkretan tok korisničke radnje.
4. Snimi `data/analysis/<slug>.json`, koji sadrži komponente, veze, relativne source putanje, broj linije i SHA-256 relevantnog fajla.
5. Svaku vezu označi `observed` ili `documented`; nepodržane veze izostavi i stavi u listu otvorenih pitanja.
6. Pripremi stvarni Archify JSON u `data/maps/<slug>.json` prema shemi pribavljene upstream verzije.
7. Pokrene validaciju, isporuku i browser pregled.

`data/analysis` je naš evidencioni sloj. Archify native source-evidence funkcija za javni Git commit nije isto što i provjera lokalnog fajla. Za lokalne/private projekte dokaz ostaje u našem analysis JSON-u i katalogu; ne tvrditi da je upstream Git verifikacija obavljena.

`ProjectAnalysis` definisati u `src/maps/analysis-schema.ts`: `schemaVersion: 1`, `projectId: string`, `projectRoot: string`, `generatedAt: string`, `components: { id: string; name: string; purpose: string; evidenceIds: string[] }[]`, `edges: { from: string; to: string; label: string; status: 'observed' | 'documented'; evidenceIds: string[] }[]`, `evidence: { id: string; relativePath: string; line: number; fileHash: string }[]` i `openQuestions: string[]`. Svi evidence ID-jevi moraju postojati, a source putanje ostati unutar projectRoot poslije realpath provjere. Fingerprint koristi te relativne putanje razriješene u projectRoot.

Za prvi projekat `creative-forge` provjeriti stvarni tok: korisnik na stranici → ekstenzija → lokalni bridge → lokalno čuvanje. Ovo je hipoteza iz roditeljske dokumentacije, koju kod mora potvrditi. Ako projekta nema, izabrati `session-miner`; ako ni njega nema, napraviti fixture demo i jasno prijaviti da stvarna projektna mapa nije isporučena.

### Pribavljanje Archifyja

- Pročitati upstream README i `archify/SKILL.md` prije integracije.
- Pribaviti lokalnu kopiju upstream projekta u `vendor/archify`, bez mijenjanja globalnih profila. Zabilježiti tačan Git commit/verziju i licencu u `data/archify-version.json`.
- Putanju CLI-ja provjeriti na pribavljenoj verziji. Ne kopirati pretpostavljenu JSON shemu iz ovog plana.
- Pokrenuti doctor i jedan upstream example prije našeg adaptera.
- Početni upstream opis na datum plana pokazuje komande oblika `node bin/archify.mjs doctor` i `deliver workflow ... --quality showcase --json`; proveriti njihove stvarne argumente lokalno.
- Automatsko korišćenje opcionalne provjere upstream updatea isključiti kroz podržanu postavku `ARCHIFY_UPDATE_CHECK_DISABLED=1` pri renderovanju, radi ponovljivog offline rada.

Integracija treba da sačuva JSON izvor i HTML rezultat. Ako validacija nove mape padne, zadržati prethodni HTML i prijaviti grešku. Ne zamijeniti Archify generičkim graf rendererom uz tvrdnju da je integracija završena.

## 7. Interfejs i svakodnevna upotreba

### Početni ekran

Naslov „Moje AI okruženje“, datum posljednjeg skeniranja, brojači Projekti / Skillovi / MCP / Dokumenti, pretraga i filteri. Oznaka „Djelimičan pregled“ pojavljuje se ako postoje preskočeni izvori ili limit.

Filteri: tip, profil, dokaz, tag i duplikati. Pretraga uključuje naziv, opis, putanju i korisničke bilješke. Izbor kartice otvara detalje na istom ekranu.

### Detalji stavke

Prikazati opis, putanju s dugmetom „Kopiraj putanju“, profil, status dokaza, povezane stavke, bilješku i mapu ako postoji. Putanja ima selectable tekst kao fallback ako Clipboard API nije dostupan na `file://`.

Ne obećati da browser klik otvara Explorer. Lokalni fajl linkovi nisu pouzdani u svim browserima; prva verzija garantuje kopiranje putanje. Mape su relativni HTML linkovi koje browser može otvoriti.

### Bilješke

Autoritativne bilješke su u `config/overrides.json`. CLI `note` dodaje/izmjenjuje bilješku po ID-u i regeneriše katalog. Browser je read-only za bilješke u MVP-u; bez skrivenog čuvanja u localStorage koje korisnik može izgubiti.

### Izgled

Jednostavan raspored sa lijevim filterima, srednjom listom i panelom detalja. Na uskom ekranu jedna kolona. Čitljiv tekst, jasni statusi, tastaturna navigacija, vidljiv fokus i poštovanje reduced-motion. Bez CDN fontova, analitike ili eksternih asseta.

Katalog i mapa se međusobno razlikuju: kartice služe pronalaženju alata; Archify mapa razumijevanju toka konkretnog projekta.

## 8. Struktura fajlova

```text
Archify/
  plan-izrade-ai-workspace-atlas.md     # ovaj dokument; sačuvati
  README.md                           # instalacija i upotreba na BCS-u
  AGENTS.md                           # granice rada i komande za ovaj projekat
  package.json
  package-lock.json
  tsconfig.json
  .gitignore
  config/
    sources.example.json
    sources.local.json                # stvarne lokalne putanje; nije za dijeljenje
    overrides.json
  src/
    cli.ts
    domain/schema.ts
    domain/identity.ts
    scan/config.ts
    scan/filesystem.ts
    scan/projects.ts
    scan/skills.ts
    scan/mcp.ts
    scan/documents.ts
    scan/inventory.ts
    maps/analysis-schema.ts
    maps/archify.ts
    output/write.ts
    output/build-catalog.ts
    ui/index.ts
    ui/styles.css
    ui/template.html
  tests/
    identity.test.ts
    scanners.test.ts
    output.test.ts
    archify.test.ts
    fixtures/
    browser/catalog.spec.ts
  scripts/build.mjs
  data/
    inventory.json
    scan-report.md
    archify-version.json
    analysis/<slug>.json
    maps/<slug>.json
    map-registry.json
  output/
    index.html
    maps/<slug>.html
    verification.md
  vendor/archify/                     # lokalna upstream kopija
```

Ne unositi izvornu dokumentaciju/korporse u `vendor`. Ignorisati `node_modules`, lokalnu konfiguraciju, generisane inventare/izlaze i upstream checkout u našem Git-u. Licence korišćenih zavisnosti zadržati. Git commitovi se rade samo ako postoji namjenski Git repozitorij ovog projekta; ne praviti commit roditeljskog workspacea automatski.

## 9. CLI ugovor

Svi naredni primjeri su **komande koje treba implementirati**, ne tvrdnja da već rade.

| Komanda | Ponašanje |
|---|---|
| `npm run build` | TypeScript CLI build i inline browser bundle |
| `npm run atlas -- init` | Napravi lokalnu konfiguraciju samo ako ne postoji |
| `npm run atlas -- scan` | Inventar + izvještaj; prethodni katalog ostaje dok se ne osvježi |
| `npm run atlas -- refresh` | Skeniranje, validacija, izrada kataloga; bez novih AI analiza/mapa |
| `npm run atlas -- map --project creative-forge` | Render iz postojećeg analysis/map JSON-a i registracija mape |
| `npm run atlas -- note --id <id> --text "Moja bilješka"` | Sačuvaj overlay i obnovi katalog |
| `npm run atlas -- open` | Otvori lokalni index kroz platformski opener bez shell interpolacije |
| `npm run check` | Typecheck + unit/integration tests + build |
| `npm run test:e2e` | Playwright nad offline katalogom i isporučenom mapom |

`atlas` script poziva `node dist/cli.js`. `--config <path>` podržati na svim komandama. Exit kodovi: 0 uspjeh, 1 fatalna greška, 2 djelimičan rezultat zbog nečitljivog izvora/limita. Izvještaj jasno kaže šta je preskočeno. `refresh` kod djelimičnog rezultata objavljuje validan katalog s upozorenjem; kod fatalne greške ostavlja prethodni izlaz.

`map` ne poziva model i ne pravi novu arhitekturu. Ako JSON ne postoji, vraća 1 i objašnjava da Codex prvo treba da uradi analizu prema sekciji 6.

## 10. Offline isporuka, putanje i privatnost

- U `index.html` ugraditi inventar i browser JS/CSS; ne koristiti `fetch()` za lokalni JSON niti ES module imports preko `file://`.
- JSON embed mora escapeovati `<` u `\u003c` da tekst `</script>` ne zatvori script element. DOM sadržaj unositi kroz `textContent`; ne renderovati nepouzdani opis kao HTML/Markdown.
- Za maps registre prihvatiti samo relativne putanje unutar `output/maps`, bez `..`, apsolutnih putanja i `javascript:`/`data:` URL-ova.
- `map` koristi `spawn`/`execFile` s argumentima kao nizom, `shell: false`; bez string-built shell komandi.
- Izvještaji i error poruke ne smiju sadržati cijeli neuspješni JSON ili vrijednosti konfiguracije.
- Svaki izlaz prvo pisati u staging fajl, validirati, pa zamijeniti canonical izlaz. Zamjena koja padne mora sačuvati prethodni fajl ili vratiti backup i prijaviti grešku.
- Katalog sadrži privatne lokalne putanje. Ne objavljivati ga automatski.

## 11. Osvježavanje i tačnost mapa

`refresh` ponovo čita izvore i čuva iste ID-jeve za iste instance. Ako stavka nestane, izostavlja se iz novog inventara; njen overlay ostaje sa upozorenjem „Bilješka za trenutno nepronađenu stavku“.

Za svaku mapu fingerprint računati kao SHA-256 od sortirane liste relevantnih source putanja i njihovih hashova, zabilježenih u analysis JSON-u. Ako se bilo koji evidentirani source fajl promijeni ili nestane, mapa dobija `stale`. Ako evidence lista nedostaje, dobija `unverified`.

„Current“ znači da evidentirani source fajlovi nisu promijenjeni. Ne znači da je cijeli projekat automatski provjeren: nova komponenta izvan evidence liste može ostati neotkrivena. Taj opis prikazati u detaljima mape.

Ne prepisivati analysis/map JSON prilikom običnog refresh-a. Za osvježavanje arhitekture korisnik traži novu analizu od Codexa, koji zatim ponovo renderuje mapu.

## 12. Kriterijumi prihvatanja

- [ ] Korisnik otvara `output/index.html` direktno, bez servera i bez interneta.
- [ ] Pretraga i filteri rade nad stvarnim inventarom.
- [ ] Svaka stavka ima putanju, profil kada je poznat i status dokaza.
- [ ] Dvije instance istog skilla u različitim profilima ostaju odvojene.
- [ ] MCP konfiguracija ne izlazi s args/env vrijednostima/URL/header tajnama.
- [ ] Nedostajući profil izaziva upozorenje, ostali izvori ostaju vidljivi.
- [ ] `note` čuva bilješku, a `refresh` je zadržava.
- [ ] Stvarna mapa jednog dostupnog projekta sadrži 8–15 komponenti i jedan provjeren tok.
- [ ] Archify verzija/commit, JSON izvor, validacija i HTML su evidentirani.
- [ ] Neuspješna mapa ne uništava prethodnu ispravnu mapu.
- [ ] Promjena evidentiranog source fajla označi mapu zastarjelom.
- [ ] `npm run check` i `npm run test:e2e` prolaze ili je precizan vanjski blokator naveden.
- [ ] Izvorni projekti i konfiguracije nisu mijenjani.
- [ ] README sadrži tačne komande i objašnjenje granica detekcije.

## 13. Plan implementacije za Codex

### Zadatak 1: Osnova, konfiguracija i identitet

**Fajlovi:** `package.json`, `tsconfig.json`, `src/cli.ts`, `src/domain/schema.ts`, `src/domain/identity.ts`, `src/scan/config.ts`, `config/sources.example.json`, `tests/identity.test.ts`, `AGENTS.md`.

**Interfejsi:** `loadConfig(path: string): Promise<ScanConfig>`; `makeItemId(kind: ItemKind, profile: string | undefined, sourcePath: string, subkey?: string): string`; `InventorySchema`, `OverlaySchema`.

- [ ] Pregledaj okruženje, postojeće fajlove i instrukcije; sačuvaj ovaj plan.
- [ ] Napiši testove: ID je isti poslije promjene separatora/case Windows putanje; različit profil ili MCP podključ daje različit ID; nevalidan config se odbija prije output pisanja.
- [ ] Implementiraj sheme, identitet i config; dodaj root realpath provjeru i limite iz sekcije 4.
- [ ] Dodaj npm scripts iz sekcije 9 i `init` koji ne prepisuje postojeću konfiguraciju.
- [ ] Pokreni typecheck i identity/config testove; potvrdi konkretne rezultate.

### Zadatak 2: Skeneri i inventar

**Fajlovi:** `src/scan/filesystem.ts`, `projects.ts`, `skills.ts`, `mcp.ts`, `documents.ts`, `inventory.ts`, `tests/scanners.test.ts`, `tests/fixtures/`.

**Interfejsi:** `ScanResult = { items: Item[]; warnings: Warning[] }`; `scanProjects(config: ScanConfig): Promise<ScanResult>`; `scanSkills(config: ScanConfig): Promise<ScanResult>`; `scanMcp(config: ScanConfig): Promise<ScanResult>`; `scanDocuments(config: ScanConfig): Promise<ScanResult>`; `buildInventory(config: ScanConfig): Promise<Inventory>`.

- [ ] Napiši fixture testove za validan projekat, skill sa frontmatterom i dva istoimena skilla u različitim profilima.
- [ ] Testiraj nečitljiv/odsutan root, nevalidan JSON/frontmatter, prevelik fajl i junction ciklus; ostatak skeniranja mora preživjeti.
- [ ] U MCP fixture ubaci jedinstvene sentinel tajne u args, URL, env i headers; nijedna ne smije postojati u serijalizovanom inventaru ili warning tekstu.
- [ ] Implementiraj četiri skenera, determinističko sortiranje i validaciju inventara.
- [ ] Dodaj `scan` i čitljiv izvještaj sa brojačima, izvorima i preskočenim stavkama.
- [ ] Pokreni testove i skeniranje eksplicitno podešenih stvarnih izvora; uporedi uzorak s fajlovima na disku.

### Zadatak 3: Katalog koji radi kroz file://

**Fajlovi:** `src/output/write.ts`, `src/output/build-catalog.ts`, `src/ui/index.ts`, `src/ui/styles.css`, `src/ui/template.html`, `scripts/build.mjs`, `tests/output.test.ts`, `tests/browser/catalog.spec.ts`.

**Interfejsi:** `writeSafely(path: string, content: string): Promise<void>`; `buildCatalog(inventory: Inventory, overlay: Overlay, outputPath: string): Promise<void>`.

- [ ] Testiraj JSON embed s `</script><img onerror=...>` naslovom: payload ostaje tekst i ne izvršava se.
- [ ] Implementiraj inline bundle, početni pregled, kombinovane filtere, pretragu, detalje i prikaz duplikata.
- [ ] Dodaj kopiranje/selectable putanju, tastaturni fokus i responsive raspored.
- [ ] Dodaj `refresh` i `open`; fatalno build pisanje ne smije ukloniti stari katalog.
- [ ] Browser test otvara `file://` preko `pathToFileURL`, provjerava pretragu, filter profil+tip, detalje i odsustvo HTTP/HTTPS zahtjeva.
- [ ] Provjeri screenshot na 1440×900 i 390×844; sadržaj mora biti čitljiv bez horizontalnog scrolla cijele stranice.

### Zadatak 4: Bilješke i evidencija zastarjelosti

**Fajlovi:** `src/cli.ts`, `src/output/build-catalog.ts`, `src/maps/analysis-schema.ts`, `tests/output.test.ts`, `config/overrides.json`.

**Interfejsi:** `loadOverlay(path: string): Promise<Overlay>`; `setNote(path: string, id: string, text: string): Promise<void>`; `computeSourceFingerprint(evidenceFiles: string[]): Promise<string>`; `getMapStatus(entry: MapEntry, analysis: ProjectAnalysis): Promise<MapEntry['status']>`.

- [ ] Testiraj da bilješka ostaje nakon refresh-a i promjene opisa skilla.
- [ ] Testiraj nestalu stavku: overlay ostaje, nastaje upozorenje, ne pojavljuje se lažna instalirana stavka.
- [ ] Testiraj promjenu i brisanje evidence fajla: mapa postaje `stale`; nepotpuna evidencija daje `unverified`.
- [ ] Implementiraj `note`, učitavanje overlay-a i status mapa u katalogu.
- [ ] Provjeri bilješku na jednoj stvarnoj stavci kroz CLI i browser.

### Zadatak 5: Lokalna Archify integracija i stvarna mapa

**Fajlovi:** `src/maps/archify.ts`, `src/maps/analysis-schema.ts`, `tests/archify.test.ts`, `data/archify-version.json`, `data/analysis/creative-forge.json`, `data/maps/creative-forge.json`, `data/map-registry.json`, `output/maps/creative-forge.html`.

**Interfejsi:** `renderArchifyMap(options: { cliPath: string; diagramType: string; inputPath: string; outputPath: string }): Promise<{ ok: boolean; diagnostics: string[] }>`; `registerMap(entry: MapEntry): Promise<void>`.

- [ ] Pribavi upstream lokalno, zabilježi verziju/commit i prouči stvarni CLI/sheme.
- [ ] Pokreni upstream doctor i demo. Ako mreža/pribavljanje blokira, završi katalog, zabilježi blokator i ostavi ovaj zadatak nezavršen.
- [ ] Testiraj adapter kroz kontrolisani fake CLI: proslijeđene putanje s razmacima ostaju pojedinačni argumenti; nonzero exit ne zamjenjuje stari HTML.
- [ ] Analiziraj stvarni `creative-forge` po sekciji 6, uz lokalne instrukcije; sačuvaj analysis i Archify JSON.
- [ ] Validiraj i renderuj mapu; inspect screenshot i bar jednu putanju kroz komponente.
- [ ] Registruj relativni HTML link, obnovi katalog i provjeri otvaranje mape preko `file://`.
- [ ] Pokreni stvarni upstream smoke test, pored fake-CLI testa. Fake test sam nije dokaz integracije.

### Zadatak 6: Završna provjera i uputstva

**Fajlovi:** `README.md`, `output/verification.md`, `.gitignore`, `tests/browser/catalog.spec.ts`.

- [ ] U README napiši setup, prve komande, dodavanje izvora, bilješke, refresh i ponovno generisanje mape.
- [ ] Dodaj browser provjeru otvaranja stvarne projektne mape i njenog osnovnog interaktivnog ponašanja prema upstream verziji.
- [ ] Pokreni `npm run check` i `npm run test:e2e` iz `Archify`, nikada iz roditeljskog foldera.
- [ ] Ponovo provjeri sentinel tajne kroz sve generisane izlaze i reportove.
- [ ] Uporedi hashove izvornih konfiguracija prije/poslije rada; ne smiju se promijeniti.
- [ ] Zabilježi verzije alata, komande, rezultate i poznate granice u verification fajl.
- [ ] Ostaviti korisniku funkcionalan index, JSON inventar, stvarnu mapu i kratak izvještaj. Ne označiti demo kao stvarnu projektnu analizu.

## 14. Uputstvo koje vlasnik šalje Codexu

Otvori `Archify` kao radni folder i pošalji sljedeće. Ovaj prompt pokreće buduću implementaciju; izrada ovog dokumenta sama ne instalira niti pravi aplikaciju.

```text
Read plan-izrade-ai-workspace-atlas.md and implement the local AI Workspace
Atlas described in it, task by task.

Use this document as both the product specification and implementation plan.
Read applicable AGENTS.md and CLAUDE.md instructions before working.

Keep all implementation files and generated artifacts inside this Archify
project. Treat scanned projects, source documents and AI configurations as
read-only. Do not change global skills, plugins or MCP settings.

Build the offline catalog first. Then integrate a pinned local Archify copy
and produce one evidence-backed map of an accessible real project.
Inspect upstream schemas and CLI commands instead of inventing them.

Keep configured, documented and unknown state distinct. Never infer that a
globally discovered skill is used by every project. Exclude secret values
from inventory, HTML and logs.

Run the required checks and browser verification. Update the task checkboxes
as work is completed. If Archify or a source is unavailable, complete
unaffected work and report the exact remaining limitation honestly.

Finish with the path to output/index.html, the real project map, commands
for refreshing the catalog, and verification results in BCS.
```

## 15. Poslije prve verzije

Tek nakon stvarne upotrebe razmotriti: Codex TOML adapter prema tadašnjoj stvarnoj shemi, više projektnih mapa, katalog pluginova prema provjerenim registrima i browser editor bilješki uz lokalni server. Svaki dodatak treba da riješi konkretan problem koji se pojavio u korišćenju prve verzije.

Najvažniji prvi rezultat je da korisnik pronađe alat/konfiguraciju kroz pretragu i razumije jedan svoj projekat kroz stvarnu mapu, bez ručnog pretraživanja velikog broja foldera.

Ažurirano: 2026-10-13. Osvježiti ovaj plan kada upstream Archify promijeni CLI/sheme ili se dogovori novi obim projekta.
