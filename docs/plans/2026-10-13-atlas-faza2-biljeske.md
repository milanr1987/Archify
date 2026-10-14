# Atlas Faza 2: bilješke — plan implementacije

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline execution, or superpowers:subagent-driven-development only if the owner explicitly chooses delegation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodavati lokalne bilješke kroz CLI i prikazivati ih u offline katalogu bez gubitka nakon refresh-a.

**Architecture:** Zaseban overlay modul validira bilješke u config/overrides.json. Renderer ugrađuje overlay odvojeno od inventara; CLI objavljuje bilješke i HTML u istoj postojećoj transakciji sa lockom i recoveryjem. Izvorni skeneri i identiteti ostaju isti.

**Tech Stack:** Postojeći Python >=3.12, stdlib, unittest, lokalni Playwright, čisti JS/CSS; bez novih zavisnosti.

**Spec:** `docs/specs/2026-10-13-atlas-faza2-biljeske-design.md`, odobren u razgovoru.

## Global Constraints

- Radni folder: C:\Users\PC\OneDrive\Desktop\Project\Archify. Komande se pokreću samo odatle, interpreterom `.\.venv\Scripts\python.exe`.
- Autoritativni fajl je `config/overrides.json`, lokalni i izuzet iz Gita.
- Limit fajla je 1 MiB; tekst najviše 10.000 znakova, najviše 20 jedinstvenih oznaka po 100 znakova. ID mora biti 64 heksadecimalna znaka.
- Skenirani izvori ostaju samo za čitanje. Bez izmjene globalnih skillova, pluginova ili MCP postavki.
- Sav korisnički tekst ide u DOM preko `textContent`; bez localStorage, servera i mrežnih resursa.
- Iz MCP izvora zadržati postojeću allowlistu; ne prikazivati vrijednosti kredencijala.
- Bez kupovine i dodatne naplate. Ako Codex limit spriječi rad, obavijestiti vlasnika i prekinuti AI zadatak.
- Bilješke nestalih stavki ostaju u overlay-u, bez stvaranja lažnih instaliranih stavki.
- Mape i fingerprint nisu dio ovog plana.

## Review Focus

1. Nevalidan ili prevelik overlay ne smije prepisati izlaze: Task 1 i 4.
2. Oznake bez --tag moraju ostati, a --clear-tags ih eksplicitno uklanja: Task 4.
3. Prekid između objave overlay-a i HTML-a zahtijeva recovery oba fajla: Task 2.
4. Nestala i kasnije vraćena stavka zadržava istu bilješku: Task 4.
5. XSS i BCS dijakritika u bilješci moraju ostati bezbjedni i pretraživi: Task 3 i 5.

## Mapa fajlova

- Novi `src/atlas/overlay.py`: model, validacija, ograničeno čitanje, izmjena i kanonski JSON.
- `src/atlas/paths.py`: putanja overrides.
- `src/atlas/writeout.py`: recovery allowlist za tačno overrides, bez širenja na proizvoljne config fajlove.
- `src/atlas/catalog.py`, `outputs.py`: zaseban overlay payload i validacija.
- `src/atlas/ui/template.html`, `app.js`, `styles.css`: prikaz i pretraga bilješki.
- `src/atlas/cli.py`: note i integracija build/refresh.
- `.gitignore`, `README.md`: privatnost i upotreba.
- Novi `tests/test_overlay.py`; postojeći catalog, writeout, CLI i e2e testovi.

### Task 1: Validirani overlay

**Interfaces:** `Note(text: str, tags: list[str])`, `Overlay(notes: dict[str, Note])`, `OverlayError`; `load_overlay(path: Path) -> Overlay`; `overlay_from_dict(data: object) -> Overlay`; `overlay_to_dict(overlay: Overlay) -> dict`; `canonical_overlay(overlay: Overlay) -> str`; `update_note(overlay: Overlay, item_id: str, *, text: str | None = None, tags: list[str] | None = None, delete: bool = False) -> Overlay`. Funkcije ne mijenjaju ulazni objekat. Novi tekst trimovati; prazne oznake odbiti, ostale trimovati i deduplicirati očuvanjem redoslijeda. ID prihvata oba case-a i kanonizuje u lowercase; kolizije kanonizacije odbiti.

