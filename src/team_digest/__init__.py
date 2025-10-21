# src/team_digest/__init__.py
try:
    from importlib.metadata import version, PackageNotFoundError
except Exception:
    from importlib_metadata import version, PackageNotFoundError  # for Py<3.8 backport if needed

try:
    __version__ = version("team-digest")  # must match your PyPI project name
except PackageNotFoundError:
    __version__ = "0+unknown"
