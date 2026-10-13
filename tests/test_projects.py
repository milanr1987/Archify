import json

from helpers import TempDirTestCase, write

from atlas.config import parse_config
from atlas.identity import norm_path
from atlas.model import Relation
from atlas.scan.collector import Collector
from atlas.scan.documents import document_title, scan_documents
from atlas.scan.projects import scan_projects


class ProjectTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        ws = self.tmp / "ws"
        write(ws / "proj-node/package.json", json.dumps({
            "name": "proj-node-app", "description": "Node app",
            "scripts": {"start": "node secret-arg.js", "test": "node --test"}}))
        write(ws / "proj-node/README.md", "Uvod\n# Proj Node\n")
        write(ws / "proj-node/AGENTS.md", "bez naslova\n")
        write(ws / "proj-node/.mcp.json", "{}")
        write(ws / "proj-py/pyproject.toml",
              '[project]\nname = "proj-py"\ndescription = "Py tool"\n[project.scripts]\npyt = "x:y"\n')
        write(ws / "notes/README.md", "# Bilješke\n")
        write(ws / ".hidden/package.json", "{}")
        write(ws / "Archify/package.json", "{}")
        write(ws / "extra/run.py", "print(1)\n")
        write(ws / "badjson/package.json", "{")
        write(ws / "dotnet/App.sln", "")
        write(ws / "guide.md", "# Vodič kroz sistem\n")
        self.ws = ws

    def config(self, **extra):
        data = {"workspaceRoot": str(self.ws), "projectRoots": ["."], "extraProjects": ["extra", "nema"],
                "excludeNames": ["Archify"]}
        data.update(extra)
        return parse_config(data)

    def projects(self, c):
        return {i.name: i for i in c.items.values() if i.kind == "project"}

    def test_markers_names_and_types(self):
        c = Collector()
        scan_projects(self.config(), c)
        found = self.projects(c)
        self.assertEqual(set(found), {"proj-node-app", "proj-py", "extra", "badjson", "dotnet"})
        node = found["proj-node-app"]
        self.assertEqual(node.description, "Node app")
        self.assertEqual(node.metadata, {"projectType": "node", "markers": ["package.json"],
                                         "scriptNames": ["start", "test"]})
        self.assertEqual(found["proj-py"].metadata["scriptNames"], ["pyt"])
        self.assertEqual(found["extra"].metadata, {"projectType": "other"})
        self.assertEqual(found["dotnet"].metadata["projectType"], "dotnet")

    def test_script_values_are_not_stored(self):
        c = Collector()
        scan_projects(self.config(), c)
        self.assertNotIn("secret-arg", json.dumps([i.metadata for i in c.items.values()]))

    def test_bad_manifest_and_missing_extra_warn(self):
        c = Collector()
        scan_projects(self.config(), c)
        codes = [w.code for w in c.warnings]
        self.assertIn("bad-manifest", codes)
        self.assertIn("source-missing", codes)

    def test_project_docs_and_mcp_file(self):
        c = Collector()
        result = scan_projects(self.config(), c)
        node = self.projects(c)["proj-node-app"]
        docs = {i.name: i for i in c.items.values() if i.kind == "document"}
        self.assertEqual(set(docs), {"Proj Node", "AGENTS.md"})
        for doc in docs.values():
            self.assertIn(Relation(node.id, doc.id, "documented-by"), c.relations)
            self.assertEqual(doc.metadata, {"referenceStatus": "project-doc"})
        self.assertEqual(result.mcp_files, [(str(self.ws / "proj-node"), str(self.ws / "proj-node/.mcp.json"))])
        self.assertEqual(result.index[norm_path(self.ws / "proj-node")], node.id)

    def test_project_found_twice_is_one_item(self):
        c = Collector()
        scan_projects(self.config(extraProjects=["proj-py"]), c)
        self.assertEqual(len([i for i in c.items.values() if i.name == "proj-py"]), 1)
        self.assertEqual(len(self.projects(c)["proj-py"].locations), 1)


class DocumentTests(TempDirTestCase):
    def test_listed_documents(self):
        write(self.tmp / "guide.md", "# Vodič\n")
        cfg = parse_config({"workspaceRoot": str(self.tmp), "documents": [
            {"path": "guide.md", "title": "Moj vodič"}, {"path": "nema.md", "title": "X"}]})
        c = Collector()
        scan_documents(cfg, c)
        [doc] = list(c.items.values())
        self.assertEqual(doc.name, "Moj vodič")
        self.assertEqual(doc.metadata, {"referenceStatus": "listed"})
        self.assertIn("source-missing", [w.code for w in c.warnings])

    def test_title_from_first_heading_or_none(self):
        self.assertEqual(document_title(str(write(self.tmp / "a.md", "x\n# Naslov  \n"))), "Naslov")
        self.assertIsNone(document_title(str(write(self.tmp / "b.md", "bez naslova\n"))))
        self.assertIsNone(document_title(str(self.tmp / "nema.md")))