- [ ] Dodati failing unittest testove za nedostajući fajl, roundtrip, nepoznata polja, bool schemaVersion, ne-string tekst/oznake, nevalidan ID i koliziju ID-ja.
- [ ] Dodati testove granica: 10.000/10.001 znakova, 20/21 jedinstvenih oznaka, 100/101 znakova oznake, 1 MiB/1 MiB+1 bajt fajla; prevelik fajl odbiti prije parsiranja.
- [ ] Pokrenuti `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_overlay.py" -v`; potvrditi da pad nastaje zbog nedostajućeg ponašanja.
- [ ] Implementirati navedene interfejse. Greške sadrže kod/putanju, bez sadržaja bilješki. Dodati `AppPaths.overrides` i ignore unos `config/overrides.json`.
- [ ] Ponoviti overlay testove; zahtijevati OK.
- [ ] Pregledati diff; commit samo fajlova ovog zadatka ako je Git root Archify i radni kontekst dozvoljava commit.

### Task 2: Transakcija i oporavak bilješki

**Interfaces:** Novi `overlay_target(paths: AppPaths, overlay: Overlay) -> Target` u outputs.py koristi canonical_overlay i validaciju overlay_from_dict. `_validated_journal` prihvata paths.overrides pored postojeća tri tačna cilja.

- [ ] U test_writeout dodati transakciju overrides+catalog: greška drugog replace-a vraća oba stara fajla; prekid procesa između replace-ova pa recovery vraća oba.
- [ ] Dodati test prvog kreiranja overlay-a: rollback uklanja novi fajl; committed cleanup zadržava oba nova fajla; proizvoljni config cilj u journalu i dalje se odbija.
- [ ] Pokrenuti `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_writeout.py" -v`; potvrditi novi failing slučaj.
- [ ] Implementirati tačan allowlist dodatak i overlay_target bez izmjene lock/rollback protokola.
- [ ] Ponoviti writeout testove; zahtijevati OK i pregledati diff.

### Task 3: Renderer, prikaz i pretraga

**Interfaces:** `render_catalog(inv, inv_hash, overlay: Overlay | None = None) -> str`; `validate_catalog(html, inv_hash) -> None` validira oba payload-a; `catalog_target(paths, inv, inv_hash, overlay: Overlay | None = None) -> Target`. None znači prazan overlay radi kompatibilnosti postojećih poziva. Novi script marker `atlas-overlay`; DOM `.detail-note` i `.note-tags`.

- [ ] Dodati testove renderera: overlay roundtrip, escape `</script>&<>`, nevalidan overlay payload se odbija, originalni inventory hash ostaje isti.
- [ ] Pokrenuti `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_catalog.py" -v` i potvrditi novi failing test.
- [ ] Ugraditi zaseban payload kroz embed_json; prikazivati samo bilješku odabrane postojeće stavke. Dopuniti pretraživi tekst bilješkom i oznakama kroz postojeći fold.
- [ ] Dodati čitljive stilove bez eksternih resursa. Za sav tekst koristiti textContent.
- [ ] Ponoviti catalog testove i zahtijevati OK.

### Task 4: CLI note i lifecycle

**Interfaces:** `_cmd_note(paths: AppPaths, item_id: str, *, text: str | None, tags: list[str] | None, delete: bool) -> int`; zajednički helper za učitavanje postojećeg inventara; `orphan_note_ids(inv: Inventory, overlay: Overlay) -> list[str]` u overlay.py. --clear-tags se mapira na praznu listu, nezadati --tag na None.

