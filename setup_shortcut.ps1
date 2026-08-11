# Setup desktop shortcut for Job Application Assistant
$AppDir  = "C:\Users\kmaje\Documents\job_application_assistant"
$Pythonw = "C:\Users\kmaje\AppData\Local\Programs\Python\Python312\pythonw.exe"
$Script  = "$AppDir\launch_app.pyw"
$Icon    = "$AppDir\app_icon.ico"
$Desktop = [System.Environment]::GetFolderPath("Desktop")
$ShortcutPath = "$Desktop\Job Application Assistant.lnk"

$Shell = New-Object -ComObject WScript.Shell
$SC    = $Shell.CreateShortcut($ShortcutPath)

$SC.TargetPath       = $Pythonw
$SC.Arguments        = "`"$Script`""
$SC.WorkingDirectory = $AppDir
$SC.IconLocation     = "$Icon,0"
$SC.Description      = "Job Application Assistant v2.0 - AI-Powered"
$SC.WindowStyle      = 1

$SC.Save()
Write-Host "Shortcut created at: $ShortcutPath"
