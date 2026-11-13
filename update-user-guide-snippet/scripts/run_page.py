#!/usr/bin/env python3
"""Run the python snippets of a user-guide page against a live Milvus server.

Each page is verified against ITS OWN isolated collection(s): every collection
name the page references (a known fixture OR the page's own placeholder name)
is rewritten to a page-unique name, seeded per the page's needs, executed, and
dropped after the run. No shared fixture survives between pages, so a page can
never be affected by (or affect) another page's schema/state — a dim or field
that one page's index type requires cannot leak into another page's run.

Usage:
  python3 run_page.py <page.md>                    # auto-seed referenced collections (isolated per page)
  python3 run_page.py <page.md> <seed.py> [..]     # also exec extra seed snippets (isolated too)
  python3 run_page.py <page.md> --keep <name>      # keep a page collection after the run (debugging)

Exit code is non-zero if any non-empty block fails.
"""
import os
import re
import sys
import traceback

try:
    from pymilvus import Function, FunctionType
except Exception:
    # Function/FunctionType are also injected via the exec prelude; module-level
    # import is only for the generic seed engine's BM25/sparse specs.
    Function = None
    FunctionType = None

URI = "http://localhost:19530"
TOKEN = "root:Milvus"

KEEP = {"quick_setup"}  # opt-out: names that survive a run (see --keep)


def _pick_dim_for_page(md, default=8):
    """Pick a vector dim that satisfies the page's own index constraints.

    For PQ-family docs (m subquantizers) dim must be a multiple of m; use a
    multiple that keeps the fixture small but valid (dim == m when m is already
    a sensible dimension, else a fixed large multiple).
    """
    m = re.search(r'["\']?m["\']?\s*:\s*(\d+)', md)
    if m:
        mval = int(m.group(1))
        return max(default, mval)
    return default


# ---------------------------------------------------------------------------
# Data-driven collection specs.
#
# Adding support for a new collection name is a DATA change (one entry below),
# not a new function: every spec is rendered by the generic `_seed_from_spec`
# engine below. A spec describes:
#   fields    : list of (name, datatype-keyword, kwargs) for schema.add_field
#   index     : optional dict passed to prepare_index_params().add_index(...)
#   index_use : "create" (index included at create_collection) | "doc" (the doc
#               builds its own index; seed must NOT pre-create one)
#   rows      : int count, or callable(client, DataType, name, dim) -> rows
#   partitions: optional list of partition names
#   load      : bool — whether to load right after seeding (default True)
#   dim_fn    : optional callable(md) -> int, to size the float vector per page
# ---------------------------------------------------------------------------

def _gen_float_rows(count, vec_field, dim):
    return [{"id": i, vec_field: [0.1] * (i % 5) + [0.2] * (dim - (i % 5))}
            for i in range(count)]


def _gen_quick_setup_rows(client, DataType, name, dim):
    """Standard quick_setup data (mirrors the Insert Entities doc):
    id 0-9 in the default partition, id 10-19 in `partitionA`, plus ids
    551/296/43 used by the Primary-Key Search snippets.
    """
    colors = ["pink_8682", "red_7025", "orange_6781", "pink_9298", "red_4794",
              "yellow_4222", "red_9392", "grey_8510", "white_9381", "purple_4976"]
    vectors = [
        [0.3580376395471989, -0.6023495712049978, 0.18414012509913835, -0.26286205330961354, 0.9029438446296592],
        [0.19886812562848388, 0.06023560599112088, 0.6976963061752597, 0.2614474506242501, 0.838729485096104],
        [0.43742130801983836, -0.5597502546264526, 0.6457887650909682, 0.7894058910881185, 0.20785793220625592],
        [0.3172005263489739, 0.9719044792798428, -0.36981146090600725, -0.4860894583077995, 0.95791889146345],
        [0.4452349528804562, -0.8757026943054742, 0.8220779437047674, 0.46406290649483184, 0.30337481143159106],
        [0.985825131989184, -0.8144651566660419, 0.6299267002202009, 0.1206906911183383, -0.1446277761879955],
        [0.8371977790571115, -0.015764369584852833, -0.31062937026679327, -0.562666951622192, -0.8984947637863987],
        [-0.33445148015177995, -0.2567135004164067, 0.8987539745369246, 0.9402995886420709, 0.5378064918413052],
        [0.39524717779832685, 0.4000257286739164, -0.5890507376891594, -0.8650502298996872, -0.6140360785406336],
        [0.5718280481994695, 0.24070317428066512, -0.3737913482606834, -0.06726932177492717, -0.6980531615588608],
    ]
    default_rows = [{"id": i, "vector": vectors[i], "color": colors[i]} for i in range(10)]
    part_rows = [{"id": i + 10, "vector": vectors[i], "color": colors[i]} for i in range(10)]
    pk_rows = [
        {"id": 551, "vector": [0.1, 0.2, 0.3, 0.4, 0.5], "color": colors[0]},
        {"id": 296, "vector": [0.2, 0.2, 0.3, 0.4, 0.5], "color": colors[1]},
        {"id": 43, "vector": [0.3, 0.2, 0.3, 0.4, 0.5], "color": colors[2]},
    ]
    client.insert(name, default_rows)
    client.insert(name, part_rows, partition_name="partitionA")
    client.insert(name, pk_rows)
    client.flush(name)
    return []


