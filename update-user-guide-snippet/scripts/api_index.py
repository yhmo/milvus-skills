#!/usr/bin/env python3
"""Shared API-index consumer for the user-guide snippet tooling.

Loads the per-(sdk, tag) TSV indexes produced by `gen_api_index.py` and answers
API-existence questions without touching the SDK repositories. Used by
`check_snippets.py` and the `run_page_*.py` runners.

Index format (see gen_api_index.py): tab-separated, one symbol per line:
  symbol<TAB>lang<TAB>kind<TAB>owner<TAB>params<TAB>return<TAB>file:line

Queries
  - find(symbol, lang=None) -> [Record]
  - has_symbol(symbol, lang, owner=None) -> bool
  - check_code(lang, code, sdk) -> [UnknownCall]   # parse method calls from a
    code block and report any that are not in the index (heuristic; skips
    known stdlib / local identifiers).

Records support: .symbol .lang .kind .owner .params .return .loc
"""
import os
import re

INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "sdk-tmp", "api-index")

# SDK (as used in --sdk-tag / gen_api_index) -> index 'lang' column and the
# canonical sdk key used in index filenames. `python` is an alias for pymilvus;
# the go SDK lives in the milvus repo (module client/v3) -> filename key `go`,
# and its tags are `client/vX.Y.Z` (path-safe normalization below).
SDK_LANG = {
    "pymilvus": "pymilvus", "python": "pymilvus",
    "java": "java", "node": "node", "go": "go", "cpp": "cpp", "rust": "rust",
}


def sdk_key(sdk):
    """Canonical filename key for an SDK: python->pymilvus; go stays go."""
    return {"python": "pymilvus"}.get(sdk, sdk)


def tag_key(tag):
    """Path-safe tag for index filenames.

    The go SDK lives in the milvus repo and its tags are `client/vX.Y.Z`;
    the index filename drops the `client/` prefix (e.g. go-v3.0.0-beta.tsv).
    """
    if tag.startswith("client/"):
        tag = tag[len("client/"):]
    return tag.replace("/", "-")

# Symbols we never flag even if absent from the index: common receivers,
# stdlib calls, control flow, and known-guide constants.
STD_IGNORE = {
    "client", "session", "schema", "ctx", "context", "cli", "console", "print",
    "println", "printf", "log", "fmt", "len", "range", "make", "append",
    "new", "return", "if", "else", "for", "while", "switch", "case", "break",
    "continue", "def", "import", "from", "as", "try", "except", "finally",
    "raise", "assert", "with", "class", "struct", "interface", "fn", "let",
    "var", "const", "func", "package", "use", "pub", "async", "await", "self",
    "this", "super", "system", "out", "err", "nil", "null", "None", "True",
    "False", "true", "false", "TODO", "Note", "Notes", "progress", "res",
    "resp", "response", "result", "results", "jobId", "job_id", "jobID",
    "index", "indexes", "fields", "field", "data", "vector", "query_vector",
    "database", "db", "collection", "collection_name", "db_name", "name",
    "time", "sleep", "sum", "list", "dict", "set", "str", "int", "float",
    "string", "bool", "ArrayList", "List", "Map", "Set", "HashMap",
    "Arrays", "Collections", "Optional", "System", "TimeUnit", "Thread",
    "std", "string", "vector", "map", "unordered_map", "set", "cout", "cin",
    "cerr", "endl", "nullptr", "make_shared", "shared_ptr", "move", "printf",
    "sprintf", "getenv", "atoi", "to_string", "stoi", "begin", "end", "size",
    "empty", "push_back", "emplace_back", "insert", "find", "count", "clear",
    "reserve", "capacity", "front", "back", "first", "second", "key", "value",
    "push", "pop", "top", "peek", "append", "join", "split", "replace",
    "strip", "lower", "upper", "format", "encode", "decode", "read", "write",
    "open", "close", "flush", "sync", "commit", "rollback", "start", "stop",
    "run", "wait", "notify", "lock", "unlock", "sleep", "yield", "join",
    "equals", "hashCode", "toString", "getClass", "clone", "finalize",
    "wait", "get", "set", "put", "remove", "contains", "isEmpty", "size",
    "getBytes", "getProperty", "getProperty", "load", "loadClass",
    "WithCancel", "WithDeadline", "WithTimeout", "WithValue",
    "addProperty", "add", "addProperty",
    "NewAutoIndex", "NewGenericIndex", "NewFlatIndex", "NewHNSWIndex",
    "NewIvfFlatIndex", "NewDiskANNIndex", "NewAISAQIndex", "NewSparseInvertedIndex",
    "NewRTreeIndex", "NewTrieIndex", "NewInvertedIndex", "NewBitmapIndex",
    "NewSortedIndex", "NewJSONPathIndex", "NewAutoAnnParam", "NewHNSWAnnParam",
}

