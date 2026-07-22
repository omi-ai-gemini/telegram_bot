$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $ScriptDir "gateway_config.json"

if (Test-Path $ConfigPath) {
    Write-Host "gateway_config.json already exists. Existing settings were kept."
    exit 0
}

$bytes = New-Object byte[] 48
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $rng.GetBytes($bytes)
}
finally {
    $rng.Dispose()
}
$secret = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')

$candidates = @(
    "N:\Comfy-Desktop\ComfyUI-Installs\Telemini文生圖\ComfyUI",
    "C:\ComfyUI",
    "C:\ComfyUI_windows_portable\ComfyUI"
)

$comfyRoot = $candidates[0]
foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
        $comfyRoot = $candidate
        break
    }
}

$config = [ordered]@{
    LOCAL_AI_GATEWAY_SECRET = $secret
    LOCAL_AI_GATEWAY_PORT = 8787
    COMFYUI_BASE_URL = "http://127.0.0.1:8188"
    COMFYUI_ROOT = $comfyRoot
    COMFYUI_TEMP_RETENTION_SECONDS = 1800
    RENDER_BASE_URL = "https://你的服務.onrender.com"
    LOCAL_AI_WORKER_ENABLED = 1
    LOCAL_AI_WORKER_ID = "telemini-local-worker"
    LOCAL_AI_WORKER_POLL_SECONDS = 3
    LOCAL_AI_WORKER_TASK_TIMEOUT_SECONDS = 900
}

$json = $config | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($ConfigPath, $json, (New-Object System.Text.UTF8Encoding($false)))

$renderLine = "LOCAL_AI_GATEWAY_SECRET=$secret"
try {
    Set-Clipboard -Value $renderLine
    $clipboardNote = "The Render secret line was copied to the clipboard."
}
catch {
    $clipboardNote = "Clipboard copy failed. Copy the Render secret line shown below."
}

Write-Host ""
Write-Host "Gateway config created: $ConfigPath"
Write-Host "ComfyUI root: $comfyRoot"
Write-Host ""
Write-Host "Add this environment variable to Render:"
Write-Host $renderLine
Write-Host "Also remove or clear LOCAL_AI_GATEWAY_URL on Render to use reverse worker mode."
Write-Host "Then edit gateway_config.json and set RENDER_BASE_URL to your Render service URL."
Write-Host $clipboardNote
Write-Host ""
Write-Host "Keep gateway_config.json private. Do not commit it to GitHub."
