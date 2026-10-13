param(
  [string]$Bin = (Join-Path $PSScriptRoot '../build-windows/native/bin/Release'),
  [string]$Worker = (Join-Path $PSScriptRoot '../genesis-gcompose.exe'),
  [switch]$ControlsOnly,
  [switch]$BackgroundOnly,
  [string]$ReportDirectory = ''
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$root = Join-Path $project 'build-windows'
$work = Join-Path $root ('test-' + [guid]::NewGuid().ToString('N'))
$reports = if ($ReportDirectory) { [System.IO.Path]::GetFullPath($ReportDirectory) }
  else { Join-Path $root ('reports-' + [guid]::NewGuid().ToString('N')) }
# Each invocation owns fresh durable receipts. Keep previous runs intact,
# including failed receipts, instead of colliding with exclusive test outputs.
if (Test-Path -LiteralPath $reports) {
  throw "[GA_TEST_REPORT_EXISTS] Report directory already exists: $reports"
}
New-Item -ItemType Directory -Path $reports -ErrorAction Stop | Out-Null
Write-Host "Windows test reports: $reports"
$previousWorker = $env:GENESIS_GCOMPOSE
$previousNativeColor = $env:GENESIS_NATIVE_HDR_COLOR
New-Item -ItemType Directory -Path $work | Out-Null
function Invoke-Native([string]$Name, [string[]]$Arguments, [int]$Expected = 0) {
  $start = [System.Diagnostics.ProcessStartInfo]::new()
  $start.FileName = Join-Path $Bin $Name
  $start.UseShellExecute = $false
  $start.RedirectStandardOutput = $true
  $start.RedirectStandardError = $true
  $start.Environment.Remove('GENESIS_FAKE_PROVIDER') | Out-Null
  $start.Environment['GENESIS_SCRATCH'] = $work
  $start.Environment['GENESIS_FONT'] = Join-Path $project 'fonts/NotoSansJP.ttf'
  foreach ($argument in $Arguments) { [void]$start.ArgumentList.Add($argument) }
  $child = [System.Diagnostics.Process]::Start($start)
  $stdout = $child.StandardOutput.ReadToEndAsync()
  $stderr = $child.StandardError.ReadToEndAsync()
  if (-not $child.WaitForExit(120000)) { $child.Kill($true); throw "$Name exceeded the test deadline." }
  # A failed child can leave an inherited pipe open in a worker. Bound capture
  # separately so that failure is reported instead of hanging after WaitForExit.
  if (-not $stdout.Wait(5000) -or -not $stderr.Wait(5000)) {
    throw "$Name exit $($child.ExitCode): [GA_TEST_CAPTURE] a child output pipe remained open."
  }
  $text = $stdout.GetAwaiter().GetResult()
  $errorText = $stderr.GetAwaiter().GetResult()
  if ($child.ExitCode -ne $Expected) { throw "$Name exit $($child.ExitCode): $text $errorText" }
  $text
}
try {
  # Existing exact color contracts retain their reference path. The dedicated
  # native HDR gate below resets this override in every candidate child.
  $env:GENESIS_NATIVE_HDR_COLOR = '0'
  $media = Join-Path $work 'real clip 日本語.mp4'
  & ffmpeg -nostdin -y -v error -f lavfi -i 'color=c=red:s=640x360:r=30:d=1' `
    -f lavfi -i 'color=c=blue:s=640x360:r=30:d=1' `
    -f lavfi -i 'sine=frequency=440:sample_rate=48000:duration=2' `
    -filter_complex '[0:v][1:v]concat=n=2:v=1:a=0[v]' -map '[v]' -map '2:a' `
    -c:v libx264 -pix_fmt yuv420p -c:a aac -t 2 $media
  if ($LASTEXITCODE -ne 0) { throw 'Could not generate the real video fixture.' }

  $env:GENESIS_GCOMPOSE = $Worker
  if (-not $ControlsOnly) {
  Write-Host (Invoke-Native 'genesis-ui-pixels.exe' @()).TrimEnd()
  $captureResult = Invoke-Native 'genesis-ui-capture.exe' @()
  $captureReport = $captureResult | ConvertFrom-Json
  if (-not $captureReport.passed -or $captureReport.checks -ne 25) { throw 'Native pointer capture gate failed.' }
  Write-Host $captureResult.TrimEnd()
  Set-Content -LiteralPath (Join-Path $reports 'ui-capture-windows.json') -Value $captureResult
  if (-not $BackgroundOnly) {
    $clipboardResult = Invoke-Native 'genesis-ui-clipboard.exe' @()
    Write-Host $clipboardResult.TrimEnd()
    Set-Content -LiteralPath (Join-Path $reports 'ui-clipboard-windows.log') -Value $clipboardResult
  } else { Write-Host 'Background gate: live system clipboard check deferred.' }
  & python (Join-Path $PSScriptRoot 'channel_deadlines.py') --binary (Join-Path $Bin 'genesis-channel-deadlines.exe') `
    --root (Join-Path $work 'channel-deadlines') --report (Join-Path $reports 'channel-deadlines-tests.json')
  if ($LASTEXITCODE -ne 0) { throw 'The real TCP channel deadline gate failed.' }
  & python (Join-Path $PSScriptRoot 'net_loopback_windows.py') `
    --classifier (Join-Path $Bin 'genesis-net-loopback-classifier.exe') `
    --policy (Join-Path $Bin 'genesis-net-loopback-policy.exe') `
    --resource (Join-Path $Bin 'genesis-net-loopback-resource.exe') `
    --report (Join-Path $reports 'net-loopback-windows.json')
  if ($LASTEXITCODE -ne 0) { throw 'The native loopback transport policy/resource gate failed.' }
  Write-Host (Invoke-Native 'genesis-linked-media.exe' @((Join-Path $work 'linked-media'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'linked-media/linked-media-tests.json') -Destination (Join-Path $reports 'linked-media-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-snap-controls.exe' @((Join-Path $work 'snap-controls'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'snap-controls/snap-controls-tests.json') -Destination (Join-Path $reports 'snap-controls-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-transition-controls.exe' @((Join-Path $work 'transition-controls'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'transition-controls/transition-controls-tests.json') -Destination (Join-Path $reports 'transition-controls-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-filter-transactions.exe' @((Join-Path $work 'filter-transactions'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'filter-transactions/filter-transactions-tests.json') -Destination (Join-Path $reports 'filter-transactions-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-audio-context.exe' @((Join-Path $work 'audio-context'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'audio-context/audio-context-tests.json') -Destination (Join-Path $reports 'audio-context-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-audio-tail-context.exe' @((Join-Path $work 'audio-tail-context'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'audio-tail-context/audio-tail-context-tests.json') -Destination (Join-Path $reports 'audio-tail-context-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-clip-clipboard.exe' @((Join-Path $work 'clip-clipboard'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'clip-clipboard/clip-clipboard-tests.json') -Destination (Join-Path $reports 'clip-clipboard-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-editing-safety.exe' @((Join-Path $work 'editing-safety'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'editing-safety/editing-safety-tests.json') -Destination (Join-Path $reports 'editing-safety-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-picture-clock.exe' @((Join-Path $reports 'picture-clock-tests.json'))).TrimEnd()
  Write-Host (Invoke-Native 'genesis-preview-batch.exe' @((Join-Path $work 'preview-batch'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'preview-batch/preview-batch-tests.json') -Destination (Join-Path $reports 'preview-batch-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-preview-fifo.exe' @((Join-Path $work 'preview-fifo'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'preview-fifo/preview-fifo-tests.json') -Destination (Join-Path $reports 'preview-fifo-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-standalone-endpoint-controller.exe' @((Join-Path $work 'standalone-endpoint-controller'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'standalone-endpoint-controller/controller-tests.json') -Destination (Join-Path $reports 'standalone-endpoint-controller-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-standalone-endpoint-preview.exe' @((Join-Path $work 'standalone-endpoint-preview'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'standalone-endpoint-preview/preview-endpoint-tests.json') -Destination (Join-Path $reports 'standalone-endpoint-preview-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-channel-read-first.exe' @((Join-Path $work 'channel-read-first'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'channel-read-first/channel-read-first-tests.json') -Destination (Join-Path $reports 'channel-read-first-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-timeline-track-scroll.exe' @((Join-Path $work 'track-scroll'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'track-scroll/timeline-track-scroll-tests.json') -Destination (Join-Path $reports 'timeline-track-scroll-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-waveform-view.exe' @((Join-Path $work 'waveform-view'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'waveform-view/waveform-view-tests.json') -Destination (Join-Path $reports 'waveform-view-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-waveform-visual.exe' @((Join-Path $work 'waveform-visual'))).TrimEnd()
  $visualModel = Get-Content -LiteralPath (Join-Path $work 'waveform-visual/waveform-visual-tests.json') -Raw | ConvertFrom-Json
  if ($visualModel.payload.status -ne 'pass' -or $visualModel.payload.cases.total -ne 11 -or
      $visualModel.payload.cases.passed -ne 11 -or $visualModel.payload.cases.failed -ne 0 -or
      $visualModel.payload.cases.skipped -ne 0 -or $visualModel.payload.checks -ne 100) { throw 'Visual reference identity/publication/budget/pixels gate failed.' }
  Copy-Item -LiteralPath (Join-Path $work 'waveform-visual/waveform-visual-tests.json') -Destination (Join-Path $reports 'waveform-visual-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-waveform-detail.exe' @((Join-Path $work 'waveform-detail'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'waveform-detail/waveform-detail-tests.json') -Destination (Join-Path $reports 'waveform-detail-tests.json') -Force
  $previousStripFixture = $env:GENESIS_TEST_STRIP_INPUT
  try {
    $env:GENESIS_TEST_STRIP_INPUT = Join-Path $work 'strip-viewport/strip-worker.txt'
    Write-Host (Invoke-Native 'genesis-strip-viewport.exe' @((Join-Path $work 'strip-viewport'), (Join-Path $Bin 'genesis-worker-wrapper.exe'))).TrimEnd()
  } finally {
    if ($null -eq $previousStripFixture) { Remove-Item Env:GENESIS_TEST_STRIP_INPUT -ErrorAction SilentlyContinue }
    else { $env:GENESIS_TEST_STRIP_INPUT = $previousStripFixture }
  }
  Copy-Item -LiteralPath (Join-Path $work 'strip-viewport/strip-viewport-tests.json') -Destination (Join-Path $reports 'strip-viewport-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-audio-clock.exe' @()).TrimEnd()
  $waitResult = Invoke-Native 'genesis-process-wait.exe' @()
  Write-Host $waitResult.TrimEnd()
  Set-Content -LiteralPath (Join-Path $reports 'process-wait-windows.log') -Value $waitResult
  $canvasResult = Invoke-Native 'genesis-compound-canvas.exe' @()
  Write-Host $canvasResult.TrimEnd()
  Set-Content -LiteralPath (Join-Path $reports 'compound-canvas-windows.log') -Value $canvasResult
  $pictureMemoryResult = Invoke-Native 'genesis-picture-memory-lifecycle.exe' @()
  Write-Host $pictureMemoryResult.TrimEnd()
  Set-Content -LiteralPath (Join-Path $reports 'picture-memory-windows.log') -Value $pictureMemoryResult
  $nativeU16Result = Invoke-Native 'genesis-native-u16-upload.exe' @()
  Write-Host $nativeU16Result.TrimEnd()
  Set-Content -LiteralPath (Join-Path $reports 'native-u16-upload-windows.log') -Value $nativeU16Result
  if (-not $BackgroundOnly) {
    & python (Join-Path $PSScriptRoot 'audio_clock.py') --library (Join-Path $Bin 'genesis-native-audio.dll') `
      --report (Join-Path $reports 'native-audio-clock.json')
    if ($LASTEXITCODE -ne 0) { throw 'Native audio device clock continuity failed.' }
  } else { Write-Host 'Background gate: hardware audio clock check deferred.' }
  $identityResults = @(
    (Invoke-Native 'genesis-native-hdr-runtime.exe' @('idle', 'ignored')),
    (Invoke-Native 'genesis-native-hdr-runtime.exe' @('cpu', 'ignored')),
    (Invoke-Native 'genesis-native-hdr-runtime.exe' @('identity', (Join-Path $work 'native-hdr-identity')))
  )
  $identityResults | Set-Content -LiteralPath (Join-Path $reports 'native-hdr-runtime.log')
  Write-Host ($identityResults -join '')
  $native = Invoke-Native 'genesis-native.exe' @($work, $media)
  Write-Host $native.TrimEnd()
  $previousInputFixture = $env:GENESIS_TEST_PREVIEW_INPUT
  try {
    $env:GENESIS_TEST_PREVIEW_INPUT = '1'
    $inputRoot = Join-Path $work 'preview-input 日本語'
    Write-Host (Invoke-Native 'genesis-preview-input.exe' @($inputRoot, (Join-Path $Bin 'genesis-worker-wrapper.exe'))).TrimEnd()
    Copy-Item -LiteralPath (Join-Path $inputRoot 'preview-input-tests.json') -Destination (Join-Path $reports 'preview-input-tests.json') -Force
  } finally {
    if ($null -eq $previousInputFixture) { Remove-Item Env:GENESIS_TEST_PREVIEW_INPUT -ErrorAction SilentlyContinue }
    else { $env:GENESIS_TEST_PREVIEW_INPUT = $previousInputFixture }
  }
  $wave = Join-Path $work 'queued audio 日本語.wav'
  & ffmpeg -nostdin -y -v error -i $media -vn -ac 2 -ar 48000 -c:a pcm_s16le $wave
  if ($LASTEXITCODE -ne 0) { throw 'Could not generate native audio fixture.' }
  $pannedWave = Join-Path $work 'left audio.wav'
  $silentWave = Join-Path $work 'muted audio.wav'
  & ffmpeg -nostdin -y -v error -i $wave -af 'pan=stereo|c0=c0|c1=0*c1' -c:a pcm_s16le $pannedWave
  if ($LASTEXITCODE -ne 0) { throw 'Could not generate panned device fixture.' }
  & ffmpeg -nostdin -y -v error -i $wave -af 'volume=0' -c:a pcm_s16le $silentWave
  if ($LASTEXITCODE -ne 0) { throw 'Could not generate silent device fixture.' }
  if (-not $BackgroundOnly) { Write-Host (Invoke-Native 'genesis-audio-device.exe' @($wave,$pannedWave,$silentWave)).TrimEnd() }
  else { Write-Host 'Background gate: live speaker/device check deferred.' }
  $env:GENESIS_GCOMPOSE = $Worker
  if (Test-Path -LiteralPath $worker) {
    & python (Join-Path $PSScriptRoot 'clip_clipboard_media.py') `
      --client (Join-Path $Bin 'genesis-clip-clipboard-media.exe') --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --worker $worker --report (Join-Path $reports 'clip-clipboard-media.json')
    if ($LASTEXITCODE -ne 0) { throw 'Clipboard authored graph, independent pasted pixels/PCM and Save/Open acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'lazy_gpu.py') --worker $worker `
      --fault-shim (Join-Path $Bin 'lazy-gpu-fault/OpenCL.dll') --report (Join-Path $reports 'lazy-gpu.json')
    if ($LASTEXITCODE -ne 0) { throw 'Lazy OpenCL initialization, retained history and failure cleanup failed.' }
    if (Test-Path -LiteralPath (Join-Path (Split-Path $worker -Parent) 'genesis-media-runtime.txt')) {
      & python (Join-Path $PSScriptRoot 'shared_media_runtime.py') --worker $worker
      if ($LASTEXITCODE -ne 0) { throw 'Shared MM-AIR media runtime acceptance failed.' }
    }
    & python (Join-Path $PSScriptRoot 'compound_pixels.py') --worker $worker `
      --report (Join-Path $reports 'compound-pixels.json')
    if ($LASTEXITCODE -ne 0) { throw 'Independent compound compositor pixels and recovery failed.' }
    & python (Join-Path $PSScriptRoot 'native_u16_upload.py') --worker $worker `
      --report (Join-Path $reports 'native-u16-upload.json')
    if ($LASTEXITCODE -ne 0) { throw 'Native 16-bit upload, frame identity and exact pixel acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'picture_memory_pixels.py') --worker $worker `
      --report (Join-Path $reports 'picture-memory-pixels.json')
    if ($LASTEXITCODE -ne 0) { throw 'Immutable GPU picture lifetime and pixel acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'nested_picture.py') --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --worker $worker --report (Join-Path $reports 'nested-picture.json')
    if ($LASTEXITCODE -ne 0) { throw 'Saved-project nested picture preview/master acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'nested_timeline_bitmaps.py') `
      --client (Join-Path $Bin 'genesis-nested-timeline-bitmaps.exe') --worker $worker `
      --report (Join-Path $reports 'nested-timeline-bitmap-pixels.json')
    if ($LASTEXITCODE -ne 0) { throw 'Actual asynchronous compound timeline bitmaps and recovery failed.' }
    & python (Join-Path $PSScriptRoot 'nested_waveforms.py') `
      --client (Join-Path $Bin 'genesis-nested-waveforms.exe') --worker $worker `
      --report (Join-Path $reports 'nested-waveforms.json')
    if ($LASTEXITCODE -ne 0) { throw 'Processed compound waveforms, stale publication and cancellation failed.' }
    & python (Join-Path $PSScriptRoot 'direct_waveforms.py') `
      --client (Join-Path $Bin 'genesis-direct-waveforms.exe') --worker $worker `
      --report (Join-Path $reports 'direct-waveforms.json')
    if ($LASTEXITCODE -ne 0) { throw 'Processed direct-source stereo waveforms, viewport scheduling and cancellation failed.' }
    & python (Join-Path $PSScriptRoot 'waveform_visual.py') `
      --client (Join-Path $Bin 'genesis-waveform-visual-media.exe') --worker $worker `
      --report (Join-Path $reports 'waveform-visual.json')
    if ($LASTEXITCODE -ne 0) { throw 'Independent display-reference and legacy processed waveform peaks failed.' }
    $visualProof = Get-Content -LiteralPath (Join-Path $reports 'waveform-visual.json') -Raw | ConvertFrom-Json
    $visualClientHash = (Get-FileHash -Algorithm SHA256 (Join-Path $Bin 'genesis-waveform-visual-media.exe')).Hash.ToLowerInvariant()
    $visualWorkerHash = (Get-FileHash -Algorithm SHA256 $worker).Hash.ToLowerInvariant()
    if ($visualProof.schema -ne 'genesis.waveform-visual.v1' -or -not $visualProof.passed -or
        $visualProof.failures.Count -ne 0 -or $visualProof.cases.Count -ne 8 -or
        $visualProof.client_cases -ne 8 -or $visualProof.client_checks -ne 64 -or
        $visualProof.numeric_peak_values -ne 320 -or $visualProof.independent_pcm_values -ne 3072000 -or
        $visualProof.peak_tolerance -ne 0.000002 -or $visualProof.normalization -or
        -not $visualProof.client_joined -or $visualProof.observed_worker_pids_joined.Count -eq 0 -or
        $visualProof.owned_caches.Count -ne 0 -or $visualProof.client_sha256 -ne $visualClientHash -or
        $visualProof.worker_sha256 -ne $visualWorkerHash) { throw 'Visual waveform proof identity/count/resource contract failed.' }
    & python (Join-Path $PSScriptRoot 'direct_waveform_stream.py') --worker $worker `
      --report (Join-Path $reports 'direct-waveform-stream.json')
    if ($LASTEXITCODE -ne 0) { throw 'Streamed direct waveform partitions, coded refusals and retained-cache recovery failed.' }
    & python (Join-Path $PSScriptRoot 'preview_fit.py') --worker $worker
    if ($LASTEXITCODE -ne 0) { throw 'GPU fitted monitor pixel acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'video_transfer.py') --worker $worker
    if ($LASTEXITCODE -ne 0) { throw 'Native video readback pixel acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'native_hdr_color.py') --worker $worker `
      --require-qualified --report (Join-Path $reports 'native-hdr-color.json') --scratch (Join-Path $work 'native-hdr-color')
    if ($LASTEXITCODE -ne 0) { throw 'Qualified native HDR color, exact fallback and runtime identity failed.' }
    & python (Join-Path $PSScriptRoot 'hdr_preview.py') --worker $worker
    if ($LASTEXITCODE -ne 0) { throw 'Native HDR preview color, precision and frame selection acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'odd_hdr_preview.py') --worker $worker --report (Join-Path $reports 'odd-hdr-preview.json')
    if ($LASTEXITCODE -ne 0) { throw 'Odd-sized HDR preview/master acceptance failed.' }
    Write-Host (Invoke-Native 'genesis-preview-async.exe' @($worker, $media, (Join-Path $work 'async'))).TrimEnd()
    Write-Host (Invoke-Native 'genesis-preview-stream.exe' @((Join-Path $work 'stream'), $worker, $media)).TrimEnd()
    & python (Join-Path $PSScriptRoot 'frame_identity.py') --worker $worker --client (Join-Path $Bin 'genesis-preview-stream.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Per-frame monitor and timeline bitmap acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'keyed_video.py') --worker $worker --client (Join-Path $Bin 'genesis-keyed-video.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Inspector picture-key preview/master acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'keyframe_controls.py') --worker $worker `
      --client (Join-Path $Bin 'genesis-keyframe-controls.exe') --report (Join-Path $reports 'keyframe-controls-media.json')
    if ($LASTEXITCODE -ne 0) { throw 'Key management preview/master pixel acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'transition_controls_media.py') --worker $worker `
      --client (Join-Path $Bin 'genesis-transition-controls-media.exe') --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --report (Join-Path $reports 'transition-controls-media-tests.json')
    if ($LASTEXITCODE -ne 0) { throw 'Transition controls preview/master pixels and unchanged audio acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'upper_transition_protocol.py') --worker $worker `
      --report (Join-Path $reports 'upper-transition-protocol.json')
    if ($LASTEXITCODE -ne 0) { throw 'Upper transition alpha, side blends, resource lifecycle and protocol refusal acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'upper_transition_media.py') --worker $worker `
      --binary (Join-Path $Bin 'Genesis-AIR.exe') --report (Join-Path $reports 'upper-transition-media.json')
    if ($LASTEXITCODE -ne 0) { throw 'Upper transition lower-gap and ordered side preview/master pixel acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'preview_canvas.py') --worker $worker --binary (Join-Path $Bin 'Genesis-AIR.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Small-sequence preview/master pixel acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'large_preview.py') --worker $worker --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --report (Join-Path $reports 'large-preview.json')
    if ($LASTEXITCODE -ne 0) { throw 'Large-sequence preview geometry and physical effect-radius acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'spatial_transitions.py') --worker $worker --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --stream-client (Join-Path $Bin 'genesis-preview-stream.exe') --wrapper (Join-Path $Bin 'genesis-worker-wrapper.exe') `
      --report (Join-Path $reports 'spatial-transitions.json')
    if ($LASTEXITCODE -ne 0) { throw 'Large-sequence spatial transition preview/master acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'filter_order.py') --worker $worker --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --report (Join-Path $reports 'filter-order.json')
    if ($LASTEXITCODE -ne 0) { throw 'Ordered and duplicate picture-filter preview/master acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'filter_titles.py') --worker $worker --binary (Join-Path $Bin 'Genesis-AIR.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Ordered title and independent multilayer raster acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'transition_clips.py') --worker $worker --binary (Join-Path $Bin 'Genesis-AIR.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Per-clip transition preview/master acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_export_length.py') --worker $worker
    if ($LASTEXITCODE -ne 0) { throw 'Final audio sample and stream-duration acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_mix_headroom.py') --worker $worker `
      --report (Join-Path $reports 'audio-mix-headroom.json')
    if ($LASTEXITCODE -ne 0) { throw 'Independent signed audio headroom and final-output scope acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_mix_project.py') --worker $worker `
      --binary (Join-Path $Bin 'Genesis-AIR.exe') --report (Join-Path $reports 'audio-mix-project.json')
    if ($LASTEXITCODE -ne 0) { throw 'Saved-project overlap audio audition/export acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_fade_project.py') --worker $worker `
      --binary (Join-Path $Bin 'Genesis-AIR.exe') --report (Join-Path $reports 'audio-fade-project.json')
    if ($LASTEXITCODE -ne 0) { throw 'Saved-project keyed fade audition/master acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'playback_timing.py') --worker $worker --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --report (Join-Path $reports 'playback-timing-fixture.json')
    if ($LASTEXITCODE -ne 0) { throw 'Audio-timed picture, histogram and timeline acceptance failed.' }
    Copy-Item -LiteralPath (Join-Path $work 'async/timeline-scrub.png') -Destination (Join-Path $reports 'timeline-scrub.png') -Force
    & python (Join-Path $PSScriptRoot 'audio_stream.py') --worker $worker --client (Join-Path $Bin 'genesis-audio-playback.exe') `
      --cancel-client (Join-Path $Bin 'genesis-audio-cancel.exe') --wrapper (Join-Path $Bin 'genesis-worker-wrapper.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Continuous audio and active cancellation acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_keys.py') --worker $worker --client (Join-Path $Bin 'genesis-audio-playback.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Clip gain automation PCM acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_fade_keys.py') --worker $worker --client (Join-Path $Bin 'genesis-audio-fade-keys.exe') `
      --report (Join-Path $reports 'audio-fade-keys.json')
    if ($LASTEXITCODE -ne 0) { throw 'Clip fade automation SDK/PCM acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_nested.py') --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --client (Join-Path $Bin 'genesis-audio-nested.exe') --worker $worker `
      --report (Join-Path $reports 'audio-nested.json')
    if ($LASTEXITCODE -ne 0) { throw 'Recursive nested audio audition/playback/master acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_source_boundaries.py') --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --client (Join-Path $Bin 'genesis-audio-nested.exe') --worker $worker `
      --report (Join-Path $reports 'audio-source-boundaries.json')
    if ($LASTEXITCODE -ne 0) { throw 'Native sample boundaries, source offsets and mono alignment acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_nested_cancel.py') --client (Join-Path $Bin 'genesis-audio-nested-cancel.exe') `
      --worker $worker --report (Join-Path $reports 'audio-nested-cancel.json')
    if ($LASTEXITCODE -ne 0) { throw 'Active nested audio warm cancellation and recovery acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_continuity.py') --worker $worker --report (Join-Path $reports 'audio-continuity.json')
    if ($LASTEXITCODE -ne 0) { throw 'Long fractional-rate audio continuity and resumed-seek acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_edit_context.py') --client (Join-Path $Bin 'genesis-audio-edit-context.exe') `
      --binary (Join-Path $Bin 'Genesis-AIR.exe') --worker $worker --report (Join-Path $reports 'audio-edit-context.json')
    if ($LASTEXITCODE -ne 0) { throw 'Preserved audio edit context PCM/peaks/export acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_nested_edit_context.py') --client (Join-Path $Bin 'genesis-audio-nested-edit-context.exe') `
      --worker $worker --report (Join-Path $reports 'audio-nested-edit-context.json')
    if ($LASTEXITCODE -ne 0) { throw 'Descendant-shortened nested audio context PCM/peaks acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_context_retime.py') --client (Join-Path $Bin 'genesis-audio-context-retime.exe') `
      --worker $worker --report (Join-Path $reports 'audio-context-retime.json')
    if ($LASTEXITCODE -ne 0) { throw 'The forward audio context retime gate failed.' }
    & python (Join-Path $PSScriptRoot 'audio_tail_history.py') --client (Join-Path $Bin 'genesis-audio-tail-history.exe') `
      --worker $worker --report (Join-Path $reports 'audio-tail-history.json')
    if ($LASTEXITCODE -ne 0) { throw 'Original-end audio tail history, actual EOF, cancellation and lossless-master acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_tail_protocol.py') --worker $worker --report (Join-Path $reports 'audio-tail-protocol.json')
    if ($LASTEXITCODE -ne 0) { throw 'Actual EOF audio tail protocol, capacity and cache-identity acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_eof_query.py') --worker $worker --report (Join-Path $reports 'audio-eof-query.json')
    if ($LASTEXITCODE -ne 0) { throw 'Committed audio EOF query, generation and cache-identity acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_tail_phase.py') --worker $worker --report (Join-Path $reports 'audio-tail-phase.json')
    if ($LASTEXITCODE -ne 0) { throw 'Native sample phase, actual EOF, retained cache and true effect-tail capacity acceptance failed.' }
    # Independent media/export and actor oracles execute the background workers.
    # Timing remains a separately invoked diagnostic; no device/GUI loop claim.
    $endpointClient = Join-Path $Bin 'genesis-standalone-endpoint-media.exe'
    $endpointPublisher = Join-Path $Bin 'air-file-publish.exe'
    if (-not (Test-Path -LiteralPath $endpointPublisher -PathType Leaf)) { throw 'Standalone endpoint export requires its adjacent atomic publisher.' }
    $endpointReferences = Join-Path $work 'standalone-endpoint-pcm'
    & python (Join-Path $PSScriptRoot 'standalone_endpoint_media.py') --client $endpointClient --worker $worker `
      --work $endpointReferences --report (Join-Path $reports 'standalone-endpoint-media.json')
    if ($LASTEXITCODE -ne 0) { throw 'Standalone accepted EOF, no-carrier ordered DSP and exact PCM acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'standalone_endpoint_export.py') --client $endpointClient --worker $worker `
      --references $endpointReferences --work (Join-Path $work 'standalone-endpoint-export') `
      --report (Join-Path $reports 'standalone-endpoint-export.json')
    if ($LASTEXITCODE -ne 0) { throw 'Standalone accepted EOF exact-count default and marked export acceptance failed.' }
    $endpointActor = Join-Path $Bin 'genesis-standalone-endpoint-actor.exe'
    $endpointCancel = Join-Path $Bin 'genesis-standalone-endpoint-cancel.exe'
    $endpointActorReport = Join-Path $reports 'standalone-endpoint-actor.json'
    & python (Join-Path $PSScriptRoot 'standalone_endpoint_actor.py') --client $endpointActor --worker $worker `
      --cancel-client $endpointCancel --work (Join-Path $work 'standalone-endpoint-actor') --report $endpointActorReport
    if ($LASTEXITCODE -ne 0) { throw 'Standalone background actor lifecycle and observed cold cancellation acceptance failed.' }
    $actorProof = Get-Content -LiteralPath $endpointActorReport -Raw | ConvertFrom-Json
    if (-not $actorProof.passed -or $actorProof.failures.Count -ne 0 -or $actorProof.requests -ne 26 -or
        $actorProof.pcm_values -ne 1393786 -or $actorProof.max_error_codes -gt 1 -or -not $actorProof.cache_cleanup -or
        -not $actorProof.actor.actor_joined -or -not $actorProof.cold_cancel.executed -or -not $actorProof.cold_cancel.passed -or
        -not $actorProof.cold_cancel.actor_joined -or $actorProof.cold_cancel.recovery_pcm_values -ne 225600 -or
        $actorProof.cold_cancel.recovery_max_error_codes -gt 1 -or $actorProof.cold_cancel.acknowledgement_ns -gt 2000000000 -or
        $actorProof.worker_sha256 -ne (Get-FileHash -LiteralPath $worker -Algorithm SHA256).Hash.ToLowerInvariant() -or
        $actorProof.client_sha256 -ne (Get-FileHash -LiteralPath $endpointActor -Algorithm SHA256).Hash.ToLowerInvariant() -or
        $actorProof.cold_cancel.client_sha256 -ne (Get-FileHash -LiteralPath $endpointCancel -Algorithm SHA256).Hash.ToLowerInvariant()) {
      throw 'Standalone actor receipt count, cleanup, cancellation or exact binary identity mismatch.'
    }
    $pictureInputs = @{
      protocol = (Join-Path $Bin 'genesis-program-picture-protocol.exe')
      control = (Join-Path $Bin 'genesis-program-picture-control.exe')
      persistent = (Join-Path $Bin 'genesis-program-picture-persistent.exe')
      epoch = (Join-Path $Bin 'genesis-program-picture-epoch.exe')
      mock = (Join-Path $Bin 'genesis-program-picture-mock.exe')
      worker = $worker
      helper = (Join-Path $PSScriptRoot 'program_picture_transport.py')
    }
    $pictureReport = Join-Path $reports 'program-picture-transport.json'
    & python $pictureInputs.helper --protocol-client $pictureInputs.protocol --control-client $pictureInputs.control `
      --mock $pictureInputs.mock --persistent-client $pictureInputs.persistent --epoch-client $pictureInputs.epoch `
      --worker $pictureInputs.worker --report $pictureReport
    if ($LASTEXITCODE -ne 0) { throw 'Persistent Program picture records, retirement and epoch acceptance failed.' }
    $pictureProof = Get-Content -LiteralPath $pictureReport -Raw | ConvertFrom-Json
    if ($pictureProof.schema -ne 'genesis.program-picture-transport.v2' -or -not $pictureProof.passed -or
        $pictureProof.cases.Count -ne 24 -or $pictureProof.protocol_cases -ne 17 -or $pictureProof.control_cases -ne 5 -or
        $pictureProof.real_pictures_each -ne 8193 -or $pictureProof.real_epoch_windows -ne 7 -or $pictureProof.real_metadata_workers -ne 1 -or $pictureProof.real_render_epochs -ne 5 -or
        @($pictureProof.inputs.PSObject.Properties).Count -ne 7) {
      throw 'Persistent Program picture report schema/count mismatch.'
    }
    $pictureHashes = @{}
    foreach ($entry in $pictureInputs.GetEnumerator()) {
      $path = (Resolve-Path -LiteralPath $entry.Value).Path
      $pin = @($pictureProof.inputs.PSObject.Properties | Where-Object { $_.Name -ieq $path })
      $digest = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
      if ($pin.Count -ne 1 -or $pin[0].Value -ne $digest) { throw ('Persistent picture exact input identity mismatch: ' + $entry.Key) }
      $pictureHashes[$entry.Key] = $digest
    }
    foreach ($case in $pictureProof.cases) {
      if (-not $case.passed -or $case.exit -ne 0 -or -not $case.client_joined -or -not $case.all_owned_exited -or
          $case.owned_pids.Count -eq 0 -or $case.failure -or $case.final_observation_error -or $case.parent_cleanup_error) {
        throw ('Persistent picture case failure or unjoined ownership: ' + $case.name)
      }
      $kind = if ($case.name -like 'protocol-*') { 'protocol' } elseif ($case.name -like 'control-*') { 'control' }
        elseif ($case.name -eq 'sustained') { 'persistent' } elseif ($case.name -eq 'epochs') { 'epoch' } else { throw 'Unknown picture case name.' }
      $engine = if ($kind -in @('protocol','control')) { 'mock' } else { 'worker' }
      if ($case.client_sha256 -ne $pictureHashes[$kind] -or $case.worker_sha256 -ne $pictureHashes[$engine]) {
        throw ('Persistent picture per-case binary identity mismatch: ' + $case.name)
      }
    }
    $sustained = @($pictureProof.cases | Where-Object { $_.name -eq 'sustained' })
    $epochs = @($pictureProof.cases | Where-Object { $_.name -eq 'epochs' })
    if ($sustained.Count -ne 1 -or $epochs.Count -ne 1 -or $sustained[0].observed_worker_pids.Count -ne 2 -or
        $sustained[0].owned_pids.Count -ne 2 -or $epochs[0].observed_worker_pids.Count -ne 6 -or $epochs[0].owned_pids.Count -ne 6) {
      throw 'Persistent picture exact physical epoch count mismatch.'
    }
    # The profile client is compiled separately; this gate makes no profile/cadence/device execution claim.
    & python (Join-Path $PSScriptRoot 'audio_plan_preflight.py') --binary (Join-Path $Bin 'genesis-audio-plan-preflight.exe') `
      --worker $worker --root (Join-Path $work 'audio-plan-preflight') --report (Join-Path $reports 'audio-plan-preflight.json')
    if ($LASTEXITCODE -ne 0) { throw 'Loaded-project audio preflight and valid-media recovery acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'audio_reverse.py') --worker $worker --report (Join-Path $reports 'reverse-audio-profile.json')
    if ($LASTEXITCODE -ne 0) { throw 'Long reverse audio and resampling acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'export_cancel.py') --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --worker $worker --wrapper (Join-Path $Bin 'genesis-worker-wrapper.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Active export cancellation and retry acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'export_ownership.py') --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --fixture (Join-Path $Bin 'genesis-export-ownership-worker.exe') --helper (Join-Path $Bin 'air-file-publish.exe') `
      --report (Join-Path $reports 'export-ownership.json')
    if ($LASTEXITCODE -ne 0) { throw 'Exclusive export ownership and no-replace publication acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'media_sessions.py') --fixture (Join-Path $Bin 'genesis-media-session.exe') `
      --worker $worker --binary (Join-Path $Bin 'Genesis-AIR.exe') --report (Join-Path $reports 'media-sessions.json')
    if ($LASTEXITCODE -ne 0) { throw 'Concurrent media session isolation acceptance failed.' }
  }
  Write-Host (Invoke-Native 'genesis-project-safety.exe' @($work)).TrimEnd()
  & python (Join-Path $PSScriptRoot 'recovery_ownership.py') --binary (Join-Path $Bin 'genesis-recovery-ownership.exe') `
    --report (Join-Path $reports 'recovery-ownership.json')
  if ($LASTEXITCODE -ne 0) { throw 'Concurrent recovery ownership acceptance failed.' }
  foreach ($artifact in @('project-safety-tests.json', 'project-decision.png', 'recovery-decision.png')) {
    Copy-Item -LiteralPath (Join-Path $work "project-safety/$artifact") -Destination (Join-Path $reports $artifact) -Force
  }
  Write-Host (Invoke-Native 'genesis-picture-queue.exe' @((Join-Path $reports 'picture-queue-tests.json'))).TrimEnd()
  Write-Host (Invoke-Native 'genesis-window-cache.exe' @((Join-Path $work 'window-cache'))).TrimEnd()
  Write-Host (Invoke-Native 'genesis-editor-trim.exe' @((Join-Path $work 'editor-trim'))).TrimEnd()
  Write-Host (Invoke-Native 'genesis-trim-history.exe' @((Join-Path $work 'trim-history'))).TrimEnd()
  Write-Host (Invoke-Native 'genesis-spatial-canvas.exe' @((Join-Path $reports 'spatial-canvas-tests.json'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'editor-trim/editor-trim-tests.json') -Destination (Join-Path $reports 'editor-trim-tests.json') -Force
  Copy-Item -LiteralPath (Join-Path $work 'trim-history/trim-history-tests.json') -Destination (Join-Path $reports 'trim-history-tests.json') -Force
  & python (Join-Path $PSScriptRoot 'window_timing_test.py')
  if ($LASTEXITCODE -ne 0) { throw 'Native window timing reader regression failed.' }
  & python (Join-Path $PSScriptRoot 'window_loss.py') --self-test
  if ($LASTEXITCODE -ne 0) { throw 'Native window loss attribution regression failed.' }
  Write-Host (Invoke-Native 'genesis-live-paint.exe' @($work)).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'live-paint-tests.json') -Destination (Join-Path $reports 'live-paint-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-inspector.exe' @($work)).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'inspector-tests.json') -Destination (Join-Path $reports 'inspector-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-keyframe-controls.exe' @((Join-Path $work 'keyframe-controls'))).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'keyframe-controls/keyframe-controls-tests.json') -Destination (Join-Path $reports 'keyframe-controls-tests.json') -Force
  $fadeControls = Join-Path $work 'fade-controls'
  Write-Host (Invoke-Native 'genesis-fade-controls.exe' @($fadeControls)).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $fadeControls 'fade-controls-tests.json') -Destination (Join-Path $reports 'fade-controls-tests.json') -Force
  $nestedControls = Join-Path $work 'nested-audio-controls'
  Write-Host (Invoke-Native 'genesis-nested-audio-controls.exe' @($nestedControls)).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $nestedControls 'nested-audio-controls-tests.json') -Destination (Join-Path $reports 'nested-audio-controls-tests.json') -Force
  $nestedBitmaps = Join-Path $work 'nested-timeline-bitmaps'
  Write-Host (Invoke-Native 'genesis-nested-timeline-bitmaps.exe' @($nestedBitmaps)).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $nestedBitmaps 'nested-timeline-bitmaps-tests.json') -Destination (Join-Path $reports 'nested-timeline-bitmaps-tests.json') -Force
  $nestedPlan = Join-Path $work 'nested-picture-plan'
  Write-Host (Invoke-Native 'genesis-nested-picture-plan.exe' @($nestedPlan)).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $nestedPlan 'nested-picture-plan-tests.json') -Destination (Join-Path $reports 'nested-picture-plan-tests.json') -Force
  $memoryPlan = Join-Path $work 'picture-memory'
  Write-Host (Invoke-Native 'genesis-picture-memory.exe' @($memoryPlan)).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $memoryPlan 'picture-memory-tests.json') -Destination (Join-Path $reports 'picture-memory-tests.json') -Force
  Copy-Item -LiteralPath (Join-Path $work 'native-tests.json') -Destination (Join-Path $reports 'native-tests.json') -Force

  $headless = Invoke-Native 'genesis-headless.exe' @($work, (Join-Path $work 'project.air'), (Join-Path $work 'frame.png'))
  Set-Content -LiteralPath (Join-Path $reports 'headless-output.txt') -Value $headless
  $facts = @{}
  foreach ($line in ($headless -split "`n")) {
    $parts = $line.TrimEnd("`r") -split "`t", 2
    if ($parts.Count -eq 2) { $facts[$parts[0]] = $parts[1] }
  }
  $checked = 0
  foreach ($line in Get-Content (Join-Path $PSScriptRoot 'headless.expected.tsv')) {
    $parts = $line -split "`t", 2
    if ($parts.Count -ne 2 -or $parts[0] -eq 'status_pixel_r') { continue }
    if ($facts[$parts[0]] -ne $parts[1]) { throw "Headless $($parts[0]): expected $($parts[1]), got $($facts[$parts[0]])" }
    $checked++
  }
  foreach ($name in @('drop_imported', 'drop_order')) { if ($facts[$name] -ne 'true') { throw "Headless $name failed." } }
  if ($facts['drop_count'] -ne '2') { throw 'Headless native drop count failed.' }
  Write-Host "Headless: $checked saved application facts and 3 native-drop checks passed."
  }

  $clicks = 0
  foreach ($tab in @('properties', 'filters', 'scopes', 'audio')) {
    $controls = Invoke-Native 'genesis-controls.exe' @($work, $tab)
    Set-Content -LiteralPath (Join-Path $reports "controls-$tab.txt") -Value $controls
    $rectangles = @{}
    foreach ($line in ($controls -split "`n")) {
      $parts = $line.TrimEnd("`r") -split "`t"
      if ($parts.Count -ge 9) {
        if ([string]::IsNullOrWhiteSpace($parts[8])) { throw "Unwired $tab control: $($parts[3])" }
        $clicks++
      }
      if ($parts.Count -eq 4 -and $parts[0] -eq 'RECT') {
        if (-not $rectangles.ContainsKey($parts[1])) { $rectangles[$parts[1]] = @() }
        $xy = @($parts[3] -split ',' | ForEach-Object { [double]$_ })
        foreach ($existing in $rectangles[$parts[1]]) {
          if ($xy[0] -lt $existing[2] -and $xy[2] -gt $existing[0] -and
              $xy[1] -lt $existing[3] -and $xy[3] -gt $existing[1]) {
            throw "Overlapping controls in $tab/$($parts[1]): $($parts[2])"
          }
        }
        $rectangles[$parts[1]] += ,$xy
      }
    }
  }
  Write-Host "Controls: $clicks clicks reported an outcome; all four tabs passed overlap checks."

  $probe = Invoke-Native 'Genesis-AIR.exe' @('probe', $media, (Join-Path $work 'real.png'))
  if ($probe -notmatch 'source_frame ok' -or $probe -notmatch 'provider_failures 0') { throw "Real GUI media path failed: $probe" }
  $failure = Invoke-Native 'Genesis-AIR.exe' @('probe', (Join-Path $work 'missing.mp4'), (Join-Path $work 'missing.png')) 1
  if ($failure -notmatch 'GA_MEDIA_COMMAND') { throw 'The probe command hid its media error code.' }
  Copy-Item -LiteralPath (Join-Path $work 'real.png') -Destination (Join-Path $reports 'real-media.png') -Force
  Write-Host 'Real Windows media/Unicode paths, source/program preview and failure exit codes passed.'
} finally {
  if ($null -eq $previousNativeColor) { Remove-Item Env:GENESIS_NATIVE_HDR_COLOR -ErrorAction SilentlyContinue }
  else { $env:GENESIS_NATIVE_HDR_COLOR = $previousNativeColor }
  if ($null -eq $previousWorker) { Remove-Item Env:GENESIS_GCOMPOSE -ErrorAction SilentlyContinue }
  else { $env:GENESIS_GCOMPOSE = $previousWorker }
  $resolved = (Resolve-Path -LiteralPath $work).Path
  $expectedRoot = [System.IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
  if (-not $resolved.StartsWith($expectedRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Test cleanup path escaped the build directory.' }
  try { Remove-Item -LiteralPath $resolved -Recurse -Force }
  catch { Write-Warning "[GA_TEST_CLEANUP] Could not remove $resolved : $($_.Exception.Message)" }
}