COLLECTION_SPECS = {
    "quick_setup": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("color", "VARCHAR", {"max_length": 512}),
        ],
        "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "IP"},
        "index_use": "create",
        "partitions": ["partitionA"],
        "rows": _gen_quick_setup_rows,
    },
    "my_collection": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("color", "VARCHAR", {"max_length": 512}),
            ("likes", "INT64", {}),
            ("price", "DOUBLE", {}),
            ("rating", "INT64", {}),
            ("category", "VARCHAR", {"max_length": 64}),
            ("docId", "INT64", {}),
            ("chunk", "VARCHAR", {"max_length": 512}),
        ],
        "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "COSINE"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: _gen_rows_my_collection(dim),
    },
    # Load & Release page: "Load Specific Fields" uses my_id/my_vector field names.
    "my_collection_myid": {
        "fields": [
            ("my_id", "INT64", {"is_primary": True}),
            ("my_vector", "FLOAT_VECTOR", {"dim": 5}),
            ("color", "VARCHAR", {"max_length": 512}),
        ],
        "index": {"field_name": "my_vector", "index_type": "AUTOINDEX", "metric_type": "COSINE"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"my_id": i, "my_vector": [0.1 * (i % 5), 0.2, 0.3, 0.4, 0.5], "color": "c%d" % i}
            for i in range(5)
        ],
    },
    # Alter Collection Field page: my_collection has varchar/array/doc_chunk fields.
    "my_collection_alter": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("varchar", "VARCHAR", {"max_length": 512}),
            ("array", "ARRAY", {"element_type": "VARCHAR", "max_capacity": 8,
                                 "max_length": 32}),
            ("doc_chunk", "VARCHAR", {"max_length": 512}),
        ],
        "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "COSINE"},
        "index_use": "create",
        "load": False,  # alter field props requires the collection NOT loaded
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "vector": [0.1, 0.2, 0.3, 0.4, 0.5], "varchar": "v%d" % i,
             "array": ["a%d" % i], "doc_chunk": "c%d" % i} for i in range(5)
        ],
    },
    # Upsert Entities page: my_collection has id/vector/title/issue (no color).
    "my_collection_upsert": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("title", "VARCHAR", {"max_length": 512}),
            ("issue", "VARCHAR", {"max_length": 128}),
        ],
        "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "COSINE"},
        "index_use": "create",
        "partitions": ["partitionA"],
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "vector": [0.1 * (i % 5), 0.2, 0.3, 0.4, 0.5],
             "title": "t%d" % i, "issue": "vol.%d" % (i + 1)} for i in range(10)
        ],
    },
    # Primary-Key Search page: my_collection carries the pk ids 551/296/43.
    "my_collection_pk": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("color", "VARCHAR", {"max_length": 512}),
            ("likes", "INT64", {}),
            ("docId", "INT64", {}),
        ],
        "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "COSINE"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"id": 551, "vector": [0.1, 0.2, 0.3, 0.4, 0.5], "color": "red_7025", "likes": 100, "docId": 1},
            {"id": 296, "vector": [0.2, 0.2, 0.3, 0.4, 0.5], "color": "red_4794", "likes": 60, "docId": 2},
            {"id": 43, "vector": [0.3, 0.2, 0.3, 0.4, 0.5], "color": "red_9392", "likes": 70, "docId": 3},
        ] + [{"id": i, "vector": [0.1 * (i % 5), 0.2, 0.3, 0.4, 0.5],
               "color": "c%d" % (i % 4), "likes": i * 10, "docId": i} for i in range(0, 10)],
    },
    "product_catalog": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("embedding", "FLOAT_VECTOR", {"dim": 5}),
            ("price", "DOUBLE", {}),
            ("rating", "DOUBLE", {}),
            ("category", "VARCHAR", {"max_length": 64}),
        ],
        "index": {"field_name": "embedding", "index_type": "AUTOINDEX", "metric_type": "L2"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "embedding": [0.1, 0.2, 0.3, 0.4, 0.5], "price": 10.0 + i,
             "rating": 4.0 + (i % 10) / 10, "category": "cate" + str(i % 5)}
            for i in range(1, 21)
        ],
    },
    "iterator_collection": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("color", "VARCHAR", {"max_length": 512}),
        ],
        "index": {"field_name": "vector", "index_type": "FLAT", "metric_type": "L2"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "vector": [0.1 * (i % 5), 0.2, 0.3, 0.4, 0.5],
             "color": "color_" + str(i % 7)} for i in range(100)
        ],
    },
    "customer_profiles": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("customer_tier", "VARCHAR", {"max_length": 64}),
            ("region", "VARCHAR", {"max_length": 64}),
            ("purchase_amount", "DOUBLE", {}),
            ("satisfaction_score", "INT64", {}),
            ("last_purchase_date", "VARCHAR", {"max_length": 64}),
        ],
        "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "L2"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "vector": [0.1, 0.2, 0.3, 0.4, 0.5],
             "customer_tier": "premium" if i % 5 == 0 else "standard",
             "region": "North America" if i % 2 == 0 else "Europe",
             "purchase_amount": 10.0 + i, "satisfaction_score": i % 5,
             "last_purchase_date": "2024-01-01",
             } for i in range(1, 1001)
        ],
    },
    "my_collection_1": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("color", "VARCHAR", {"max_length": 512}),
        ],
        "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "COSINE"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "vector": [0.1, 0.2, 0.3, 0.4, 0.5], "color": "c" + str(i)}
            for i in range(5)
        ],
    },
    "my_collection_2": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("color", "VARCHAR", {"max_length": 512}),
        ],
        "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "COSINE"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "vector": [0.1, 0.2, 0.3, 0.4, 0.5], "color": "c" + str(i)}
            for i in range(5)
        ],
    },
    # Count Entities doc: `test_collection` holds 20 rows so count(*) == 20.
    "test_collection": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
            ("color", "VARCHAR", {"max_length": 512}),
        ],
        "index": {"field_name": "vector", "index_type": "AUTOINDEX", "metric_type": "L2"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "vector": [0.1 * (i % 5), 0.2, 0.3, 0.4, 0.5], "color": "c" + str(i % 4)}
            for i in range(20)
        ],
    },
    # Force Merge Compaction doc: compacts `target_collection`.
    "target_collection": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 5}),
        ],
        "index": {"field_name": "vector", "index_type": "FLAT", "metric_type": "L2"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "vector": [0.1, 0.2, 0.3, 0.4, 0.5]} for i in range(100)
        ],
    },
    # Tune Index Build Level doc: `customized_setup` — doc builds the index itself.
    "customized_setup": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vector", "FLOAT_VECTOR", {"dim": 8}),
        ],
        "index_use": "doc",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "vector": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]} for i in range(20)
        ],
    },
    # Use Large TopK doc: `scenarios_corpus` — page builds its own index (dim 4).
    "scenarios_corpus": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("scenario_id", "VARCHAR", {"max_length": 64}),
            ("title", "VARCHAR", {"max_length": 128}),
            ("vector", "FLOAT_VECTOR", {"dim": 4}),
        ],
        "index_use": "doc",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "scenario_id": "s%d" % i, "title": "scenario %d" % i,
             "vector": [0.1, 0.2, 0.3, 0.4]} for i in range(20)
        ],
    },
    # placeholder collection used by the index docs (FLAT/IVF_*/HNSW/SCANN/GPU_*).    # NO index pre-created: the doc's own Build index block calls create_index()
    # on this field, so an AUTOINDEX here would collide.
    "your_collection_name": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("your_vector_field_name", "FLOAT_VECTOR", {"dim": 8}),
        ],
        "index_use": "doc",
        "dim_fn": _pick_dim_for_page,
        "rows": lambda client, DataType, name, dim: _gen_float_rows(20, "your_vector_field_name", dim),
        "load": False,
    },
    # placeholder binary collection for BIN_IVF_FLAT / BIN_FLAT (8 bits -> 1 byte).
    "your_binary_collection_name": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("binary_vector_field", "BINARY_VECTOR", {"dim": 8}),
        ],
        "index_use": "doc",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "binary_vector_field": os.urandom(1)} for i in range(20)
        ],
        "load": False,
    },
    # SPARSE_INVERTED_INDEX doc (BM25): `your_collection_name` holds a `text`
    # field plus a BM25 Function-generated `sparse` field and a `sparse_vector`
    # field. Selected by page matcher when the page builds SPARSE_INVERTED_INDEX
    # with BM25 (see PAGE_SPEC_MATCHERS).
    "your_collection_name_sparse": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("text", "VARCHAR", {"max_length": 512, "enable_analyzer": True,
                                 "analyzer_params": {"type": "english"}}),
            ("sparse", "SPARSE_FLOAT_VECTOR", {}),
            ("sparse_vector", "SPARSE_FLOAT_VECTOR", {}),
        ],
        "functions": [{
            "name": "text_bm25",
            "input_field_names": ["text"],
            "output_field_names": ["sparse"],
            "function_type": "BM25",
        }],
        "index_use": "doc",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "text": "information retrieval document %d" % i,
             "sparse_vector": {1: 0.2, i + 2: 0.5}} for i in range(10)
        ],
        "load": False,
    },
    # NGRAM index doc — collection with a VARCHAR "text" field. A dummy vector
    # field is required (Milvus needs at least one vector field to create a
    # collection); the doc indexes the VARCHAR "text" field.
    "Documents": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("text", "VARCHAR", {"max_length": 512}),
            ("_dummy", "FLOAT_VECTOR", {"dim": 8}),
        ],
        "index_use": "doc",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "text": "sample document text number %d" % i, "_dummy": [0.1] * dim}
            for i in range(20)
        ],
    },
    # RTREE index doc — collection with a GEOMETRY "geo" field (WKT strings)
    # plus a "vec" float field that the search blocks query. The seed builds an
    # AUTOINDEX on vec so the filtered search can run; the doc itself adds the
    # RTREE index on geo.
    "geo_demo": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("vec", "FLOAT_VECTOR", {"dim": 5}),
            ("geo", "GEOMETRY", {}),
        ],
        "index": {"field_name": "vec", "index_type": "AUTOINDEX", "metric_type": "L2"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"id": i,
             "vec": [0.1, 0.2, 0.3, 0.4, 0.5],
             "geo": "POLYGON ((%d %d, %d %d, %d %d, %d %d, %d %d))" % (i, 0, i + 1, 0, i + 1, 1, i, 1, i, 0)}
            for i in range(20)
        ],
    },
    # STL_SORT index doc — collection with a TIMESTAMPTZ "tsz" field.
    "tsz_demo": {
        "fields": [
            ("id", "INT64", {"is_primary": True}),
            ("tsz", "TIMESTAMPTZ", {}),
            ("_dummy", "FLOAT_VECTOR", {"dim": 8}),
        ],
        "index_use": "doc",
        "rows": lambda client, DataType, name, dim: [
            {"id": i, "tsz": "2024-01-01T00:00:%02d+08:00" % (i % 60), "_dummy": [0.1] * dim}
            for i in range(20)
        ],
    },
    # StructArray pages (Create/Insert/Index StructArray Fields) use `tech_articles`
    # with a struct-array `chunks` field plus a float vector `title_vector`.
    "tech_articles": {
        "fields": [
            ("doc_id", "INT64", {"is_primary": True}),
            ("title", "VARCHAR", {"max_length": 512}),
            ("category", "VARCHAR", {"max_length": 128}),
            ("title_vector", "FLOAT_VECTOR", {"dim": 4}),
            ("chunks", "ARRAY", {"element_type": "STRUCT", "max_capacity": 1000,                                  "nullable": True}),
        ],
        "index": {"field_name": "title_vector", "index_type": "AUTOINDEX", "metric_type": "COSINE"},
        "index_use": "create",
        "rows": lambda client, DataType, name, dim: [
            {"doc_id": i, "title": "article %d" % i, "category": "c%d" % (i % 3),
             "title_vector": [0.1, 0.2, 0.3, 0.4], "chunks": None}
            for i in range(5)
        ],
    },
    # Basic Operators / Pattern Matching / Filter Templating / ARRAY Operators pages:
    # prereq fixture collections (dedicated seeds render the real schema).
    "products": {"fields": [("id", "INT64", {"is_primary": True})]},
    "log_events": {"fields": [("id", "INT64", {"is_primary": True})]},
    "hello_milvus": {"fields": [("id", "INT64", {"is_primary": True})]},
    "users": {"fields": [("pk", "INT64", {"is_primary": True})]},
}


