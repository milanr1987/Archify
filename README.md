# Archify: AI Workspace Atlas

A local, offline catalog of everything in your AI coding setup: projects, skills, plugins, MCP servers, slash commands, subagents, hooks and documents across all your Claude Code and Codex profiles. It adds private notes, project maps, skill drift detection and project activity on top.

The result is a single HTML file (`output/index.html`) that opens with a double click. Search, filters, details and "copy path" work without a server or an internet connection.

- **Local only.** No subscription, hosting or API key. Internet is needed once, to download free dependencies.
- **Read-only.** The scanner never runs your projects, skills or commands and never changes scanned files.
- **Private by design.** Each computer builds its own inventory. Your paths, notes and catalog never go into Git.

> The catalog UI is in Bosnian/Croatian/Serbian. UI labels are quoted below with an English translation where it helps.

## Who it is for

Anyone who uses Claude Code (one or several profiles such as `~/.claude`, `~/.claude-work`) and optionally Codex, and has lost track of which skill, plugin, MCP server or hook lives where. Clone it, run setup, and the catalog shows **your own** machine. Nothing from the author's machine is included.

**Requirements and limitations**

- Windows only (`setup.ps1`, `atlas.cmd`). The Python core is portable, but no macOS/Linux launcher is provided.
- Python 3.12+ and any modern browser. Node.js 18+ only for the optional project maps.
- The catalog UI is in Bosnian/Croatian/Serbian; this README and the code are in English.
- Reads the standard Claude Code and Codex file layouts. Other tools are not scanned.

## Contents

