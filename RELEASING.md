# Releasing

How to cut a release and publish it to PyPI and Zenodo.

## Versioning

This project uses semantic versioning, MAJOR.MINOR.PATCH.

- MAJOR, for example 1.0.0, is a breaking change to the public API or the MCP
  tool surface.
- MINOR, for example 0.2.0, adds features in a backward-compatible way.
- PATCH, for example 0.1.1, is a small fix or a docs and packaging update.

While the version is below 1.0.0 the API may still change between minor versions.
Release 1.0.0 when the API is declared stable.

## One-time setup (maintainer, in the web UIs)

These cannot be done from the repository, they need your accounts.

1. PyPI Trusted Publishing. Create a PyPI account, then add a **pending**
   trusted publisher, because the project does not exist on PyPI yet. On PyPI go
   to Account, Publishing, and add a pending publisher with these exact fields:
   PyPI project name `lcf-strain-life`, owner `dfieser`, repository
   `lcf-strain-life`, workflow name `publish.yml` (the filename, not a path), and
   environment name `pypi`. In the GitHub repo, Settings, Environments, create an
   environment named `pypi`. On the first successful publish the pending
   publisher converts to a normal one and the project is created. The environment
   name in the workflow must match the one on PyPI exactly.
2. TestPyPI, optional, for a dry run. Same trusted-publisher setup on
   test.pypi.org if you want to test the upload first.
3. Zenodo, optional, for a citable DOI. Log in to zenodo.org with GitHub, open the
   GitHub settings in Zenodo, and switch the toggle ON for `lcf-strain-life`. The
   next GitHub Release is archived automatically and a DOI is minted.

Confirm the distribution name `lcf-strain-life` is free on PyPI before the first
upload.

## Release process (each release)

1. Choose the version bump per the rules above.
2. Update the version in `pyproject.toml` and in `CITATION.cff`, and set the
   `date-released` in `CITATION.cff`.
3. In `CHANGELOG.md`, move the Unreleased notes into a new dated version section.
4. If any equation, default, or citation changed, regenerate
   `docs/PHYSICS_REVIEW.pdf` with `pdflatex docs/PHYSICS_REVIEW.tex`.
5. Verify locally:

   ```
   ./.venv/Scripts/python.exe -m pytest
   ./.venv/Scripts/python.exe -m build
   ./.venv/Scripts/python.exe -m twine check dist/*
   ```

6. Commit and push the version bump:

   ```
   git commit -am "release: vX.Y.Z"
   git push origin main
   ```

7. Create a GitHub Release with a new tag `vX.Y.Z`. Creating the release also
   creates and pushes the tag, which triggers both of these:
   - `publish.yml` runs on the `v*` tag push, builds the sdist and wheel, and
     uploads them to PyPI through trusted publishing.
   - Zenodo archives the release and mints or updates the DOI.

   You can also publish to PyPI without a GitHub Release by pushing a tag
   directly with `git tag vX.Y.Z && git push origin vX.Y.Z`, but then Zenodo is
   not triggered.

8. After the first release, add the Zenodo DOI badge to `README.md` and the DOI
   to `CITATION.cff`. Zenodo gives a concept DOI that always points to the latest
   version, use that one for the badge.

## Optional dry run to TestPyPI

```
./.venv/Scripts/python.exe -m build
./.venv/Scripts/python.exe -m twine upload --repository testpypi dist/*
```