def _seed_tech_articles(client, DataType, name, md=""):
    """Seed a StructArray `tech_articles` collection with a struct `chunks` field."""
    s = client.create_schema(auto_id=False, enable_dynamic_field=True)
    s.add_field("doc_id", DataType.INT64, is_primary=True)
    s.add_field("title", DataType.VARCHAR, max_length=512)
    s.add_field("category", DataType.VARCHAR, max_length=128)
    s.add_field("title_vector", DataType.FLOAT_VECTOR, dim=4)
    chunk_schema = client.create_struct_field_schema()
    chunk_schema.add_field("text", DataType.VARCHAR, max_length=65535)
    chunk_schema.add_field("section", DataType.VARCHAR, max_length=128)
    chunk_schema.add_field("page", DataType.INT64)
    chunk_schema.add_field("quality_score", DataType.FLOAT)
    chunk_schema.add_field("has_code", DataType.BOOL)
    chunk_schema.add_field("emb_list_vector", DataType.FLOAT_VECTOR, dim=4)
    chunk_schema.add_field("emb", DataType.FLOAT_VECTOR, dim=4)
    chunk_schema.add_field("code_emb", DataType.FLOAT_VECTOR, dim=4)
    s.add_field("chunks", DataType.ARRAY, element_type=DataType.STRUCT,
                struct_schema=chunk_schema, max_capacity=1000, nullable=True)
    ix = client.prepare_index_params()
    ix.add_index(field_name="title_vector", index_type="AUTOINDEX", metric_type="COSINE")
    # The Insert Data page queries/loads the collection and needs the chunk
    # sub-field vector indexes present; the Index page creates them itself, so
    # do NOT pre-create them there (multiple indexes on the same field rejected).
    page_creates_chunk_index = bool(re.search(
        r"create_index[\s\S]*?chunks\[(?:emb_list_vector|emb|code_emb)\]", md))
    if not page_creates_chunk_index:
        ix.add_index(field_name="chunks[emb_list_vector]", index_type="HNSW",
                     metric_type="MAX_SIM_COSINE", index_name="chunks_emb_list_max_sim",
                     params={"M": 16, "efConstruction": 200})
        ix.add_index(field_name="chunks[emb]", index_type="HNSW",
                     metric_type="COSINE", index_name="chunks_emb_cosine",
                     params={"M": 16, "efConstruction": 200})
        ix.add_index(field_name="chunks[code_emb]", index_type="HNSW",
                     metric_type="COSINE", index_name="chunks_code_emb",
                     params={"M": 16, "efConstruction": 200})
    client.create_collection(name, schema=s, index_params=ix)
    rows = [
        {"doc_id": 1, "title": "StructArray indexing patterns", "category": "index",
         "title_vector": [0.12, 0.08, 0.32, 0.48],
         "chunks": [
             {"text": "Create one index for each vector subfield.", "section": "index",
              "page": 1, "quality_score": 0.96, "has_code": False,
              "emb_list_vector": [0.10, 0.20, 0.30, 0.40],
              "emb": [0.10, 0.20, 0.30, 0.40],
              "code_emb": [0.11, 0.21, 0.31, 0.41]},
             {"text": "Use MAX_SIM metrics for EmbeddingList search.", "section": "index",
              "page": 2, "quality_score": 0.91, "has_code": True,
              "emb_list_vector": [0.16, 0.24, 0.35, 0.45],
              "emb": [0.16, 0.24, 0.35, 0.45],
              "code_emb": [0.17, 0.25, 0.34, 0.44]},
         ]},
        {"doc_id": 2, "title": "Filtered StructArray search", "category": "filter",
         "title_vector": [0.20, 0.18, 0.22, 0.40],
         "chunks": [
             {"text": "Use element_filter to match scalar conditions within the same Struct element.",
              "section": "filter", "page": 1, "quality_score": 0.93, "has_code": True,
              "emb_list_vector": [0.21, 0.18, 0.33, 0.44],
              "emb": [0.21, 0.18, 0.33, 0.44],
              "code_emb": [0.22, 0.19, 0.32, 0.43]},
             {"text": "MATCH_LEAST checks how many elements satisfy a predicate.",
              "section": "filter", "page": 2, "quality_score": 0.88, "has_code": False,
              "emb_list_vector": [0.24, 0.22, 0.31, 0.39],
              "emb": [0.24, 0.22, 0.31, 0.39],
              "code_emb": [0.25, 0.23, 0.30, 0.38]},
         ]},
        {"doc_id": 3, "title": "Element-level search with offsets", "category": "search",
         "title_vector": [0.33, 0.11, 0.29, 0.37],
         "chunks": [
             {"text": "Element-level search can return the offset of the matched Struct element.",
              "section": "search", "page": 1, "quality_score": 0.95, "has_code": False,
              "emb_list_vector": [0.32, 0.14, 0.28, 0.41],
              "emb": [0.32, 0.14, 0.28, 0.41],
              "code_emb": [0.33, 0.15, 0.27, 0.40]},
         ]},
    ]
    client.insert(name, rows)
    client.flush(name)
    client.load_collection(name)
    return {name}


