<#
.SYNOPSIS
  Windows fallback for the Makefile targets, for when GNU Make is not installed.
  Keep the two in step: every target here must do what the Makefile does.

.EXAMPLE
  .\make.ps1 dev
  .\make.ps1 migrate
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('dev', 'down', 'logs', 'shell', 'migrate', 'migrate-check', 'test', 'lint', 'fmt',
        'seed', 'instruments', 'create-user', 'kite-credentials')]
    [string]$Target = 'dev'
)

$ErrorActionPreference = 'Stop'
$compose = @('compose', '-f', 'docker-compose.dev.yml')

function Invoke-Compose { docker @compose @args; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
function Invoke-Api { Invoke-Compose exec -T api @args }

switch ($Target) {
    'dev' {
        Invoke-Compose up -d --build
        Write-Output 'API health: http://localhost:8000/api/v1/health'
        Write-Output "Web: run 'npm run dev' in apps/web"
    }
    'down' { Invoke-Compose down }
    'logs' { Invoke-Compose logs -f api }
    'shell' { Invoke-Compose exec api bash }
    'migrate' { Invoke-Api alembic upgrade head }
    'migrate-check' { Invoke-Api alembic check }
    'test' { Invoke-Api pytest }
    'lint' {
        Invoke-Api ruff check .
        Invoke-Api ruff format --check .
        Invoke-Api mypy
        Push-Location apps/web
        try { npm run lint; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } } finally { Pop-Location }
    }
    'fmt' {
        Invoke-Api ruff format .
        Invoke-Api ruff check --fix .
    }
    'seed' { Invoke-Api python -m app.cli seed }
    'instruments' { Invoke-Api python -m app.cli instruments }
    # These prompt, so they need a terminal: no -T.
    'create-user' { Invoke-Compose exec api python -m app.cli create-user }
    'kite-credentials' { Invoke-Compose exec api python -m app.cli set-kite-credentials }
}
