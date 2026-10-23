#!/usr/bin/env python3
"""Unit tests for input/output behavior extraction."""

from __future__ import annotations

import unittest

from helpers import load_script


behavior = load_script("extract_behavior")


class ExtractBehaviorTests(unittest.TestCase):
    def test_java_direct_request_and_response_members(self) -> None:
        source = """
public class InsertReq {
    private List<JsonObject> data;
    private String collectionName;

    public static InsertReqBuilder builder() { return new InsertReqBuilder(); }
    public List<JsonObject> getData() { return data; }

    public static class InsertReqBuilder {
        private List<JsonObject> data = java.util.List.of();
        public InsertReq build() { return new InsertReq(this); }
    }
}
"""
        block = behavior.find_type_block("java", "InsertReq", {"InsertReq.java": source})
        self.assertIsNotNone(block)
        fields, accessors = behavior.parse_java_members(block)
        self.assertEqual([field["name"] for field in fields], ["data", "collectionName"])
        resolved = behavior.type_members("java", "InsertReq", {"InsertReq.java": source})
        self.assertEqual(resolved["fields"][0]["default"], "java.util.List.of()")
        self.assertEqual(accessors[0]["name"], "getData")

    def test_csharp_properties_preserve_defaults(self) -> None:
        source = """
public sealed class CreateCollectionReq {
    public string? DatabaseName { get; set; }
    public string CollectionName { get; set; } = \"\";
    public int NumShards { get; set; } = 1;
}
"""
        block = behavior.find_type_block("csharp", "CreateCollectionReq", {"CreateCollectionReq.cs": source})
        self.assertIsNotNone(block)
        fields, _ = behavior.parse_csharp_members(block)
        self.assertEqual([field["name"] for field in fields], ["DatabaseName", "CollectionName", "NumShards"])
        self.assertEqual([field["default"] for field in fields], [None, '""', "1"])

    def test_rust_struct_fields(self) -> None:
        source = """
pub struct CreateCollectionRequest {
    pub(crate) database_name: Option<String>,
    pub collection_name: String,
    pub num_shards: i32,
}
impl CreateCollectionRequest {
    fn empty() -> Self {
        Self { num_shards: 1, collection_name: String::new() }
    }
}
"""
        block = behavior.find_type_block("rust", "CreateCollectionRequest", {"request/collection.rs": source})
        self.assertIsNotNone(block)
        fields, _ = behavior.parse_rust_members(block)
        resolved = behavior.type_members(
            "rust", "CreateCollectionRequest", {"request/collection.rs": source}
        )
        self.assertEqual([field["name"] for field in fields], ["database_name", "collection_name", "num_shards"])
        self.assertEqual(fields[2]["type"], "i32")
        self.assertEqual(resolved["fields"][2]["default"], "1")

    def test_cpp_inherited_request_fields_are_included(self) -> None:
        sources = {
            "InsertRequest.h": (
                "class InsertRequest : public DMLRequestBase<InsertRequest> {\n"
                " public:\n"
                "    void SetRowsData(int rows);\n"
                " private:\n"
                "    int rows_data_;\n"
                "};\n"
            ),
            "DMLRequestBase.h": (
                "template <typename T> class DMLRequestBase {\n"
                " public:\n"
                "    void SetCollectionName(const std::string& name);\n"
                " private:\n"
                "    std::string collection_name_;\n"
                "};\n"
            ),
        }
        block = behavior.find_type_block("cpp", "InsertRequest", sources)
        self.assertIsNotNone(block)
        fields, accessors = behavior.parse_cpp_members(block)
        # type_members resolves the base declaration and appends inherited members.
        resolved = behavior.type_members("cpp", "InsertRequest", sources)
        self.assertEqual([field["name"] for field in fields], ["rows_data"])
        self.assertIn("SetRowsData", [accessor["name"] for accessor in accessors])
        self.assertIn("collection_name", [field["name"] for field in resolved["fields"]])

    def test_facade_body_uses_declared_facade_file(self) -> None:
        sources = {
            "sdk-core/src/main/java/io/milvus/client/AbstractClient.java": (
                "public class AbstractClient {\n"
                "    public void insert(int x) { other(); }\n"
                "}\n"
            ),
            "sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java": (
                "public class MilvusClientV2 {\n"
                "    public void\n"
                "    insert(InsertReq request) {\n"
                "        if (request == null) { throw new IllegalArgumentException(); }\n"
                "    }\n"
                "}\n"
            ),
        }
        method = {
            "name": "insert",
            "file": "sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java",
        }
        block = behavior.method_block("java", method, sources)
        self.assertIsNotNone(block)
        self.assertEqual(block["file"], "sdk-core/src/main/java/io/milvus/v2/client/MilvusClientV2.java")
        self.assertEqual(block["line"], 2)

    def test_facade_body_selects_matching_overload(self) -> None:
        source = """public class MilvusClientV2 {
    public void insert(String collectionName) { first(); }
    public void insert(String collectionName, int count) { second(); }
}
"""
        method = {
            "name": "insert",
            "file": "MilvusClientV2.java",
            "parameters": [
                {"name": "collectionName", "type": "String"},
                {"name": "count", "type": "int"},
            ],
        }
        block = behavior.method_block("java", method, {"MilvusClientV2.java": source})
        self.assertIsNotNone(block)
        self.assertIn("second()", block["text"])

    def test_python_input_and_output_evidence(self) -> None:
        source = """
class MilvusClient:
    def insert(self, collection_name, data, timeout=None, **kwargs):
        if not collection_name:
            raise ValueError(\"empty\")
        if data == []:
            return {\"insert_count\": 0, \"ids\": []}
        return kwargs[\"handler\"].insert()
"""
        tree = __import__("ast").parse(source)
        method = behavior.python_function(source, {"name": "insert"})
        self.assertIsNotNone(method)
        self.assertEqual(behavior.python_kwargs_names(method), ["handler"])
        self.assertEqual(
            behavior.python_return_values(method),
            ["insert_count", "ids", "kwargs['handler'].insert()"],
        )
        self.assertEqual(len(behavior.python_validation_signals(method, "milvus_client.py")), 2)
        self.assertIsNotNone(tree)


if __name__ == "__main__":
    unittest.main()
