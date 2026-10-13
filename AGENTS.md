# AGENTS.md — AI Workspace Atlas

- Spec: `docs/specs/2026-10-13-atlas-design.md`. Plan: `docs/plans/2026-10-13-atlas-faza1.md`.
- Komande se pokreću iz ovog foldera, interpreterom `.\.venv\Scripts\python.exe`. Nikad iz roditeljskog foldera.
- Testovi: `.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v`; browser: vidi README.
- Skenirani fajlovi (profili, configi, projekti) su samo za čitanje. Ne mijenjaj globalne skillove, pluginove ni MCP postavke.
- Iz MCP izvora u izlaz smiju samo: ime, profil, scope, projectPath, transport, executableName, envNames, sourceFormat.
- UI: sadržaj ide u DOM samo preko `textContent`; nikakvi eksterni resursi.
- `config/sources.local.json`, `data/`, `output/`, `.venv/`, `.playwright-browsers/` nisu u gitu.
- Bilješke i Archify mape su van Faze 1; za njih prvo novi spec.