def _gen_rows_my_collection(dim):
    import random
    colors = ["red_7025", "pink_8682", "orange_6781", "purple_4976", "yellow_4222",
              "grey_8510", "white_9381"]
    rows = []
    for i in range(30):
        rows.append({
            "id": i, "vector": [random.random() for _ in range(dim)],
            "color": random.choice(colors), "likes": i * 10, "price": i + 0.5,
            "rating": i % 5, "category": "cat" + str(i % 4), "docId": i,
            "chunk": "text chunk " + str(i),
        })
    return rows


def _seed_from_spec(client, DataType, name, spec, md=""):
    """Generic collection seeder driven by a COLLECTION_SPECS entry.

    A spec may additionally define:
      functions : list of dicts for schema.add_function, e.g.
                  [{"name": ..., "input_field_names": [...],
                    "output_field_names": [...], "function_type": <keyword>}]
      load      : bool — whether to load right after seeding (default True)
    """
    if client.has_collection(name):
        if spec.get("load", True) and not spec.get("index_use") == "doc":
            try:
                client.load_collection(name)
            except Exception:
                pass
        return set()

    dim = None
    if spec.get("dim_fn"):
        dim = spec["dim_fn"](md)
    elif spec.get("vector_dim"):
        dim = spec["vector_dim"]
    # otherwise derive dim from the first FLOAT_VECTOR field that fixes one
    if dim is None:
        for fname, ftype, kwargs in spec["fields"]:
            if ftype == "FLOAT_VECTOR" and kwargs.get("dim"):
                dim = kwargs["dim"]
                break
    if dim is None:
        dim = 8

    s = client.create_schema(auto_id=False, enable_dynamic_field=True)
    for fname, ftype, kwargs in spec["fields"]:
        kwargs = dict(kwargs)
        if ftype == "FLOAT_VECTOR" and "dim" not in kwargs:
            kwargs["dim"] = dim
        s.add_field(fname, getattr(DataType, ftype), **kwargs)
    for fn in spec.get("functions", []):
        fnd = dict(fn)
        ftype = fnd.pop("function_type")
        s.add_function(Function(name=fnd.pop("name"),
                                input_field_names=fnd.pop("input_field_names"),
                                output_field_names=fnd.pop("output_field_names"),
                                function_type=getattr(FunctionType, ftype),
                                **fnd))
    
    if spec.get("index") and spec.get("index_use") == "create":
        ix = client.prepare_index_params()
        ix.add_index(**spec["index"])
        client.create_collection(name, schema=s, index_params=ix)
    else:
        client.create_collection(name, schema=s)

    # partitions must exist before a spec's rows lambda can insert into them
    for part in spec.get("partitions", []):
        if not client.has_partition(collection_name=name, partition_name=part):
            client.create_partition(collection_name=name, partition_name=part)

    rows = spec.get("rows")
    if rows is None:
        rows = _gen_float_rows(20, spec["fields"][1][0], dim)
    elif callable(rows):
        rows = rows(client, DataType, name, dim)
    if rows:
        client.insert(name, rows)
        client.flush(name)

    if spec.get("load", True) and spec.get("index_use") != "doc":
        client.load_collection(name)
    return {name}


