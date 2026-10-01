param(
  [string]$AirSdk = $env:AIR_HOME,
  [string]$LinuxCompiler = '/root/AIR-win-port-build/bin/airc',
  [string]$Distro = 'Ubuntu',
  [string]$Destination = $PSScriptRoot,
  [string]$NativeBuild = '',
  [switch]$Launch,
  [switch]$SkipSmoke,
  [switch]$RunTests
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
if (-not $AirSdk) {
  $AirSdk = @((Join-Path $here 'build-windows\AIR-SDK'), (Join-Path $here '..\AIR-windows-native'), (Join-Path $here '..\AIR'),
    (Join-Path $here '..\air-sdk-nle')) |
    Where-Object { Test-Path -LiteralPath (Join-Path $_ 'runtime') } | Select-Object -First 1
}
if (-not $AirSdk) { throw 'Pass -AirSdk C:\path\to\AIR or set AIR_HOME.' }
$sdk = (Resolve-Path -LiteralPath $AirSdk).Path
$buildRoot = Join-Path $here 'build-windows'
$generated = Join-Path $buildRoot 'generated'
New-Item -ItemType Directory -Force -Path $generated, $Destination | Out-Null
function WslPath([string]$Value) {
  $mapped = (& wsl.exe -d $Distro -u root -- wslpath -a ($Value -replace '\\', '/')).Trim()
  if ($LASTEXITCODE -ne 0) { throw "Cannot map $Value into WSL." }
  $mapped
}
$sdkLinux = WslPath $sdk
$sources = ,@('main', 'src/main.ai')
if ($RunTests) { $sources += @(@('headless', 'tests/headless.ai'), @('controls', 'tests/controls.ai'), @('native', 'tests/native.ai'), @('audio-device', 'tests/audio_device.ai'), @('preview-async', 'tests/preview_async.ai'), @('inspector', 'tests/inspector.ai')) }
foreach ($entry in $sources) {
  $inputLinux = WslPath (Join-Path $here $entry[1])
  $outputLinux = WslPath (Join-Path $generated ($entry[0] + '.c'))
  & wsl.exe -d $Distro -u root -- env "AIR_STDLIB=$sdkLinux/stdlib" $LinuxCompiler build $inputLinux `
    -o "$outputLinux.bootstrap" --mode release --provider hash.sha256=portable --keep-c $outputLinux
  if ($LASTEXITCODE -ne 0) { throw "AIR compilation failed: $($entry[1])" }
}
$cmake = (Get-Command cmake.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $cmake) {
  $cmake = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/2022/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
}
if (-not (Test-Path -LiteralPath $cmake)) { throw 'Install Visual Studio C++ Build Tools with CMake.' }
$build = if ($NativeBuild) { $NativeBuild } else { Join-Path $buildRoot 'native' }
$projectCmake = $here -replace '\\', '/'
$generatedCmake = $generated -replace '\\', '/'
$includeCmake = (Join-Path $here 'windows/configure.cmake') -replace '\\', '/'
& $cmake -S $sdk -B $build -G 'Visual Studio 17 2022' -A x64 "-DGENESIS_ROOT=$projectCmake" `
  "-DCMAKE_PROJECT_air_INCLUDE=$includeCmake" "-DGENESIS_TESTS=$($RunTests.IsPresent)" `
  "-DAIR_WINDOWS_APP_C=$generatedCmake/main.c" -DAIR_WINDOWS_APP_NAME=Genesis-AIR `
  -DAIR_DESKTOP=OFF -DAIR_SAM3=OFF -DCMAKE_DISABLE_FIND_PACKAGE_CUDAToolkit=TRUE
if ($LASTEXITCODE -ne 0) { throw 'Windows CMake configuration failed.' }
$targets = @('air_windows_app', 'air_native_shell', 'air_native_dialogs', 'air_ui_host', 'genesis_native_audio')
if ($RunTests) { $targets += @('genesis-headless', 'genesis-controls', 'genesis-native', 'genesis-worker-wrapper', 'genesis-audio-device', 'genesis-preview-async', 'genesis-inspector') }
& $cmake --build $build --config Release --target @targets -- /m
if ($LASTEXITCODE -ne 0) { throw 'Native Windows build failed.' }
$bin = Join-Path $build 'bin/Release'
foreach ($name in @('Genesis-AIR.exe', 'air-native-shell.dll', 'air-native-dialogs.dll', 'air-ui-host.dll', 'genesis-native-audio.dll')) {
  $sourceFile = Join-Path $bin $name
  $targetFile = Join-Path $Destination $name
  if ((Test-Path -LiteralPath $targetFile) -and
      (Get-FileHash -LiteralPath $sourceFile).Hash -eq (Get-FileHash -LiteralPath $targetFile).Hash) { continue }
  try { Copy-Item -LiteralPath $sourceFile -Destination $targetFile -Force }
  catch [System.IO.IOException] {
    # Preserve the loaded image while publishing its replacement. Windows keeps
    # the existing process's file handle; it uses the new version on restart.
    $backupFolder = Join-Path $buildRoot 'runtime-backups'
    New-Item -ItemType Directory -Force -Path $backupFolder | Out-Null
    $backupFile = Join-Path $backupFolder ([guid]::NewGuid().ToString('N') + '-' + $name)
    Move-Item -LiteralPath $targetFile -Destination $backupFile
    Copy-Item -LiteralPath $sourceFile -Destination $targetFile
  }
}
$executable = Join-Path (Resolve-Path -LiteralPath $Destination).Path 'Genesis-AIR.exe'
if (-not $SkipSmoke) {
  $smoke = Join-Path $buildRoot 'smoke'
  New-Item -ItemType Directory -Force -Path $smoke | Out-Null
  # Test-only settings belong to this child, never the shell or the launched editor.
  $start = [System.Diagnostics.ProcessStartInfo]::new()
  $start.FileName = $executable
  $start.UseShellExecute = $false
  $start.RedirectStandardOutput = $true
  $start.RedirectStandardError = $true
  $start.Environment['GENESIS_FAKE_PROVIDER'] = '1'
  $start.Environment['GENESIS_SCRATCH'] = $smoke
  foreach ($argument in @('demo', (Join-Path $smoke 'genesis-demo.png'), (Join-Path $smoke 'genesis-demo.air'))) {
    [void]$start.ArgumentList.Add($argument)
  }
  $process = [System.Diagnostics.Process]::Start($start)
  $stdoutTask = $process.StandardOutput.ReadToEndAsync()
  $stderrTask = $process.StandardError.ReadToEndAsync()
  if (-not $process.WaitForExit(120000)) { $process.Kill($true); throw '[GA_BUILD_SMOKE] Render exceeded its deadline.' }
  $stdout = $stdoutTask.GetAwaiter().GetResult()
  $stderr = $stderrTask.GetAwaiter().GetResult()
  if ($process.ExitCode -ne 0) { throw "[GA_BUILD_SMOKE] $stderr $stdout" }
  if (-not (Test-Path -LiteralPath (Join-Path $smoke 'genesis-demo.png')) -or
      -not (Test-Path -LiteralPath (Join-Path $smoke 'genesis-demo.air'))) { throw '[GA_BUILD_SMOKE] Missing demo output.' }
  Write-Host 'Genesis AIR native render smoke passed.'
}
if ($RunTests) { & (Join-Path $here 'tests/windows.ps1') -Bin $bin }
Write-Output "Genesis AIR: $executable"
if ($Launch) { Start-Process -FilePath $executable -WorkingDirectory $Destination -WindowStyle Normal }
