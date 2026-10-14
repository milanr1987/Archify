# Faza 6: neusklađenost i stanje

**Datum:** 2026-10-14
**Status:** implementacija odobrena korisnikovim zahtjevom da poslije speca i plana nastavimo.

## Cilj i granice

Deterministički offline snimak sadržaja skillova, matrice deklarisanih hookova i aktivnosti projekata. Nema LLM-a, mreže, izvršavanja skeniranog koda ili pisanja u izvore. Hash nije sadržaj; Git datum i mtime sesije nisu dokaz stvarnog korištenja projekta. Svi privatni izlazi ostaju u data/ i output/.

## Sadržaj skillova

Svaka Location skilla dobija contentHash (64 mala hex znaka ili `unknown`). SHA-256 ulaz je verzijski prefiks, zatim fajlovi sortirani po relativnoj POSIX putanji: dužina UTF-8 putanje (8 bajtova), putanja, dužina sadržaja (8 bajtova), sirovi bajtovi. Dužine izbjegavaju dvosmisleno spajanje. Uključeni su svi regularni fajlovi, uključujući skrivene, bez izlaznog sadržaja ili liste fajlova. Granice: 1.024 fajla, 16 MiB po fajlu, 64 MiB ukupno, 4.096 ukupnih unosa direktorija, dubina 32. Prekoračenje, promjena tokom čitanja, nečitljiv fajl, poseban fajl, ciklus ili link van stvarnog korijena daju `unknown` i warn. Root može biti već evidentirani link; unutrašnji linkovi smiju samo unutar tog stvarnog root-a. Junction/reparse putanje provjeravaju se realpathom. Keš postoji unutar skeniranja po stvarnom folderu. Revizija 2026-10-14: hladno skeniranje 482 skilla trajalo je 148 s, toplo 21–31 s, jer se svaki fajl otvara pri svakom skeniranju. Zato postoji i trajni keš `data/skill-hash-cache.json` (privatno, van Gita): hash foldera se ponovo koristi samo ako je lista svih fajlova (relativna putanja, veličina, mtime_ns) identična prošloj; svaka promjena imena, veličine ili vremena izmjene znači ponovno čitanje. `unknown` se ne kešira, čuvaju se samo unosi iz zadnjeg skeniranja, a neispravan keš znači prazan keš. Granica: izmjena sadržaja koja zadrži istu veličinu i isti mtime_ns ne bi bila primijećena; to se u praksi ne dešava bez namjernog vraćanja vremena. Realpath provjera se radi samo za linkove i junctione.

Postojeći duplicate_group ostaje grupisanje po imenu. Poređenje sadržaja ima zasebne kohorte: svi samostalni skillovi istog imena; plugin skillovi samo ako su isti naziv plugina + marketplace + poznata verzija. Različiti pluginovi/verzije i samostalni naspram plugin skilla nisu drift. Nepoznat plugin/verzija nije pouzdano uporediv i daje nepoznato. Kohorta sa jednom lokacijom nije dokaz duplikata. Grupa: nepoznato ako bilo koji uporediv hash nedostaje; inače razlikuje se ako neka kohorta ima različite hashove; inače isti. Različit sadržaj prikazuje kratki hash i tačne profile, lokacije i porijeklo/verziju. Filter uključuje samo stvarno različite kohorte; izvještaj posebno navodi drift vlastitih skillova.

## Hook matrica

Inventar dobija sortiranu listu profila iz svih config skillRoots/pluginRegistries/mcpSources, uključujući profile bez stavki. Red je (event, matcher); ćelija agregira hookCount/hookTypes i porijeklo settings/plugin iz postojećih bezbjednih lokacija. Isti deklarisani izvor ne broji se dvaput. Prazna ćelija znači „nema u ovom profilu“ u snimku, ne dokaz da profil nema hook zbog nečitljivog izvora. Postojeća upozorenja ostaju vidljiva. Nema pristupa command/prompt/url/headers/env poljima u novoj obradi. UI tabela je skrolabilna unutar panela, bez horizontalnog page scrolla. Revizija 2026-10-14 (čitljivost): kolone imaju samo profili sa bar jednim hookom, a ostali se navode ispod tabele („Profili bez ijednog hooka: …“), pa informacija ostaje; prazna ćelija je „—“ uz skriven tekst „nema u ovom profilu“ za čitače ekrana. Od 700 px matrica zauzima i prostor liste, ima dugme „Zatvori matricu“, a promjena filtera ili pretrage je zatvara.

## Projekti

