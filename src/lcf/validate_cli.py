"""Command line validation of interchange documents.

``lcf-validate file.json [more.json ...]`` validates each file against the
formats defined in :mod:`lcf.interchange` and exits nonzero when any file is
invalid. ``--write-schemas DIR`` writes the JSON Schema artifacts instead,
that is how ``docs/schemas/`` is generated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import interchange

#: The document kinds with schema artifacts, in output order.
KINDS = ("material", "test-record", "collection")


def _validate_files(paths: list[str]) -> int:
    failed = 0
    for raw in paths:
        path = Path(raw)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL {path}: cannot read JSON: {exc}")
            failed += 1
            continue
        result = interchange.validate_document(doc)
        if result["valid"]:
            print(f"ok   {path}: {result['schema']}@{result['version']}")
        else:
            failed += 1
            print(f"FAIL {path}")
            for err in result["errors"]:
                print(f"     {err}")
    return 1 if failed else 0


def _write_schemas(directory: str) -> int:
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    for kind in KINDS:
        target = out_dir / f"{kind}.v1.schema.json"
        text = json.dumps(
            interchange.json_schema(kind), indent=2, sort_keys=True
        )
        target.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lcf-validate",
        description=(
            "Validate lcf-strain-life interchange documents, or write the "
            "JSON Schema artifacts."
        ),
    )
    parser.add_argument("files", nargs="*", help="JSON documents to validate")
    parser.add_argument(
        "--write-schemas", metavar="DIR", default=None,
        help="write the JSON Schemas for all document kinds to DIR",
    )
    args = parser.parse_args(argv)
    if args.write_schemas is not None:
        return _write_schemas(args.write_schemas)
    if not args.files:
        parser.error("give at least one file, or --write-schemas DIR")
    return _validate_files(args.files)


if __name__ == "__main__":
    sys.exit(main())
