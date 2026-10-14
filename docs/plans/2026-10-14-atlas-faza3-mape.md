# Faza 3 — implementacioni plan

Spec: docs/specs/2026-10-14-atlas-faza3-mape-design.md. Izvršavati inline kroz Superpowers executing-plans; vlasnik je odobrio rad do kraja. Sve komande iz Archify foldera, Python preko .venv/Scripts/python.exe.

1. Dodati tests/test_maps.py za strogu analizu, containment, fingerprint i current/stale/unverified. Posmatrati RED. Implementirati src/atlas/maps.py: validate_analysis, source_fingerprint, map_status, load_registry, render_map. Testove ponoviti GREEN.
2. Dodati map CLI i testove: nevalidan project ID/slug, lista argumenta bez shell-a, upstream nonzero čuva izlaze. Implementirati registry/map ciljeve i recovery allowlist za provjerene map/analysis JSON i HTML ciljeve; objava zajedno sa katalogom. Posmatrati RED/GREEN.
3. Renderer/UI: zaseban atlas-maps payload, map status i validiran relativni link. Build/refresh učitavaju registar, računaju status, bez mijenjanja evidence izvora. Testovi unsafe linkova i nestalog projekta.
4. Lokalni upstream doctor/demo; pripremiti demonstracionu analizu i nativni JSON prema stvarnoj shemi. Renderovati, registrovati demo, otvoriti mapu kroz browser, provjeriti mrežu i screenshot. Nema creative-forge/session-miner izvora: dokumentovati da je to demo.
5. README i verificiranje: puni unit/integration/browser suite bez skipova, stvarni zapis rezultata i ograničenja. Bez objave ili kupovine. Buduće opcije iz sekcije 15 originalnog plana nisu automatske obavezne faze.

## Izvršenje 2026-10-14

Zadaci 1–5 implementirani i provjereni. Finalni suite: 156 testova, OK, bez skipova. Realni upstream doctor/demo i finalize standard workflow prolaze, uključujući validate/deliver/check/browser-check. Browser otvara native mapu iz kataloga, bez mrežnih zahtjeva; screenshot pregledan.

Isporučen eksplicitni Atlas demo jer originalni ciljni projekti nisu dostupni. Ručno korisničko prihvatanje iz Faze 1 nije izmišljeno. Detaljan zapis i ograničenja: output/verification-final.md.

Pri pregledu ispravljeni: neispravni endpointi, limit konačne UTF-8 serijalizacije, privatne putanje nakon resolve-a i pogrešan limit inventara. Lokalni sources.current config uveden da rad na ovom računaru ne zavisi od starih putanja; eksplicitni --config ima prednost. Nema globalnih izmjena ili plaćanja.
