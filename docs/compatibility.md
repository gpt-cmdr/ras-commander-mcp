# Compatibility and release maintenance

Package version, domain-library version and MCP protocol revision are independent.
The 0.4 candidate uses official MCP SDK >=2.3,<3 and ras-commander >=0.103,<1.
These bounds are declared intent, not proof that every future minor works.

## Release sequence

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

Minimum/current-stable contract checks should exercise actual units/descriptions,
upstream availability, bounded structured outputs and prohibited-file rejection.
A newer major SDK must receive migration review rather than an automatic relaxed
range. Existing pins remain valid user choices. A fresh authorized managed install
should use compatible stable releases, then retain a lock for reproducibility.

`server_information(check_updates=true)` gives optional cached latest metadata with
timeouts, explicit offline status and update flags. It never upgrades an environment.

## Implemented qualification boundary

The packaging workflow builds wheel/sdist on Linux and Windows, inspects metadata
and file boundaries, installs minimum/current-compatible dependencies, reports
resolved versions, and runs `pip check`. It does not run project API contract
scenarios, read-only filesystem assertions, a protocol session, or Windows path
attack cases. Those functional checks remain pending explicit task authorization;
a passing packaging job is not functional or platform qualification.
