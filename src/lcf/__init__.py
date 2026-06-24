"""lcf — material-agnostic Low Cycle Fatigue (LCF) strain-life analysis.

Core library for reducing strain-controlled fatigue test data and fitting the
standard strain-life models (Basquin, Coffin-Manson, Ramberg-Osgood) plus
mean-stress corrections. All analysis uses *true* stress/strain; the fatigue
exponents ``b`` and ``c`` are negative.

See ``docs/`` for the equations, workflow, and design decisions (ADRs).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
