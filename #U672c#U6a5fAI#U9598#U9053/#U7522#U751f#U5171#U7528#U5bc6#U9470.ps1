$bytes = New-Object byte[] 64
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$secret = [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_').TrimEnd('=')
Write-Host ""
Write-Host "請把下面同一組值分別放到："
Write-Host "1. 本機 閘道設定.cmd 的 LOCAL_AI_GATEWAY_SECRET"
Write-Host "2. Render Environment 的 LOCAL_AI_GATEWAY_SECRET"
Write-Host ""
Write-Host $secret
Write-Host ""
Read-Host "按 Enter 結束"
