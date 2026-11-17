# Script de configuração do Agendador de Tarefas do Windows
$TaskName = "MonitorRastreio"

# Determina dinamicamente a pasta onde este script está localizado
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }

$WorkingDir = $ScriptDir
$BatPath = Join-Path $ScriptDir "run.bat"

# Ação: executar o run.bat em segundo plano
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`"" -WorkingDirectory $WorkingDir

# Trigger: Executar a cada 1 hora repetidamente
$Trigger = New-ScheduledTaskTrigger -Once -At 00:00 -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)

# Configurações de confiabilidade
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Registrar ou atualizar a tarefa
Register-ScheduledTask -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Rastreamento automatico a cada 1 hora com envio inteligente por email." `
    -Force

Write-Host "Tarefa '$TaskName' reconfigurada com sucesso para rodar A CADA 1 HORA!"
Write-Host "Diretório de trabalho: $WorkingDir"
Write-Host "Arquivo batch: $BatPath"
