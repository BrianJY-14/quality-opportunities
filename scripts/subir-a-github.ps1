<#
.SYNOPSIS
  Sube el repositorio a GitHub paso a paso, con comprobaciones de seguridad y commits por modulo.

.DESCRIPTION
  Ejecutar desde cualquier carpeta; el script se ubica solo en la raiz del repositorio.

  Pasos:
    1. Comprueba Git, la rama y el remoto.
    2. Bloquea la subida si hay secretos o bases de datos a punto de entrar al repositorio.
    3. (Opcional) Ejecuta pytest del backend y el build del frontend.
    4. Crea un commit por modulo (historial legible en lugar de un commit gigante).
    5. Trae los cambios del equipo (git pull) y se detiene si hay conflictos.
    6. Muestra lo que se va a subir y pide confirmacion antes del push.

.PARAMETER Prueba
  Modo ensayo: muestra lo que haria sin crear commits ni subir nada.

.PARAMETER SinPruebas
  Omite pytest y el build del frontend.

.PARAMETER Rama
  Rama destino. Por defecto: main.

.PARAMETER Remoto
  Nombre del remoto destino. Por defecto: origin. Si no hay acceso, el script ofrece iniciar sesion
  con otra cuenta o subir a un repositorio propio (remoto "personal").

.PARAMETER Lote
  Sube el historial por tramos de N commits, del mas antiguo al mas nuevo (0 = todo de una vez).
  El resultado final en GitHub es el mismo; sirve para ir comprobando cada tramo.

.PARAMETER Pausa
  Segundos de espera entre un commit y el siguiente (por defecto 30; 0 = sin espera).
  En el modo ensayo no se espera.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\subir-a-github.ps1 -Prueba
  powershell -ExecutionPolicy Bypass -File .\scripts\subir-a-github.ps1
