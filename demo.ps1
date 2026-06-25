# ─────────────────────────────────────────────────────────────────────────────
# demo.ps1 — Script de démonstration de la stack Observa
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   DÉMONSTRATION DE L'APPLICATION OBSERVA         " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Vérification de la santé globale de l'application
Write-Host "`n[1/4] Vérification de l'état de santé de l'application..." -ForegroundColor Yellow
$health = Invoke-RestMethod -Uri "http://localhost/health" -Method Get
Write-Host "Statut global : " -NoNewline
Write-Host $health.status -ForegroundColor Green
Write-Host "Vérifications de santé internes :"
Write-Host " - API : " -NoNewline
Write-Host $health.checks.api -ForegroundColor Green
Write-Host " - Database : " -NoNewline
Write-Host $health.checks.database -ForegroundColor Green
Write-Host " - Redis : " -NoNewline
Write-Host $health.checks.redis -ForegroundColor Green

# 2. Soumission d'une tâche asynchrone
Write-Host "`n[2/4] Soumission d'une tâche asynchrone (Celery / Redis / PostgreSQL)..." -ForegroundColor Yellow
$body = @{
    name = "calcul_statistiques_mensuelles"
    payload = @{
        trimestre = "T2"
        annee = 2026
        generer_pdf = $true
    }
} | ConvertTo-Json

$task = Invoke-RestMethod -Uri "http://localhost/api/v1/tasks/" -Method Post -ContentType "application/json" -Body $body
Write-Host "Tâche créée avec succès !" -ForegroundColor Green
Write-Host " - ID Tâche : " -NoNewline
Write-Host $task.id -ForegroundColor Cyan
Write-Host " - Statut initial : " -NoNewline
Write-Host $task.status -ForegroundColor Yellow
Write-Host " - ID Celery : " -NoNewline
Write-Host $task.celery_task_id -ForegroundColor Cyan

# 3. Suivi de l'exécution de la tâche (polling)
Write-Host "`n[3/4] Suivi en temps réel de l'exécution de la tâche..." -ForegroundColor Yellow
$taskId = $task.id
$status = $task.status

while ($status -eq "PENDING" -or $status -eq "RUNNING") {
    Start-Sleep -Seconds 1
    $taskStatus = Invoke-RestMethod -Uri "http://localhost/api/v1/tasks/$taskId" -Method Get
    $status = $taskStatus.status
    Write-Host " - Statut actuel : " -NoNewline
    if ($status -eq "SUCCESS") {
        Write-Host $status -ForegroundColor Green
    } elseif ($status -eq "FAILURE") {
        Write-Host $status -ForegroundColor Red
    } else {
        Write-Host $status -ForegroundColor Yellow
    }
}

# Affichage des résultats
Write-Host "`nTâche terminée !" -ForegroundColor Green
Write-Host "Détails de la tâche :"
$taskStatus | Format-List -Property id, name, status, celery_task_id, result, error_message

# 4. Liste de toutes les tâches
Write-Host "`n[4/4] Récupération de la liste de toutes les tâches..." -ForegroundColor Yellow
$taskList = Invoke-RestMethod -Uri "http://localhost/api/v1/tasks/" -Method Get
Write-Host "Nombre total de tâches en DB : " -NoNewline
Write-Host $taskList.total -ForegroundColor Green
Write-Host "Liste des 3 dernières tâches :"
$taskList.items | Select-Object -First 3 | Format-Table -Property id, name, status

Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host "   SERVICES ACCESSIBLES                           " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " - API Swagger Docs : http://localhost/api/docs" -ForegroundColor White
Write-Host " - Grafana Dashboard : http://monitoring.localhost/grafana/" -ForegroundColor White
Write-Host "   (Identifiants: admin / grafana_devops_pwd_8293)" -ForegroundColor White
Write-Host " - Prometheus (interne) : http://localhost:9090 (uniquement en dev)" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Cyan
