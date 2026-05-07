# toggle_nightlight.ps1 — Toggle Night Light via UI Automation
# Usage: powershell -ExecutionPolicy Bypass -File toggle_nightlight.ps1
#
# Finds both "Turn on now" and "Turn off now" buttons and clicks
# whichever one is present.

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

# Open Night Light settings
Start-Process "ms-settings:nightlight"

# Wait for the Settings window to appear (retry up to 10 seconds)
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
        $name = $win.Current.Name
        if ($name -match "Settings|Night") {
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

# Try both button IDs: "Turn on now" and "Turn off now"
$buttonIds = @(
    "SystemSettings_Display_BlueLight_ManualToggleOn_Button",
    "SystemSettings_Display_BlueLight_ManualToggleOff_Button"
)

$clicked = $false

foreach ($btnId in $buttonIds) {
    $btnCondition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
        $btnId
    )
    $toggleBtn = $settingsWin.FindFirst(
        [System.Windows.Automation.TreeScope]::Descendants,
        $btnCondition
    )

    if ($toggleBtn) {
        try {
            # Try Invoke pattern first (for buttons)
            $invokePattern = $null
            $hasInvoke = $toggleBtn.TryGetCurrentPattern(
                [System.Windows.Automation.InvokePattern]::Pattern,
                [ref]$invokePattern
            )
            if ($hasInvoke -and $invokePattern) {
                $invokePattern.Invoke()
                $clicked = $true
                Write-Output "SUCCESS"
                break
            }

            # Fallback: try Toggle pattern
            $togglePattern = $null
            $hasToggle = $toggleBtn.TryGetCurrentPattern(
                [System.Windows.Automation.TogglePattern]::Pattern,
                [ref]$togglePattern
            )
            if ($hasToggle -and $togglePattern) {
                $togglePattern.Toggle()
                $clicked = $true
                Write-Output "SUCCESS"
                break
            }
        } catch {
            Write-Output "ERROR: $_"
        }
    }
}

if (-not $clicked) {
    # Last resort: find ANY button with "night" or "Turn" in its name
    $allCondition = [System.Windows.Automation.Condition]::TrueCondition
    $elements = $settingsWin.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        $allCondition
    )

    foreach ($elem in $elements) {
        try {
            $name = $elem.Current.Name
            if ($name -match "Turn (on|off) now") {
                $invokePattern = $null
                $hasInvoke = $elem.TryGetCurrentPattern(
                    [System.Windows.Automation.InvokePattern]::Pattern,
                    [ref]$invokePattern
                )
                if ($hasInvoke -and $invokePattern) {
                    $invokePattern.Invoke()
                    $clicked = $true
                    Write-Output "SUCCESS"
                    break
                }
            }
        } catch { continue }
    }
}

if (-not $clicked) {
    Write-Output "NO_TOGGLE"
}

Start-Sleep -Seconds 1
Stop-Process -Name SystemSettings -Force -ErrorAction SilentlyContinue
