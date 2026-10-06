# Compatibility and release maintenance

Package version, domain-library version and MCP protocol revision are independent.
Version 0.4 uses official MCP SDK >=2.3,<3 and ras-commander >=0.103,<1.
These bounds are declared intent, not proof that every future minor works.

## Published status

ras-commander-mcp 0.4.0 and ras-commander 0.104.0, which publishes `RasText`, are
on PyPI. With 0.104.0 or later, all tools are available; with 0.103.0, units and
descriptions work and metadata/configuration tools report that `RasText` is
unavailable. The published 0.4.0 wheel includes the Windows extended-length read
change (PR #10).

Corpus qualification of the release read 983 HEC-RAS text files with
0 errors on Linux and on native Windows from a UNC project root. Before the
extended-length change, all 69 corpus files whose Windows path reached 260
characters failed with a generic read error; after it, all 69 passed. The PyPI
packages reproduced the results obtained from source. No engine, simulation or
hydraulic check was part of this qualification.

## Release sequence (completed)

1. Review and release upstream `RasText` in ras-commander. Its pure snapshot API
   owns project/plan parsing, requires no engine, and never resolves references.
2. Qualify this adapter against 0.103.0 (units/descriptions; explicit unavailable
   metadata errors), current stable PyPI, and the upstream candidate (full metadata).
3. Build/install wheel and sdist, compare metadata/entry points/version identity,
   and qualify Linux/macOS plus native Windows file-handle containment.
4. Release MCP 0.4 only after the relevant contracts and platform boundaries pass.
   Record exact tested versions in a compatibility report; do not advertise a
   hypothetical upstream version before it is published.

No metadata parser is vendored into MCP. Until `RasText` is installed, metadata tools
fail clearly while units/descriptions retain the current released path. No fallback
initializes a project, loads binaries or accepts HEC terms.

## Current-version workflow

`refresh_compatibility.py` reads fixed PyPI JSON endpoints with response bounds and
writes package versions/dependency metadata/artifact hashes only when they change.
The scheduled/manual workflow opens a draft compatibility PR. The
`ras-commander-release` repository-dispatch hook allows an authorized upstream release
workflow to trigger the same process; cross-repository dispatch credentials/config
remain a maintainer step. No publishing job, installation during queries, or automatic
merge is configured. GitHub settings must permit workflow-created PRs for the update
job to work. PRs created with the default GitHub workflow token may not trigger
additional PR workflows; a maintainer must dispatch the packaging workflow on the
update branch or use an approved GitHub App identity. This is an enablement step,
not evidence that bot PRs received compatibility checks. Actions versions follow the current repository baseline; review supply
chain pins under the organization's policy before enabling workflows.

Minimum/current-compatible contract checks exercise actual units/descriptions,
upstream availability, bounded structured outputs, prohibited-file rejection,
killable workers and SDK auto/legacy stdio sessions.
A newer major SDK must receive migration review rather than an automatic relaxed
range. Existing pins remain valid user choices. A fresh authorized managed install
should use compatible stable releases, then retain a lock for reproducibility.

`server_information(check_updates=true)` gives optional cached latest metadata with
timeouts, explicit offline status and update flags. It never upgrades an environment.

## Implemented qualification boundary

The workflow builds wheel/sdist on Linux and Windows, inspects metadata and file
boundaries, installs minimum/current-compatible dependencies, records resolved
versions, and runs read-only text, bounds, worker and protocol contracts plus
`pip check`. Tests use public library templates and clearly identified synthetic
plan syntax. Separately acquired official model text can be exercised with
`RAS_MCP_REAL_TEXT_FIXTURES`; no model data is redistributed by this package.

Local Linux CPython3.11 qualification covered ras-commander0.103.0/MCP2.3.0 and
the source candidate containing RasText. Published0.103.0 deliberately lacks
RasText: metadata availability errors are tested, while candidate metadata tests
run separately. SDK auto and legacy sessions both passed. These are text/API
contract results, not engine, hydraulic, all-client or native Windows acceptance.

Windows CI runs platform-independent contracts and handle-based reads; POSIX
symlink cases are skipped there. Native Windows junction/UNC/race behavior needs
separate explicit cases and retained evidence before claiming that qualification.

## Local evidence, October 4, 2026

On Linux CPython3.11 with MCP2.3.0 and published RAS Commander0.103.0:

- Released API suite: 69 passed, 2 expected RasText-candidate skips, including an
  optional live bounded PyPI check and locally acquired official example text.
- Source candidate containing RasText: 70 passed, 1 optional live-network skip.
- Installed MCP0.4 wheel, tested outside the checkout: 68 passed, 3 expected
  skips (two unreleased RasText cases and optional live-network check).
- Focused upstream pure RasText readers: 21 passed.
- Wheel/sdist build, metadata/entry-point boundary inspection and `pip check` passed.

The real fixture is official Muncie project/plan text from the HEC6.6 example
archive. Its `.p01` records `Program Version=5.00`; archive label and source program
version are different facts. Source hashes were retained privately; model inputs
and descriptions were not redistributed. Queries read only the four explicitly
named project/plan text files, never geometry or binary results.

Retained logs/XML and exact dependency/artifact hashes are in the implementation
packet. No engine/simulation/physical verification was performed. Native Windows
cases remain unobserved locally; cross-platform CI results must be reviewed before
expanding the platform claim.
