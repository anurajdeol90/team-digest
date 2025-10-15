# Stop on errors
$ErrorActionPreference = "Stop"

Write-Host "== Ensure in-package examples layout =="
$examplesLogs = "team_digest\examples\logs"
$examplesCfg  = "team_digest\examples\config"
New-Item -ItemType Directory -Force -Path $examplesLogs | Out-Null
New-Item -ItemType Directory -Force -Path $examplesCfg  | Out-Null

# Move sample log into in-package examples if you currently keep it elsewhere
if (Test-Path ".\examples\logs\sample.md") {
    Write-Host "Moving examples/logs/sample.md -> team_digest/examples/logs/"
    Move-Item ".\examples\logs\sample.md" "$examplesLogs\" -Force
}

# If you had config templates at repo root, move them into examples/config/
foreach ($f in @("config.json","people_map.json")) {
    if (Test-Path ".\$f") {
        Write-Host "Moving $f -> team_digest/examples/config/"
        Move-Item ".\$f" "$examplesCfg\" -Force
    }
}

# Remove dev-only clutter at repo root (customers don't need these)
$toDelete = @(
    "digest.bat",
    "Makefile",
    "pytest.ini",
    "requirements.txt",
    "requirements.lock.txt"
)

foreach ($f in $toDelete) {
    if (Test-Path ".\$f") {
        Write-Host "Removing $f"
        Remove-Item ".\$f" -Force
    }
}

# Keep .editorconfig/.gitattributes/.gitignore for contributors by default.
# Flip to $true if you really want them gone.
$deleteEditorFiles = $false
if ($deleteEditorFiles) {
    foreach ($f in @(".editorconfig",".gitattributes",".gitignore")) {
        if (Test-Path ".\$f") {
            Write-Host "Removing $f"
            Remove-Item ".\$f" -Force
        }
    }
}

# Write/overwrite MANIFEST.in exactly as specified
@"
# --- Core metadata & docs
include README.md
include LICENSE
include CHANGELOG.md
include VERSION

# --- Package source
graft team_digest

# --- Examples & docs (source copies; wheel includes examples via package-data)
recursive-include team_digest/examples *.md *.json *.yml *.yaml
graft docs

# --- Exclusions (don’t ship dev clutter in SDist)
exclude Makefile
exclude pytest.ini
exclude requirements*.txt
exclude digest.bat

# Extra safety: never include git internals
prune .git
"@ | Set-Content -Encoding UTF8 ".\MANIFEST.in"

Write-Host "== Cleanup complete. Next: build & verify =="