def _make_seed(spec):
    def seed(client, DataType, name, md=""):
        return _seed_from_spec(client, DataType, name, spec, md)
    return seed


def _seed_my_collection_alter(client, DataType, name, md=""):
    """Seed the Alter Collection Field page's my_collection: varchar/array/doc_chunk
    fields, NOT loaded (altering field properties requires a released collection)."""
    s = client.create_schema(auto_id=False, enable_dynamic_field=False)
    s.add_field("id", DataType.INT64, is_primary=True)
    s.add_field("vector", DataType.FLOAT_VECTOR, dim=5)
    s.add_field("varchar", DataType.VARCHAR, max_length=512)
    s.add_field("array", DataType.ARRAY, element_type=DataType.VARCHAR,
                max_capacity=8, max_length=32)
    s.add_field("doc_chunk", DataType.VARCHAR, max_length=512)
    ix = client.prepare_index_params()
    ix.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(name, schema=s, index_params=ix)
    rows = [{"id": i, "vector": [0.1, 0.2, 0.3, 0.4, 0.5], "varchar": "v%d" % i,
             "array": ["a%d" % i], "doc_chunk": "c%d" % i} for i in range(5)]
    client.insert(name, rows)
    client.flush(name)
    try:
        client.release_collection(name)
    except Exception:
        pass
    return {name}


def _seed_my_collection_upsert(client, DataType, name, md=""):
    """Upsert Entities page: my_collection has id/vector/title/issue, partitionA."""
    s = client.create_schema(auto_id=False, enable_dynamic_field=True)
    s.add_field("id", DataType.INT64, is_primary=True)
    s.add_field("vector", DataType.FLOAT_VECTOR, dim=5)
    s.add_field("title", DataType.VARCHAR, max_length=512)
    s.add_field("issue", DataType.VARCHAR, max_length=128)
    ix = client.prepare_index_params()
    ix.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(name, schema=s, index_params=ix)
    if not client.has_partition(collection_name=name, partition_name="partitionA"):
        client.create_partition(collection_name=name, partition_name="partitionA")
    rows = [{"id": i, "vector": [0.1 * (i % 5), 0.2, 0.3, 0.4, 0.5],
             "title": "t%d" % i, "issue": "vol.%d" % (i + 1)} for i in range(10)]
    client.insert(name, rows)
    client.flush(name)
    client.load_collection(name)
    return {name}


def _seed_my_collection_pk(client, DataType, name, md=""):
    """Primary-Key Search page: my_collection carries pk ids 551/296/43."""
    s = client.create_schema(auto_id=False, enable_dynamic_field=True)
    s.add_field("id", DataType.INT64, is_primary=True)
    s.add_field("vector", DataType.FLOAT_VECTOR, dim=5)
    s.add_field("color", DataType.VARCHAR, max_length=512)
    s.add_field("likes", DataType.INT64)
    s.add_field("docId", DataType.INT64)
    ix = client.prepare_index_params()
    ix.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(name, schema=s, index_params=ix)
    rows = [
        {"id": 551, "vector": [0.1, 0.2, 0.3, 0.4, 0.5], "color": "red_7025", "likes": 100, "docId": 1},
        {"id": 296, "vector": [0.2, 0.2, 0.3, 0.4, 0.5], "color": "red_4794", "likes": 60, "docId": 2},
        {"id": 43, "vector": [0.3, 0.2, 0.3, 0.4, 0.5], "color": "red_9392", "likes": 70, "docId": 3},
    ] + [{"id": i, "vector": [0.1 * (i % 5), 0.2, 0.3, 0.4, 0.5],
          "color": "c%d" % (i % 4), "likes": i * 10, "docId": i} for i in range(0, 10)]
    client.insert(name, rows)
    client.flush(name)
    client.load_collection(name)
    return {name}


