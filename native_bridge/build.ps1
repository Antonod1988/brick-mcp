$ErrorActionPreference = 'Stop'
$shipManaged = 'D:\Progs\Studio 2.0\Studio_Data\Managed'
$shipWorker = [IO.Path]::GetFullPath("$PSScriptRoot\..\.cache\studio-worker")
if (Test-Path -LiteralPath "$shipWorker\source.json") {
    $shipSource = Get-Content -LiteralPath "$shipWorker\source.json" -Raw | ConvertFrom-Json
    $shipManaged = Join-Path $shipSource.studio_dir 'Studio_Data\Managed'
}
$shipRefs = @('mscorlib','System','System.Core','netstandard','UnityEngine','UnityEngine.CoreModule','Newtonsoft.Json') | ForEach-Object { "/r:$shipManaged\$_.dll" }
& 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe' /nologo /noconfig /target:library /nostdlib+ "/out:$shipWorker\BepInEx\plugins\StudioBridge.dll" @shipRefs "/r:$shipWorker\BepInEx\core\BepInEx.dll" "/r:$shipWorker\BepInEx\core\0Harmony.dll" "$PSScriptRoot\StudioBridge.cs"
if ($LASTEXITCODE -ne 0) { throw 'Native bridge compilation failed' }
