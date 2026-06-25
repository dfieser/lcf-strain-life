# Installation

## Requirements

Python 3.11 or newer. The core depends on numpy, scipy, pandas, matplotlib,
pydantic, and pyarrow. The MCP server adds the optional `mcp` SDK.

## From source

```
git clone https://github.com/dfieser/lcf-strain-life
cd lcf-strain-life
py -3.13 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[mcp,dev]"
```

On macOS or Linux use `python3 -m venv .venv` and `.venv/bin/python`.

## Extras

- `mcp` installs the MCP server SDK so you can run `lcf-mcp`.
- `dev` installs pytest for the test suite.

## Verify

```
./.venv/Scripts/python.exe -c "import lcf; print(lcf.__version__)"
./.venv/Scripts/python.exe -m pytest -q
```

## Running the MCP server

```
lcf-mcp            # stdio transport
python -m lcf      # same entry point
```

The result store directory comes from the `LCF_STORE_DIR` environment variable
and defaults to `.lcfstore`.