# Call receivers that we treat as SDK entry points per language, so we only
# flag calls on these receivers (and bare builder chains like `.fieldName(`).
SDK_RECEIVERS = {
    "python": {"client", "session", "schema", "index_params"},
    "java": {"client", "session", "schema", "externalSpec"},
    "javascript": {"client", "session", "schema"},
    "go": {"client", "cli", "schema", "session", "index", "vectorIndex", "categoryIndex"},
    "cpp": {"client", "session", "schema"},
    "rust": {"client", "session"},
}

# Known non-SDK methods on those receivers / builder-method patterns: these are
# API calls, but they live on request objects we cannot resolve. We still check
# them against the index by symbol name only (owner-agnostic).
BUILDER_STRIP = re.compile(r"\.(?:builder|stream|of|asList|singletonList|singleton)\s*\(")


def _load_file(path):
    recs = []
    try:
        with open(path, encoding="utf-8") as f:
            for ln in f:
                parts = ln.rstrip("\n").split("\t")
                if len(parts) < 5:
                    continue
                recs.append({
                    "symbol": parts[0], "lang": parts[1], "kind": parts[2],
                    "owner": parts[3], "params": parts[4],
                    "return": parts[5] if len(parts) > 5 else "",
                    "loc": parts[6] if len(parts) > 6 else "",
                })
    except OSError:
        pass
    return recs


class ApiIndex:
    def __init__(self, sdk, tag, index_dir=INDEX_DIR):
        self.sdk = sdk_key(sdk)
        self.tag = tag
        self.lang = SDK_LANG.get(sdk, sdk_key(sdk))
        self.path = os.path.join(index_dir, f"{self.sdk}-{tag_key(tag)}.tsv")
        self._records = _load_file(self.path)
        self._by_symbol = {}
        for r in self._records:
            self._by_symbol.setdefault(r["symbol"], []).append(r)

    @property
    def loaded(self):
        return bool(self._records)

    def find(self, symbol):
        return self._by_symbol.get(symbol, [])

    def has_symbol(self, symbol, lang=None):
        if lang and lang != self.lang:
            return False
        return symbol in self._by_symbol

    def has_owner_method(self, symbol, owner):
        return any(r["owner"] == owner for r in self._by_symbol.get(symbol, []))

    def __repr__(self):
        return f"<ApiIndex {self.sdk}@{self.tag} {len(self._records)} symbols: {self.path}>"


CALL_RE = re.compile(
    r"(?<![\w.])([A-Za-z_]\w*)\s*\((?:[^()]*|\([^()]*\))*\)",
    re.M | re.S,
)


def check_code(idx, lang, code, sdk):
    """Return list of (call_expr, symbol) API calls found in `code` that are not
    in the index. Heuristic: looks at `receiver.method(...)` and bare
    `builderWord(...)` chains, skipping stdlib / local names.
    """
    if not idx.loaded:
        return []
    receivers = SDK_RECEIVERS.get(lang, set())
    unknown = []
    # receiver.method(...)
    for m in re.finditer(r"(?<![\w.])([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(", code):
        recv, meth = m.group(1), m.group(2)
        if recv in receivers and meth not in STD_IGNORE:
            if not idx.has_symbol(meth):
                unknown.append((m.group(0)[:80], meth))
    # bare builder chains: `.WithXxx(` / `.fieldName(` / `.add_index(` on any
    # dotted receiver that we can't attribute — flag only clearly-SDK builder
    # prefixes, owner-agnostic.
    for m in re.finditer(r"\.\s*(With[A-Za-z_]\w*|add[A-Za-z_]\w*|create[A-Za-z_]\w*|prepare[A-Za-z_]\w*|refresh[A-Za-z_]\w*|get[A-Za-z_]\w*|use[A-Za-z_]\w*|list[A-Za-z_]\w*|drop[A-Za-z_]\w*|describe[A-Za-z_]\w*|load[A-Za-z_]\w*|release[A-Za-z_]\w*|has[A-Za-z_]\w*|insert[A-Za-z_]\w*|upsert[A-Za-z_]\w*|delete[A-Za-z_]\w*|query[A-Za-z_]\w*|search[A-Za-z_]\w*|hybrid[A-Za-z_]\w*)\s*\(", code):
        meth = m.group(1)
        if meth not in STD_IGNORE and not idx.has_symbol(meth):
            unknown.append((m.group(0)[:80], meth))
    # dedupe preserving order
    seen, out = set(), []
    for expr, sym in unknown:
        if (expr, sym) not in seen:
            seen.add((expr, sym))
            out.append((expr, sym))
    return out


def resolve_index(sdk, tag, index_dir=INDEX_DIR):
    """Return an ApiIndex, or None if the index file is missing."""
    idx = ApiIndex(sdk, tag, index_dir)
    return idx if idx.loaded else None


if __name__ == "__main__":
    import sys
    sdk, tag = sys.argv[1], sys.argv[2]
    idx = resolve_index(sdk, tag)
    if not idx:
        print(f"no index for {sdk}@{tag}; run gen_api_index.py first")
        sys.exit(1)
    print(idx)
    for sym in sys.argv[3:]:
        print(f"{sym}:")
        for r in idx.find(sym):
            print(f"  {r['kind']:<8} {r['owner']:<32} {r['params']:<50} {r['loc']}")
