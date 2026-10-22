# Example-code deprecated-API checklist

Load when the diff adds or modifies example, tutorial, benchmark-demo, or
doc-snippet code — `examples/`, `example/`, `tutorial/`, README or docs
code blocks — in any repository. Especially important for Milvus SDK
repositories, where examples are part of the public contract.

## Detection markers by language

| Language | Deprecated markers |
|---|---|
| Java | `@Deprecated` annotation, `@deprecated` Javadoc |
| Rust | `#[deprecated]`, `#[deprecated(since = "...", note = "...")]` |
| C# | `[Obsolete]`, `[Obsolete("message")]` |
| C++ | `[[deprecated]]`, `[[deprecated("message")]]` |
| Go | `// Deprecated:` doc-comment convention |
| Python | `deprecated` decorator, `DeprecationWarning`, `DEPRECATED` in docstring |
| TypeScript / JavaScript | `@deprecated` JSDoc tag |

## Rules

- Newly added example code must not call deprecated methods, constructors,
  enums, or enum values. Severity `Medium`: examples teach users the
  supported pattern and are part of the public contract.
- When the PR modifies an example that already uses a deprecated API, flag
  the touched lines and recommend migrating them; severity `Medium` when the
  example is substantially rewritten, `Low` for an incidental touch.
- Every finding must name the recommended replacement, sourced from the
  deprecation marker's message, nearby documentation, or the loaded
  repository skill. If no replacement is documented, use the `question`
  shape and ask which API the example should demonstrate instead.
- Deprecated enum values follow the same rule as deprecated methods.
- Legitimate exception: when the example's explicit purpose is demonstrating
  the deprecated API itself (for example a migration guide from the old API
  to its replacement), do not flag it; verify the example states that
  purpose.

## Milvus-family note

Most Milvus SDKs keep V1 APIs for compatibility while V2 is the active
surface (`MilvusClientV2`, `milvus::v2`, Rust `ClientV2`, and equivalents).
New examples should use the V2 surface unless the loaded repository skill or
the example's stated purpose says otherwise. Do not extend legacy ORM/V1
examples with new deprecated-API usage.