def _seed_products(client, DataType, name, md=""):
    """Basic Operators page: products collection with nullable category."""
    s = client.create_schema(auto_id=False, enable_dynamic_field=False)
    s.add_field("id", DataType.INT64, is_primary=True)
    s.add_field("product_name", DataType.VARCHAR, max_length=64)
    s.add_field("category", DataType.VARCHAR, max_length=64, nullable=True)
    s.add_field("embedding", DataType.FLOAT_VECTOR, dim=5)
    ix = client.prepare_index_params()
    ix.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(name, schema=s, index_params=ix)
    rows = [
        {"id": 1, "product_name": "Phone", "category": "electronics", "embedding": [0.1] * 5},
        {"id": 2, "product_name": "Shoes", "category": None, "embedding": [0.2] * 5},
        {"id": 3, "product_name": "Hat", "category": "fashion", "embedding": [0.3] * 5},
    ]
    client.insert(name, rows)
    client.flush(name)
    client.load_collection(name)
    return {name}


def _seed_log_events(client, DataType, name, md=""):
    """Pattern Matching page: log_events with message/severity."""
    s = client.create_schema(auto_id=False, enable_dynamic_field=False)
    s.add_field("id", DataType.INT64, is_primary=True)
    s.add_field("message", DataType.VARCHAR, max_length=128)
    s.add_field("severity", DataType.VARCHAR, max_length=16)
    s.add_field("embedding", DataType.FLOAT_VECTOR, dim=5)
    ix = client.prepare_index_params()
    ix.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(name, schema=s, index_params=ix)
    rows = [
        {"id": 1, "message": "Error E1234 occurred", "severity": "error", "embedding": [0.1] * 5},
        {"id": 2, "message": "Warning E9999", "severity": "warn", "embedding": [0.2] * 5},
        {"id": 3, "message": "Info message", "severity": "info", "embedding": [0.3] * 5},
    ]
    client.insert(name, rows)
    client.flush(name)
    client.load_collection(name)
    return {name}


def _seed_hello_milvus(client, DataType, name, md=""):
    """Filter Templating page: hello_milvus with age/city/message fields."""
    s = client.create_schema(auto_id=False, enable_dynamic_field=False)
    s.add_field("id", DataType.INT64, is_primary=True)
    s.add_field("embeddings", DataType.FLOAT_VECTOR, dim=2)
    s.add_field("age", DataType.INT64)
    s.add_field("city", DataType.VARCHAR, max_length=64)
    s.add_field("message", DataType.VARCHAR, max_length=128)
    ix = client.prepare_index_params()
    ix.add_index(field_name="embeddings", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(name, schema=s, index_params=ix)
    rows = [
        {"id": 1, "embeddings": [0.1, 0.2], "age": 25, "city": "北京", "message": "E1234 hi"},
        {"id": 2, "embeddings": [0.2, 0.1], "age": 30, "city": "上海", "message": "E5678 yo"},
        {"id": 3, "embeddings": [0.3, 0.3], "age": 28, "city": "北京", "message": "E9999 hey"},
    ]
    client.insert(name, rows)
    client.flush(name)
    client.load_collection(name)
    return {name}


def _seed_users(client, DataType, name, md=""):
    """ARRAY Operators page: users with pk + ARRAY<VARCHAR> tags."""
    s = client.create_schema(auto_id=False, enable_dynamic_field=False)
    s.add_field("pk", DataType.INT64, is_primary=True)
    s.add_field("embedding", DataType.FLOAT_VECTOR, dim=5)
    s.add_field("tags", DataType.ARRAY, element_type=DataType.VARCHAR,
                max_capacity=8, max_length=32)
    ix = client.prepare_index_params()
    ix.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="L2")
    client.create_collection(name, schema=s, index_params=ix)
    rows = [
        {"pk": 1, "embedding": [0.1, 0.2, 0.3, 0.4, 0.5], "tags": ["new", "trial", "premium"]},
        {"pk": 2, "embedding": [0.6, 0.7, 0.8, 0.9, 1.0], "tags": ["new", "trial"]},
    ]
    client.insert(name, rows)
    client.flush(name)
    client.load_collection(name)
    return {name}


def _seed_my_collection_partitioned(client, DataType, name, md=""):
    """Query page: my_collection with a partitionA partition (ids 10-19 red)."""
    s = client.create_schema(auto_id=False, enable_dynamic_field=True)
    s.add_field("id", DataType.INT64, is_primary=True)
    s.add_field("vector", DataType.FLOAT_VECTOR, dim=5)
    s.add_field("color", DataType.VARCHAR, max_length=512)
    s.add_field("likes", DataType.INT64)
    s.add_field("price", DataType.DOUBLE)
    s.add_field("rating", DataType.INT64)
    s.add_field("docId", DataType.INT64)
    s.add_field("chunk", DataType.VARCHAR, max_length=512)
    ix = client.prepare_index_params()
    ix.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
    client.create_collection(name, schema=s, index_params=ix)
    if not client.has_partition(collection_name=name, partition_name="partitionA"):
        client.create_partition(collection_name=name, partition_name="partitionA")
    colors = ["red_7025", "pink_8682", "orange_6781", "purple_4976", "yellow_4222",
              "grey_8510", "white_9381"]
    default_rows = [{"id": i, "vector": [0.1] * (i % 5) + [0.2] * (5 - (i % 5)),
                     "color": colors[i % 7], "likes": i * 10, "price": i + 0.5,
                     "rating": i % 5, "docId": i, "chunk": "c%d" % i} for i in range(10)]
    part_rows = [{"id": i + 10, "vector": [0.1] * (i % 5) + [0.2] * (5 - (i % 5)),
                  "color": "red_" + str(1000 + i), "likes": 60 + i, "price": i + 10.5,
                  "rating": i % 5, "docId": i + 10, "chunk": "pc%d" % i} for i in range(10)]
    client.insert(name, default_rows)
    client.insert(name, part_rows, partition_name="partitionA")
    client.flush(name)
    client.load_collection(name)
    return {name}


