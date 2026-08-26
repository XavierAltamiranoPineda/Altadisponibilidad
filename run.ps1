[CmdletBinding()]
param(
    [ValidateSet('menu', 'all', 'validate', 'start', 'stop', 'failover', 'cleanup', 'reset', 'backup')]
    [string]$Action = 'menu'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $root 'run-ansible.ps1'

if (-not (Test-Path $runner)) {
    throw "No existe el lanzador: $runner"
}

function Invoke-Playbook {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [switch]$AskVault
    )

    Write-Host "`n>>> $Path" -ForegroundColor Cyan
    $arguments = @($Path)
    if ($AskVault) {
        $arguments += '--ask-vault-pass'
    }

    & $runner @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "El playbook fallo: $Path"
    }
}

function Invoke-All {
    Invoke-Playbook 'playbooks/infrastructure/swarm_setup.yml'
    Invoke-Playbook 'playbooks/infrastructure/network_setup.yml'
    $keyfile = Join-Path $root 'secrets\mongo-keyfile'
    if (-not (Test-Path $keyfile)) {
        Invoke-Playbook 'playbooks/security/keyfile_setup.yml'
    } else {
        Write-Host '>>> Keyfile existente, se conserva' -ForegroundColor DarkGray
    }
    Invoke-Playbook 'playbooks/security/keyfile_secret.yml'
    Invoke-Playbook 'playbooks/mongodb/mongo_services.yml'
    Invoke-Playbook 'playbooks/mongodb/mongo_replset.yml'
    Invoke-Playbook 'playbooks/mongodb/mongo_replset_nodes.yml'
    Invoke-Playbook 'playbooks/mongodb/mongo_create_admin.yml'
    Invoke-Playbook 'playbooks/mongodb/mongo_replset_add_nodes.yml'
    Invoke-Playbook 'playbooks/mongodb/configure_priorities.yml' 
    Invoke-Playbook 'playbooks/validation/validate_mongodb.yml'
    Invoke-Playbook 'playbooks/validation/validate_replset.yml' 
    Invoke-playbook 'playbooks/tests/test_replication_data.yml'
    Invoke-playbook 'playbooks/tests/test_high_availability.yml'

}


function Invoke-backup {
    Invoke-Playbook 'playbooks/backup/backup_tools_setup.yml'
    Invoke-Playbook 'playbooks/backup/backup_create_users.yml'
    Invoke-Playbook 'playbooks/backup/backup_tools_image_setup.yml'

    Invoke-Playbook 'playbooks/backup/backup_run.yml'
    Invoke-Playbook 'playbooks/backup/backup_validate.yml'
    Invoke-Playbook 'playbooks/backup/restore_create_user.yml'
    Invoke-Playbook 'playbooks/backup/restore_test.yml'
    Invoke-Playbook 'playbooks/backup/restore_disaster_test.yml'
}

function Show-Menu {
    Write-Host "`nBaseSpringApi - MongoDB HA / Docker Swarm" -ForegroundColor Green
    Write-Host '1. Despliegue completo'
    Write-Host '2. Validar cluster'
    Write-Host '3. Iniciar nodos'
    Write-Host '4. Detener nodos y conservar 0/0'
    Write-Host '5. Ejecutar prueba de failover'
    Write-Host '6. Limpiar datos de prueba'
    Write-Host '7. Reset destructivo'
    $selection = Read-Host 'Selecciona una opcion'
    switch ($selection) {
        '1' { Invoke-All }
        '2' { Invoke-Playbook 'playbooks/validation/validate_replset.yml' -AskVault }
        '3' { Invoke-Playbook 'playbooks/mongodb/start_mongo.yml' }
        '4' { Invoke-Playbook 'playbooks/mongodb/stop_mongo.yml' }
        '5' { Invoke-Playbook 'playbooks/tests/test_high_availability.yml' -AskVault }
        '6' { Invoke-Playbook 'playbooks/tests/cleanup_test_data.yml' -AskVault }
        '7' {
            $confirmation = Read-Host 'Escribe RESET para confirmar eliminacion de servicios, volumenes y secret'
            if ($confirmation -cne 'RESET') { throw 'Reset cancelado' }
            Invoke-Playbook 'playbooks/tests/reset_local_environment.yml'
        }
        default { throw 'Opcion no valida' }
    }
}

switch ($Action) {
    'menu' { Show-Menu }
    'all' { Invoke-All }
    'backup' { Invoke-backup }
    'validate' { Invoke-Playbook 'playbooks/validation/validate_replset.yml' -AskVault }
    'start' { Invoke-Playbook 'playbooks/mongodb/start_mongo.yml' }
    'stop' { Invoke-Playbook 'playbooks/mongodb/stop_mongo.yml' }
    'failover' { Invoke-Playbook 'playbooks/tests/test_high_availability.yml' -AskVault }
    'cleanup' { Invoke-Playbook 'playbooks/tests/cleanup_test_data.yml' -AskVault }
    'reset' {
        $confirmation = Read-Host 'Escribe RESET para confirmar eliminacion de servicios, volumenes y secret'
        if ($confirmation -cne 'RESET') { throw 'Reset cancelado' }
        Invoke-Playbook 'playbooks/tests/reset_local_environment.yml'
    }
}
