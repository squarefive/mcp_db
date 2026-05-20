$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SrcPath = Join-Path $ProjectRoot "src"
$RuntimeDir = Join-Path $ProjectRoot ".inspector-runtime"
$ConfigPath = Join-Path $RuntimeDir "mcp.json"
$ServerName = "harmony-sqlite-db"
$Ports = @(6274, 6277)

function Stop-PortOwner {
    param(
        [Parameter(Mandatory = $true)]
        [int] $Port
    )

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $processId = $connection.OwningProcess
        if ($processId -eq $PID) {
            continue
        }

        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            Write-Host "Stopping process $($process.Id) using port $Port ($($process.ProcessName))"
            Stop-Process -Id $process.Id -Force
        }
    }
}

foreach ($Port in $Ports) {
    Stop-PortOwner -Port $Port
}

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

$EscapedSrcPath = $SrcPath -replace "\\", "\\"
$ConfigJson = @"
{
  "mcpServers": {
    "$ServerName": {
      "command": "python",
      "args": ["-m", "mcp_db.server"],
      "env": {
        "PYTHONPATH": "$EscapedSrcPath"
      }
    }
  }
}
"@

$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($ConfigPath, $ConfigJson, $Utf8NoBom)

Write-Host "Starting MCP Inspector..."
Write-Host "Project root: $ProjectRoot"
Write-Host "Config: $ConfigPath"
Write-Host "Server: $ServerName"
Write-Host ""

npx -y @modelcontextprotocol/inspector `
    --config $ConfigPath `
    --server $ServerName
