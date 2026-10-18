$ErrorActionPreference = 'Stop'
$taskProject = $PSScriptRoot
$taskPython = Join-Path $taskProject '.venv\Scripts\python.exe'
$taskVersion = (Get-Content -Raw (Join-Path $taskProject 'package.json') | ConvertFrom-Json).version
$taskName = "VGN-X68-Custom-Firmware-$taskVersion-Windows"
Push-Location -LiteralPath $taskProject
try {
    & $taskPython -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Checks failed.' }
    # Single EXE. Only runtime files are bundled: our patches, fonts, pixel art and the knowledge doc.
    # No VGN binary is included; the app fetches the official payload from VGN on first install.
    & $taskPython -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name $taskName `
        --icon assets/icon.ico `
        --add-data 'firmware-patches;firmware-patches' `
        --add-data 'docs/AI-KNOWLEDGE.md;docs' `
        --add-data 'assets/fonts;assets/fonts' `
        --add-data 'assets/icon.png;assets' `
        --add-data 'assets/pixel/home-scene.png;assets/pixel' `
        --add-data 'assets/pixel/battery-scene.png;assets/pixel' `
        --add-data 'assets/pixel/bunny-sprite.png;assets/pixel' `
        --add-data 'assets/pixel/lcd-preview.png;assets/pixel' `
        --hidden-import tools.reflash_v0113 --hidden-import x68.windows_input app.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }
    $taskExe = Join-Path $taskProject "dist\$taskName.exe"
    $taskHash = (Get-FileHash -LiteralPath $taskExe -Algorithm SHA256).Hash.ToLower()
    "$taskHash  $taskName.exe" | Out-File -Encoding ascii (Join-Path $taskProject 'dist\SHA256SUMS.txt')
    Get-Item $taskExe | Select-Object Name, Length
    Write-Output "SHA256 $taskHash"
} finally { Pop-Location }
