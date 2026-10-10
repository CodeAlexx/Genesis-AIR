param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Destination = [IO.Path]::GetFullPath($Destination)
$deps = Join-Path $repo 'build-windows/deps'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
if (-not $vs) { throw 'The OpenCL fault fixture needs MSVC Build Tools.' }
$dev = Join-Path $vs 'Common7/Tools/VsDevCmd.bat'
$environmentLines = & cmd.exe /d /s /c "`"$dev`" -arch=x64 -host_arch=x64 >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'Cannot initialize the MSVC fixture environment.' }
foreach ($line in $environmentLines) {
  if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
}
$loader = Join-Path $deps 'opencl-build/Release/OpenCL.dll'
$imports = Join-Path $deps 'opencl-build/Release/OpenCL.lib'
$names = & dumpbin.exe /nologo /exports $loader | ForEach-Object {
  if ($_ -match '^\s+\d+\s+[0-9A-F]+\s+[0-9A-F]+\s+(\S+)\s*$') { $matches[1] }
}
if ($LASTEXITCODE -ne 0 -or -not $names) { throw 'Cannot inspect the original OpenCL loader exports.' }
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$forwarders = @($names | Where-Object { $_ -notin @('clGetPlatformIDs', 'clEnqueueReadBuffer') } |
  ForEach-Object { "/EXPORT:$_=OpenCL_real.$_" })
# The import library resolves the forwarded exports while creating the proxy's
# own import library. At runtime the temporary OpenCL_real.dll is the original
# loader; this fault proxy is never installed beside the production worker.
$compileArguments = @('/nologo', '/LD', '/O2', "/I$(Join-Path $deps 'OpenCL-Headers')",
  (Join-Path $PSScriptRoot 'lazy_gpu_fault_windows.c'), "/Fo$(Join-Path $Destination 'proxy.obj')",
  '/link', $imports) + $forwarders + @("/OUT:$(Join-Path $Destination 'OpenCL.dll')", "/IMPLIB:$(Join-Path $Destination 'OpenCL.lib')")
& cl.exe @compileArguments
if ($LASTEXITCODE -ne 0) { throw 'OpenCL fault proxy compilation failed.' }
