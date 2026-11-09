# Creates the Hypervisor desktop shortcut and stamps its AppUserModelID so a
# pinned taskbar icon matches the running window's identity (the app sets the
# same ID via SetCurrentProcessExplicitAppUserModelID at startup).
# All paths derive from this script's location, so it works on any machine.
# Usage: powershell -ExecutionPolicy Bypass -File create-shortcut.ps1
$root = $PSScriptRoot
$pythonw = (Get-Command pythonw -ErrorAction Stop).Source
$ws = New-Object -ComObject WScript.Shell
$desktop = [System.Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "Hypervisor.lnk"
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = $pythonw
$sc.Arguments = "`"$(Join-Path $root 'hypervisor-app.py')`""
$sc.WorkingDirectory = $root
$sc.IconLocation = "$(Join-Path $root 'assets\hypervisor.ico'),0"
$sc.Save()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($sc) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ws) | Out-Null
[GC]::Collect(); [GC]::WaitForPendingFinalizers()
Start-Sleep -Milliseconds 300
Write-Host "Shortcut created at: $lnk"

# WScript.Shell cannot set System.AppUserModel.ID; pywin32's propsys can.
$py = @"
import sys
from win32com.propsys import propsys, pscon
from win32com.shell import shellcon
lnk = sys.argv[1]
store = propsys.SHGetPropertyStoreFromParsingName(lnk, None, shellcon.GPS_READWRITE, propsys.IID_IPropertyStore)
store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType('Hyper.Hypervisor'))
store.Commit()
print('AppUserModelID set: Hyper.Hypervisor')
"@
try {
    $py | python - $lnk
} catch {
    Write-Host "Note: could not set AppUserModelID (pywin32 missing?) - process-level ID still applies at runtime."
}
