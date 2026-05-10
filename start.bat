@echo off
setlocal enabledelayedexpansion

:: Cambiar al directorio donde esta el script
cd /d "%~dp0"

:: Configurar codificacion UTF-8
chcp 65001 >nul 2>&1

echo.
echo ========================================================
echo    Video QA Tester - Setup y Arranque (Web)
echo ========================================================
echo.

:: -- Verificar Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo.
    echo Presiona una tecla para salir...
    pause >nul
    exit /b 1
)
echo [OK] Python encontrado.

:: -- Crear .env si no existe
if not exist ".env" (
    echo [INFO] Creando archivo .env a partir de .env.example...
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [OK] Archivo .env creado.
    ) else (
        echo [WARN] No se encontro .env.example. Omitiendo creacion de .env.
    )
) else (
    echo [OK] Archivo .env detectado.
)

:: -- Verificar/Crear entorno virtual
if not exist ".venv" (
    echo [INFO] Creando entorno virtual .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        echo.
        echo Presiona una tecla para salir...
        pause >nul
        exit /b 1
    )
    echo [OK] Entorno virtual creado.
) else (
    echo [OK] Entorno virtual disponible.
)

:: -- Activar entorno virtual
echo [INFO] Activando entorno virtual...
call .venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Fallo al activar el entorno virtual.
    echo.
    echo Presiona una tecla para salir...
    pause >nul
    exit /b 1
)

:: -- Instalar dependencias core
echo [INFO] Instalando dependencias del core...
python -m pip install -q -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Fallo al instalar las dependencias de requirements.txt.
    echo.
    echo Presiona una tecla para salir...
    pause >nul
    exit /b 1
)
echo [OK] Dependencias core listas.

:: -- Instalar dependencias web
echo [INFO] Instalando dependencias del panel web...
python -m pip install -q -r web\requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Fallo al instalar las dependencias de web\requirements.txt.
    echo.
    echo Presiona una tecla para salir...
    pause >nul
    exit /b 1
)
echo [OK] Dependencias web listas.

:: -- Instalar Playwright Chromium
echo [INFO] Verificando navegadores de Playwright...
playwright install chromium
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Fallo al instalar los navegadores de Playwright.
    echo.
    echo Presiona una tecla para salir...
    pause >nul
    exit /b 1
)
echo [OK] Navegadores Playwright listos.

:: -- Ejecutar el script
echo.
echo ----------------------------------------------------
echo [INFO] Iniciando el servidor web FastAPI...
echo [OK] El servidor estara disponible en: http://localhost:8081
echo ----------------------------------------------------
echo.

python web\main.py

echo.
echo ----------------------------------------------------
echo.

if %ERRORLEVEL% equ 0 (
    echo [OK] Servidor detenido exitosamente.
) else (
    echo [ERROR] El servidor finalizo con errores.
)

echo.
echo Presiona una tecla para salir...
pause >nul
endlocal
