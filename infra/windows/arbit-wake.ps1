<#
.SYNOPSIS
  Wakes this PC for Arbit's reads before NFL games and the daily injury report reads, then
  lets it sleep again (OWN-065, R-066).

.DESCRIPTION
  The PC sleeps when its owner chooses. Sleep stays in the Start menu. While the PC sleeps,
  Arbit's worker in WSL stops, so the ESPN game-day status before kickoff is missed. This script
  schedules Windows to wake the PC for each window, keeps it awake through the window, and then
  puts it back to sleep, but only if this task woke it and nobody has used the PC since.

  Windows:
  - Games: from 120 minutes before each kickoff (inactives are posted about 90 minutes before)
    to 30 minutes after. Kickoffs come from ESPN's public NFL scoreboard, read once a day.
  - Injury report: 12:00 and 19:15 US Eastern every day, 5 minutes before to 20 minutes after.
  - Windows less than 30 minutes apart are merged.

  -Install   copy this script to %LOCALAPPDATA%\Arbit, register the daily planner, plan now.
  -Plan      read the schedule and replace the \Arbit\ wake tasks for the next -Days days.
  -Hold      run by each wake task: keep the PC awake until -Until, then sleep if untouched.
  -Preview   read the schedule and print the coming windows without changing anything.
  -Windows   print the windows for -KickoffsJson at -Now, as JSON (tests).
  -Uninstall remove every \Arbit\ task and the installed copy.
#>
[CmdletBinding(DefaultParameterSetName = 'Windows')]
param(
  [Parameter(ParameterSetName = 'Install')][switch]$Install,
  [Parameter(ParameterSetName = 'Plan')][switch]$Plan,
  [Parameter(ParameterSetName = 'Hold')][switch]$Hold,
  [Parameter(ParameterSetName = 'Uninstall')][switch]$Uninstall,
  [Parameter(ParameterSetName = 'Windows')][switch]$Windows,
  [Parameter(ParameterSetName = 'Preview')][switch]$Preview,
  [Parameter(ParameterSetName = 'Hold')][string]$Start,
  [Parameter(ParameterSetName = 'Hold')][string]$Until,
  [Parameter(ParameterSetName = 'Windows')][string]$KickoffsJson,
  [Parameter(ParameterSetName = 'Windows')][string]$Now,
  [Parameter(ParameterSetName = 'Install')]
  [Parameter(ParameterSetName = 'Plan')]
  [Parameter(ParameterSetName = 'Preview')]
  [Parameter(ParameterSetName = 'Windows')][int]$Days = 8
)

$ErrorActionPreference = 'Stop'
$TaskPath = '\Arbit\'
$Home_ = Join-Path $env:LOCALAPPDATA 'Arbit'
$Installed = Join-Path $Home_ 'arbit-wake.ps1'
$LogFile = Join-Path $Home_ 'wake.log'
$Eastern = [TimeZoneInfo]::FindSystemTimeZoneById('Eastern Standard Time')
$BeforeKickoff = [TimeSpan]::FromMinutes(120)
$AfterKickoff = [TimeSpan]::FromMinutes(30)
$ReadTimes = @('12:00', '19:15')
$BeforeRead = [TimeSpan]::FromMinutes(5)
$AfterRead = [TimeSpan]::FromMinutes(20)
$MergeGap = [TimeSpan]::FromMinutes(30)

function Write-Log([string]$Message) {
  if (-not (Test-Path $Home_)) { New-Item -ItemType Directory -Path $Home_ | Out-Null }
  $line = '{0} {1}' -f [DateTime]::UtcNow.ToString('o'), $Message
  Add-Content -Path $LogFile -Value $line
}

function Get-WakeWindows([DateTime[]]$Kickoffs, [DateTime]$NowUtc, [int]$Horizon) {
  # All times UTC. Returns merged [start, end) windows that end after now.
  $spans = New-Object System.Collections.Generic.List[object]
  foreach ($k in $Kickoffs) {
    $spans.Add([pscustomobject]@{ Start = $k - $BeforeKickoff; End = $k + $AfterKickoff })
  }
  $today = [TimeZoneInfo]::ConvertTimeFromUtc($NowUtc, $Eastern).Date
  for ($d = 0; $d -le $Horizon; $d++) {
    foreach ($t in $ReadTimes) {
      $local = [DateTime]::SpecifyKind($today.AddDays($d).Add([TimeSpan]::Parse($t)), 'Unspecified')
      $utc = [TimeZoneInfo]::ConvertTimeToUtc($local, $Eastern)
      $spans.Add([pscustomobject]@{ Start = $utc - $BeforeRead; End = $utc + $AfterRead })
    }
  }
  # Through the end of the Eastern day -Horizon days ahead; 0 is today.
  $limit = [TimeZoneInfo]::ConvertTimeToUtc([DateTime]::SpecifyKind($today.AddDays($Horizon + 1), 'Unspecified'), $Eastern)
  $merged = New-Object System.Collections.Generic.List[object]
  foreach ($s in ($spans | Sort-Object Start)) {
    if ($s.End -le $NowUtc -or $s.Start -ge $limit) { continue }
    $last = if ($merged.Count) { $merged[$merged.Count - 1] } else { $null }
    if ($last -and $s.Start -le $last.End + $MergeGap) {
      if ($s.End -gt $last.End) { $last.End = $s.End }
    } else {
      $merged.Add([pscustomobject]@{ Start = $s.Start; End = $s.End })
    }
  }
  return $merged
}

