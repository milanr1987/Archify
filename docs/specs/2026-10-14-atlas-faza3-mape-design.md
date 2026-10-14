# Faza 3: lokalne Archify mape i evidencija zastarjelosti

Vlasnik je odobrio nastavak svih faza originalnog plana bez novih međukoraka potvrde. Ovaj spec ispunjava AGENTS.md zahtjev za zaseban spec mapa.

## Obim

Lokalni Python modul validira ProjectAnalysis iz originalnog plana: schemaVersion, projectId, projectRoot, generatedAt, components, edges, evidence i openQuestions. ID-jevi su jedinstveni, reference moraju postojati; evidence putanje su relativne, bez izlaska iz projectRoot poslije realpath provjere, line je pozitivan integer, fileHash je SHA-256. Nečitljiva ili nepotpuna evidencija znači unverified; promjena ili brisanje ranije evidentiranog fajla znači stale; potpuno poklapanje znači current. Fingerprint je SHA-256 kanonski sortiranih parova relativna putanja/hash; ne uključuje vrijeme.

Registar data/map-registry.json povezuje projektni ID sa naslovom, relativnim maps/<slug>.html linkom, analizom, vremenom i fingerprintom. Katalog ugrađuje zaseban map payload, prikazuje status i relativni link samo za postojeći projektni item. Nestali projekat ne postaje lažna instalacija. Build/refresh računaju status iz lokalne evidence evidencije, bez izmjene izvornih projekata.

CLI `map PROJECT_ID --analysis PATH --input PATH --slug SLUG --type workflow|architecture` koristi provjerenu lokalnu upstream verziju u vendor/archify. Node se pronalazi kroz postojeći lokalni Playwright driver ili PATH. Argumenti su lista bez shella, update check je isključen, timeout je 120 sekundi. Upstream validacija mora proći prije renderovanja. Novi HTML se pravi u privatnom staging folderu; ako upstream ili validacija padaju, stari HTML i registar ostaju. HTML, analiza, JSON mapa, registar i katalog objavljuju se zajedno kroz prošireni postojeći lock/journal protokol. Recovery dozvoljava samo tačno imenovane map izlaze sa provjerenim slugom; ne proizvoljne putanje.

Nativna upstream JSON shema i CLI se čitaju sa pribavljene verzije. Ne tvrditi da je generički renderer Archify niti da su lokalni hashovi Git verifikacija. Prva mapa je jasno označen lokalni demo jer creative-forge i session-miner nisu prisutni u trenutnom Project folderu; ne tvrditi da je stvarna mapa tih aplikacija isporučena.

## Granice i privatnost

Bez servera, clouda, plaćanja ili globalnih instalacija. Izvori samo za čitanje. Lokalni vendor, registri, analize i output izuzeti iz Gita. Samo hashes/relativne putanje i ručno sažeti opisi izlaze u analizu; bez sadržaja tajnih fajlova. Evidence fajlove ograničiti na 8 MiB, analizu i registar na 1 MiB. Putanje .env, auth, credentials i skriveni profil folderi ne služe kao evidence.

## Prihvatanje

Unit testovi validacije/containmenta, fingerprinta, promjene/brisanja, fake CLI argumenta sa razmacima i greške koja čuva stare izlaze. Stvarni upstream doctor i demo, validacija i render demo JSON-a. Browser provjera lokalnog linka, statusa, rada bez mrežnih zahtjeva i screenshot mape. Pun Atlas suite bez skipova. Preostala ručna korisnička provjera iz Faze 1 se ne izmišlja.
