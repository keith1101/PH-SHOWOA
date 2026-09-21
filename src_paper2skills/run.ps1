$ErrorActionPreference = 'Stop'
$solverArguments = $args
& (Join-Path $PSScriptRoot 'build.ps1')
& java -Xmx1g -cp (Join-Path $PSScriptRoot 'build/classes') phshowoa.Main @solverArguments
if ($LASTEXITCODE -ne 0) { throw "Solver exited with code $LASTEXITCODE" }
