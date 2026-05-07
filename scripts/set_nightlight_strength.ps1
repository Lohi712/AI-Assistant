# set_nightlight_strength.ps1 — Set Night Light strength via UI Automation
# Usage: powershell -ExecutionPolicy Bypass -File set_nightlight_strength.ps1 -Value 70
#
# Sets the Night Light "Strength" slider to the given value (0-100).

param(
    [Parameter(Mandatory=$true)]
    [int]$Value
)

# Clamp to valid range
if ($Value -lt 0)   { $Value = 0 }
if ($Value -gt 100) { $Value = 100 }

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

# Open Night Light settings
Start-Process "ms-settings:nightlight"

# Wait for the Settings window
$root = [System.Windows.Automation.AutomationElement]::RootElement
$settingsWin = $null

for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500

    $classCondition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ClassNameProperty,
        "ApplicationFrameWindow"
    )
    $allWindows = $root.FindAll(
        [System.Windows.Automation.TreeScope]::Children,
        $classCondition
    )

    foreach ($win in $allWindows) {
        if ($win.Current.Name -match "Settings|Night") {
            $settingsWin = $win
            break
        }
    }

    if ($settingsWin) { break }
}

if (-not $settingsWin) {
    Write-Output "NO_WINDOW"
    exit
}

# Find the Strength slider by AutomationId
$sliderCondition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
    "SystemSettings_Display_BlueLight_ColorTemperature_Slider"
)
$slider = $settingsWin.FindFirst(
    [System.Windows.Automation.TreeScope]::Descendants,
    $sliderCondition
)

if ($slider) {
    try {
        $rvp = $null
        $hasRV = $slider.TryGetCurrentPattern(
            [System.Windows.Automation.RangeValuePattern]::Pattern,
            [ref]$rvp
        )
        if ($hasRV -and $rvp) {
            $rvp.SetValue($Value)
            Write-Output "SUCCESS:$Value"
        } else {
            Write-Output "NO_PATTERN"
        }
    } catch {
        Write-Output "ERROR: $_"
    }
} else {
    Write-Output "NO_SLIDER"
}

Start-Sleep -Seconds 1
Stop-Process -Name SystemSettings -Force -ErrorAction SilentlyContinue
