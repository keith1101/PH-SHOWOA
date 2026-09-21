param([switch]$Test)
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$classesDirectory = Join-Path $projectDirectory 'build/classes'
New-Item -ItemType Directory -Force -Path $classesDirectory | Out-Null
$sourceFiles = @(Get-ChildItem -LiteralPath (Join-Path $projectDirectory 'src/main/java') -Filter '*.java' -Recurse | ForEach-Object { $_.FullName })
if ($Test) {
    $sourceFiles += @(Get-ChildItem -LiteralPath (Join-Path $projectDirectory 'src/test/java') -Filter '*.java' -Recurse | ForEach-Object { $_.FullName })
}
& javac -encoding UTF-8 -source 8 -target 8 -Xlint:all -d $classesDirectory @sourceFiles
if ($LASTEXITCODE -ne 0) { throw 'Java compilation failed' }
Write-Host "Compiled Java sources into $classesDirectory"
if ($Test) {
    & java -Xmx1g -ea -cp $classesDirectory phshowoa.RegressionTests $projectDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Java regression tests failed' }
}
