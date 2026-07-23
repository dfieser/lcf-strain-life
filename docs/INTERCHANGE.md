# Interchange formats

lcf-strain-life defines three small JSON document formats for exchanging
strain-life fatigue data between tools and for publishing open datasets.
There is no de facto standard for this exchange. These formats are documented
here so others can adopt or adapt them, and the library is their reference
reader, writer, and validator.

Machine-readable JSON Schemas live in `docs/schemas/`:
[material](schemas/material.v1.schema.json),
[test-record](schemas/test-record.v1.schema.json), and
[collection](schemas/collection.v1.schema.json). They are generated from the
pydantic models in `lcf.interchange` and a test fails if the checked-in
artifacts drift from the code.

| Format id | One line |
|---|---|
| `lcf-strain-life/material@1` | Strain-life constants for one material |
| `lcf-strain-life/test-record@1` | One strain-controlled fatigue test |
| `lcf-strain-life/collection@1` | A dataset manifest bundling the other two |

## Versioning policy

The `version` field is an integer. Readers refuse unknown schemas, unknown
versions, and unknown unit systems rather than guessing. Within a version,
new optional fields may be added over time and readers accept and preserve
unknown fields. Any breaking change, removing a field, changing a meaning or
a unit, bumps the version. Version 1 of each format is frozen as specified
here.

## Unit conventions, fixed

All documents use true stress and true strain. The `units` block is required
and must match exactly.

| Quantity | Unit |
|---|---|
| stress | MPa |
| strain | dimensionless fraction |
| life | reversals, 2N |
| temperature (test-record only) | degrees C |

The exponents b and c are negative by convention. Documents violating these
conventions are refused at import, nothing is silently converted.

## material@1

The four strain-life constants with the cyclic curve and provenance.
Produced by `lcf.interchange.export_material`, read by `import_material`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema` | string | yes | `lcf-strain-life/material` |
| `version` | int | yes | 1 |
| `name` | string | yes | Material name |
| `units` | object | yes | Exactly the fixed unit block |
| `E` | number > 0 | yes | Elastic modulus, MPa |
| `basquin.sigma_f` | number > 0 | yes | Fatigue strength coefficient, MPa |
| `basquin.b` | number < 0 | yes | Fatigue strength exponent |
| `coffin_manson.eps_f` | number > 0 | yes | Fatigue ductility coefficient |
| `coffin_manson.c` | number < 0 | yes | Fatigue ductility exponent |
| `transition_reversals` | number > 0 | no | 2N where elastic and plastic parts are equal |
| `ramberg_osgood.K_prime` | number > 0 | no | Cyclic strength coefficient, MPa |
| `ramberg_osgood.n_prime` | number > 0 | no | Cyclic strain hardening exponent |
| `provenance.source` | string | no | Citation for the constants |
| `provenance.notes` | string | no | Free text |

## test-record@1

One strain-controlled fatigue test, the unit of an open dataset. The design
follows the reporting spirit of ASTM E606: enough metadata that the test can
be interpreted, with every field beyond the minimal core optional. Produced
by `export_test_record`, read by `import_test_record`.

The minimal core is `record_id`, `material`, the control amplitude, the
failure outcome, and a provenance source. A record without provenance is not
accepted.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema` | string | yes | `lcf-strain-life/test-record` |
| `version` | int | yes | 1 |
| `record_id` | string | yes | Unique id within a collection |
| `material` | string | yes | Material name |
| `condition` | string | no | Heat treatment or condition |
| `units` | object | yes | Exactly the fixed unit block, with temperature |
| `test.control_mode` | string | yes | `strain` or `stress` |
| `test.strain_amplitude` | number > 0 | with strain control | Controlled true strain amplitude |
| `test.stress_amplitude` | number > 0 | with stress control | Controlled true stress amplitude, MPa |
| `test.strain_ratio` | number | no | R ratio of the controlled strain |
| `test.stress_ratio` | number | no | R ratio of the controlled stress |
| `test.frequency_hz` | number > 0 | no | Cycling frequency |
| `test.strain_rate` | number > 0 | no | Strain rate, per second |
| `test.temperature_C` | number | no | Test temperature |
| `test.environment` | string | no | For example lab air, vacuum |
| `test.waveform` | string | no | For example triangular |
| `specimen.geometry` | string | no | For example uniform gauge, hourglass |
| `specimen.gauge_diameter_mm` | number > 0 | no | Gauge diameter |
| `specimen.gauge_length_mm` | number > 0 | no | Gauge length |
| `specimen.surface_finish` | string | no | Surface preparation |
| `specimen.orientation` | string | no | Sampling orientation |
| `response.stress_amplitude` | number > 0 | no | Stabilized stress amplitude, MPa |
| `response.mean_stress` | number | no | Stabilized mean stress, MPa |
| `response.elastic_strain_amplitude` | number > 0 | no | Stabilized elastic strain amplitude |
| `response.plastic_strain_amplitude` | number >= 0 | no | Stabilized plastic strain amplitude |
| `response.at_life_fraction` | number in (0, 1] | no | Life fraction the values were read at, 0.5 is half life |
| `failure.reversals_to_failure` | number > 0 | yes | 2Nf, or the suspension point for a runout |
| `failure.runout` | bool | no, default false | True when suspended without failure |
| `failure.criterion` | string | no | For example 30% load drop |
| `per_cycle` | object | no | Per-cycle evolution table, see below |
| `provenance.source` | string | yes | Citation or origin of the data |
| `provenance.license` | string | no | SPDX id when the contributor licenses own data |
| `provenance.origin` | string | no | One of `own-data`, `republished-factual`, `digitized`, `permissioned` |
| `provenance.notes` | string | no | Free text |

