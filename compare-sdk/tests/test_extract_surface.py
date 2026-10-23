#!/usr/bin/env python3
"""Unit tests for language-specific SDK facade extraction."""

from __future__ import annotations

import unittest

from helpers import load_script


extractor = load_script("extract_surface")


class ExtractSurfaceTests(unittest.TestCase):
    def test_python_includes_async_and_deprecated(self) -> None:
        source = '''
from typing import Any

class MilvusClient:
    def create_collection(self, collection_name: str, timeout: float | None = None) -> None:
        pass

    async def async_action(self, **kwargs: Any) -> dict:
        return {}

    def deprecated_method(self):
        pass
'''
        methods = extractor.extract_python(source)
        self.assertEqual([method["name"] for method in methods], ["create_collection", "async_action", "deprecated_method"])
        self.assertIsNone(methods[0]["parameters"][0]["default"])
        self.assertEqual(methods[0]["parameters"][1]["default"], "None")
        self.assertTrue(methods[1]["is_async"])
        self.assertEqual(methods[1]["parameters"][0]["name"], "**kwargs")

    def test_java_extracts_public_generic_and_deprecated(self) -> None:
        source = '''
public class MilvusClientV2 {
    public void createCollection(CreateCollectionReq request) {}
    public <T> T get(GetReq request) { return null; }
    public CompletableFuture<SearchResp> searchAsync(SearchReq request) { return null; }
    public MilvusClientV2() {}
    public class Inner {}
    @Deprecated
    public void oldApi() {}
}
'''
        methods = extractor.extract_java(source)
        self.assertEqual(
            [method["name"] for method in methods],
            ["createCollection", "get", "searchAsync", "oldApi"],
        )
        self.assertEqual(methods[0]["request_type"], "CreateCollectionReq")
        self.assertEqual(methods[0]["line"], 3)
        self.assertEqual(methods[1]["return_type"], "T")
        self.assertEqual(methods[1]["line"], 4)
        self.assertTrue(methods[2]["is_async"])
        self.assertEqual(methods[2]["response_type"], "SearchResp")
        self.assertTrue(methods[3]["deprecated"])

    def test_cpp_extracts_virtual_multiline(self) -> None:
        source = '''
class MilvusClientV2 {
public:
    virtual Status CreateCollection(
        const CreateCollectionRequest& request) override = 0;
    virtual ClientTelemetryManagerPtr GetTelemetry() const {
        return nullptr;
    }
    virtual Status Search(const SearchRequest& request, SearchResults& response) = 0;
    virtual ~MilvusClientV2() = default;
};
'''
        methods = extractor.extract_cpp(source)
        self.assertEqual(len(methods), 3)
        self.assertEqual(methods[0]["name"], "CreateCollection")
        self.assertEqual(methods[0]["return_type"], "Status")
        self.assertEqual(methods[0]["line"], 4)
        self.assertEqual(methods[0]["parameters"][0]["type"], "const CreateCollectionRequest&")
        self.assertEqual(methods[1]["name"], "GetTelemetry")
        self.assertEqual(methods[1]["return_type"], "ClientTelemetryManagerPtr")
        self.assertEqual(methods[1]["line"], 6)
        self.assertEqual(methods[2]["response_type"], "SearchResults")

    def test_csharp_extracts_multiline_async_and_obsolete(self) -> None:
        source = '''
public sealed partial class MilvusClientV2 {
    public async Task CreateCollectionAsync(
        CreateCollectionReq request,
        CancellationToken cancellationToken = default) {}

    public MilvusClientV2(ConnectConfig config) {}

    [Obsolete]
    public void OldApi() {}
}
'''
        methods = extractor.extract_csharp(source)
        self.assertEqual([method["name"] for method in methods], ["CreateCollectionAsync", "OldApi"])
        self.assertTrue(methods[0]["is_async"])
        self.assertEqual(methods[0]["line"], 3)
        self.assertEqual(methods[0]["parameters"][1]["default"], "default")
        self.assertEqual(methods[0]["response_type"], "void")
        self.assertTrue(methods[1]["deprecated"])

    def test_rust_extracts_async_signature_and_params(self) -> None:
        source = '''
impl ClientV2 {
    #[deprecated]
    pub async fn search(&self, request: SearchRequest) -> Result<SearchResponse> { todo!() }
    pub fn new(config: ConnectConfig) -> Self { todo!() }
}
'''
        methods = extractor.extract_rust(source)
        self.assertEqual([method["name"] for method in methods], ["search", "new"])
        self.assertTrue(methods[0]["is_async"])
        self.assertTrue(methods[0]["deprecated"])
        self.assertEqual(methods[0]["return_type"], "Result<SearchResponse>")
        self.assertEqual(methods[0]["response_type"], "SearchResponse")
        self.assertEqual(methods[0]["request_type"], "SearchRequest")

    def test_overloads_are_renumbered_across_partial_files(self) -> None:
        first = extractor.base_method(
            "search",
            file="Client.A.cs",
            line=1,
            parameters=[],
            return_type="void",
        )
        second = extractor.base_method(
            "search",
            file="Client.B.cs",
            line=2,
            parameters=[],
            return_type="void",
        )
        self.assertEqual(
            [method["method_id"] for method in extractor.renumber_overloads([first, second])],
            ["search#0", "search#1"],
        )


if __name__ == "__main__":
    unittest.main()
