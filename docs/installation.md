# Installation

## Requirements

Python 3.11 or newer. The core depends on numpy, scipy, pandas, matplotlib,
pydantic, and pyarrow.

## From PyPI

```bash
pip install lcf-strain-life
```

Extras:

- `mcp` installs the MCP SDK so you can run the `lcf-mcp` server.
- `gui` installs Streamlit for the no-code interface, `lcf-gui`.
- `dev` installs pytest, ruff, and mypy.
- `docs` installs the documentation toolchain.

```bash
pip install "lcf-strain-life[mcp,gui]"
```

## From source

```bash
git clone https://github.com/dfieser/lcf-strain-life
cd lcf-strain-life
py -3.13 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[mcp,gui,dev]"
```

On macOS or Linux use `python3 -m venv .venv` and `.venv/bin/python`.

## Verify

```bash
python -c "import lcf; print(lcf.__version__)"
python -m pytest -q
```

## Command line entries

| Command | What it starts |
|---|---|
| `lcf-mcp` | The MCP server on stdio, same as `python -m lcf` |
| `lcf-gui` | The no-code Streamlit interface |
| `lcf-validate` | Validation of interchange JSON documents |

The result store directory comes from the `LCF_STORE_DIR` environment
variable and defaults to `.lcfstore`.

## MCP client configuration

A typical MCP client entry:

```json
{
  "mcpServers": {
    "lcf-strain-life": {
      "command": "lcf-mcp"
    }
  }
}
```

The [agent usage guide](AGENT_USAGE.md) documents every tool.
