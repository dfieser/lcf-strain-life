# Installing the lcf-strain-life MCP server

Instructions for an AI assistant setting this server up for a user. Follow
them in order. Nothing here needs an API key, an account, or a network
service at run time. The server runs locally over stdio and stores results
on the user's machine.

## What the user gets

Tools for low cycle fatigue analysis of materials: reduce raw
strain-controlled test data, fit Basquin, Coffin-Manson, and
Ramberg-Osgood constants, count rainflow cycles per ASTM E1049, apply
mean-stress corrections, run notch and multiaxial analysis, fit design
curves, and predict life. Every method cites a published source. Call
`tools/list` for the exact set in the installed version.

## Requirements

- Python 3.11 or newer.
- Either `uv`, which needs no prior install of the package, or `pip`.

## Option 1, uv, nothing to install first

Preferred when the user has [uv](https://docs.astral.sh/uv/) or is willing
to install it. Add this to the MCP client configuration:

```json
{
  "mcpServers": {
    "lcf": {
      "command": "uvx",
      "args": ["--from", "lcf-strain-life[mcp]", "lcf-mcp"]
    }
  }
}
```

uv resolves and caches the package on first run. No separate install step.

## Option 2, pip

```bash
pip install "lcf-strain-life[mcp]"
```

Then register the installed entry point:

```json
{
  "mcpServers": {
    "lcf": {
      "command": "lcf-mcp"
    }
  }
}
```

If `lcf-mcp` is not on PATH, use the interpreter that ran the install:

```json
{
  "mcpServers": {
    "lcf": {
      "command": "python",
      "args": ["-m", "lcf"]
    }
  }
}
```

## Client-specific notes

- VS Code in Copilot agent mode uses the key `servers`, not `mcpServers`,
  in `.vscode/mcp.json`. Everything else is the same.
- Claude Desktop needs a restart after the config file changes.
- Claude Code can add it in one command:
  `claude mcp add lcf -- uvx --from "lcf-strain-life[mcp]" lcf-mcp`

## Optional configuration

The server writes computed results to a local store so they can be
recalled without recomputation. The directory comes from `LCF_STORE_DIR`
and defaults to `.lcfstore` in the working directory. Set it only if the
user wants a specific location:

```json
{
  "mcpServers": {
    "lcf": {
      "command": "lcf-mcp",
      "env": { "LCF_STORE_DIR": "/path/to/store" }
    }
  }
}
```

## Verify the install

Call `fit_strain_life` with the published SAE 1137 example. These inputs
have known outputs, so they confirm the server computes correctly rather
than merely starting:

```json
{
  "total_strain_amp": [0.009, 0.007, 0.005, 0.003, 0.002, 0.00175],
  "stress_amp": [553, 522, 464, 405, 350, 319],
  "reversals": [4234, 7398, 14768, 77104, 437498, 3327958],
  "E": 208000,
  "min_plastic_strain": 5e-4
}
```

Expected, to three significant figures: `basquin.sigma_f` about 1073 MPa,
`basquin.b` about -0.0836, `coffin_manson.eps_f` about 1.11,
`coffin_manson.c` about -0.620, and `transition_reversals` about 22,400.
If those match, the install is good.

The result also carries a note that this material departs from Masing
behaviour. That is a property of the data, not an error.

## Units and conventions, tell the user

Stress and modulus in MPa. Strain is a dimensionless fraction, so 0.005
means 0.5 percent, not 5. Life is in reversals, and two reversals make one
cycle. All analysis uses true stress and true strain, and the exponents
`b` and `c` are negative.

## If something fails

- `lcf-mcp` not found: the `mcp` extra was not installed. Use
  `pip install "lcf-strain-life[mcp]"`, not `pip install lcf-strain-life`.
- Python too old: the package needs 3.11 or newer.
- More fixes are on the
  [troubleshooting page](https://github.com/dfieser/lcf-strain-life/wiki/Troubleshooting).