def _seed_for_collection(n, md):
    """Pick the seed function for a collection name, honoring page features.

    `your_collection_name` is a generic placeholder: the right schema depends on
    what the page actually indexes on it:
      - BIN_*/binary field      -> binary schema (8-bit vector)
      - SPARSE_INVERTED_INDEX
        with BM25               -> text + BM25 Function sparse schema
      - otherwise               -> float vector schema
    `my_collection` on the Load & Release page uses `my_id`/`my_vector` fields
    (the doc's Load Specific Fields section assumes them), so it gets a
    page-specific variant.
    Returns the SEEDS callable.
    """
    if n != "your_collection_name":
        if n == "tech_articles":
            return _seed_tech_articles
        if n == "products":
            return _seed_products
        if n == "log_events":
            return _seed_log_events
        if n == "hello_milvus":
            return _seed_hello_milvus
        if n == "users":
            return _seed_users
        if n == "my_collection":
            if re.search(r"partition_names\s*=\s*\[\s*[\"']partitionA[\"']", md):
                return _seed_my_collection_partitioned
            if re.search(r"alter_collection_field", md) and "max_length" in md:
                return _seed_my_collection_alter
            if re.search(r"partial_update|field_ops|FieldOp|upsert", md) and '"issue"' in md:
                return _seed_my_collection_upsert
            if re.search(r"551,?\s*296,?\s*43|551\b", md):
                return _seed_my_collection_pk
            if re.search(r"load_fields\s*=|my_id|my_vector", md):
                return SEEDS["my_collection_myid"]
        return SEEDS[n]
    uses_binary = bool(re.search(
        r"BIN_|binary_vector_field|BINARY_VECTOR|BinaryVec|BinFlat|BinIvfFlat|Binary", md))
    if uses_binary:
        return SEEDS["your_binary_collection_name"]
    uses_sparse_bm25 = bool(re.search(
        r"SPARSE_INVERTED_INDEX|SPARSE_INVERTED_INDEX_CC|metric_type.?=.?[\"']?BM25|MetricType\.BM25|IndexType\.SparseInverted", md))
    if uses_sparse_bm25:
        return SEEDS["your_collection_name_sparse"]
    return SEEDS["your_collection_name"]


SEEDS = {name: _make_seed(spec) for name, spec in COLLECTION_SPECS.items()}

# Pages with a divergent schema for a known name create that collection
# themselves — the runner must not pre-seed it or create_collection fails.
DROP_FIRST = {"my_collection"}


def _page_stem(page):
    base = os.path.basename(page)
    stem = re.sub(r"\.md$", "", base)
    stem = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    return stem


def _referenced(md):
    return [n for n in SEEDS if re.search(rf"\b{re.escape(n)}\b", md)]


def _page_creates(md, name):
    return bool(re.search(
        r"create_collection\s*\([\s\S]*?collection_name\s*=\s*[\"']?" + re.escape(name) +
        r"|create_collection\s*\(\s*[\"']?" + re.escape(name), md))


def _unique_collection_names(md, seed_srcs, stem):
    """Map every collection name the page touches to a page-unique name.

    A name is "touched" when the page text or an ad-hoc seed file references it
    (as a fixture to seed, or as a collection the page creates). Placeholder
    names defined only by an ad-hoc seed file (e.g. `your_collection_name`) are
    included so page and seed agree on the same isolated name.
    """
    names = set(_referenced(md))
    for src in seed_srcs:
        for m in re.finditer(
                r"(?:create_collection|has_collection|drop_collection|load_collection|"
                r"create_partition|search|query)\s*\([\s\S]*?collection_name\s*=\s*"
                r"[\"']([^\"']+)[\"']|create_collection\s*\(\s*[\"']([^\"']+)[\"']", src):
            names.add(m.group(1) or m.group(2))
    # page-defined names (its own create_collection) must also be isolated
    for m in re.finditer(
            r"create_collection\s*\([\s\S]*?collection_name\s*=\s*[\"']([^\"']+)[\"']"
            r"|create_collection\s*\(\s*[\"']([^\"']+)[\"']", md):
        names.add(m.group(1) or m.group(2))
    mapping = {}
    for n in sorted(names):
        mapping[n] = f"{stem}_{n}"
    return mapping


def _rewrite(text, mapping):
    for orig, repl in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"\b{re.escape(orig)}\b", repl, text)
    return text


def _strip_python_imports(block, out):
    """Remove `from X import ...` / `import X` statements from a python block,
    appending each to `out` (caller dedupes). Handles single-line imports and
    multi-line parenthesized `from X import (...)` groups."""
    lines = block.split("\n")
    kept = []
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("from ") or s.startswith("import "):
            stmt = [line]
            depth = s.count("(") - s.count(")")
            j = i + 1
            while depth > 0 and j < len(lines):
                nxt = lines[j]
                stmt.append(nxt)
                depth += nxt.count("(") - nxt.count(")")
                j += 1
            out.append("\n".join(stmt).strip())
            i = j
            continue
        kept.append(line)
        i += 1
    return "\n".join(kept)


