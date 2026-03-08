Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder lpString, int nMaxCount);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
}
'@

$script:targetHwnd = [IntPtr]::Zero
[Win32]::EnumWindows({
    param($hwnd, $lparam)
    $sb = New-Object System.Text.StringBuilder(256)
    [Win32]::GetWindowText($hwnd, $sb, 256) | Out-Null
    $title = $sb.ToString()
    if ($title -match 'pygame|CTES|Colony|Settlers') {
        $script:targetHwnd = $hwnd
        Write-Host "Found window: $title"
    }
    return $true
}, [IntPtr]::Zero)

if ($script:targetHwnd -ne [IntPtr]::Zero) {
    [Win32]::ShowWindow($script:targetHwnd, 9) | Out-Null
    [Win32]::SetForegroundWindow($script:targetHwnd) | Out-Null
    Start-Sleep -Milliseconds 800
} else {
    Write-Host "No matching window found"
}

$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save('C:\Users\me\Programming\ctes-game\screenshot.png')
$graphics.Dispose()
$bitmap.Dispose()
Write-Host 'Screenshot saved'
