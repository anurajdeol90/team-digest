# Contributing to team-digest

Thanks for contributing!

## Workflow

- All changes land via PRs.
- CI must be green (tests + packaging sanity check).
- **Releases are automatic on push to `main`.** Bump the version before merging.

## Releasing

We use [bumpver](https://pypi.org/project/bumpver/).

1. Install once:
   ```bash
   pip install bumpver