- [ ] Dodati CLI testove dodavanja/izmjene/brisanja; odsustvo teksta za novu bilješku odbiti; tags-only izmjena postojeće dozvoljena. --delete je idempotentan za validan ID.
- [ ] Testirati --text/--delete konflikt, --tag/--clear-tags konflikt, nedostajući inventar, nepoznatu stavku pri dodavanju i očuvanje starih izlaza kod nevalidnog overlay-a.
- [ ] Testirati da nezadate oznake ostaju; --clear-tags ih prazni; duplikati --tag se spajaju.
- [ ] Testirati refresh sa promijenjenim opisom i istim ID-jem, nestanak i povratak stavke. build/refresh prijavljuju samo broj orphan bilješki; ne mijenjaju inventar niti njegove warnings. Kod 2 ostaje vezan za djelimično skeniranje.
- [ ] Pokrenuti `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_cli.py" -v`; potvrditi novi failing slučaj.
- [ ] Implementirati parser i CLI helper; note koristi postojeći lock/recovery i objavljuje overlay+catalog zajedno. build/refresh učitavaju overlay prije objave; scan ostaje nezavisan od bilješki.
- [ ] Ponoviti CLI testove i cijeli unit/integration suite; zahtijevati OK, postojeći e2e skip bez ATLAS_E2E prijaviti kao skip.

### Task 5: Browser provjera i dokumentacija

- [ ] Dodati browser fixture bilješku sa XSS tekstom i oznakom `Đurđevak`; test potvrđuje literalni prikaz, pretragu `djurdjevak` i odsustvo HTTP/HTTPS zahtjeva. Test bez overlay-a i dalje radi.
- [ ] Pokrenuti browser test, potvrditi eventualni stvarni pad i ispraviti samo utvrđenu grešku.
- [ ] Dopuniti README komandama note, pravilima oznaka, orphan bilješkama, privatnošću overrides i činjenicom da browser samo čita.
- [ ] Iz Archify foldera pokrenuti puni suite sa postojećim lokalnim browserom:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
$env:ATLAS_E2E = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

- [ ] Za završno prihvatanje zahtijevati OK bez skipa; ako postojeći browser nije dostupan, zabilježiti blokator umjesto tvrditi završetak. Ne instalirati plaćene usluge niti mijenjati naplatu.
- [ ] Zapisati stvarne rezultate u `output/verification-faza2.md`; demonstraciju note raditi na kontrolisanom privremenom inventaru u projektu, bez izmišljenih bilješki vlasnika na stvarnim stavkama.
- [ ] Pregledati finalni diff, status i ignorisanje overrides; sažeti promjene i preostalu korisničku provjeru. Komitovati samo namjenske praćene fajlove ako je dozvoljeno; nikad `git add .` za privatne izlaze.

## Provjera plana

Obuhvaćene su sekcije odobrenog speca: čuvanje/identitet (1), oporavak (2), UI i privatnost (3,5), CLI i orphan lifecycle (4), prihvatanje (1–5). Mape su eksplicitno odložene. Plan ne zahtijeva nove zavisnosti ili plaćene usluge. Izvršenje čeka pregled vlasnika i izbor načina rada.

## Izvršenje 2026-10-14

Vlasnik je odobrio plan i direktno izvršenje u razgovoru. Zadaci 1–4 su implementirani; dokumentacija i nezavisni pregled završeni. Task 5 ostaje djelimično verifikovan: 145 testova, OK, 10 browser skipova; odvojena stvarna Node/Chromium provjera bilješki prolazi. Potpuni Python browser suite blokiran je nekompatibilnim kopiranim Playwright okruženjem i formalno prihvatanje ostaje otvoreno. Detalji: `output/verification-faza2.md`.

Nije pravljen worktree ili commit jer Git nije dostupan; rad ostaje u traženom folderu. Lokalni venv obnovljen iz postojećeg Pythona bez kupovine/preuzimanja. Nema promjena globalnih AI izvora ili konfiguracija. Checklist koraka iznad ostaje originalni plan; ovaj zapis opisuje stvarno izvršenje i njegova odstupanja.

Naknadno, tokom Faze 3, preuzet je besplatan lokalni Python 3.13.3 runtime iz python.org unutar .venv. Playwright blokator je riješen i svih 145 tadašnjih testova prošlo je bez skipova. Faza 2 više nema tehnički browser blokator.