function Get-Kickoffs([DateTime]$NowUtc, [int]$Horizon) {
  # ESPN's public scoreboard, one day per request (it refuses date ranges): no cookies,
  # read-only, a second apart. Times not yet set (timeValid false) are skipped; the daily plan
  # picks them up once ESPN sets them.
  $kickoffs = @()
  $style = [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal
  $first = [TimeZoneInfo]::ConvertTimeFromUtc($NowUtc, $Eastern).Date
  for ($d = 0; $d -le $Horizon; $d++) {
    $day = $first.AddDays($d).ToString('yyyyMMdd')
    $url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=$day"
    $board = Invoke-RestMethod -Uri $url -UserAgent 'Arbit/0.1 wake planner' -TimeoutSec 30
    foreach ($e in $board.events) {
      $competition = $e.competitions | Select-Object -First 1
      if ($competition.timeValid -eq $false) { continue }
      $kickoffs += [DateTime]::Parse($e.date, [Globalization.CultureInfo]::InvariantCulture, $style)
    }
    Start-Sleep -Seconds 1
  }
  return $kickoffs
}

function Format-Windows($Spans) {
  # An empty plan reaches here as null: PowerShell unrolls empty collections.
  return @($Spans | Where-Object { $null -ne $_ } | ForEach-Object {
      [ordered]@{ start = $_.Start.ToString('yyyy-MM-ddTHH:mm:ssZ'); end = $_.End.ToString('yyyy-MM-ddTHH:mm:ssZ') }
    })
}

function New-HiddenAction([string]$Arguments) {
  # conhost --headless (Windows 11) runs PowerShell with no window, even while someone uses the PC.
  return New-ScheduledTaskAction -Execute 'conhost.exe' -Argument ('--headless powershell.exe ' + $Arguments)
}

function Invoke-Plan([int]$Horizon) {
  $nowUtc = [DateTime]::UtcNow
  $wakeWindows = Get-WakeWindows -Kickoffs (Get-Kickoffs $nowUtc $Horizon) -NowUtc $nowUtc -Horizon $Horizon
  Get-ScheduledTask -TaskPath $TaskPath -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskName -like 'Wake *' } |
    ForEach-Object { Unregister-ScheduledTask -TaskName $_.TaskName -TaskPath $TaskPath -Confirm:$false }
  $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  $count = 0
  foreach ($w in $wakeWindows) {
    $startUtc = if ($w.Start -lt $nowUtc.AddMinutes(2)) { $nowUtc.AddMinutes(2) } else { $w.Start }
    $local = $startUtc.ToLocalTime()
    $arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Hold -Start {1} -Until {2}' -f `
      $Installed, $startUtc.ToString('yyyy-MM-ddTHH:mm:ssZ'), $w.End.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $action = New-HiddenAction $arguments
    $trigger = New-ScheduledTaskTrigger -Once -At $local
    $limit = ($w.End - $startUtc) + [TimeSpan]::FromMinutes(30)
    $settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries `
      -DontStopIfGoingOnBatteries -ExecutionTimeLimit $limit -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $name = 'Wake {0}' -f $local.ToString('yyyy-MM-dd HHmm')
    Register-ScheduledTask -TaskPath $TaskPath -TaskName $name -Action $action -Trigger $trigger `
      -Settings $settings -Principal $principal -Description 'Arbit: wake for NFL reads (R-066)' | Out-Null
    $count++
  }
  Write-Log ("planned {0} wake windows over {1} days" -f $count, $Horizon)
  return $wakeWindows
}

Add-Type -Namespace Arbit -Name Power -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);
[DllImport("powrprof.dll")] public static extern bool SetSuspendState(bool hibernate, bool force, bool wakeupEventsDisabled);
[StructLayout(LayoutKind.Sequential)] public struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
[DllImport("user32.dll")] public static extern bool GetLastInputInfo(ref LASTINPUTINFO info);
public static uint Tick() { return unchecked((uint)System.Environment.TickCount); }
public static bool InputSince(uint startTick) {
  LASTINPUTINFO info = new LASTINPUTINFO();
  info.cbSize = (uint)System.Runtime.InteropServices.Marshal.SizeOf(info);
  if (!GetLastInputInfo(ref info)) { return true; }
  return unchecked((int)(info.dwTime - startTick)) > 0;
}
'@ -ErrorAction SilentlyContinue

