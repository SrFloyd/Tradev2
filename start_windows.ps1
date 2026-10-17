$ErrorActionPreference = 'Stop'
$key = Read-Host 'API Key Binance (somente leitura)'
$secure = Read-Host 'API Secret Binance (não será salva em arquivo)' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $secret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
$env:BINANCE_API_KEY = $key
$env:BINANCE_API_SECRET = $secret
try { python (Join-Path $PSScriptRoot 'server.py') } finally { Remove-Item Env:BINANCE_API_KEY -ErrorAction SilentlyContinue; Remove-Item Env:BINANCE_API_SECRET -ErrorAction SilentlyContinue; $secret = $null }
