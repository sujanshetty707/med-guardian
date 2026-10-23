# Med-Guardian Windows PowerShell helper
param (
    [string]$Command = "help"
)

$VENV_PYTHON = ".\.venv\Scripts\python.exe"
$VENV_PYTEST = ".\.venv\Scripts\pytest.exe"

switch ($Command) {
    "test" {
        Write-Host "Running Pytest Test Suite..." -ForegroundColor Cyan
        & $VENV_PYTEST -v tests/
    }
    "sim" {
        Write-Host "Running End-to-End ASI:One Simulator..." -ForegroundColor Cyan
        & $VENV_PYTHON tests/e2e_chat_sim.py
    }
    "seed" {
        Write-Host "Seeding Demo Data..." -ForegroundColor Cyan
        & $VENV_PYTHON scripts/seed_demo_data.py
    }
    "register" {
        Write-Host "Displaying Agentverse Registration Profiles..." -ForegroundColor Cyan
        & $VENV_PYTHON scripts/register_agents.py
    }
    "run" {
        Write-Host "Starting All 5 Med-Guardian Agents via Bureau..." -ForegroundColor Cyan
        & $VENV_PYTHON scripts/run_agents.py
    }
    default {
        Write-Host "Med-Guardian CLI Commands:" -ForegroundColor Yellow
        Write-Host "  .\run.ps1 test       - Run all 12 unit and resilience tests"
        Write-Host "  .\run.ps1 sim        - Run the multi-turn ASI:One primary demo simulation"
        Write-Host "  .\run.ps1 seed       - Seed initial demo patient and caregiver records"
        Write-Host "  .\run.ps1 register   - Show deterministic agent addresses & Agentverse metadata"
        Write-Host "  .\run.ps1 run        - Start the 5-agent Bureau network"
    }
}
