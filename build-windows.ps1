param(
  [string]$AirSdk = $env:AIR_HOME,
  [switch]$Launch,
  [switch]$SkipSmoke
)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot

if (-not $AirSdk) {
  $candidates = @(
    (Join-Path $here '..\AIR-windows-native'),
    (Join-Path $here '..\AIR'),
    (Join-Path $here '..\air-sdk-nle')
  )
  $AirSdk = $candidates |
    Where-Object { Test-Path -LiteralPath (Join-Path $_ 'tools\build-windows-app.ps1') } |
    Select-Object -First 1
}
if (-not $AirSdk) {
  throw 'AIR was not found. Pass -AirSdk C:\path\to\AIR or set AIR_HOME.'
}
$AirSdk = (Resolve-Path -LiteralPath $AirSdk).Path
$builder = Join-Path $AirSdk 'tools\build-windows-app.ps1'
if (-not (Test-Path -LiteralPath $builder)) {
  throw "This AIR checkout has no native Windows application builder: $builder"
}

$source = Join-Path $here 'src\main.ai'
& $builder -Source $source -Name 'Genesis-AIR'
if ($LASTEXITCODE -ne 0) { throw 'The AIR native Windows build failed.' }
$built = Join-Path $AirSdk 'build-win\bin\Release\Genesis-AIR.exe'
if (-not (Test-Path -LiteralPath $built)) {
  throw "AIR did not produce the expected executable: $built"
}

$output = Join-Path $here 'build-windows'
New-Item -ItemType Directory -Force -Path $output | Out-Null
$executable = Join-Path $output 'Genesis-AIR.exe'
Copy-Item -LiteralPath $built -Destination $executable -Force

if (-not $SkipSmoke) {
  $smoke = Join-Path $output 'smoke'
  New-Item -ItemType Directory -Force -Path $smoke | Out-Null
  $env:GENESIS_FAKE_PROVIDER = '1'
  $env:GENESIS_SCRATCH = $smoke
  $frame = Join-Path $smoke 'genesis-demo.png'
  $project = Join-Path $smoke 'genesis-demo.air'
  $start = [System.Diagnostics.ProcessStartInfo]::new()
  $start.FileName = $executable
  $start.UseShellExecute = $false
  $start.RedirectStandardOutput = $true
  $start.RedirectStandardError = $true
  [void]$start.ArgumentList.Add('demo')
  [void]$start.ArgumentList.Add($frame)
  [void]$start.ArgumentList.Add($project)
  $process = [System.Diagnostics.Process]::Start($start)
  $stdout = $process.StandardOutput.ReadToEnd()
  $stderr = $process.StandardError.ReadToEnd()
  $process.WaitForExit()
  if ($stdout) { Write-Host $stdout.TrimEnd() }
  if ($stderr) { Write-Error $stderr.TrimEnd() }
  if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $frame) -or
      -not (Test-Path -LiteralPath $project)) {
    throw 'Genesis AIR native render smoke failed.'
  }
  Write-Host "Genesis AIR smoke passed: $frame"
}

Write-Output $executable
if ($Launch) {
  $env:GENESIS_FAKE_PROVIDER = '1'
  $env:GENESIS_SCRATCH = Join-Path $output 'scratch'
  New-Item -ItemType Directory -Force -Path $env:GENESIS_SCRATCH | Out-Null
  Start-Process -FilePath $executable -ArgumentList 'new' -WindowStyle Normal
}
