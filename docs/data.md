# The open data effort

Fatigue model papers routinely state the same problem: there is no
independent, well-documented, redistributable strain-life data to validate
against. Published S-N collections exist, but curated strain-controlled
records with metadata, runouts, and per-cycle evolution do not.

lcf-strain-life is building that dataset in the open, in three layers.

## 1. The formats

Versioned, machine-readable JSON formats for material constants, single
test records with ASTM E606-style metadata, and dataset collections,
specified in [INTERCHANGE.md](INTERCHANGE.md) with JSON Schemas for
[materials](schemas/material.v1.schema.json),
[test records](schemas/test-record.v1.schema.json), and
[collections](schemas/collection.v1.schema.json). The library is the
reference reader, writer, and validator, and `lcf-validate` checks any
document from the command line.

## 2. The seed collection

A small, citable, schema-reference collection ships with the repository at
[`docs/data/seed_collection.json`](data/seed_collection.json) and builds
programmatically from `lcf.datasets.seed_collection()`:

- Six SAE 1137 strain-controlled tests, re-tabulated from Williams, Lee,
  Rilly, International Journal of Fatigue 25 (2003) 427-436.
- Three verified published constant sets as material documents, SAE 1005
  from Lee, Pan, Hathaway, Barkey 2005, and Man-Ten and RQC-100 from the
  SAE committee benchmark constants with cyclic curve constants from Wu,
  Zhang, Paraschivoiu, Materials 17 (2024) 4521.

Every value is factual data re-tabulated with attribution, every entry
carries provenance, and a test suite validates the collection and guards
the artifact against drift.

Stated plainly: the seed demonstrates the formats and the pipeline. It is
not yet a database at publishable scale. Growing it is the point of the
contribution process.

## 3. Contributions

[CONTRIBUTING-DATA.md](CONTRIBUTING-DATA.md) defines what a contribution
needs: provenance for every record, explicit license basis, E606-style
metadata, runouts flagged rather than dropped, and per-cycle tables where
they exist, because cyclic evolution is the data no open collection
provides.

## Using a collection

```python
from lcf import datasets, interchange

col = datasets.seed_collection()
interchange.validate_document(col)          # {"valid": True, ...}
records = interchange.import_collection(col).records

import pandas as pd
df = pd.DataFrame({
    "strain_amplitude": [r.test.strain_amplitude for r in records],
    "reversals": [r.failure.reversals_to_failure for r in records],
    "runout": [r.failure.runout for r in records],
})
```

From an MCP client, `validate_interchange` checks any document and
`summarize_collection` reports counts, ranges, and licensing at a glance.
