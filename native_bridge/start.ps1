$ErrorActionPreference = 'Stop'
$shipWorker = [IO.Path]::GetFullPath("$PSScriptRoot\..\.cache\studio-worker")
$shipExecutable = "$shipWorker\StudioWorker.exe"
if (Test-Path -LiteralPath "$shipWorker\worker.pid") {
    $shipPid = [int](Get-Content -LiteralPath "$shipWorker\worker.pid")
    $shipOldProcess = Get-Process -Id $shipPid -ErrorAction SilentlyContinue
    if ($shipOldProcess -and $shipOldProcess.Path -eq $shipExecutable) { Stop-Process -Id $shipPid }
}
& "$PSScriptRoot\build.ps1"
$shipProcess = Start-Process -FilePath $shipExecutable -WorkingDirectory $shipWorker -ArgumentList @('-batchmode','-skipupdate','-screen-fullscreen','0','-screen-width','800','-screen-height','600','-logFile','worker-player.log','-files', "$shipWorker\jobs\bootstrap.io") -WindowStyle Hidden -PassThru
$shipProcess.Id | Set-Content -LiteralPath "$shipWorker\worker.pid"
$shipProcess.Id