#>
param(
  [switch]$Prueba,
  [switch]$SinPruebas,
  [string]$Rama = 'main',
  [string]$Remoto = 'origin',
  [int]$Lote = 0,
  [int]$Pausa = 30
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ------------------------------------------------------------------ configuracion
# Un commit por grupo, en este orden. Solo se incluyen rutas con cambios; un grupo vacio se salta.
$Grupos = @(
  @{ Mensaje = 'feat(ia): cliente LLM comun y AI Scoper con saneamiento previo'
     Rutas   = @('backend/app/servicios/llm.py', 'backend/app/servicios/preparador_llm.py', 'backend/app/servicios/preparador_reglas.py',
                 'backend/app/servicios/puertos.py', 'backend/app/servicios/registro.py', 'backend/app/servicios/retos.py',
                 'backend/app/core/config.py', 'backend/.env.example') },
  @{ Mensaje = 'feat(ia): juez IA, analisis estatico, tutor y defensa tecnica'
     Rutas   = @('backend/app/servicios/juez_ia.py', 'backend/app/servicios/analisis_estatico.py', 'backend/app/servicios/tutor_ia.py',
                 'backend/app/servicios/defensa_ia.py', 'backend/app/models') },
  @{ Mensaje = 'feat(cv): CV dinamico con grafo de aptitudes y ranking por XP'
     Rutas   = @('backend/app/servicios/cv.py', 'backend/app/dominio', 'backend/app/api', 'backend/app/schemas') },
  @{ Mensaje = 'fix(evaluacion): ninguna evaluacion queda en EN_EJECUCION'
     Rutas   = @('backend/app/servicios/evaluacion.py', 'backend/app/servicios/evaluador_e2b.py', 'backend/app/servicios/workspace.py',
                 'backend/app/servicios/certificacion.py', 'backend/app/main.py') },
  @{ Mensaje = 'feat(bd): migracion de las funciones de IA y datos de demostracion'
     Rutas   = @('backend/alembic', 'backend/seed.py', 'backend/seed_ia.py') },
  @{ Mensaje = 'test: pruebas de IA y de robustez de la evaluacion'
     Rutas   = @('backend/tests', 'backend/pyproject.toml') },
  @{ Mensaje = 'feat(frontend): sistema visual qo y pantallas de IA, CV, ranking y organizacion'
     Rutas   = @('Quality-Oportunities-app/src', 'Quality-Oportunities-app/index.html', 'Quality-Oportunities-app/package.json',
                 'Quality-Oportunities-app/package-lock.json', 'Quality-Oportunities-app/vite.config.js') },
  @{ Mensaje = 'docs: ADR-007 y ADR-008'
     Rutas   = @('docs') },
  @{ Mensaje = 'chore: script de subida a GitHub'
     Rutas   = @('scripts') },
  @{ Mensaje = 'chore: cambios restantes'
     Rutas   = @('.') }
)

# Nombres de archivo que nunca deben subirse, y patrones de secretos dentro de lo que se sube.
$ArchivosProhibidos = '(^|/)\.env$|\.env\.(local|respaldo)|\.db$|\.sqlite3?$|(^|/)\.venv/|node_modules/|(^|/)dist/|\.pem$|\.key$'
$PatronesSecretos   = @(
  'gsk_[A-Za-z0-9]{20,}',               # Groq
  'e2b_[A-Za-z0-9]{20,}',               # E2B
  'sk-[A-Za-z0-9_\-]{20,}',              # OpenAI y similares
  'AIza[0-9A-Za-z_\-]{30,}',            # Google
  'postgres(ql)?://[^\s:@]+:[^\s@]+@',  # cadena de conexion con contrasena
  'ghp_[A-Za-z0-9]{30,}'                # token de GitHub
)

# ------------------------------------------------------------------ utilidades
function Paso($n, $texto) { Write-Host "`n[$n] $texto" -ForegroundColor Cyan }
function Ok($texto)       { Write-Host "    OK  $texto" -ForegroundColor Green }
function Aviso($texto)    { Write-Host "    !!  $texto" -ForegroundColor Yellow }
function Alto($texto)     { Write-Host "`n    ALTO: $texto`n" -ForegroundColor Red; exit 1 }
function GitSeguro { & git.exe @args; if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') fallo (codigo $LASTEXITCODE)" } }
# Ejecuta git sin que su salida por stderr (progreso, avisos) se convierta en error de PowerShell 5.1.
function GitNativo {
  $anterior = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $salida = & git.exe @args 2>&1 | ForEach-Object { "$_" }
  $codigo = $LASTEXITCODE
  $ErrorActionPreference = $anterior
  return [pscustomobject]@{ Codigo = $codigo; Salida = @($salida) }
}
function Confirmar($pregunta) {
  $r = Read-Host "    $pregunta [s/N]"
  return $r -match '^(s|si|y|yes)$'
}

# ------------------------------------------------------------------ 1. entorno
Paso 1 'Comprobando Git, repositorio, rama y remoto'
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { Alto 'Git no esta instalado o no esta en el PATH.' }
$ubicacion = GitNativo -C $PSScriptRoot rev-parse --show-toplevel
$raiz = $ubicacion.Salida | Select-Object -First 1
if ($ubicacion.Codigo -ne 0 -or -not $raiz) { Alto 'El script no esta dentro de un repositorio Git.' }
Set-Location $raiz
Ok "Repositorio: $raiz"

$lock = Join-Path $raiz '.git/index.lock'
if (Test-Path $lock) {
  Aviso 'Existe .git/index.lock (queda cuando un git se interrumpe).'
  if (Confirmar 'Borrarlo? Solo si no hay otro git abierto.') { Remove-Item $lock -Force; Ok 'index.lock borrado' } else { Alto 'Cerrar otros procesos de git y volver a ejecutar.' }
}

$ramaActual = (& git.exe branch --show-current).Trim()
if ($ramaActual -ne $Rama) {
  Aviso "La rama actual es '$ramaActual', no '$Rama'."
  if (-not (Confirmar "Continuar subiendo '$ramaActual'?")) { Alto "Cambiar de rama con: git switch $Rama" }
  $Rama = $ramaActual
}
Ok "Rama: $Rama"

$urlRemoto = (GitNativo remote get-url $Remoto).Salida | Select-Object -First 1
if (-not $urlRemoto -or $urlRemoto -match '^(error|fatal)') { Alto "No hay remoto '$Remoto'. Agregarlo con: git remote add $Remoto https://github.com/USUARIO/REPO.git" }
Ok "Remoto: $Remoto -> $urlRemoto"

# Acceso al remoto ANTES de probar y crear commits: si no hay permiso, no tiene sentido seguir.
$remotoVacio = $false
while ($true) {
  $acceso = GitNativo ls-remote --heads $Remoto
  if ($acceso.Codigo -eq 0) {
    $remotoVacio = -not ($acceso.Salida | Where-Object { $_ -match "refs/heads/$Rama$" })
    if ($remotoVacio) { Ok "Acceso correcto; '$Rama' aun no existe en el remoto (repositorio nuevo)." } else { Ok 'Acceso de lectura al remoto correcto' }
    break
  }
  Aviso ("GitHub respondio: " + (($acceso.Salida | Where-Object { $_ -match 'remote:|fatal:' }) -join ' '))
  Write-Host @"

    'Repository not found' con un repositorio existente significa que la cuenta con la que Git
    inicia sesion no tiene acceso: el repositorio es privado y esa cuenta no es colaboradora, o
    Windows tiene guardada otra cuenta de GitHub.

      [1] Borrar la sesion guardada de GitHub y volver a iniciar sesion (se abre el navegador)
      [2] Subir a un repositorio PROPIO (crearlo vacio antes en https://github.com/new)
      [3] Salir
"@
  $op = Read-Host '    Opcion'
  if ($op -eq '1') {
    "protocol=https`nhost=github.com`n" | & git.exe credential reject
    Ok 'Sesion de GitHub olvidada. Al reintentar, iniciar sesion con la cuenta que tiene acceso.'
  } elseif ($op -eq '2') {
    $url = Read-Host '    URL del repositorio propio (ej. https://github.com/BrianJY-14/quality-opportunities.git)'
    if ($url -notmatch '^https://github\.com/[^/]+/[^/]+?(\.git)?$') { Aviso 'La URL no tiene la forma https://github.com/USUARIO/REPO.git'; continue }
    $Remoto = 'personal'
    if ((GitNativo remote get-url personal).Codigo -eq 0) { GitSeguro remote set-url personal $url } else { GitSeguro remote add personal $url }
    $urlRemoto = $url
    Ok "Remoto 'personal' -> $url (origin sigue apuntando al repositorio del equipo)"
  } else {
    Alto 'Sin acceso al remoto. Pedir acceso de escritura al dueno del repositorio o usar la opcion 2.'
  }
}

$usuario = (& git.exe config user.name); $correo = (& git.exe config user.email)
if (-not $usuario -or -not $correo) {
  Aviso 'Git no tiene nombre o correo configurado; los commits quedarian sin autor claro.'
  $usuario = Read-Host '    Nombre para los commits'
  $correo  = Read-Host '    Correo (el mismo de GitHub)'
  if (-not $Prueba) { GitSeguro config user.name $usuario; GitSeguro config user.email $correo }
}
Ok "Autor: $usuario <$correo>"

# ------------------------------------------------------------------ 2. seguridad
Paso 2 'Buscando secretos y archivos que no deben subirse'
foreach ($archivoEnv in @('backend/.env', 'Quality-Oportunities-app/.env')) {
  if (Test-Path $archivoEnv) {
    & git.exe check-ignore -q $archivoEnv
    if ($LASTEXITCODE -ne 0) { Alto "$archivoEnv existe y NO esta en .gitignore. Agregar '.env' a .gitignore antes de seguir." }
  }
}
Ok '.env ignorado por Git'

$pendientes = @(& git.exe status --porcelain --untracked-files=all | ForEach-Object { $_.Substring(3).Trim('"') -replace '^.* -> ', '' })
if (-not $pendientes) { Aviso 'No hay cambios locales para confirmar.' }
$malos = $pendientes | Where-Object { $_ -replace '\\', '/' -match $ArchivosProhibidos }
if ($malos) { Alto "Estos archivos no deben subirse:`n      $($malos -join "`n      ")`n    Agregarlos a .gitignore o moverlos fuera del repositorio." }
Ok "$($pendientes.Count) archivo(s) con cambios, ninguno prohibido"

$hallazgos = @()
foreach ($f in $pendientes) {
  if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { continue }
  if ((Get-Item -LiteralPath $f -Force).Length -gt 2MB) { continue }
  $texto = Get-Content -LiteralPath $f -Raw -Force -ErrorAction SilentlyContinue
  if (-not $texto) { continue }
  foreach ($p in $PatronesSecretos) { if ($texto -match $p) { $hallazgos += "$f  (patron $p)" } }
}
if ($hallazgos) { Alto "Posibles secretos en archivos a subir:`n      $($hallazgos -join "`n      ")`n    Quitar el valor del archivo y dejarlo solo en .env." }
Ok 'Sin claves ni contrasenas en los archivos modificados'

# ------------------------------------------------------------------ 3. pruebas
Paso 3 'Pruebas automaticas'
if ($SinPruebas) {
  Aviso 'Omitidas por -SinPruebas.'
} else {
  $py = @('backend/.venv/Scripts/python.exe', '.venv/Scripts/python.exe') | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
  if ($py) {
    if (Test-Path $py) { $py = (Resolve-Path $py).Path }
    Push-Location backend
    $ErrorActionPreference = 'Continue'
    & $py -m pytest -q 2>&1 | Select-Object -Last 3 | ForEach-Object { Write-Host "    $_" }
    $okPy = $LASTEXITCODE -eq 0
    $ErrorActionPreference = 'Stop'
    Pop-Location
    if ($okPy) { Ok 'pytest en verde' } elseif (-not (Confirmar 'pytest fallo. Subir de todos modos?')) { Alto 'Corregir las pruebas y volver a ejecutar.' }
  } else { Aviso 'No se encontro Python; se omite pytest.' }

  if ((Get-Command npm -ErrorAction SilentlyContinue) -and -not (Test-Path 'Quality-Oportunities-app/node_modules')) {
    if (Confirmar 'El frontend no tiene node_modules. Ejecutar npm install ahora (1-2 min)?') {
      Push-Location Quality-Oportunities-app
      $ErrorActionPreference = 'Continue'; & npm install --no-audit --no-fund 2>&1 | Select-Object -Last 2 | ForEach-Object { Write-Host "    $_" }; $ErrorActionPreference = 'Stop'
      Pop-Location
    }
  }
  if ((Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path 'Quality-Oportunities-app/node_modules')) {
    Push-Location Quality-Oportunities-app
    $ErrorActionPreference = 'Continue'
    & npm run build --silent 2>&1 | Select-Object -Last 2 | ForEach-Object { Write-Host "    $_" }
    $okNpm = $LASTEXITCODE -eq 0
    $ErrorActionPreference = 'Stop'
    Pop-Location
    if ($okNpm) { Ok 'build del frontend correcto' } elseif (-not (Confirmar 'El build fallo. Subir de todos modos?')) { Alto 'Corregir el build y volver a ejecutar.' }
  } else { Aviso 'Sin node_modules en el frontend (npm install); se omite el build.' }
}

# ------------------------------------------------------------------ 4. commits por modulo
Paso 4 'Commits por modulo'
$creados = 0
$asignados = @{}
foreach ($g in $Grupos) {
  $rutas = @($g.Rutas | Where-Object { Test-Path $_ })
  if (-not $rutas) { continue }
  # En el ensayo nada se confirma, asi que se descartan a mano los archivos ya asignados a un grupo anterior.
  $cambios = @((GitNativo status --porcelain --untracked-files=all -- @rutas).Salida | Where-Object { $_ -and -not $asignados.ContainsKey($_) })
  if (-not $cambios) { continue }
  $cambios | ForEach-Object { $asignados[$_] = $true }
  Write-Host "    - $($g.Mensaje)  ($($cambios.Count) archivo(s))"
  if ($Prueba) { $cambios | Select-Object -First 6 | ForEach-Object { Write-Host "        $_" -ForegroundColor DarkGray }; continue }
  GitSeguro add -- @rutas
  $enIndice = @((GitNativo diff --cached --name-only).Salida | Where-Object { $_ })
  if ($enIndice) {
    if ($creados -gt 0 -and $Pausa -gt 0) {
      for ($seg = $Pausa; $seg -gt 0; $seg--) {
        Write-Progress -Activity 'Pausa entre commits' -Status "Siguiente commit en $seg s" -PercentComplete (100 * ($Pausa - $seg) / $Pausa)
        Start-Sleep -Seconds 1
      }
      Write-Progress -Activity 'Pausa entre commits' -Completed
    }
    GitSeguro commit -q -m $g.Mensaje
    $creados++
    Write-Host "      commit $creados creado a las $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor DarkGray
  }
}
if ($Prueba) { Ok "Modo ensayo: no se creo ningun commit. De verdad, con pausas de $Pausa s entre commits." } else { Ok "$creados commit(s) creados" }

# ------------------------------------------------------------------ 5. traer cambios del equipo
Paso 5 "Trayendo cambios del remoto ($Remoto/$Rama)"
if ($remotoVacio) {
  Ok 'Repositorio destino vacio: no hay nada que traer.'
} elseif ($Prueba) {
  $null = GitNativo fetch $Remoto $Rama
  $atras = (GitNativo rev-list --count "HEAD..$Remoto/$Rama").Salida | Select-Object -First 1
  Ok "El remoto tiene $atras commit(s) que no estan en local; se fusionaran antes de subir."
} else {
  $pull = GitNativo pull --no-rebase --no-edit $Remoto $Rama
  $pull.Salida | Select-Object -Last 4 | ForEach-Object { Write-Host "    $_" }
  if ($pull.Codigo -ne 0) {
    $conflictos = @((GitNativo diff --name-only --diff-filter=U).Salida | Where-Object { $_ })
    if ($conflictos) {
      Alto ("Conflictos en:`n      $($conflictos -join "`n      ")`n" +
            "    Abrir cada archivo, elegir el contenido correcto entre <<<<<<< y >>>>>>>, y luego:`n" +
            "      git add <archivo>`n      git commit --no-edit`n    y volver a ejecutar este script.")
    }
    Alto 'git pull fallo. Revisar la conexion o las credenciales de GitHub.'
  }
  Ok 'Local al dia con el remoto'
}

# ------------------------------------------------------------------ 6. subir
Paso 6 'Resumen antes de subir'
$rango = if ($remotoVacio) { 'HEAD' } else { "$Remoto/$Rama..HEAD" }
$porSubir = (GitNativo rev-list --count $rango).Salida | Select-Object -First 1
(GitNativo log --oneline -n 15 $rango).Salida | ForEach-Object { Write-Host "    $_" }
if ($Prueba) { Ok "Modo ensayo terminado ($porSubir commit(s) locales por subir antes de los nuevos). Ejecutar sin -Prueba para subir."; exit 0 }
if ($porSubir -eq '0') { Ok 'No hay nada nuevo que subir.'; exit 0 }
if (-not (Confirmar "Subir $porSubir commit(s) a $Remoto/$Rama ($urlRemoto)?")) { Alto 'Cancelado. Los commits quedan en local.' }
function Empujar($referencia) {
  $push = GitNativo push -u $Remoto "$($referencia):refs/heads/$Rama"
  $push.Salida | Select-Object -Last 3 | ForEach-Object { Write-Host "    $_" }
  if ($push.Codigo -ne 0) {
    if ($push.Salida -match '403|denied|Permission') { Alto 'La cuenta puede leer pero no escribir en ese repositorio. Pedir acceso de escritura o usar un repositorio propio (opcion 2).' }
    Alto 'git push fallo; ver el mensaje de arriba.'
  }
}
if ($Lote -gt 0) {
  # Tramos sobre la linea principal (first-parent): subir un commit sube tambien sus ancestros.
  $pendientes = @((GitNativo rev-list --reverse --first-parent $rango).Salida | Where-Object { $_ })
  $tramos = [math]::Ceiling($pendientes.Count / $Lote)
  for ($t = 1; $t -le $tramos; $t++) {
    $indice = [math]::Min($t * $Lote, $pendientes.Count) - 1
    $sha = $pendientes[$indice]
    $titulo = (GitNativo log -1 --format=%s $sha).Salida | Select-Object -First 1
    Write-Host "    Tramo $t/$tramos -> $($sha.Substring(0,7)) $titulo" -ForegroundColor Cyan
    Empujar $sha
  }
} else {
  Empujar 'HEAD'
}
$null = GitNativo branch --set-upstream-to "$Remoto/$Rama"
Ok "Subido a $urlRemoto ($Rama)"
if ($Remoto -eq 'origin') {
  Write-Host "`n    Siguiente: Render -> Manual Deploy -> Deploy latest commit. El frontend se publica solo con el push.`n" -ForegroundColor Cyan
} else {
  Write-Host @"

    Siguiente, en el repositorio nuevo:
      - Settings -> Pages -> Source: GitHub Actions (publica el frontend en cada push a $Rama).
      - Render -> el servicio -> Settings -> Repository: apuntarlo a este repositorio.
      - Render -> Environment -> CORS_ORIGINS: agregar la URL de GitHub Pages del repositorio nuevo.
"@ -ForegroundColor Cyan
}
