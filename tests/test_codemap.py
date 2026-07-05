"""Codemap: complete deterministic structural map + read/commit (AC-16, AC-16b, AC-17..AC-19)."""

import os
import re
import subprocess

from open_review import ai, cli, codemap


def _git(tmp, *a):
    subprocess.run(["git", *a], cwd=tmp, check=True, capture_output=True)


def _init_repo(tmp):
    _git(tmp, "init", "-q")
    _git(tmp, "config", "user.email", "t@example.com")
    _git(tmp, "config", "user.name", "t")
    (tmp / "a.py").write_text("def foo():\n    pass\n")
    _git(tmp, "add", ".")
    _git(tmp, "commit", "-qm", "base")


def test_codemap_is_complete(tmp_path, monkeypatch):
    """AC-16b: every symbol ast-grep finds appears in the map (matches-zero guarded).

    Includes return-type annotations, async, and decorators — the shapes a full-body
    pattern silently drops, which is the whole point of the "map EVERYTHING" invariant.
    """
    (tmp_path / "a.py").write_text(
        "import functools\n\n"
        "def foo() -> int:\n    return 1\n\n"
        "async def aio(x: str) -> None:\n    pass\n\n"
        "@functools.cache\ndef decked():\n    pass\n\n"
        "class Baz:\n    def m(self) -> bool:\n        return True\n"
    )
    (tmp_path / "b.js").write_text("function bar() {}\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    names = {n for lst in codemap._symbols(".").values() for n, _ in lst}
    assert names, "matches-zero guard: the extractor found no symbols"
    assert {"foo", "aio", "decked", "Baz", "m", "bar"} <= names

    doc = codemap.generate(".")
    for name in names:
        assert name in doc, f"codemap omitted symbol {name}"


def test_codemap_resolves_call_graph(tmp_path, monkeypatch):
    """AC-16c: cross-module call edges resolve via imports, deterministically, both ways."""
    (tmp_path / "util.py").write_text("def helper():\n    return 1\n")
    (tmp_path / "main.py").write_text(
        "from util import helper\nimport util\n\n"
        "def run():\n    a = helper()\n    return util.helper()\n"
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    g = codemap._call_graph(".")
    # both the from-import bare call and the qualified call resolve to util.helper
    assert ("util.py", "helper") in g[("main.py", "run")]["calls"]
    # reverse edge is emitted
    assert ("main.py", "run") in g[("util.py", "helper")]["called_by"]

    doc = codemap.generate(".")
    assert "calls:" in doc and "called by:" in doc


def test_codemap_marks_ambiguous_not_guessed(tmp_path, monkeypatch):
    """AC-16c: a bare name shared by two files, neither local nor imported, is marked, not guessed."""
    (tmp_path / "x.py").write_text("def shared():\n    pass\n")
    (tmp_path / "y.py").write_text("def shared():\n    pass\n")
    (tmp_path / "z.py").write_text("def go():\n    return shared()\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    g = codemap._call_graph(".")
    node = g[("z.py", "go")]
    assert "shared" in node["ambiguous"]
    # not silently resolved to either file
    assert ("x.py", "shared") not in node["calls"]
    assert ("y.py", "shared") not in node["calls"]


def test_codemap_module_vars_not_locals(tmp_path, monkeypatch):
    """AC-16d: module-level variables are listed; assignments inside functions are not."""
    (tmp_path / "a.py").write_text(
        "CONFIG = 3\nMAX_RETRIES = 5\n\ndef f():\n    local = 1\n    return local\n"
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    mv = codemap._module_vars(".")
    names = {n for n, _ in mv.get("a.py", [])}
    assert {"CONFIG", "MAX_RETRIES"} <= names
    assert "local" not in names
    assert "CONFIG" in codemap.generate(".")


def test_codemap_is_human_navigable(tmp_path, monkeypatch):
    """AC-16e: signatures, the author's own docstring, and located edges — a human can read it."""
    (tmp_path / "lib.py").write_text(
        'def helper(x, y=2):\n    """Add two numbers and return the sum."""\n    return x + y\n'
    )
    (tmp_path / "app.py").write_text("from lib import helper\n\ndef main():\n    return helper(1)\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    doc = codemap.generate(".")
    assert "helper(x, y=2)" in doc, "signature must be shown"
    assert "Add two numbers and return the sum." in doc, "docstring one-liner must be shown"
    # the cross-file edge must be navigable: name + file:line, not a bare token
    assert re.search(r"helper \(lib\.py:\d+\)", doc), "edges must carry a file:line location"


def test_codemap_enrichment_is_multilanguage(tmp_path, monkeypatch):
    """AC-16e: signatures, doc-comments, and module vars work for every language, not just Python."""
    (tmp_path / "s.go").write_text(
        "package main\n\nconst MaxConns = 10\n\n"
        "// Handle serves a request.\nfunc (s *Server) Handle(r *Req) error {\n\treturn nil\n}\n"
    )
    (tmp_path / "s.rs").write_text(
        "/// Adds two numbers.\nfn add(x: i32, y: i32) -> i32 {\n    x + y\n}\n"
    )
    (tmp_path / "s.js").write_text(
        'const API_URL = "x"\n\n/**\n * Fetches a user by id.\n */\nfunction getUser(id) { return id; }\n'
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    doc = codemap.generate(".")
    # signatures — full declarations, as written, per language
    assert "func (s *Server) Handle(r *Req) error" in doc
    assert "fn add(x: i32, y: i32) -> i32" in doc
    assert "function getUser(id)" in doc and "return id" not in doc  # body cut off
    # doc-comments extracted per convention (// , /// , JSDoc block)
    assert "Handle serves a request." in doc
    assert "Adds two numbers." in doc
    assert "Fetches a user by id." in doc
    # module-level vars for non-Python languages
    assert "MaxConns" in doc and "API_URL" in doc


def test_codemap_ai_descriptions_opt_in_and_iterate(fake_router, tmp_path, monkeypatch):
    """AC-16g: --describe adds AI one-liners for *undocumented* symbols; iterate reuses an
    unchanged symbol's description without re-calling the model (token efficiency)."""
    base_url, ctl = fake_router
    (tmp_path / "a.py").write_text("def _f(x):\n    return x * 2\n")  # no docstring
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_BASE_URL", base_url)
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("MODEL", "fake")
    for v in ("MODEL_GENERATE", "MODEL_EVALUATE", "MODEL_JUDGE"):
        monkeypatch.delenv(v, raising=False)
    ctl({"descriptions": [{"id": 0, "text": "Doubles the input."}]})

    assert "_(ai)_" not in codemap.generate(".", describe=False)  # opt-out: nothing added

    doc = codemap.generate(".", describe=True)
    assert "_(ai)_ Doubles the input." in doc

    # iterate: persist the map, drop the router entirely, regenerate — reuse must be self-sufficient
    codemap.write(".", doc)
    monkeypatch.delenv("LLM_API_KEY")
    doc2 = codemap.generate(".", describe=True)
    assert "Doubles the input." in doc2


def test_codemap_c_call_graph(tmp_path, monkeypatch):
    """AC-16c: C call edges resolve despite C's declarator ambiguity (call-context patterns)."""
    (tmp_path / "m.c").write_text(
        "int compute(int n) { return n * 2; }\n"
        "void log_it(int x) {}\n"
        "int run(int n) {\n    log_it(n);\n    return compute(n);\n}\n"
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    g = codemap._call_graph(".")
    calls = g[("m.c", "run")]["calls"]
    assert ("m.c", "compute") in calls  # return f() form
    assert ("m.c", "log_it") in calls  # statement f() form


def test_codemap_js_import_resolution(tmp_path, monkeypatch):
    """AC-16c: a TS/JS call resolves cross-file via `import { x } from './mod'`."""
    (tmp_path / "util.ts").write_text("export function helper(): number { return 1; }\n")
    (tmp_path / "app.ts").write_text(
        "import { helper } from './util'\n\nfunction run(): number { return helper(); }\n"
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    g = codemap._call_graph(".")
    assert ("util.ts", "helper") in g[("app.ts", "run")]["calls"]
    assert ("app.ts", "run") in g[("util.ts", "helper")]["called_by"]


def test_codemap_declaration_keeps_cpp_scope_operator(tmp_path, monkeypatch):
    """Regression (baseline-found): the `::` scope operator must not truncate the signature."""
    (tmp_path / "w.cpp").write_text("int Widget::compute(int n) { return n; }\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    doc = codemap.generate(".")
    assert "Widget::compute(int n)" in doc  # not cut at the first ':' of '::'


def test_codemap_doc_comment_preserves_content_chars(tmp_path, monkeypatch):
    """Regression (baseline-found): only the comment prefix is stripped, never content chars."""
    (tmp_path / "a.go").write_text("// *important* stuff!\nfunc F() {}\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    doc = codemap.generate(".")
    assert "*important* stuff!" in doc  # leading '*' and trailing '!' survive


def test_codemap_powershell_and_batch(tmp_path, monkeypatch):
    """AC-16f: PowerShell + Batch are ctags-only languages (no ast-grep) — symbols still mapped."""
    (tmp_path / "deploy.ps1").write_text(
        "# Fetches a thing.\nfunction Get-Thing {\n  param($x)\n  return $x\n}\n"
    )
    (tmp_path / "build.bat").write_text("@echo off\n:deploy\n  echo hi\n  goto :eof\n:package\n  echo pkg\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    doc = codemap.generate(".")
    assert "Get-Thing" in doc  # PowerShell function
    assert "Fetches a thing." in doc  # PowerShell `#` doc-comment
    assert "deploy" in doc and "package" in doc  # Batch labels (its callable units)


def test_codemap_lists_every_source_file(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.go").write_text("package main\nfunc doIt() {}\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    monkeypatch.chdir(tmp_path)

    doc = codemap.generate(".")
    assert "a.py" in doc
    assert "sub/b.go" in doc.replace(os.sep, "/")


def test_codemap_read_and_folded_into_prompt(tmp_path, monkeypatch):
    """AC-17: a committed codemap is fed to the reviewer as architectural context."""
    d = tmp_path / ".open-review"
    d.mkdir()
    (d / "codemap.md").write_text("# open-review codemap\n## a.py\n- foo (L1)\n")
    monkeypatch.chdir(tmp_path)

    m = codemap.read(".")
    assert m and "foo" in m
    _system, user = ai._prompt("diff", [], m, None)
    assert "Repository architecture" in user and "foo" in user


def test_codemap_commit_has_skip_ci(tmp_path, monkeypatch):
    """AC-18: an opt-in commit carries a CI-skip marker."""
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["codemap", "--commit"]) == 0
    msg = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"], cwd=tmp_path, capture_output=True, text=True
    ).stdout
    assert "[skip ci]" in msg
    assert os.path.exists(os.path.join(tmp_path, ".open-review", "codemap.md"))


def test_codemap_fork_does_not_commit(tmp_path, monkeypatch):
    """AC-19: an untrusted/fork PR generates the map but never commits it."""
    _init_repo(tmp_path)
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    monkeypatch.chdir(tmp_path)

    assert cli.main(["codemap", "--commit", "--untrusted"]) == 0
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    assert before == after
