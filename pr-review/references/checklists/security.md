# Security review checklist

Load for milvus server / milvus-common / milvus-storage PRs, and for any PR
touching auth, credentials, networking, file paths, or external input.

## Secrets

- Hardcoded credentials, API keys, tokens, passwords, or connection strings
  in source, tests, examples, or configuration.
- Credentials or request identifiers written to logs, metrics, or traces.

## Injection

- User-controlled strings reaching expression evaluators, SQL-like filter
  languages, or command execution without sanitization or parameterization.
- Path traversal in file, object-storage, or archive-handling code built from
  request-controlled names.
- Format-string or template injection where user input becomes the template.

## Authorization

- New RPCs, REST routes, or gRPC methods missing privilege checks or RBAC
  wiring (milvus server and milvus-restful PRs).
- Endpoints that bypass the established auth middleware chain.

## Deserialization and input trust

- Unsafe deserialization of untrusted data: pickle, `yaml.load` without safe
  loader, unchecked binary marshalling, or assuming internal-only callers for
  externally reachable formats.

## Transport and crypto

- TLS/certificate verification disabled or bypassed.
- Weak hashing, non-random IVs, hardcoded salts for security-relevant values.

## SDK-specific

- Token/credential handling in connection config, auth metadata, or headers.
- Request-id or tenant identifier leakage across shared connections.
