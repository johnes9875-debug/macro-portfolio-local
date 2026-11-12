Unregister-ScheduledTask -TaskName "MacroPortfolio_Close_Check" -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "MacroPortfolio_Dashboard" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Macro Portfolio scheduled tasks removed."