def main():
    argv = []
    keep_extra = []
    i = 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--keep":
            keep_extra.append(sys.argv[i + 1])
            i += 2
            continue
        argv.append(a)
        i += 1
    page = argv[0]
    seedfiles = [a for a in argv[1:] if a.endswith(".py")]
    md = open(page).read()
    stem = _page_stem(page)

    seed_srcs = [open(sf).read() for sf in seedfiles]
    mapping = _unique_collection_names(md, seed_srcs, stem)
    md = _rewrite(md, mapping)
    seed_srcs = [_rewrite(s, mapping) for s in seed_srcs]

    blocks = re.findall(r"```python\n(.*?)```", md, re.S)

    # Some pages use a non-standard client variable name (e.g. `milvus_client`);
    # detect it so the shared document-scope client matches what blocks use.
    var_re = re.compile(r"^(\w+)\s*=\s*MilvusClient\(", re.M)
    client_var = "client"
    for b in blocks:
        m = var_re.search(b)
        if m:
            client_var = m.group(1)
            break
    # Hoist every `from X import ...` / `import X` statement out of the python
    # blocks into the prelude (mirrors run_page_java.py). The doc blocks follow
    # the dependency-hoisting convention: ALL imports live in the first
    # client-using block, which may come AFTER an earlier helper/definition
    # block (e.g. a ranker Function builder) that already references those
    # names. Executing blocks strictly in document order would raise NameError
    # there; collecting the imports first and running them in the prelude makes
    # the assembled program equivalent to the Java model where imports are
    # hoisted to the top of the file.
    hoisted = []
    blocks = [_strip_python_imports(b, hoisted) for b in blocks]
    # dedupe imports, preserving first-occurrence order
    hoisted = list(dict.fromkeys(hoisted))
    prelude = ("\n".join(hoisted) + "\n") if hoisted else ""
    prelude += 'from pymilvus import MilvusClient, DataType\n'
    prelude += f'{client_var} = MilvusClient(uri="{URI}", token="{TOKEN}")\n'

    env = {"__name__": "__main__"}
    exec(prelude, env)
    client = env[client_var]
    DataType = env["DataType"]

    created = set()
    keep = set(KEEP) | set(keep_extra)

    # seed each referenced fixture under its page-unique name
    for n in sorted(mapping):
        if n not in SEEDS and n != "your_collection_name":
            continue  # page-defined or ad-hoc-only name; seeded below if needed
        if n == "your_collection_name" and _seed_for_collection(n, md) is None:
            continue
        uniq = mapping[n]
        if _page_creates(md, uniq):
            # page creates its own divergent-schema collection: do not pre-seed
            continue
        if not client.has_collection(uniq):
            seed = _seed_for_collection(n, md)
            made = seed(client, DataType, uniq, md) or {uniq}
            created.update(made)

    # extra ad-hoc seed files still supported (rewritten to isolated names).
    # A seed that fails (e.g. load before index) must not abort the run — record
    # the failure but still track its collections so cleanup always runs.
    seed_errors = []
    for src in seed_srcs:
        try:
            exec(src, env)
        except Exception as e:
            seed_errors.append(f"{type(e).__name__}: {e}")
            print(f"--- ad-hoc seed FAILED ---")
            print(traceback.format_exc()[-1200:])

    # ad-hoc seeds may create names not in SEEDS; track them for cleanup
    for src in seed_srcs:
        for m in re.finditer(r"create_collection\s*\(\s*[\"']([^\"']+)[\"']", src):
            created.add(m.group(1))

    ok, fail = [], []
    # strip per-block client/import re-declaration so the document-scope client
    # created in the prelude is reused (blocks may each declare their own).
    # Remove ONLY the `client = MilvusClient(...)` init — never the preceding
    # `from pymilvus import ...` line (it may import names used later in the
    # block, e.g. Function/FunctionType for BM25).
    client_re = re.compile(
        rf"{re.escape(client_var)}\s*=\s*MilvusClient\(\s*(?:uri\s*=\s*)?"
        r"[\"']?[^\"'()\n]*[\"']?[^()]*?\)\s*\n?")
    # harness plumbing: before a search/query block, ensure the referenced
    # isolated collections are loaded (the doc's own flow builds the index in
    # an earlier block; load is a run-harness concern, never doc content).
    load_re = re.compile(
        r"(?:client\.search\(|client\.query\(|client\.query_iterator\()[\s\S]*?"
        r"collection_name\s*=\s*[\"']([^\"']+)[\"']")
    loaded_once = set()

    def _wait_loaded(coll, client):
        try:
            st = client.get_load_state(coll)
            if isinstance(st, dict):
                val = st.get("state")
                if val is not None and "loaded" in str(val).lower():
                    return
        except Exception:
            pass
        import time
        for _ in range(60):
            try:
                st = client.get_load_state(coll)
                if isinstance(st, dict):
                    val = str(st.get("state", "")).lower()
                    if "loaded" in val:
                        return
            except Exception:
                pass
            time.sleep(0.5)

    for i, b in enumerate(blocks):
        if not b.strip():
            ok.append((i, "empty"))
            continue
        try:
            if re.search(r"(?:client\.search\(|client\.query\()", b):
                for m in load_re.finditer(b):
                    coll = m.group(1)
                    if coll not in loaded_once and client.has_collection(coll):
                        try:
                            client.load_collection(coll)
                            _wait_loaded(coll, client)
                            loaded_once.add(coll)
                        except Exception:
                            pass
            stripped = client_re.sub("", b, count=1)
            exec(stripped, env)
            ok.append((i, "OK"))
        except SystemExit:
            # an early exit mid-block truncates the run — treat as a failure
            fail.append((i, "SystemExit"))
            print(f"--- block {i} FAILED (SystemExit) ---")
            print(b[:1200])
        except Exception as e:
            fail.append((i, f"{type(e).__name__}: {e}"))
            print(f"--- block {i} FAILED ---")
            print(b[:1200])
            print(traceback.format_exc()[-1200:])

    # cleanup: drop every collection created this run (isolated per page)
    for n in sorted(created):
        if n in keep:
            continue
        try:
            if client.has_collection(n):
                client.drop_collection(n)
        except Exception:
            pass

    # cleanup databases the page created (Database doc creates my_database_*),
    # so re-runs start from a clean default-database-only state.
    try:
        for db in client.list_databases():
            if db in ("default",):
                continue
            try:
                client.drop_database(db_name=db)
            except Exception:
                pass
    except Exception:
        pass

    print(f"\n=== {page} ===")
    print(f"isolated names: {sorted(mapping.values())}")
    print(f"blocks: {len(blocks)}, OK: {len(ok)}, FAIL: {len(fail)}")
    for i, msg in fail:
        print(f"  FAIL block {i}: {msg}")

    try:
        client.close()
    except Exception:
        pass
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
