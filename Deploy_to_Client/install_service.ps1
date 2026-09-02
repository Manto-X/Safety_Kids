# 1. CÃ i Ä‘áº·t nhÃ¡nh MASTER (SYSTEM) - Xá»­ lÃ½ kill process, khÃ³a mÃ¡y
$actionMaster = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "C:\ProgramData\Safety_Kid\hc_master.py"
$triggerMaster = New-ScheduledTaskTrigger -AtStartup
$principalMaster = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settingsMaster = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "Safety_Kids_Master" -Action $actionMaster -Trigger $triggerMaster -Principal $principalMaster -Settings $settingsMaster -Force

# 2. CÃ i Ä‘áº·t nhÃ¡nh HELPER (SYSTEM) - Watchdog báº£o vá»‡ Master
$actionHelper = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "C:\ProgramData\Safety_Kid\win_sys_helper.py"
$triggerHelper = New-ScheduledTaskTrigger -AtStartup
$principalHelper = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName "Windows_System_Helper" -Action $actionHelper -Trigger $triggerHelper -Principal $principalHelper -Settings $settingsMaster -Force

# 3. CÃ i Ä‘áº·t nhÃ¡nh EYES (USER) - Khá»Ÿi Ä‘á»™ng khi User Login Ä‘á»ƒ chá»¥p Ä‘Æ°á»£c giao diá»‡n mÃ n hÃ¬nh
$actionEyes = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "C:\ProgramData\Safety_Kid\hc_eyes.py"
$triggerEyes = New-ScheduledTaskTrigger -AtLogOn
# Cháº¡y dÆ°á»›i quyá»n User Ä‘ang Ä‘Äƒng nháº­p (nhÃ³m Users)
$principalEyes = New-ScheduledTaskPrincipal -GroupId "Users" -RunLevel Highest
$settingsEyes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "Safety_Kids_Eyes" -Action $actionEyes -Trigger $triggerEyes -Principal $principalEyes -Settings $settingsEyes -Force

Write-Host "CÃ i Ä‘áº·t thÃ nh cÃ´ng. ÄÃ£ Ä‘Äƒng kÃ½ 3 Service: Safety_Kids_Master, Windows_System_Helper (SYSTEM) vÃ  Safety_Kids_Eyes (USER)."

