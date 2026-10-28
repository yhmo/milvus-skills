#!/usr/bin/env python3
"""Unit tests for client-session extraction."""

from __future__ import annotations

import unittest

from helpers import load_script


module = load_script("extract_session")


CPP_SOURCE = r"""
namespace milvus {
class MilvusClientV2Session {
 public:
    virtual const std::string& ClusterID() const = 0;
    virtual Status Search(const SearchRequest& request) = 0;
    virtual void Close() noexcept = 0;
};
}
Status Session(const std::string& cluster_id, SessionPtr& session);
"""

JAVA_SOURCE = r"""
public class MilvusClientV2Session {
    public String getClusterId() { return clusterId; }
    public SearchResp search(SearchReq request) { ensureOpen(); return null; }
    public void close() { closed = true; }
}
public MilvusClientV2Session session(String clusterId) {
    if (StringUtils.isEmpty(clusterId)) throw new IllegalArgumentException("clusterId cannot be empty");
    return new MilvusClientV2Session(this, clusterId);
}
"""

RUST_SOURCE = r"""
pub struct MilvusClientV2Session {}
impl MilvusClientV2Session {
    pub fn cluster_id(&self) -> &str { &self.cluster_id }
    pub async fn search(&self, request: SearchRequest) -> Result<SearchResponse> { Ok(todo!()) }
    pub fn close(&self) { self.closed.store(true, Ordering::SeqCst); }
}
pub fn session(&self, cluster_id: impl Into<String>) -> Result<MilvusClientV2Session> {
    if cluster_id.is_empty() { return Err(Error::validation("cluster_id", "must not be empty")); }
    Ok(MilvusClientV2Session::new(self.clone(), cluster_id))
}
"""


class ExtractSessionTests(unittest.TestCase):
    def test_cpp_surface(self) -> None:
        result = module.session_surface("cpp", {"x.h": CPP_SOURCE, "x.cc": CPP_SOURCE})
        self.assertTrue(result["capabilities"]["factory"])
        self.assertTrue(result["capabilities"]["session_type"])
        self.assertTrue(result["capabilities"]["dql_surface"])
        self.assertTrue(result["capabilities"]["cluster_id_accessor"])
        self.assertTrue(result["capabilities"]["close"])
        self.assertIn("search", result["dql_methods"])

    def test_java_surface_and_validation(self) -> None:
        result = module.session_surface("java", {"X.java": JAVA_SOURCE})
        self.assertTrue(result["capabilities"]["factory"])
        self.assertTrue(result["capabilities"]["cluster_id_accessor"])
        self.assertTrue(result["capabilities"]["empty_cluster_id_validation"])
        self.assertTrue(result["capabilities"]["close"])
        self.assertIn("search", result["dql_methods"])

    def test_rust_surface(self) -> None:
        result = module.session_surface("rust", {"session.rs": RUST_SOURCE})
        self.assertTrue(result["capabilities"]["factory"])
        self.assertTrue(result["capabilities"]["session_type"])
        self.assertTrue(result["capabilities"]["cluster_id_accessor"])
        self.assertTrue(result["capabilities"]["close"])
        self.assertIn("search", result["dql_methods"])

    def test_unavailable_sdk_is_explicit(self) -> None:
        result = module.session_surface("pymilvus", {"client.py": "class MilvusClient:\n    pass\n"})
        self.assertFalse(result["capabilities"]["factory"])
        self.assertFalse(result["capabilities"]["session_type"])
        self.assertEqual(result["session_files"], [])


if __name__ == "__main__":
    unittest.main()
