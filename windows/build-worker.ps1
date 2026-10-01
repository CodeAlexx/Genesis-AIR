param([string]$Destination = (Join-Path $PSScriptRoot '..'))
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$deps = Join-Path $repo 'build-windows/deps'
$ffmpeg = Get-Content (Join-Path $PSScriptRoot 'ffmpeg-source.json') -Raw | ConvertFrom-Json
$env:CARGO_HOME = Join-Path $deps 'cargo'
$env:RUSTUP_HOME = Join-Path $deps 'rustup'
$env:GENESIS_FFMPEG_SDK = Join-Path $deps ('ffmpeg-pinned/' + $ffmpeg.name.Replace('.zip', ''))
$env:GENESIS_OPENCL_HEADERS = Join-Path $deps 'OpenCL-Headers'
$env:GENESIS_OPENCL_LIB = Join-Path $deps 'opencl-build/Release'
$env:GENESIS_WINDOWS_COMPAT = Join-Path $repo 'windows/compat'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
if (-not $vs) { throw '[GA_BUILD_MSVC] Install Visual Studio C++ Build Tools.' }
$dev = Join-Path $vs 'Common7/Tools/VsDevCmd.bat'
$environmentLines = & cmd.exe /d /s /c "`"$dev`" -arch=x64 -host_arch=x64 >nul && set"
if ($LASTEXITCODE -ne 0) { throw '[GA_BUILD_MSVC] Could not initialize the MSVC environment.' }
foreach ($line in $environmentLines) {
  if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
$cargo = Join-Path $deps 'cargo/bin/cargo.exe'
if (-not (Test-Path -LiteralPath $cargo)) { throw '[GA_BUILD_RUST] Run setup-windows.ps1 first.' }
# A pre-existing stable toolchain is acceptable only when it is the exact pinned compiler.
$version = & (Join-Path $deps 'cargo/bin/rustc.exe') --version
$toolchain = if ($version -match '^rustc 1\.98\.1 ') { '+stable' } else { '+1.98.1' }
& $cargo $toolchain build --release --locked --manifest-path (Join-Path $repo 'build-windows/gcompose-source/gcompose/Cargo.toml')
if ($LASTEXITCODE -ne 0) { throw '[GA_BUILD_WORKER] Native compositor compilation failed.' }
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'build-windows/gcompose-source/gcompose/target/release/gcompose.exe') -Destination (Join-Path $Destination 'genesis-gcompose.exe') -Force
Get-ChildItem -LiteralPath (Join-Path $env:GENESIS_FFMPEG_SDK 'bin') -Filter '*.dll' | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination $Destination -Force
}
foreach ($name in @('ffmpeg.exe', 'ffprobe.exe')) {
  Copy-Item -LiteralPath (Join-Path $env:GENESIS_FFMPEG_SDK "bin/$name") -Destination $Destination -Force
}
Copy-Item -LiteralPath (Join-Path $env:GENESIS_OPENCL_LIB 'OpenCL.dll') -Destination $Destination -Force
