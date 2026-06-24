# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Major design decisions are recorded as ADRs in [docs/decisions/](docs/decisions/).

## [Unreleased]

### Added
- Repository scaffolding: `pyproject.toml` (hatchling, src layout), MIT `LICENSE`,
  `README.md`, `.gitignore`, this changelog, and the ADR decision log.
- Python 3.13 development virtual environment; dependency stack verified
  (numpy 2.5, scipy 1.18, pandas 3.0, matplotlib 3.11, pydantic 2.13, pyarrow 24, mcp 1.28).
- ADR-0001 through ADR-0008 capturing the core design decisions derived from the
  deep-research implementation reference.

### Notes
- Pre-existing documentation (`docs/reference/`, `docs/design/`) authored during the
  scoping phase is retained as the analytical specification.
