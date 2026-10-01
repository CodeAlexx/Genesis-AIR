param([string]$Destination = $PSScriptRoot, [switch]$SkipWorkerBuild)
$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$deps = Join-Path $repo 'build-windows/deps'
$pins = Get-Content (Join-Path $repo 'windows/source-pins.json') -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $deps, $Destination | Out-Null
function Checkout([string]$Url, [string]$Revision, [string]$Target) {
  if (-not (Test-Path -LiteralPath $Target)) {
    & git clone --filter=blob:none --no-checkout $Url $Target
    if ($LASTEXITCODE -ne 0) { throw "[GA_SETUP_CLONE] $Url" }
    & git -C $Target checkout --detach $Revision
    if ($LASTEXITCODE -ne 0) { throw "[GA_SETUP_REVISION] $Revision" }
  }
  $actual = (& git -C $Target rev-parse HEAD).Trim()
  if ($LASTEXITCODE -ne 0 -or $actual -ne $Revision) {
    throw "[GA_SETUP_REVISION] $Target must be at $Revision; existing contents were preserved."
  }
}
function Download([string]$Url, [string]$Target, [string]$Sha256) {
  if (-not (Test-Path -LiteralPath $Target)) { Invoke-WebRequest -Uri $Url -OutFile $Target }
  $actual = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash
  if ($actual -ne $Sha256) { throw "[GA_SETUP_DIGEST] $Target does not match its pinned SHA256." }
}
$sdkRevision = (Get-Content (Join-Path $repo 'air-sdk.conf') | Where-Object { $_ -match '^AIR_SDK_COMMIT=' }) -replace '^AIR_SDK_COMMIT=', ''
Checkout 'https://github.com/CodeAlexx/AIR.git' $sdkRevision (Join-Path $repo 'build-windows/AIR-SDK')
$worker = Join-Path $repo 'build-windows/gcompose-source'
Checkout 'https://github.com/CodeAlexx/Genesis-.git' $pins.worker $worker
$patch = Join-Path $repo 'windows/gcompose-windows.patch'
& git -C $worker apply --reverse --check $patch 2>$null
if ($LASTEXITCODE -ne 0) {
  & git -C $worker apply --check $patch
  if ($LASTEXITCODE -ne 0) { throw '[GA_SETUP_PATCH] The compositor has changes incompatible with the maintained patch.' }
  & git -C $worker apply $patch
  if ($LASTEXITCODE -ne 0) { throw '[GA_SETUP_PATCH] Could not apply the Windows compositor patch.' }
}
$manifest = Join-Path $worker 'gcompose/Cargo.toml'
$cargoText = [IO.File]::ReadAllText($manifest)
if ($cargoText -notmatch '(?m)^\[workspace\]') {
  [IO.File]::AppendAllText($manifest, "`n[workspace]`n", [Text.UTF8Encoding]::new($false))
}
Copy-Item -LiteralPath (Join-Path $repo 'windows/gcompose-build.rs') -Destination (Join-Path $worker 'gcompose/build.rs') -Force
Copy-Item -LiteralPath (Join-Path $repo 'windows/gcompose-Cargo.lock') -Destination (Join-Path $worker 'gcompose/Cargo.lock') -Force

$ffmpeg = Get-Content (Join-Path $repo 'windows/ffmpeg-source.json') -Raw | ConvertFrom-Json
$ffmpegRoot = Join-Path $deps 'ffmpeg-pinned'
$archive = Join-Path $deps $ffmpeg.name
if (-not (Test-Path -LiteralPath (Join-Path $ffmpegRoot ($ffmpeg.name.Replace('.zip', '') + '/lib/avcodec.lib')))) {
  Download $ffmpeg.browser_download_url $archive ($ffmpeg.digest -replace '^sha256:', '')
  Expand-Archive -LiteralPath $archive -DestinationPath $ffmpegRoot -Force
}
$font = Get-Content (Join-Path $repo 'windows/font-source.json') -Raw | ConvertFrom-Json
$fonts = Join-Path $Destination 'fonts'
New-Item -ItemType Directory -Force -Path $fonts | Out-Null
Download "https://raw.githubusercontent.com/google/fonts/$($font.revision)/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf" (Join-Path $fonts 'NotoSansJP.ttf') $font.sha256
$fontLicense = Join-Path $fonts 'OFL.txt'
if ([IO.Path]::GetFullPath($fontLicense) -ne [IO.Path]::GetFullPath((Join-Path $repo 'fonts/OFL.txt'))) {
  Copy-Item -LiteralPath (Join-Path $repo 'fonts/OFL.txt') -Destination $fontLicense -Force
}

