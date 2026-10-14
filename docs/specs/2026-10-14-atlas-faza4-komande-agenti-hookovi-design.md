# Faza 4: komande, agenti i hookovi u katalogu

**Datum:** 2026-10-14
**Status:** odobreno u razgovoru ("popravi sve" iz pregleda projekta).

## Cilj

Katalog pokazuje i slash komande, subagente i hookove, po profilu i porijeklu, uz ista pravila privatnosti kao za MCP. Ništa se ne izvršava i ne mijenja.

## Izvori

Bez novih polja u configu. Izvori se izvode iz postojećih:

- **Komande i agenti, samostalni:** za svaki `skillRoots` unos čije je ime foldera `skills`, susjedni `commands/` i `agents/` (npr. `~\.claude\skills` → `~\.claude\commands`, `~\.claude\agents`). Nepostojeći folder se tiho preskače, jer većina profila ga nema.
- **Komande i agenti iz pluginova:** `<installPath>\commands\` i `<installPath>\agents\`, samo kad je plugin prošao postojeću provjeru containmenta. Relacija `plugin contains command|agent`.
- **Hookovi:** ključ `hooks` iz `claude-json` izvora (`settings.json`) i `<installPath>\hooks\hooks.json` pluginova.

Komanda je svaki `*.md` u `commands/` do dubine 3; podfolderi daju namespace (`git/commit.md` → `git:commit`). Agent je svaki `*.md` direktno ili do dubine 2 u `agents/`. Linkovi i limiti fajlova (1 MiB) isti su kao za skillove.

## Model

- `KINDS` dobija `command`, `agent`, `hook`.
- Komanda/agent: ID = realpath fajla (kao skill), lokacija nosi profil, `root_label` i `origin` (`standalone` ili `plugin:<id>`). Ime: komanda iz putanje, agent iz frontmatter `name` ili imena fajla. Opis iz frontmatter `description` (strogo pa blaže čitanje), 500 znakova. Metadata: nema.
- Hook: jedan item po (profil, izvor, event, matcher). ID = `profile | realpath izvora | event | matcher`. Ime: `Event` ili `Event · matcher`. Metadata: `event`, `matcher`, `hookCount`, `hookTypes` (lista, npr. `command`, `prompt`).
- **Privatnost hookova:** nikad ne izlaze `command`, `prompt`, `url`, `headers`, `env` ni bilo koji drugi sadržaj hook stavke. Event i tip moraju proći `^[A-Za-z][A-Za-z0-9_-]{0,63}$`, inače `unknown`; matcher se čisti i skraćuje na 100 znakova. Sentinel test pokriva ovo isto kao za MCP.

## UI

Novi tipovi u brojačima, filteru tipa, listi i detaljima. Filter porijekla (samostalan/plugin) važi za skillove, komande i agente. Hook ima napomenu "Deklarisan u konfiguraciji; katalog ne provjerava da li se izvršava."

## Prihvatanje

Unit testovi skenera (samostalno, plugin, namespace, nepostojeći folder, blagi frontmatter), sentinel test hookova, validacija modela za nove kindove, pun suite sa browser testovima bez skipa i stvarni refresh na ovom računaru.
