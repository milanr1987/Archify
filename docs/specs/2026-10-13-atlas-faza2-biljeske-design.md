# AI Workspace Atlas, Faza 2: lokalne bilješke

Status: prijedlog za pregled vlasnika, implementacija nije započeta.

## Svrha i obim

Vlasnik je zatražio nastavak originalnog plana preko Superpowersa. Sljedeći zadatak originalnog plana obuhvata bilješke i evidenciju zastarjelosti mapa. Pošto Faza 1 nema mape niti njihov registar, ova specifikacija izdvaja bilješke kao prvi samostalan korak. Fingerprint i statusi mapa dobijaju zasebnu specifikaciju zajedno sa Archify integracijom. Ostaje postojeći Python paket i offline HTML katalog.

Korisnik kroz CLI dodaje, mijenja i briše bilješku uz stavku, a u katalogu je čita i pretražuje. Bilješka opstaje nakon osvježavanja i promjene opisa izvora. Skenirani izvori ostaju samo za čitanje.

## Čuvanje i identitet

Autoritativni fajl je `config/overrides.json`, lokalni i izuzet iz Gita. Format: `schemaVersion: 1` i `notes`, mapa postojećih stabilnih ID-jeva stavki u objekte sa poljima `text` i `tags`. Ne mijenjaju se identiteti ni shema skeniranog inventara iz Faze 1.

Nedostajući fajl znači prazne bilješke. Neispravan JSON, nepoznata polja ili neispravni tipovi prekidaju operaciju uz bezbjednu poruku, bez prepisivanja postojeće bilješke ili kataloga. Limit fajla je 1 MiB; tekst najviše 10.000 znakova, najviše 20 jedinstvenih oznaka po 100 znakova. ID mora biti 64 heksadecimalna znaka.

Bilješka nestale stavke ostaje sačuvana. Build/refresh prijavljuje broj takvih bilješki, ali ne pravi lažnu stavku instaliranog alata. Povratak istog ID-ja ponovo povezuje bilješku.

## CLI

- `atlas note ITEM_ID --text "tekst"` dodaje ili mijenja tekst; postojeće oznake ostaju ako nisu zadate.
- Ponovljeni `--tag "oznaka"` zamjenjuje skup oznaka. `--clear-tags` ga prazni; ne može se kombinovati sa `--tag`.
- `atlas note ITEM_ID --delete` uklanja bilješku i ne može se kombinovati sa tekstom ili oznakama.
- Dodavanje zahtijeva stavku u postojećem inventaru i tekst koji nije prazan nakon trimovanja. Brisanje je dozvoljeno i za nestalu stavku. Za novu bilješku oznake su podrazumijevano prazne.
- Komanda koristi postojeći inventar, ne skenira izvore, i regeneriše katalog. Ako inventar nedostaje, traži prethodni scan/refresh.

Pozivi rade kroz postojeći `atlas.cmd` i lokalni `.venv`. Greška vraća 1; uspjeh 0. Postojeći exit kod 2 za djelimično skeniranje ostaje.

## Objavljivanje i oporavak

Učitavanje i izmjena bilješki koriste postojeći međuprocesni lock. Bilješke i novi HTML objavljuju se zajedno preko postojećeg staging/backup/journal mehanizma. Prije proširenja liste ciljeva provjeriti recovery validaciju dozvoljenih putanja. Greška ili prekid ne smiju ostaviti novu bilješku sa starim katalogom; recovery vraća ili završava konzistentan komplet.

Build i refresh učitavaju overlay i ugrađuju ga u HTML kao zaseban validiran JSON payload. Inventar i njegov hash ostaju opis skeniranih izvora; overlay se ne upisuje u inventar. Validacija kataloga provjerava i payload bilješki.

## Interfejs i privatnost

Panel detalja prikazuje bilješku i oznake. Pretraga obuhvata tekst i oznake bilješke. Nema uređivanja kroz browser, localStorage, servera niti mrežnih resursa. Sav korisnički tekst ide u DOM preko `textContent`, a ugrađeni JSON escape-uje HTML graničnike kao u Fazi 1.

Katalog sadrži privatne bilješke i ostaje lokalni izlaz izuzet iz Gita. Ne čitati niti prikazivati vrijednosti kredencijala. Ne mijenjati globalne skillove, pluginove ili MCP postavke.

## Provjera prihvatanja

1. Dodavanje, izmjena, oznake i brisanje rade; neispravni argumenti ne mijenjaju izlaze.
2. Bilješka opstaje nakon refresh-a i promjene opisa uz isti ID.
3. Nestala stavka ne gubi bilješku i ne pojavljuje se kao instalirana.
4. Neispravan overlay ne prepisuje postojeće izlaze.
5. Greška objave i oporavak održavaju konzistentne bilješke i HTML.
6. Browser test potvrđuje prikaz, pretragu, XSS kao običan tekst i odsustvo HTTP/HTTPS zahtjeva.
7. Postojeći unit/integration i lokalni browser testovi prolaze. Rezultati se zapisuju iz stvarnog izvršavanja.

## Finansijska ograničenja

Koristiti postojeće uključene mogućnosti i lokalne alate. Bez kupovine, promjene plana, dodatne naplate ili novih plaćenih servisa. Ako limit zaustavi rad, obavijestiti vlasnika i prekinuti AI zadatak; ne zaobilaziti limit.

## Sljedeći korak

Vlasnik pregleda ovu specifikaciju. Nakon odobrenja napisati implementacioni plan kroz Superpowers writing-plans i predstaviti ga prije implementacije. Arhitektura mapa i evidencija njihove zastarjelosti nisu implementirane u ovom koraku.