$headers = Join-Path $deps 'OpenCL-Headers'
$loader = Join-Path $deps 'OpenCL-ICD-Loader'
Checkout 'https://github.com/KhronosGroup/OpenCL-Headers.git' $pins.opencl_headers $headers
Checkout 'https://github.com/KhronosGroup/OpenCL-ICD-Loader.git' $pins.opencl_loader $loader
$cmake = (Get-Command cmake.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $cmake) { $cmake = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/2022/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe' }
if (-not (Test-Path -LiteralPath $cmake)) { throw '[GA_SETUP_MSVC] Install Visual Studio C++ Build Tools with CMake.' }
& $cmake -S $loader -B (Join-Path $deps 'opencl-build') -G 'Visual Studio 17 2022' -A x64 "-DOPENCL_ICD_LOADER_HEADERS_DIR=$headers" -DOPENCL_ICD_LOADER_BUILD_TESTING=OFF
if ($LASTEXITCODE -ne 0) { throw '[GA_SETUP_OPENCL] Could not configure the native OpenCL loader.' }
& $cmake --build (Join-Path $deps 'opencl-build') --config Release -- /m
if ($LASTEXITCODE -ne 0) { throw '[GA_SETUP_OPENCL] Could not build the native OpenCL loader.' }

$env:CARGO_HOME = Join-Path $deps 'cargo'
$env:RUSTUP_HOME = Join-Path $deps 'rustup'
$rustup = Join-Path $env:CARGO_HOME 'bin/rustup.exe'
if (-not (Test-Path -LiteralPath $rustup)) {
  $url = 'https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe'
  $checksum = ((Invoke-WebRequest -Uri ($url + '.sha256')).Content -split '\s+')[0]
  $installer = Join-Path $deps 'rustup-init.exe'
  Download $url $installer $checksum
  & $installer -y --no-modify-path --profile minimal --default-toolchain $pins.rust
  if ($LASTEXITCODE -ne 0) { throw '[GA_SETUP_RUST] Could not install the local Rust toolchain.' }
}
$version = & (Join-Path $env:CARGO_HOME 'bin/rustc.exe') --version
if ($version -notmatch ('^rustc ' + [regex]::Escape($pins.rust) + ' ')) {
  & $rustup toolchain install $pins.rust --profile minimal
  if ($LASTEXITCODE -ne 0) { throw '[GA_SETUP_RUST] Could not install the pinned Rust compiler.' }
}
if (-not $SkipWorkerBuild) { & (Join-Path $repo 'windows/build-worker.ps1') -Destination $Destination }
$licenses = Join-Path $Destination 'licenses'
New-Item -ItemType Directory -Force -Path $licenses | Out-Null
Copy-Item -LiteralPath (Join-Path $ffmpegRoot ($ffmpeg.name.Replace('.zip', '') + '/LICENSE.txt')) -Destination (Join-Path $licenses 'FFmpeg.txt') -Force
Copy-Item -LiteralPath (Join-Path $headers 'LICENSE') -Destination (Join-Path $licenses 'OpenCL-Headers.txt') -Force
Copy-Item -LiteralPath (Join-Path $loader 'LICENSE') -Destination (Join-Path $licenses 'OpenCL-Loader.txt') -Force
Write-Output "Native media dependencies ready: $Destination. Run build-windows.ps1 to build the AIR editor."