### The per-cycle table

Most published strain-life data reduce each test to one row. The evolution of
the material during the test, cyclic hardening and softening, mean stress
relaxation, ratcheting, is lost. `per_cycle` preserves it: a rectangular
table with named `columns`, numeric `rows`, and an optional `units` map for
columns outside the fixed conventions. Recommended column names follow the
library's per-cycle metrics: `cycle`, `stress_amplitude`, `mean_stress`,
`elastic_strain_amplitude`, `plastic_strain_amplitude`,
`hysteresis_energy_MJ_m3`. Rows must all have exactly one value per column.

## collection@1

A dataset manifest bundling material documents and test records. Produced by
`export_collection`, read by `import_collection`. Every member document is
validated, a collection with an invalid member is invalid. `record_id`
values must be unique across the collection, and an empty collection is
refused.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema` | string | yes | `lcf-strain-life/collection` |
| `version` | int | yes | 1 |
| `name` | string | yes | Collection name |
| `description` | string | no | What the collection contains |
| `license` | string | yes | SPDX id of the compilation, see note |
| `created` | string | no | ISO date, `YYYY-MM-DD`, supplied by the assembler |
| `doi` | string | no | DOI of the published collection |
| `homepage` | string | no | URL |
| `contributors` | array | no | `{name, orcid}` objects |
| `materials` | array | no | material@1 documents |
| `records` | array | no | test-record@1 documents |

Note on licensing. The collection `license` covers the compilation, the
selection, arrangement, and metadata. It does not change the status of the
underlying numbers. Each record carries its own provenance: own data can be
licensed by its owner, factual values re-tabulated from a publication are
cited through `source` with `origin` set to `republished-factual`. See
[CONTRIBUTING-DATA.md](CONTRIBUTING-DATA.md) for the rules.

## Validating documents

Three ways, all the same checks.

Command line:

```bash
lcf-validate my_collection.json
```

Python:

```python
from lcf import interchange
result = interchange.validate_document(doc)   # {"valid": ..., "errors": [...]}
record = interchange.import_test_record(doc)  # raises ValueError with the reason
```

MCP: the `validate_interchange` tool returns the same structured verdict, and
`summarize_collection` reports counts and ranges for a collection.

## Adapters

`to_pylife_woehler` and `from_pylife_woehler` express the Basquin line in
pyLife WoehlerCurve conventions. `to_py_fatigue_sn` does the same for
py-fatigue. Both are shape-compatible with the documented conventions of
those libraries and round-trip exactly, but they are not integration-tested
against installed copies. A strain-life curve has no endurance limit, so the
pyLife knee `ND` is a representation choice recorded in the output.
