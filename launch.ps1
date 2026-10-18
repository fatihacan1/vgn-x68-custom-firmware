$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $projectDir '.venv')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv (Join-Path $projectDir '.venv')
    } else {
        throw 'Python 3.10 or newer is required.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& $pythonExe -c "import hid; from PIL import Image, ImageTk"
if ($LASTEXITCODE -ne 0) {
    & $pythonExe -m pip install --disable-pip-version-check -r (Join-Path $projectDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
$pythonWindowless = Join-Path $projectDir '.venv\Scripts\pythonw.exe'
$applicationPath = Join-Path $projectDir 'app.py'
Start-Process -FilePath $pythonWindowless -ArgumentList @('"' + $applicationPath + '"') -WorkingDirectory $projectDir -WindowStyle Hidden
