param(
  [Parameter(Mandatory=$true)][string]$RpId
)

function Get-LocalIPv4 {
  $ips = Get-NetIPAddress -AddressFamily IPv4 `
    | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } `
    | Sort-Object -Property InterfaceMetric
  return $ips[0].IPAddress
}

$ip = Get-LocalIPv4
if (-not $ip) { throw "Could not find a non-loopback IPv4 address." }

$hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
$entry = "$ip`t$RpId"

Write-Host "Ensuring hosts entry: $entry"
# Requires admin
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Run PowerShell as Administrator to edit hosts."
}

$hosts = Get-Content $hostsPath -ErrorAction Stop
$hosts = $hosts | Where-Object { $_ -notmatch "\s$([regex]::Escape($RpId))(\s|$)" }
$hosts += $entry
Set-Content -Path $hostsPath -Value $hosts -Encoding ASCII

Write-Host "Creating self-signed cert for $RpId in CurrentUser\My"
New-SelfSignedCertificate -DnsName $RpId -CertStoreLocation "Cert:\CurrentUser\My" | Out-Null

Write-Host "Done. Use https://$RpId/ (you still need a reverse proxy like nginx/IIS/WSL)."