- [Who it is for](#who-it-is-for)
- [Quick start](#quick-start)
- [Daily use](#daily-use)
- [What the catalog shows](#what-the-catalog-shows)
- [Command reference](#command-reference)
- [Configuration](#configuration)
- [Notes](#notes)
- [Project maps](#project-maps)
- [Accuracy and privacy](#accuracy-and-privacy)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Development and tests](#development-and-tests)
- [Project layout](#project-layout)
- [License](#license)

## Quick start

Requirements: Windows, **Python 3.12+** (3.13 recommended) and a browser. Git is only needed to clone; GitHub **Code → Download ZIP** works too.

```powershell
git clone https://github.com/milanr1987/Archify.git
cd Archify
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

Setup creates a local `.venv`, installs the package, writes your config, builds the first catalog and puts an **"AI Atlas"** shortcut on your Desktop. The `ExecutionPolicy` flag applies to that one call only; your system policy is not changed.

Setup options:

| Option | Effect |
|---|---|
| `-PythonExe "C:\path\to\python.exe"` | Use a specific Python |
| `-WithMaps` | Also install the pinned Archify renderer for [project maps](#project-maps) |
| `-Development` | Also install Playwright and a local Chromium for browser tests |
| `-NoShortcut` | Skip the Desktop shortcut |

Without the setup script:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\atlas.cmd init
.\atlas.cmd refresh
.\atlas.cmd open
```

Run setup on every new computer. Do not copy `.venv` between machines. The package is an editable install meant to run from this folder, not a portable wheel.

## Daily use

**Double-click "AI Atlas" on your Desktop.** It refreshes the catalog and opens it in your browser, with no terminal window. If something fails, the error appears in a Windows message box. To recreate the shortcut: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\create_shortcut.ps1`.

From a terminal in the Archify folder:

```powershell
.\atlas.cmd refresh   # rescan everything and rebuild the catalog
.\atlas.cmd open      # open the catalog
```

If a browser tab is already open, press **Ctrl+F5** after a refresh to load the new file.

Keyboard: `/` focuses search, arrow keys move through the list, `Enter` opens details, `Esc` closes details or clears the search.

## What the catalog shows

| Area | What it does |
|---|---|
| **Counters** (top) | Totals per type. Click one to filter. |
| **Search** | Matches name, description, paths, metadata and notes. Case and diacritics are ignored (`č` = `c`, `đ` = `dj`). |
| **Filters** (left) | Type, profile (`claude`, `max`, `pro`, `agents`, `codex`), origin (standalone or from a plugin), duplicates only, linked only, "Samo različit sadržaj" (different content only). Profile, origin and link filters must match the **same** location. |
| **"Grupiši isto ime"** (group same name) | On by default. The same skill, plugin or hook in several profiles becomes one row with all profiles and a `×N` badge. Details list every instance with its profile, version and origin. |
| **Sorting** | By name, or "Zadnja aktivnost projekta" (latest project activity: last commit or last Claude session). |
| **Details** (right) | Every location with a copy button, profiles, origin, metadata, related items (for example "Dio plugina", part of plugin), the item ID for notes, and the project map link. |
| **"Matrica hookova"** (hook matrix) | Which hook (event and matcher) exists in which profile, with count, type and settings/plugin origin. Only profiles with at least one hook get a column; the rest are listed under the table. "—" means not found in this snapshot. It uses the list area; close it with "Zatvori matricu", `Esc`, or by changing a filter or search. |

### Skill drift

Each skill location gets a SHA-256 of its whole folder (content is never exported). Copies that should be identical are compared:

- standalone skills of the same name with each other;
- plugin skills only within the same plugin, marketplace and known version.

Different plugin versions are not drift. The filter "Samo različit sadržaj" shows only groups whose copies really differ, and the details show each variant's short hash, profile and path. Limits: 1,024 files, 16 MiB per file, 64 MiB per skill. Unreadable or unsafe folders give `unknown` and a warning.

### Project activity

For projects with their own `.git`, the catalog shows branch, number of uncommitted changes (`git status --porcelain` lines) and last commit date. It also shows the newest Claude session file time per profile. Git runs read-only, with a 5 s timeout, no optional locks and no fsmonitor. Session `.jsonl` files are never opened; only their modification time is read. `unknown` does not mean inactive.

### What gets discovered

| Type | Source |
|---|---|
| Projects | Folders under `projectRoots` (see [Configuration](#configuration)) |
| Skills | `SKILL.md` folders in each skill root and inside installed plugins |
| Plugins | `installed_plugins.json` of each Claude profile |
| MCP servers | `.claude.json`, `settings.json`, project `.mcp.json` and Codex `config.toml` |
| Commands and agents | `commands/` and `agents/` next to each `skills` root, and inside plugins. `git/commit.md` becomes `git:commit`. |
| Hooks | The `hooks` key of Claude `settings.json` and plugin `hooks/hooks.json` |
| Documents | Listed documents plus each project's `README.md`, `AGENTS.md`, `CLAUDE.md` |

Skill frontmatter that is not strict YAML (for example an unquoted `Arguments: x` inside `description`) is read leniently, the same way Claude Code reads it, with an `info` note `lenient-frontmatter`. Only if that also fails does the item fall back to its folder name with a warning.

## Command reference

All commands run through `atlas.cmd`, which always uses the local `.venv` and works from any folder.

| Command | What it does |
|---|---|
| `init [--config PATH]` | Create `config/sources.local.json` if it does not exist. Never overwrites. |
| `scan [--config PATH]` | Write `data/inventory.json` and `data/scan-report.md`. |
| `build` | Rebuild `output/index.html` from the existing inventory. |
| `refresh [--config PATH]` | `scan` + `build`. |
| `open` | Recover an interrupted publish if needed, then open the catalog. |
| `launch` | `refresh` + `open` without a console; errors appear in a message box. Used by the Desktop shortcut. |
| `note ITEM_ID ...` | Add, change or delete a private note. See [Notes](#notes). |
| `map PROJECT_ID ...` | Validate and publish a project map. See [Project maps](#project-maps). |

`scan` and `refresh` first print `Config: <path>`, the config actually used. A relative `--config` path is resolved from the Archify folder, not the current directory.

Exit codes: `0` success, `2` partial result with warnings (outputs are written), `1` error (previous outputs are kept).

## Configuration

`init` writes `config/sources.local.json` for the current computer. It is private and not in Git; `config/sources.example.json` shows the format.

| Key | Meaning |
|---|---|
| `workspaceRoot` | Absolute path. Relative paths below are resolved from it. |
| `projectRoots` | Folders to search for projects. |
| `projectDepth` | How many levels below each root to search (1 to 5, default 1). |
| `extraProjects` | Extra project folders that have no marker. |
| `excludeNames` | Folder names to skip anywhere (for example `node_modules`, or a temporary folder). |
| `skillRoots` | `path`, `profile`, `label` for each skills folder. |
| `pluginRegistries` | `path` to `installed_plugins.json` and `profile`. |
| `mcpSources` | `path`, `profile` and `format`: `claude-json`, `mcp-json` or `codex-toml`. |
| `documents` | `path` and `title` of extra documents. |

**Project discovery.** A folder is a project if it has a manifest (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `.sln`, `.csproj`) or a `.git`, `CLAUDE.md` or `AGENTS.md`. The scanner does not look inside manifest projects (workspace packages are not separate projects). It does look inside git or CLAUDE.md projects, so a repository and the projects in it are found together. Hidden folders are skipped.

On a new computer, `init` fills `projectRoots` with the common project folders that exist there (Desktop, Documents, OneDrive, WebstormProjects, PycharmProjects, IdeaProjects, `source\repos`, Projects, code, dev, repos, GitHub) and sets `projectDepth` to 3. Projects show up without manual setup.

`init` also detects your profiles: `~/.agents/skills`, every `~/.claude` and `~/.claude-<name>` folder (profile `claude` or `<name>`, with its skills, plugin registry, `settings.json` and `.claude.json`) and `~/.codex/config.toml`. Only sources that exist are written, so a fresh install has no "missing source" warnings. `extraProjects` and `documents` start empty; add your own. `init` never overwrites an existing config: delete `config/sources.local.json` and run `init` again to regenerate it.

## Notes

Every item shows its ID in the details panel. Use it with the `note` command:

```powershell
.\atlas.cmd note ITEM_ID --text "My note" --tag "useful"
.\atlas.cmd note ITEM_ID --text "New text"      # tags are kept
.\atlas.cmd note ITEM_ID --clear-tags
.\atlas.cmd note ITEM_ID --delete
```

`--tag` can be repeated and replaces the tag set. Without `--tag`, existing tags stay. `--delete` cannot be combined with other options.

Notes live in `config/overrides.json` (private, not in Git) and are published together with the catalog, under the same lock and recovery as every other output. They survive refreshes. If an item disappears, its note is kept and counted as orphaned; it comes back when the same ID returns. Limits: 10,000 characters of text, 20 tags of up to 100 characters, 1 MiB file. The browser only shows and searches notes. Do not put secrets in notes: their text is embedded in the local HTML.

## Project maps

Project maps are workflow diagrams rendered by the open-source [Archify renderer](https://github.com/tt-a1i/archify) (MIT). They need **Node.js 18+** on PATH or the Node bundled with Playwright. Install the pinned renderer once:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -WithMaps
```

The version, commit and the SHA-256 of the download are pinned in `config/archify-upstream.json`. The installer refuses an archive whose hash does not match and then installs nothing. The renderer lives in `vendor/archify` (not in Git), with no global install and no update check.

**Describing a map.** Each map is a private file `config/maps/<slug>.json` (not in Git, because this repository is public). It names the catalog project, a title, lanes, and components; each component points to a source file and a line of text that marks the evidence. The field format is shown in `tests/test_mapspec.py` and `docs/specs/2026-10-14-atlas-faza5-pronalazenje-grupisanje-pokretanje-design.md`.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tools\make_map.py my-project       # one map
.\.venv\Scripts\python.exe tools\make_map.py --all            # every described map
.\.venv\Scripts\python.exe tools\make_map.py --stale          # only maps that are not current
```

The tool reads the project's files, records lines and SHA-256 hashes in `data/map-input/<slug>/analysis.json`, publishes the map and runs the renderer's `finalize` checks. Run it after `refresh`.

**Map status** in project details: "Aktuelna" (current), "Zastarjela" (stale: an evidence file changed or was deleted) or "Neprovjerena" (unverified: evidence incomplete or unreadable). Status compares local file hashes with the saved analysis; it is not a check against a Git commit.

The lower-level command, if you write the inputs yourself:

```powershell
.\atlas.cmd map PROJECT_ID --analysis data/my-analysis.json --input data/my-map.json --slug my-project --type workflow
```

`--type` is `workflow` or `architecture`. The command validates and renders in staging, then publishes the HTML, both JSON inputs, the map registry and the catalog together. On error, the previous outputs stay.

## Accuracy and privacy

- The catalog is a snapshot of the disk at scan time. An MCP server "declared in configuration" is not proof that it runs; a skill on disk is not proof that it is loaded in a session; the same hash is not proof of use.
- Skills are not linked to projects automatically. Links keep the logical path, the target and the profile.
- From MCP configs only descriptive fields are exported: name, profile, scope, project path, transport, executable name and environment variable **names**. Never `args`, env values, URLs or headers.
- From hooks only event, matcher, count and type are exported. Never `command`, `prompt`, `url`, `headers` or `env`.
- The page loads nothing from the network (strict CSP); all text goes into the page as plain text.
- `config/sources.local.json`, `config/overrides.json`, `config/maps/`, `data/`, `output/`, `.venv/`, `.playwright-browsers/`, `vendor/` and `.tools/` are not in Git. Copy notes to another computer yourself if you want them; item IDs depend on local paths.
- Claude Code may delete old sessions according to `cleanupPeriodDays`, so deleted sessions are not in the snapshot ([Claude Code settings](https://code.claude.com/docs/en/settings)).

**Safe publishing.** Outputs are prepared in staging and published with backups and a journal, so an interrupted run is rolled back or completed on the next command. Parallel runs are refused by a lock. The lock file may stay on disk after a run; the OS lock decides ownership. Recovery does not guarantee durability after a power loss. Do not delete recovery backups or the journal by hand while Atlas runs.

## Performance

Skill hashes are cached in `data/skill-hash-cache.json` (private). A skill's files are read again only when a file name, size or modification time in its folder changes. The first scan on a new computer is slower because every file is read (Windows Defender checks each file it opens); later scans take a few seconds.

If one project always shows Git `unknown` and refresh waits about 5 s, that project's Git index is probably stale (for example after copying the folder). Running `git status` once inside that project refreshes the index. Atlas itself never writes to your repositories.

## Troubleshooting

| Problem | Fix |
|---|---|
| Python not found | Run setup with `-PythonExe` and the full path to `python.exe`. |
| `.venv` missing | Run setup again. Do not copy an old environment. |
| Empty catalog or many warnings | Point `config/sources.local.json` at the sources you really use, then `refresh`. |
| A folder you do not want shows up as a project | Add its name to `excludeNames`. |
| Browser shows an old version | Press Ctrl+F5, or open the catalog through the shortcut. |
| Maps do not render | Check Node.js and `vendor/archify` (`setup.ps1 -WithMaps`). Never bypass the renderer's path-safety checks. |

A GitHub login is only needed to push or to clone a private copy, not for local use.

## Development and tests

```powershell
# unit and integration tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v

# include browser tests (after setup.ps1 -Development)
$env:PYTHONUTF8 = "1"
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
$env:ATLAS_E2E = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Tests use fake configs with sentinel secrets and check that none of them reach any output. Browser tests open the catalog over `file://` and fail on any network request. Screenshots and performance numbers go to `output/e2e/`. The search latency target is a p95 under 50 ms for 2,000 items on a local machine; CI on GitHub runs the same suite on Windows on every push with a looser limit (`ATLAS_PERF_P95_MS=200`) because shared runners are slower.

Rules for contributors and AI agents are in `AGENTS.md`. Each phase has a spec in `docs/specs/` and, where needed, a plan in `docs/plans/`. A new data type or source needs a spec first.

## Project layout

| Path | Contents |
|---|---|
| `src/atlas/` | CLI, scanners, notes, maps, state checks and the offline UI (`ui/`) |
| `tests/` | Unit, integration and browser tests (`tests/e2e/`) |
| `docs/specs/`, `docs/plans/` | Specifications and plans for phases 1 to 6 |
| `config/sources.example.json` | Example source config |
| `config/archify-upstream.json` | Pinned map renderer version and archive hash |
| `setup.ps1`, `atlas.cmd` | Install and daily use |
| `tools/` | Map tool, Desktop shortcut, renderer installer, verification helpers |
| `.github/workflows/ci.yml` | CI: full test suite on Windows on every push |

**Scope.** Phase 1: catalog. Phase 2: local notes. Phase 3: project maps and staleness. Phase 4: commands, agents and hooks. Phase 5: project discovery, grouping and the no-terminal launcher. Phase 6: skill drift, hook matrix and project activity. There is no server, no cloud and no editing in the browser.

## License

MIT, see [LICENSE](LICENSE). The optional map renderer [Archify](https://github.com/tt-a1i/archify) is a separate MIT project, downloaded at setup and not included in this repository.
