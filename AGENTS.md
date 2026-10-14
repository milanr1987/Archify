# AGENTS.md — AI Workspace Atlas

- Spec: `docs/specs/2026-10-13-atlas-design.md`. Plan: `docs/plans/2026-10-13-atlas-faza1.md`.
- Komande se pokreću iz ovog foldera, interpreterom `.\.venv\Scripts\python.exe`. Nikad iz roditeljskog foldera.
- Testovi: `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`; browser: vidi README.
- Skenirani fajlovi (profili, configi, projekti) su samo za čitanje. Ne mijenjaj globalne skillove, pluginove ni MCP postavke.
- Iz MCP izvora u izlaz smiju samo: ime, profil, scope, projectPath, transport, executableName, envNames, sourceFormat.
- Iz hookova u izlaz smiju samo: event, matcher, hookCount, hookTypes. Nikad command/prompt/url/headers/env (spec Faze 4).
- UI: sadržaj ide u DOM samo preko `textContent`; nikakvi eksterni resursi.
- `config/sources.local.json`, `config/maps/`, `data/`, `output/`, `.venv/`, `.playwright-browsers/` nisu u gitu. Repo je javan: opisi privatnih projekata ne idu u git. README je na engleskom (odluka vlasnika 2026-10-14); UI ostaje na BCS-u. Bez ličnih imena i putanja u praćenim fajlovima; primjeri koriste `C:\Users\Example`.
- Faze 2–4 imaju vlastite specove u `docs/specs/`. Novi tip podataka ili izvor: prvo novi spec.