function Invoke-Hold([DateTime]$StartUtc, [DateTime]$UntilUtc) {
  $ES_CONTINUOUS = [uint32]'0x80000000'
  $ES_SYSTEM_REQUIRED = [uint32]'0x00000001'
  $startTick = [Arbit.Power]::Tick()
  $wake = Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-Power-Troubleshooter'; Id = 1 } `
    -MaxEvents 1 -ErrorAction SilentlyContinue
  $wokeByUs = $wake -and [Math]::Abs(($wake.TimeCreated.ToUniversalTime() - $StartUtc).TotalMinutes) -le 10
  Write-Log ("hold until {0}; woken by this task: {1}" -f $UntilUtc.ToString('o'), [bool]$wokeByUs)
  [void][Arbit.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
  try {
    # Make sure WSL, and with it Arbit's worker, is running.
    Start-Process -FilePath 'wsl.exe' -ArgumentList '-d', 'Ubuntu', '-e', 'true' -WindowStyle Hidden -Wait
    while ([DateTime]::UtcNow -lt $UntilUtc) {
      Start-Sleep -Seconds ([Math]::Min(60, [Math]::Max(1, ($UntilUtc - [DateTime]::UtcNow).TotalSeconds)))
    }
  } finally {
    [void][Arbit.Power]::SetThreadExecutionState($ES_CONTINUOUS)
  }
  # Someone used the PC since the window began if its last input came after the start.
  $touched = [Arbit.Power]::InputSince($startTick)
  if ($wokeByUs -and -not $touched) {
    Write-Log 'window over; untouched since this task woke the PC, so sleeping'
    [void][Arbit.Power]::SetSuspendState($false, $false, $false)
  } else {
    Write-Log ("window over; staying awake (woken by this task: {0}; used since: {1})" -f [bool]$wokeByUs, $touched)
  }
}

switch ($PSCmdlet.ParameterSetName) {
  'Windows' {
    $nowUtc = [DateTime]::Parse($Now, [Globalization.CultureInfo]::InvariantCulture,
      [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal)
    # Windows PowerShell passes a parsed JSON array down the pipeline as one object.
    $parsed = Get-Content -Raw $KickoffsJson | ConvertFrom-Json
    $kickoffs = @(foreach ($item in $parsed) {
        [DateTime]::Parse([string]$item, [Globalization.CultureInfo]::InvariantCulture,
          [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal)
      })
    $found = Format-Windows (Get-WakeWindows $kickoffs $nowUtc $Days)
    if ($found.Count) { ConvertTo-Json -InputObject $found -Compress } else { '[]' }
  }
  'Plan' { ConvertTo-Json -InputObject (Format-Windows (Invoke-Plan $Days)) -Compress }
  'Preview' {
    $nowUtc = [DateTime]::UtcNow
    $wakeWindows = Get-WakeWindows (Get-Kickoffs $nowUtc $Days) $nowUtc $Days
    foreach ($w in $wakeWindows) {
      '{0} to {1} (this PC''s time)' -f $w.Start.ToLocalTime().ToString('ddd MMM d HH:mm'), $w.End.ToLocalTime().ToString('HH:mm')
    }
  }
  'Hold' {
    $style = [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal
    $culture = [Globalization.CultureInfo]::InvariantCulture
    Invoke-Hold ([DateTime]::Parse($Start, $culture, $style)) ([DateTime]::Parse($Until, $culture, $style))
  }
  'Install' {
    if (-not (Test-Path $Home_)) { New-Item -ItemType Directory -Path $Home_ | Out-Null }
    Copy-Item -Path $PSCommandPath -Destination $Installed -Force
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Plan -Days {1}' -f $Installed, $Days
    $action = New-HiddenAction $arguments
    $triggers = @((New-ScheduledTaskTrigger -Daily -At '9:00'), (New-ScheduledTaskTrigger -AtLogOn -User $user))
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
      -ExecutionTimeLimit ([TimeSpan]::FromMinutes(10)) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskPath $TaskPath -TaskName 'Plan wake windows' -Action $action -Trigger $triggers `
      -Settings $settings -Principal $principal -Description 'Arbit: daily wake plan from the NFL schedule (R-066)' -Force | Out-Null
    Write-Log 'installed'
    ConvertTo-Json -InputObject (Format-Windows (Invoke-Plan $Days)) -Compress
  }
  'Uninstall' {
    Get-ScheduledTask -TaskPath $TaskPath -ErrorAction SilentlyContinue |
      ForEach-Object { Unregister-ScheduledTask -TaskName $_.TaskName -TaskPath $TaskPath -Confirm:$false }
    if (Test-Path $Installed) { Remove-Item $Installed }
    'uninstalled'
  }
}
