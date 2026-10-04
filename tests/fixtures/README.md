# Text contract fixtures

The two .prj templates are unchanged public RAS Commander example project files;
provenance.json records canonical URLs and byte hashes. They contain no component
inputs or model results. representative.p01 is explicitly synthetic HEC-RAS plan
syntax for adapter tests, not an executed or hydraulically qualified model.

Tests read only .prj/.pXX source text. Prohibited-input rejection uses empty
extension canaries, never geometry, grid, DSS or HDF contents.

Optional official HEC sample models remain outside the repository. Set
`RAS_MCP_REAL_TEXT_FIXTURES` to an already acquired Muncie directory to run the
explicit project/plan text test. Acquisition and permissions are maintainer-owned;
no downloads or model redistribution occur in the test suite.
