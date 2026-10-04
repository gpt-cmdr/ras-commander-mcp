# Architecture

The package separates typed contracts, path policy, public-library adapters and
explicit MCP registration. Five tools are registered; no API reflection or dynamic
code execution exists. SDK v2 supplies structured output schemas and stdio protocol
handling. Read-only annotations are informational; server code enforces the policy.

## File boundary

Every request names an exact configured root and a relative project or plan file.
Traversal, absolute/drive paths, unsupported extensions and oversized inputs are
rejected. On POSIX, descriptor-relative directory traversal rejects symlinks at
all levels below the configured root and opens the final file with `O_NOFOLLOW`.
On Windows, the opened handle's final path is checked before content is read, so
junctions may resolve only within the configured root. Windows handling requires
native qualification before release; it is not established by Linux checks.
Only regular files are eligible. Reads are capped at 1 MiB plus a sentinel byte;
NUL-containing input and files changing during read are rejected.

Reads take immutable snapshots. Current public path-based units/description APIs
receive a copy staged in disposable private scratch outside project roots and
removed after the call. New pure `RasText` methods consume the bytes directly.
Project initialization, global project state, registry/TCU, engine discovery,
geometry files and binary readers are never invoked. The server writes no project
files. It does not constitute an OS sandbox: a trusted operator chooses the roots,
and ordinary host ACLs still govern which data the process may access.

## Scope and handoff

Only non-spatial project/plan metadata is supported. Descriptions are untrusted
narrative text, not an instruction channel. No resource templates or documentation
scraping were added. HEC documentation remains a passive reference; library API
information is discoverable from installed Python contracts outside MCP.

A bounded subagent handles a named question, selected fields, row/character budget
and compact result. The transport cannot verify its caller is a subagent; the
client/plugin must isolate project tools. Persistent main-agent exposure is not an
acceptable fallback. Spatial, binary, modifying, large and repeated reads hand off
to Python with the appropriate dependencies and user authorization.

Input-size bounds limit parsing work. Each query runs in a spawned, killable child
with a 1–30 second budget (default 10), including library imports. At most two
queries run concurrently; excess requests return a busy error. Workers redirect
incidental library stdout to stderr. Child termination may add up to two seconds
of cleanup after the deadline. Stdio does not
expose a remote listener. Remote transports, auth, tasks, sampling, elicitation and
UI output are separate future design decisions when a concrete need exists.
