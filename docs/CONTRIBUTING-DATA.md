# Contributing strain-life data

lcf-strain-life is building an open, machine-readable collection of
strain-controlled fatigue data. The formats are specified in
[INTERCHANGE.md](INTERCHANGE.md) and the current seed collection lives at
[`docs/data/seed_collection.json`](data/seed_collection.json). This page
says what a contribution needs. The bar is deliberately explicit because a
fatigue database is only useful if every number can be trusted and traced.

## What a contribution is

One `collection@1` JSON document, or a set of `test-record@1` documents,
validated with the library:

```bash
pip install lcf-strain-life
lcf-validate my_records.json
```

Open a GitHub issue or pull request with the validated file and the
provenance story. Small contributions are welcome, one well-documented test
beats fifty untraceable rows.

## The licensing rules, non-negotiable

Every record states where its numbers came from. Four origins are accepted.

1. `own-data`. You generated the data and have the right to release it.
   License it CC0-1.0 or CC-BY-4.0 in `provenance.license`. This is the most
   valuable kind of contribution, especially with per-cycle data.
2. `republished-factual`. Numeric values re-tabulated from a published table
   or text, with the full citation in `provenance.source`. Factual data
   points are not copyrightable in most jurisdictions, but the presentation
   is, so re-tabulate values, never reproduce whole formatted tables or
   figures.
3. `digitized`. Values read off a published figure, cited, with
   `provenance.notes` stating the digitization method and its precision.
4. `permissioned`. Data used with the explicit permission of its owner,
   noted in `provenance.notes`.

Not accepted under any framing: data from sources whose terms prohibit
redistribution or bulk extraction. That includes the NIMS fatigue data
sheets, the FKM guideline tables, MMPDS, licensed SAE databases, and any
scraped collection. If the terms are unclear, ask the owner first or leave
it out.

## Metadata checklist, per record

Required by the schema:

- `record_id` unique within the collection, `material`, the controlled
  amplitude, `failure.reversals_to_failure`, and `provenance.source`.

Strongly recommended, following ASTM E606 reporting practice:

- Control: `strain_ratio`, `frequency_hz` or `strain_rate`,
  `temperature_C`, `environment`, `waveform`.
- Specimen: `geometry`, gauge dimensions, `surface_finish`, `orientation`.
- Material: `condition`, the heat treatment state.
- Response at half life: `stress_amplitude`, `mean_stress`,
  `elastic_strain_amplitude`, `plastic_strain_amplitude`, and
  `at_life_fraction`.
- `failure.criterion`, for example 30% load drop.
- Runouts: set `failure.runout` true and give the suspension point. Runouts
  matter, the statistics tools treat them by maximum likelihood instead of
  deleting them.

## Per-cycle data, the most valuable part

Reduced constants exist in many places. What no open dataset provides is the
cyclic evolution: hardening and softening, mean stress relaxation,
ratcheting. If you have per-cycle values, ship them in the `per_cycle` table
with columns like `cycle`, `stress_amplitude`, `mean_stress`,
`plastic_strain_amplitude`. Units follow the fixed conventions, true stress
in MPa, strain as a fraction.

## Units and conventions

True stress and true strain. Stress in MPa, strain as a dimensionless
fraction, life in reversals, temperature in degrees C. Exponents b and c
negative. The validator refuses documents that deviate, nothing is silently
converted.

## What happens to contributions

Accepted records join a versioned collection in this repository, validated
in CI, with contributors credited in the collection metadata. When the
collection reaches a scale worth archiving it will be deposited for a DOI.
The maintainers may reformat metadata but never alter data values, and every
change to a published collection is versioned.
