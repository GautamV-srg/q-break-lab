# Run Q-Break locally with one command: API + built UI on http://localhost:8000
#
#   powershell -ExecutionPolicy Bypass -File .\start.ps1             # build the UI, start the server
#   powershell -ExecutionPolicy Bypass -File .\start.ps1 -SkipBuild  # reuse the last UI build
#
# Every MiniAES key size (4/6/8/10/12-bit) and every RSA modulus is enabled. 12-bit attacks
# take about 6-9 minutes on a fast multi-core PC; the request limit is 15 minutes.
param([switch]$SkipBuild, [int]$Port = 8000)

# Native commands are checked through $LASTEXITCODE (Stop would turn their stderr into errors).
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Creating the Python virtual environment (.venv)..."
    py -3.11 -m venv (Join-Path $root ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11 is required (py -3.11 failed)." }
}
& $py -c "import qbreak, kyber_py, cryptography, qiskit_aer" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing backend dependencies..."
    & $py -m pip install --upgrade pip
    & $py -m pip install -e "$root\backend[dev]"
    if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
}

if (-not $SkipBuild -or -not (Test-Path "$root\frontend\dist\index.html")) {
    Push-Location "$root\frontend"
    try {
        if (-not (Test-Path "node_modules")) {
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install failed (is Node.js 20 installed?)." }
        }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed." }
    } finally { Pop-Location }
}

$env:STATIC_DIR = Join-Path $root "frontend\dist"
if (-not $env:QBREAK_KEY_BITS) { $env:QBREAK_KEY_BITS = "4,6,8,10,12" }
if (-not $env:SYMMETRIC_MAX_KEY_BITS) { $env:SYMMETRIC_MAX_KEY_BITS = "12" }
if (-not $env:QBREAK_AES_TIMEOUT_S) { $env:QBREAK_AES_TIMEOUT_S = "900" }

Write-Host ""
Write-Host "Q-Break is starting on http://localhost:$Port  (Ctrl+C to stop)"
Write-Host "MiniAES key sizes: $env:QBREAK_KEY_BITS   request limit: $env:QBREAK_AES_TIMEOUT_S s"
Write-Host ""
Push-Location "$root\backend"
try { & $py -m uvicorn qbreak.api.main:app --port $Port } finally { Pop-Location }
