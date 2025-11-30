# Script para sincronizar el submódulo frontend con el backend
# Ejecutar este script después de que el frontend haga cambios

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Actualizando Frontend" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Actualizar el submódulo
Write-Host "Actualizando submódulo frontend..." -ForegroundColor Yellow
git submodule update --remote --merge

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error al actualizar el submódulo" -ForegroundColor Red
    exit 1
}

Write-Host "Submódulo actualizado!" -ForegroundColor Green
Write-Host ""

# Copiar archivos a apps/
Write-Host "Sincronizando archivos..." -ForegroundColor Yellow

Write-Host "  -> Copiando static..." -ForegroundColor Cyan
Remove-Item -Path "apps\static" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -Path "frontend\static" -Destination "apps\static" -Recurse -Force

Write-Host "  -> Copiando templates..." -ForegroundColor Cyan
Remove-Item -Path "apps\templates" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -Path "frontend\templates" -Destination "apps\templates" -Recurse -Force

Write-Host ""
Write-Host "Sincronización completada!" -ForegroundColor Green
Write-Host ""

# Verificar si hay cambios
$status = git status --porcelain
if ($status) {
    Write-Host "Cambios detectados:" -ForegroundColor Yellow
    git status --short
    Write-Host ""
    
    $commit = Read-Host "¿Hacer commit de los cambios del frontend? (s/n)"
    if ($commit -eq "s" -or $commit -eq "S") {
        git add apps/static apps/templates frontend .gitmodules
        
        # Obtener info del último commit del frontend
        Push-Location frontend
        $frontendCommit = git log -1 --pretty=format:"%s"
        Pop-Location
        
        git commit -m "Actualizar frontend: $frontendCommit"
        
        $push = Read-Host "¿Hacer push? (s/n)"
        if ($push -eq "s" -or $push -eq "S") {
            git push
            Write-Host "Cambios publicados!" -ForegroundColor Green
        }
    }
} else {
    Write-Host "No hay cambios nuevos del frontend" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Proceso completado" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
