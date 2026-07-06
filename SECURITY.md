# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |

## Reporting a vulnerability

Please report suspected vulnerabilities privately by email to
dfieser9@gmail.com rather than opening a public issue. Include the version,
a description, and steps to reproduce. You will get a response as soon as
possible, and a fix will be prioritized for the supported versions.

## Scope notes

This toolkit runs locally as a Python library and a stdio MCP server. It does
not open network ports. The MCP server reads and writes files under the
configured store directory (`LCF_STORE_DIR`, default `.lcfstore`) and reads
CSV files at paths supplied by the connected agent, so run it with the file
permissions you intend the agent to have.
