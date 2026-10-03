param(
  [Parameter(Mandatory)][string]$Sdk,
  [Parameter(Mandatory)][string]$Destination,
  [string]$MmAirRoot = $(if ($env:MM_AIR_ROOT) { $env:MM_AIR_ROOT } else { 'C:\MM-Air' })
)
$ErrorActionPreference = 'Stop'
$owner = (Resolve-Path -LiteralPath $MmAirRoot).Path
$tools = @('ffmpeg.exe', 'ffprobe.exe') | ForEach-Object {
  $tool = Join-Path $owner $_
  if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "[GA_MEDIA_RUNTIME] Missing MM-AIR tool: $tool" }
  $tool
}
$version = Split-Path $Sdk -Leaf
$shared = [IO.Path]::GetFullPath((Join-Path $owner "share/media/$version/bin"))
if (-not $shared.StartsWith($owner.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
  throw '[GA_MEDIA_RUNTIME] Shared runtime must stay inside MM-AIR.'
}
New-Item -ItemType Directory -Force -Path $shared, $Destination | Out-Null
# MM-AIR's tools stay in place. Genesis receives only locations, not a codec bundle.
Get-ChildItem -LiteralPath (Join-Path $Sdk 'bin') -Filter '*.dll' | ForEach-Object {
  $target = Join-Path $shared $_.Name
  if (Test-Path -LiteralPath $target) {
    if ((Get-FileHash -LiteralPath $target).Hash -ne (Get-FileHash -LiteralPath $_.FullName).Hash) {
      throw "[GA_MEDIA_RUNTIME] Existing shared library differs: $target"
    }
  } else { Copy-Item -LiteralPath $_.FullName -Destination $target }
}
$license = Join-Path (Split-Path $shared -Parent) 'FFmpeg.txt'
if (-not (Test-Path -LiteralPath $license)) {
  Copy-Item -LiteralPath (Join-Path $Sdk 'LICENSE.txt') -Destination $license
}
[IO.File]::WriteAllText((Join-Path $Destination 'genesis-media-runtime.txt'),
  "$shared`n$($tools[0])`n$($tools[1])`n", [Text.UTF8Encoding]::new($false))