Za root sa vlastitim .git markerom Git pozivi su argument liste, shell=False, GIT_TERMINAL_PROMPT=0, GIT_OPTIONAL_LOCKS=0, --no-optional-locks, timeout 5 s po pozivu. core.fsmonitor=false sprečava izvršavanje konfigurisanog monitora. Čitaju se samo log -1 --format=%cI, status --porcelain i rev-parse --abbrev-ref HEAD; stderr se ne izvozi. Bez .git ili pri grešci polja su unknown i info upozorenje. Ne preuzima se Git roditeljskog projekta. dirtyCount je broj porcelain linija (uključuje nepoznate direktorije kao jednu liniju), ne broj svih fajlova.

Do osam worker niti obavlja Git provjere nezavisnih projekata; rezultati se dodaju u determinističkom redoslijedu. Nema keša po HEAD-u jer dirtyCount mora primijetiti radne izmjene. Git se traži na PATH-u, uz postojeći lokalni portable Git kao fallback; ništa se ne preuzima.

Claude session root se izvodi iz config skillRoots čiji je folder skills i roditelj .claude*, te claude-json settings izvora. Samo taj profil/projects/<encoded-root> se pregleda, rekurzivno za *.jsonl, bez praćenja linkova van session foldera. Kodiranje koristi ASCII [A-Za-z0-9]; svaki drugi znak postaje jedan '-', bez spajanja crtica, bez pogađanja/sličnog podudaranja. Kolizije kodiranih putanja među projektima daju unknown/info umjesto tuđe aktivnosti. Sadržaj jsonl se nikada ne otvara. Nedostajuća sesija: unknown, bez tvrdnje o neaktivnosti; nečitljiv direktorij daje info. UTC ISO timestamp čuva najveći mtime, uz profile u sessionTimes. Sortiranje koristi max validnih lastCommitAt/lastSessionAt; nepoznati datumi idu posljednji, izjednačenja po imenu/ID-u.

Na ovoj mašini standardni .claude/.claude-max/.claude-pro nemaju projects foldere; pravilo nije potvrđeno stvarnom sesijom. Potvrđuje se fixture testovima; stvarnu potvrdu dopuniti kada su izvori dostupni.

## Ugovor i kompatibilnost

Schema ostaje 1 uz opciona proširenja: Location.contentHash, Inventory.profiles, skill metadata contentStatus/ownDrift, project metadata lastCommitAt/dirtyCount/branch/lastSessionAt/sessionTimes. Loader prihvata stari inventar bez novih polja i validira nove vrijednosti. Matrica i varijante izvode se iz bezbjednog inventara, nisu paralelni izvor istine. DOM isključivo textContent; CSP i postojeći ID-jevi ostaju.

## Prihvatanje i mjerenje

Testovi: hash redoslijeda/putanje/sadržaja/binarnih fajlova, limiti/linkovi/promjena; kohorte pluginova i unknown; prazni profili i bez tajni; Git timeout/greške/argumenti bez shell-a; jsonl mtime bez čitanja; UTC sortiranje; report i browser filter/matrica/aktivnost bez mreže.

Prije: sources.local.json 0 stavki, 0,002 s; eksplicitni sources.current.json 9 stavki, 0,030 s. Stari config nije podrazumijevani i ne mijenja se. Poslije: isti config i 9 stavki, tri zagrijana mjerenja 0,413 / 0,412 / 0,419 s; Git dio 0,075 / 0,070 / 0,073 s. Git je paralelizovan unaprijed (8 workera), izmjereni dio je ispod 5 s. Prvo hladno mjerenje je bilo 1,638 s; rezultati zavise od filesystem cachea.

Ova mjerenja su u sandboxu, gdje Git ownership zaštita odbija stvarni repo i daje unknown/info. Zasebna odobrena read-only provjera izvan sandboxa potvrdila je stvarne branch/commit/count rezultate i nepromijenjen SHA-256 Git indexa, bez promjene trust konfiguracije. Broj projekata je samo 1; nema tvrdnje o performansama na većem korisničkom inventaru. Tvrdnja oko 2 s nije reproducirana. Privatne putanje/nazivi se ne pišu u ovaj javni spec.

Dodatno: session root se izvodi i iz Claude plugin registra bez skill root-a; session obilazak je ograničen na 10.000 unosa i nečitljiva grana daje unknown/info. Stari inventar bez novih opcionih polja zadržava svoj hash radi kompatibilnosti sa validatorom i oporavkom ranijih izlaza.
