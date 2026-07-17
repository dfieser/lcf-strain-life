"""Bundled example datasets, published and citable.

One module holds the example data used by the README, the examples, and the
graphical interface, so the numbers exist in exactly one place. The test
suite keeps its own copy on purpose: a golden reference must stay independent
of the code it validates.
"""

from __future__ import annotations

import pandas as pd

SAE1137_CITATION = (
    "Williams, C.R., Lee, Y.-L., Rilly, J.T., 'A practical method for "
    "statistical analysis of strain-life fatigue data', International "
    "Journal of Fatigue 25 (2003) 427-436"
)

SAE1137_E = 208000.0
"""Nominal elastic modulus for the SAE 1137 example (MPa)."""

_SAE1137 = {
    "test": [f"SAE1137-{i}" for i in range(1, 7)],
    "total_strain_amp": [0.00900, 0.00700, 0.00500, 0.00300, 0.00200, 0.00175],
    "stress_amp": [553.0, 522.0, 464.0, 405.0, 350.0, 319.0],
    "reversals": [4234.0, 7398.0, 14768.0, 77104.0, 437498.0, 3327958.0],
}


def sae1137_reduced() -> pd.DataFrame:
    """Published SAE 1137 per-test reduced strain-life data.

    One row per test: half-life total strain amplitude (fraction), stress
    amplitude (MPa), and reversals to failure 2N_f. Source:
    :data:`SAE1137_CITATION`.
    """
    return pd.DataFrame(_SAE1137)
