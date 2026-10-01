param([string]$Bin = (Join-Path $PSScriptRoot '../build-windows/native/bin/Release'))
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$root = Join-Path $project 'build-windows'
$work = Join-Path $root ('test-' + [guid]::NewGuid().ToString('N'))
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
  $media = Join-Path $work 'real clip 日本語.mp4'
  & ffmpeg -nostdin -y -v error -f lavfi -i 'color=c=red:s=640x360:r=30:d=1' `
    -f lavfi -i 'color=c=blue:s=640x360:r=30:d=1' `
    -f lavfi -i 'sine=frequency=440:sample_rate=48000:duration=2' `
    -filter_complex '[0:v][1:v]concat=n=2:v=1:a=0[v]' -map '[v]' -map '2:a' `
    -c:v libx264 -pix_fmt yuv420p -c:a aac -t 2 $media
  if ($LASTEXITCODE -ne 0) { throw 'Could not generate the real video fixture.' }

  Write-Host (Invoke-Native 'genesis-ui-pixels.exe' @()).TrimEnd()
  $native = Invoke-Native 'genesis-native.exe' @($work, $media)
  Write-Host $native.TrimEnd()
  $wave = Join-Path $work 'queued audio 日本語.wav'
  & ffmpeg -nostdin -y -v error -i $media -vn -ac 2 -ar 48000 -c:a pcm_s16le $wave
  if ($LASTEXITCODE -ne 0) { throw 'Could not generate native audio fixture.' }
  Write-Host (Invoke-Native 'genesis-audio-device.exe' @($wave)).TrimEnd()
  $worker = Join-Path $project 'genesis-gcompose.exe'
  if (Test-Path -LiteralPath $worker) {
    Write-Host (Invoke-Native 'genesis-preview-async.exe' @($worker, $media, (Join-Path $work 'async'))).TrimEnd()
    Copy-Item -LiteralPath (Join-Path $work 'async/timeline-scrub.png') -Destination (Join-Path $root 'timeline-scrub.png') -Force
    & python (Join-Path $PSScriptRoot 'audio_stream.py') --worker $worker --client (Join-Path $Bin 'genesis-audio-playback.exe') `
      --cancel-client (Join-Path $Bin 'genesis-audio-cancel.exe') --wrapper (Join-Path $Bin 'genesis-worker-wrapper.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Continuous audio and active cancellation acceptance failed.' }
    & python (Join-Path $PSScriptRoot 'export_cancel.py') --binary (Join-Path $Bin 'Genesis-AIR.exe') `
      --worker $worker --wrapper (Join-Path $Bin 'genesis-worker-wrapper.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Active export cancellation and retry acceptance failed.' }
  }
  Write-Host (Invoke-Native 'genesis-project-safety.exe' @($work)).TrimEnd()
  foreach ($artifact in @('project-safety-tests.json', 'project-decision.png', 'recovery-decision.png')) {
    Copy-Item -LiteralPath (Join-Path $work "project-safety/$artifact") -Destination (Join-Path $root $artifact) -Force
  }
  Write-Host (Invoke-Native 'genesis-live-paint.exe' @($work)).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'live-paint-tests.json') -Destination (Join-Path $root 'live-paint-tests.json') -Force
  Write-Host (Invoke-Native 'genesis-inspector.exe' @($work)).TrimEnd()
  Copy-Item -LiteralPath (Join-Path $work 'inspector-tests.json') -Destination (Join-Path $root 'inspector-tests.json') -Force
  Copy-Item -LiteralPath (Join-Path $work 'native-tests.json') -Destination (Join-Path $root 'native-tests.json') -Force

  $headless = Invoke-Native 'genesis-headless.exe' @($work, (Join-Path $work 'project.air'), (Join-Path $work 'frame.png'))
  Set-Content -LiteralPath (Join-Path $root 'headless-output.txt') -Value $headless
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

  $clicks = 0
  foreach ($tab in @('properties', 'filters', 'scopes', 'audio')) {
    $controls = Invoke-Native 'genesis-controls.exe' @($work, $tab)
    Set-Content -LiteralPath (Join-Path $root "controls-$tab.txt") -Value $controls
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
  Copy-Item -LiteralPath (Join-Path $work 'real.png') -Destination (Join-Path $root 'real-media.png') -Force
  Write-Host 'Real Windows media/Unicode paths, source/program preview and failure exit codes passed.'
} finally {
  $resolved = (Resolve-Path -LiteralPath $work).Path
  $expectedRoot = [System.IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
  if (-not $resolved.StartsWith($expectedRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Test cleanup path escaped the build directory.' }
  try { Remove-Item -LiteralPath $resolved -Recurse -Force }
  catch { Write-Warning "[GA_TEST_CLEANUP] Could not remove $resolved : $($_.Exception.Message)" }
}
