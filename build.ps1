$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    dotnet build src/InFalsus.B30 -c Release
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    dotnet run --project tests/InFalsus.B30.Tests -c Release -- test-output
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    dotnet pack src/InFalsus.B30 -c Release -o packages
    if ($LASTEXITCODE -ne 0) { throw 'Pack failed' }
    New-Item -ItemType Directory -Force bin/win-x64 | Out-Null
    Copy-Item src/InFalsus.B30/bin/Release/net6.0/InFalsus.B30.dll,src/InFalsus.B30/bin/Release/net6.0/InFalsus.B30.xml bin/win-x64
    # NuGet restores the native dependencies; normal consumers should use PackageReference.
    $nugetRoot = if ($env:NUGET_PACKAGES) { $env:NUGET_PACKAGES } else { Join-Path $env:USERPROFILE '.nuget/packages' }
    Copy-Item "$nugetRoot/skiasharp/4.152.0/lib/net6.0/SkiaSharp.dll" bin/win-x64
    Copy-Item "$nugetRoot/skiasharp.nativeassets.win32/4.152.0/runtimes/win-x64/native/libSkiaSharp.dll" bin/win-x64
    Copy-Item "$nugetRoot/skiasharp/4.152.0/LICENSE.txt" bin/win-x64/SkiaSharp-LICENSE.txt
    Copy-Item "$nugetRoot/skiasharp.nativeassets.win32/4.152.0/THIRD-PARTY-NOTICES.txt" bin/win-x64/SkiaSharp-THIRD-PARTY-NOTICES.txt
} finally { Pop-Location }
