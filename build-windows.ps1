param(
  [string]$AirSdk = $env:AIR_HOME,
  [string]$LinuxCompiler = '/root/Genesis-AIR-compiler/bin/airc',
  [string]$Distro = 'Ubuntu',
  [string]$Destination = $PSScriptRoot,
  [string]$NativeBuild = '',
  [string]$GeneratedDirectory = '',
  [string]$CompositorSource = (Join-Path $PSScriptRoot 'build-windows/gcompose-source/gcompose/csrc/fpx_gpu.c'),
  [string]$Worker = (Join-Path $PSScriptRoot 'genesis-gcompose.exe'),
  [switch]$Launch,
  [switch]$SkipSmoke,
  [switch]$SkipTestRun,
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
$publishPatch = Join-Path $here 'patches/air-file-publish.patch'
if (-not (Test-Path -LiteralPath $publishPatch)) { throw '[GA_SDK_PUBLISH_PATCH_MISSING] The portable file publication overlay is missing.' }
$publishNativePreference = $PSNativeCommandUseErrorActionPreference
try {
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $publishPatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $publishPatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_PUBLISH_PATCH_BASE] File publication overlay does not match SDK; existing changes preserved.' }
    & git -C $sdk apply $publishPatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_PUBLISH_PATCH_APPLY] Could not apply file publication overlay.' }
  }
} finally { $PSNativeCommandUseErrorActionPreference = $publishNativePreference }
$editorPatch = Join-Path $here 'patches/air-editor.patch'
if (-not (Test-Path -LiteralPath $editorPatch)) { throw '[GA_SDK_PATCH_MISSING] The shared editor overlay is missing.' }
$previousNativePreference = $PSNativeCommandUseErrorActionPreference
try {
  # A check refusal is an expected probe outcome, including in PowerShell 7
  # sessions that promote native exit codes to terminating errors.
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $editorPatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $editorPatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_PATCH_BASE] The editor overlay does not match this AIR SDK; existing changes were preserved.' }
    & git -C $sdk apply $editorPatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_PATCH_APPLY] Could not apply the shared editor overlay.' }
  }
} finally {
  $PSNativeCommandUseErrorActionPreference = $previousNativePreference
}
$editorIoPatch = Join-Path $here 'patches/air-editor-io.patch'
if (-not (Test-Path -LiteralPath $editorIoPatch)) { throw '[GA_SDK_IO_PATCH_MISSING] The shared project codec overlay is missing.' }
try {
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $editorIoPatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $editorIoPatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_IO_PATCH_BASE] The project codec overlay does not match this AIR SDK; existing changes were preserved.' }
    & git -C $sdk apply $editorIoPatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_IO_PATCH_APPLY] Could not apply the shared project codec overlay.' }
  }
} finally { $PSNativeCommandUseErrorActionPreference = $previousNativePreference }
$channelPatch = Join-Path $here 'patches/air-channel-deadlines.patch'
if (-not (Test-Path -LiteralPath $channelPatch)) { throw '[GA_SDK_CHANNEL_PATCH_MISSING] The shared channel deadline overlay is missing.' }
try {
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $channelPatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $channelPatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_CHANNEL_PATCH_BASE] The channel deadline overlay does not match this AIR SDK; existing changes were preserved.' }
    & git -C $sdk apply $channelPatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_CHANNEL_PATCH_APPLY] Could not apply the shared channel deadline overlay.' }
  }
} finally { $PSNativeCommandUseErrorActionPreference = $previousNativePreference }
$channelReadPatch = Join-Path $here 'patches/air-channel-read-first.patch'
if (-not (Test-Path -LiteralPath $channelReadPatch)) { throw '[GA_SDK_CHANNEL_READ_PATCH_MISSING] The shared channel terminal delivery overlay is missing.' }
try {
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $channelReadPatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $channelReadPatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_CHANNEL_READ_PATCH_BASE] The channel terminal delivery overlay does not match this AIR SDK; existing changes preserved.' }
    & git -C $sdk apply $channelReadPatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_CHANNEL_READ_PATCH_APPLY] Could not apply the shared channel terminal delivery overlay.' }
  }
} finally { $PSNativeCommandUseErrorActionPreference = $previousNativePreference }
$processPatch = Join-Path $here 'patches/air-process-wait-windows.patch'
$loopbackPatch = Join-Path $here 'patches/air-net-loopback-windows.patch'
if (-not (Test-Path -LiteralPath $loopbackPatch)) { throw '[GA_SDK_LOOPBACK_PATCH_MISSING] The Windows loopback transport overlay is missing.' }
try {
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $loopbackPatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $loopbackPatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_LOOPBACK_PATCH_BASE] The loopback overlay does not match this AIR SDK; existing changes were preserved.' }
    & git -C $sdk apply $loopbackPatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_LOOPBACK_PATCH_APPLY] Could not apply the Windows loopback transport overlay.' }
  }
} finally { $PSNativeCommandUseErrorActionPreference = $previousNativePreference }
if (-not (Test-Path -LiteralPath $processPatch)) { throw '[GA_SDK_PROCESS_PATCH_MISSING] The Windows process overlay is missing.' }
try {
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $processPatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $processPatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_PROCESS_PATCH_BASE] The process overlay does not match this AIR SDK; existing changes were preserved.' }
    & git -C $sdk apply $processPatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_PROCESS_PATCH_APPLY] Could not apply the Windows process overlay.' }
  }
} finally {
  $PSNativeCommandUseErrorActionPreference = $previousNativePreference
}
$textPatch = Join-Path $here 'patches/air-ui-text-windows.patch'
if (-not (Test-Path -LiteralPath $textPatch)) { throw '[GA_SDK_TEXT_PATCH_MISSING] The Windows text overlay is missing.' }
try {
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $textPatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $textPatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_TEXT_PATCH_BASE] The text overlay does not match this AIR SDK; existing changes were preserved.' }
    & git -C $sdk apply $textPatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_TEXT_PATCH_APPLY] Could not apply the Windows text overlay.' }
  }
} finally {
  $PSNativeCommandUseErrorActionPreference = $previousNativePreference
}
$capturePatch = Join-Path $here 'patches/air-ui-capture-windows.patch'
if (-not (Test-Path -LiteralPath $capturePatch)) { throw '[GA_SDK_CAPTURE_PATCH_MISSING] The Windows capture overlay is missing.' }
try {
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $capturePatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $capturePatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_CAPTURE_PATCH_BASE] The capture overlay does not match this AIR SDK; existing changes were preserved.' }
    & git -C $sdk apply $capturePatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_CAPTURE_PATCH_APPLY] Could not apply the Windows capture overlay.' }
  }
} finally { $PSNativeCommandUseErrorActionPreference = $previousNativePreference }
$buildRoot = Join-Path $here 'build-windows'
$presentPatch = Join-Path $here 'patches/air-ui-present-immediate-windows.patch'
if (-not (Test-Path -LiteralPath $presentPatch)) { throw '[GA_SDK_PRESENT_PATCH_MISSING] The Windows presenter overlay is missing.' }
try {
  $PSNativeCommandUseErrorActionPreference = $false
  $null = & git -C $sdk apply --reverse --check $presentPatch 2>$null
  if ($LASTEXITCODE -ne 0) {
    $null = & git -C $sdk apply --check $presentPatch 2>$null
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_PRESENT_PATCH_BASE] The presenter overlay does not match this AIR SDK; existing changes were preserved.' }
    & git -C $sdk apply $presentPatch
    if ($LASTEXITCODE -ne 0) { throw '[GA_SDK_PRESENT_PATCH_APPLY] Could not apply the Windows presenter overlay.' }
  }
} finally { $PSNativeCommandUseErrorActionPreference = $previousNativePreference }
$generated = if ($GeneratedDirectory) { [IO.Path]::GetFullPath($GeneratedDirectory) } else { Join-Path $buildRoot 'generated' }
New-Item -ItemType Directory -Force -Path $generated, $Destination | Out-Null
function WslPath([string]$Value) {
  $mapped = (& wsl.exe -d $Distro -u root -- wslpath -a ($Value -replace '\\', '/')).Trim()
  if ($LASTEXITCODE -ne 0) { throw "Cannot map $Value into WSL." }
  $mapped
}
$sdkLinux = WslPath $sdk
& wsl.exe -d $Distro -u root --exec test -x $LinuxCompiler
if ($LASTEXITCODE -ne 0) { throw '[GA_TOOLCHAIN] Build the matching AIR compiler first with .\build-compiler-wsl.ps1.' }
$sources = ,@('main', 'src/main.ai')
if ($RunTests) { $sources += @(@('headless', 'tests/headless.ai'), @('controls', 'tests/controls.ai'), @('native', 'tests/native.ai'), @('audio-device', 'tests/audio_device.ai'), @('audio-playback', 'tests/audio_playback.ai'), @('audio-cancel', 'tests/audio_cancel.ai'), @('preview-async', 'tests/preview_async.ai'), @('preview-stream', 'tests/preview_stream.ai'), @('preview-input', 'tests/preview_input.ai'), @('inspector', 'tests/inspector.ai'), @('live-paint', 'tests/live_paint.ai'), @('project-safety', 'tests/project_safety.ai'), @('picture-queue', 'tests/picture_queue.ai')) }
if ($RunTests) { $sources += @(@('keyed-video', 'tests/keyed_video.ai'), @('window-cache', 'tests/window_cache.ai'), @('editor-trim', 'tests/editor_trim.ai'), @('trim-history', 'tests/trim_history.ai'), @('recovery-ownership', 'tests/recovery_ownership.ai'), @('media-session', 'tests/media_session.ai'), @('spatial-canvas', 'tests/spatial_canvas.ai')) }
if ($RunTests) { $sources += @(@('fade-controls', 'tests/fade_controls.ai'), @('audio-fade-keys', 'tests/audio_fade_keys.ai'), @('audio-nested', 'tests/audio_nested.ai'), @('audio-nested-cancel', 'tests/audio_nested_cancel.ai'), @('nested-audio-controls', 'tests/nested_audio_controls.ai')) }
if ($RunTests) { $sources += ,@('nested-timeline-bitmaps', 'tests/nested_timeline_bitmaps.ai') }
if ($RunTests) { $sources += ,@('nested-picture-plan', 'tests/nested_picture_plan.ai') }
if ($RunTests) { $sources += ,@('picture-memory', 'tests/picture_memory.ai') }
if ($RunTests) { $sources += ,@('nested-waveforms', 'tests/nested_waveforms.ai') }
if ($RunTests) { $sources += ,@('direct-waveforms', 'tests/direct_waveforms.ai') }
if ($RunTests) { $sources += ,@('timeline-track-scroll', 'tests/timeline_track_scroll.ai') }
if ($RunTests) { $sources += ,@('waveform-view', 'tests/waveform_view.ai') }
if ($RunTests) { $sources += ,@('waveform-visual', 'tests/waveform_visual.ai') }
if ($RunTests) { $sources += ,@('waveform-visual-media', 'tests/waveform_visual_media.ai') }
if ($RunTests) { $sources += ,@('waveform-detail', 'tests/waveform_detail.ai') }
if ($RunTests) { $sources += ,@('strip-viewport', 'tests/strip_viewport.ai') }
if ($RunTests) { $sources += @(@('clip-clipboard', 'tests/clip_clipboard.ai'), @('clip-clipboard-media', 'tests/clip_clipboard_media.ai')) }
if ($RunTests) { $sources += @(@('editing-safety', 'tests/editing_safety.ai'), @('picture-clock', 'tests/picture_clock.ai')) }
if ($RunTests) { $sources += @(@('preview-batch', 'tests/preview_batch.ai'), @('preview-fifo', 'tests/preview_fifo.ai')) }
if ($RunTests) { $sources += ,@('audio-plan-preflight', 'tests/audio_plan_preflight.ai') }
if ($RunTests) { $sources += ,@('linked-media', 'tests/linked_media.ai') }
if ($RunTests) { $sources += ,@('audio-context', 'tests/audio_context.ai') }
if ($RunTests) { $sources += ,@('audio-context-retime', 'tests/audio_context_retime.ai') }
if ($RunTests) { $sources += ,@('audio-tail-context', 'tests/audio_tail_context.ai') }
if ($RunTests) { $sources += ,@('audio-tail-history', 'tests/audio_tail_history.ai') }
if ($RunTests) { $sources += ,@('standalone-endpoint-controller', 'tests/standalone_endpoint_controller_lifecycle.ai') }
if ($RunTests) { $sources += ,@('standalone-endpoint-preview', 'tests/standalone_endpoint_preview.ai') }
if ($RunTests) { $sources += ,@('standalone-endpoint-media', 'tests/standalone_endpoint_media.ai') }
if ($RunTests) { $sources += ,@('standalone-endpoint-actor', 'tests/standalone_endpoint_actor_lifecycle.ai') }
if ($RunTests) { $sources += ,@('standalone-endpoint-cancel', 'tests/standalone_endpoint_cancel.ai') }
if ($RunTests) { $sources += ,@('standalone-endpoint-timing', 'tests/standalone_endpoint_timing.ai') }
if ($RunTests) { $sources += ,@('program-picture-persistent', 'tests/program_picture_persistent.ai') }
if ($RunTests) { $sources += ,@('program-picture-protocol', 'tests/program_picture_protocol.ai') }
if ($RunTests) { $sources += ,@('program-picture-control', 'tests/program_picture_control.ai') }
if ($RunTests) { $sources += ,@('program-picture-epoch', 'tests/program_picture_epoch.ai') }
if ($RunTests) { $sources += ,@('program-picture-profile', 'tests/program_picture_profile.ai') }
if ($RunTests) { $sources += ,@('audio-edit-context', 'tests/audio_edit_context.ai') }
if ($RunTests) { $sources += ,@('audio-nested-edit-context', 'tests/audio_nested_edit_context.ai') }
if ($RunTests) { $sources += ,@('keyframe-controls', 'tests/keyframe_controls.ai') }
if ($RunTests) { $sources += ,@('snap-controls', 'tests/snap_controls.ai') }
if ($RunTests) { $sources += ,@('bidi-layout', 'tests/bidi_layout.ai') }
if ($RunTests) { $sources += ,@('transition-controls', 'tests/transition_controls.ai') }
if ($RunTests) { $sources += ,@('transition-controls-media', 'tests/transition_controls_media.ai') }
if ($RunTests) { $sources += ,@('filter-transactions', 'tests/filter_transactions.ai') }
if ($RunTests) { $sources += ,@('channel-deadlines', 'tests/channel_deadlines.ai') }
if ($RunTests) { $sources += ,@('channel-read-first', 'tests/channel_read_first.ai') }
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
$compositorCmake = $CompositorSource -replace '\\', '/'
$includeCmake = (Join-Path $here 'windows/configure.cmake') -replace '\\', '/'
& $cmake -S $sdk -B $build -G 'Visual Studio 17 2022' -A x64 "-DGENESIS_ROOT=$projectCmake" `
  "-DGENESIS_GENERATED_DIR=$generatedCmake" `
  "-DGENESIS_COMPOSITOR_SOURCE=$compositorCmake" `
  "-DCMAKE_PROJECT_air_INCLUDE=$includeCmake" "-DGENESIS_TESTS=$($RunTests.IsPresent)" `
  "-DAIR_WINDOWS_APP_C=$generatedCmake/main.c" -DAIR_WINDOWS_APP_NAME=Genesis-AIR `
  -DAIR_DESKTOP=OFF -DAIR_SAM3=OFF -DCMAKE_DISABLE_FIND_PACKAGE_CUDAToolkit=TRUE
if ($LASTEXITCODE -ne 0) { throw 'Windows CMake configuration failed.' }
$targets = @('air_windows_app', 'air_native_shell', 'air_native_dialogs', 'air_ui_host', 'genesis_native_audio', 'air_file_publish')
if ($RunTests) { $targets += @('genesis-headless', 'genesis-controls', 'genesis-native', 'genesis-worker-wrapper', 'genesis-audio-device', 'genesis-audio-clock', 'genesis-audio-playback', 'genesis-audio-cancel', 'genesis-preview-async', 'genesis-preview-stream', 'genesis-preview-input', 'genesis-inspector', 'genesis-ui-pixels', 'genesis-live-paint', 'genesis-project-safety', 'genesis-picture-queue') }
if ($RunTests) { $targets += @('genesis-keyed-video', 'genesis-window-cache', 'genesis-editor-trim', 'genesis-trim-history', 'genesis-recovery-ownership', 'genesis-media-session', 'genesis-spatial-canvas') }
if ($RunTests) { $targets += @('genesis-fade-controls', 'genesis-audio-fade-keys', 'genesis-audio-nested', 'genesis-audio-nested-cancel', 'genesis-nested-audio-controls') }
if ($RunTests) { $targets += @('genesis-process-wait') }
if ($RunTests) { $targets += @('genesis-ui-clipboard', 'genesis-ui-capture') }
if ($RunTests) { $targets += @('genesis-nested-timeline-bitmaps') }
if ($RunTests) { $targets += @('genesis-nested-picture-plan', 'genesis-compound-canvas') }
if ($RunTests) { $targets += @('genesis-picture-memory', 'genesis-picture-memory-lifecycle') }
if ($RunTests) { $targets += @('genesis-nested-waveforms') }
if ($RunTests) { $targets += @('genesis-direct-waveforms') }
if ($RunTests) { $targets += @('genesis-timeline-track-scroll') }
if ($RunTests) { $targets += @('genesis-waveform-view') }
if ($RunTests) { $targets += @('genesis-waveform-visual', 'genesis-waveform-visual-media') }
if ($RunTests) { $targets += @('genesis-waveform-detail') }
if ($RunTests) { $targets += @('genesis-strip-viewport') }
if ($RunTests) { $targets += @('genesis-clip-clipboard', 'genesis-clip-clipboard-media') }
if ($RunTests) { $targets += @('genesis-editing-safety', 'genesis-picture-clock') }
if ($RunTests) { $targets += @('genesis-preview-batch', 'genesis-preview-fifo') }
if ($RunTests) { $targets += @('genesis-audio-plan-preflight') }
if ($RunTests) { $targets += @('genesis-linked-media') }
if ($RunTests) { $targets += @('genesis-channel-deadlines') }
if ($RunTests) { $targets += @('genesis-channel-read-first') }
if ($RunTests) { $targets += @('genesis-net-loopback-classifier', 'genesis-net-loopback-policy', 'genesis-net-loopback-resource') }
if ($RunTests) { $targets += @('genesis-lazy-gpu-fault') }
if ($RunTests) { $targets += @('genesis-native-hdr-runtime') }
if ($RunTests) { $targets += @('genesis-native-u16-upload') }
if ($RunTests) { $targets += @('genesis-export-ownership-worker') }
if ($RunTests) { $targets += @('genesis-audio-context') }
if ($RunTests) { $targets += @('genesis-audio-context-retime') }
if ($RunTests) { $targets += @('genesis-audio-tail-context', 'genesis-audio-tail-history') }
if ($RunTests) { $targets += @('genesis-standalone-endpoint-controller', 'genesis-standalone-endpoint-preview', 'genesis-standalone-endpoint-media', 'genesis-standalone-endpoint-actor', 'genesis-standalone-endpoint-cancel', 'genesis-standalone-endpoint-timing') }
if ($RunTests) { $targets += @('genesis-program-picture-persistent', 'genesis-program-picture-protocol', 'genesis-program-picture-control', 'genesis-program-picture-epoch', 'genesis-program-picture-profile', 'genesis-program-picture-mock') }
if ($RunTests) { $targets += @('genesis-audio-edit-context') }
if ($RunTests) { $targets += @('genesis-audio-nested-edit-context') }
if ($RunTests) { $targets += @('genesis-keyframe-controls') }
if ($RunTests) { $targets += @('genesis-snap-controls') }
if ($RunTests) { $targets += @('genesis-bidi-layout') }
if ($RunTests) { $targets += @('genesis-transition-controls') }
if ($RunTests) { $targets += @('genesis-transition-controls-media') }
if ($RunTests) { $targets += @('genesis-filter-transactions') }
& $cmake --build $build --config Release --target @targets -- /m
if ($LASTEXITCODE -ne 0) { throw 'Native Windows build failed.' }
$bin = Join-Path $build 'bin/Release'
foreach ($name in @('Genesis-AIR.exe', 'air-native-shell.dll', 'air-native-dialogs.dll', 'air-ui-host.dll', 'genesis-native-audio.dll', 'air-file-publish.exe')) {
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
$fontOutput = Join-Path $Destination 'fonts'
New-Item -ItemType Directory -Force -Path $fontOutput | Out-Null
foreach ($fontName in @('NotoSansJP.ttf', 'OFL.txt')) {
  $fontSource = Join-Path $here ('fonts/' + $fontName)
  $fontTarget = Join-Path $fontOutput $fontName
  if ((Test-Path -LiteralPath $fontTarget) -and
      (Get-FileHash -LiteralPath $fontSource).Hash -eq (Get-FileHash -LiteralPath $fontTarget).Hash) { continue }
  Copy-Item -LiteralPath $fontSource -Destination $fontTarget -Force
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
if ($RunTests -and -not $SkipTestRun) { & (Join-Path $here 'tests/windows.ps1') -Bin $bin -Worker $Worker }
Write-Output "Genesis AIR: $executable"
if ($Launch) { Start-Process -FilePath $executable -WorkingDirectory $Destination -WindowStyle Normal }
