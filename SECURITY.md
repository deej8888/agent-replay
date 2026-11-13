# Security

AgentReplay is a local, single-user development tool. Keep services bound to loopback. If hosting remotely, use TLS and an authenticated reverse proxy protecting both the web application and API. The optional backend shared API key is not per-user authentication, authorization, tenant isolation, or web login.

Trace data may contain sensitive application content despite best-effort redaction. Add domain-specific rules, minimize captured data, review traces before sharing, and protect/expire database and recording files. Files are not encrypted by AgentReplay. Do not use real credentials in names, identifiers, test fixtures or screenshots.

Replay mocks decorated integration boundaries and blocks common socket operations in its active Python context. It does not sandbox arbitrary code. Never execute untrusted recordings with untrusted Python agents on a host containing valuable credentials or data. The server only re-executes the bundled deterministic demo. It does not dynamically import or execute uploaded code.

Report security vulnerabilities privately through the repository's GitHub Security reporting feature if enabled. Otherwise contact the maintainer through their public GitHub profile to arrange a private report; avoid posting working exploits or sensitive traces in public issues.
