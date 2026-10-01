param(
  [string]$AirSdk = (Join-Path $PSScriptRoot 'build-windows/AIR-SDK'),
  [string]$Distro = 'Ubuntu',
  [string]$BuildDirectory = '/root/Genesis-AIR-compiler',
  [ValidateRange(1, 16)][int]$Jobs = 4
)
$ErrorActionPreference = 'Stop'
$sdkPath = (Resolve-Path -LiteralPath $AirSdk).Path
$sdkLinux = (& wsl.exe -d $Distro -u root --exec wslpath -a ($sdkPath -replace '\\', '/')).Trim()
if ($LASTEXITCODE -ne 0) { throw '[GA_TOOLCHAIN_PATH] Cannot map AIR-SDK into WSL.' }
if (-not $BuildDirectory.StartsWith('/')) { throw '[GA_TOOLCHAIN_PATH] BuildDirectory must be an absolute WSL path.' }
# Keep compiler build trees attached to their source. Do not silently repurpose an
# unrelated AIR compiler checkout or alter its cache.
$cache = & wsl.exe -d $Distro -u root --exec cat "$BuildDirectory/CMakeCache.txt" 2>$null
if ($LASTEXITCODE -eq 0) {
  $existingSource = ($cache | Where-Object { $_ -like 'CMAKE_HOME_DIRECTORY:INTERNAL=*' }) -replace '^CMAKE_HOME_DIRECTORY:INTERNAL=', ''
  if ($existingSource -and $existingSource -ne $sdkLinux) {
    throw "[GA_TOOLCHAIN_SOURCE] $BuildDirectory belongs to $existingSource. Choose a separate BuildDirectory."
  }
}
& wsl.exe -d $Distro -u root --exec cmake -S $sdkLinux -B $BuildDirectory -G Ninja `
  -DCMAKE_BUILD_TYPE=Release -DAIR_DESKTOP=OFF -DAIR_SAM3=OFF -DCMAKE_DISABLE_FIND_PACKAGE_CUDAToolkit=TRUE
if ($LASTEXITCODE -ne 0) { throw '[GA_TOOLCHAIN_CONFIG] Install the AIR compiler prerequisites in WSL; CMake configuration failed.' }
& wsl.exe -d $Distro -u root --exec cmake --build $BuildDirectory --target airc "-j$Jobs"
if ($LASTEXITCODE -ne 0) { throw '[GA_TOOLCHAIN_BUILD] AIR compiler build failed.' }
Write-Output "AIR compiler: $BuildDirectory/bin/airc"
