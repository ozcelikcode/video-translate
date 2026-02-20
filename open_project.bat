@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "HOST=%~1"
if "%HOST%"=="" set "HOST=127.0.0.1"

set "PORT=%~2"
if "%PORT%"=="" set "PORT=8765"

set "SKIP_INSTALL=0"
set "NO_UI=0"
if /I "%~3"=="--skip-install" set "SKIP_INSTALL=1"
if /I "%~3"=="--no-ui" set "NO_UI=1"
if /I "%~4"=="--skip-install" set "SKIP_INSTALL=1"
if /I "%~4"=="--no-ui" set "NO_UI=1"

echo.
echo [video-translate] Startup script
echo [video-translate] Workspace: %CD%
echo.

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python bulunamadi. Python 3.12+ kur ve tekrar dene.
    goto :fail
  )
  set "PYTHON_CMD=python"
)

%PYTHON_CMD% -V >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python calistirilamadi.
  goto :fail
)

if not exist ".venv\Scripts\python.exe" (
  echo [video-translate] .venv olusturuluyor...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Sanal ortam olusturulamadi.
    goto :fail
  )
)

set "VENV_PY=.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] .venv python bulunamadi: %VENV_PY%
  goto :fail
)

set "PYTHONPATH=%CD%\src"

if "%SKIP_INSTALL%"=="0" goto :install
echo [video-translate] Kurulum adimi atlandi (--skip-install).
goto :after_install

:install
echo [video-translate] Bagimliliklar kuruluyor/guncelleniyor...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] pip guncellenemedi.
  goto :fail
)
"%VENV_PY%" -m pip install -e ".[dev,m2,tts_piper]"
if errorlevel 1 (
  echo [ERROR] Proje bagimliliklari kurulurken hata olustu.
  goto :fail
)

:after_install

if not exist ".venv\Scripts\piper.exe" (
  echo [video-translate] Piper runtime kuruluyor...
  "%VENV_PY%" -m pip install "piper-tts>=1.4.1" "pathvalidate>=3.2.3"
  if errorlevel 1 (
    echo [ERROR] Piper runtime kurulumu basarisiz.
    goto :fail
  )
)

echo [video-translate] Piper model dosyalari kontrol ediliyor...
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $modelPath='models/piper/tr_TR-dfki-medium.onnx'; $configPath='models/piper/tr_TR-dfki-medium.onnx.json'; $modelUrl='https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx?download=true'; $configUrl='https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx.json?download=true'; New-Item -ItemType Directory -Force -Path (Split-Path -Parent $modelPath) | Out-Null; if (!(Test-Path $modelPath)) { Invoke-WebRequest -Uri $modelUrl -OutFile $modelPath }; if (!(Test-Path $configPath)) { Invoke-WebRequest -Uri $configUrl -OutFile $configPath }"
if errorlevel 1 (
  echo [ERROR] Piper model dosyalari hazirlanamadi.
  goto :fail
)

echo [video-translate] Ortam kontrolu calisiyor...
set "DOCTOR_CONFIG="
if exist "configs\profiles\gtx1650_piper.toml" set "DOCTOR_CONFIG=configs\profiles\gtx1650_piper.toml"
if "%DOCTOR_CONFIG%"=="" if exist "configs\profiles\gtx1650_i5_12500h.toml" set "DOCTOR_CONFIG=configs\profiles\gtx1650_i5_12500h.toml"
if "%DOCTOR_CONFIG%"=="" (
  "%VENV_PY%" -m video_translate.cli doctor
) else (
  "%VENV_PY%" -m video_translate.cli doctor --config "%DOCTOR_CONFIG%"
)
if errorlevel 1 (
  echo [ERROR] Doctor kontrolu basarisiz. Ciktiyi inceleyip tekrar dene.
  goto :fail
)

if "%NO_UI%"=="1" (
  echo [video-translate] Baslangic kontrolleri tamamlandi --no-ui
  goto :ok
)

powershell -NoProfile -Command "$ids=@(); try { $ids=@(Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique) } catch {}; foreach($id in $ids){ if($id -and $id -ne 0){ Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } }" >nul 2>nul

echo.
echo [video-translate] UI uygulamasi baslatiliyor: http://%HOST%:%PORT%
echo [video-translate] Cikmak icin CTRL+C
echo.
"%VENV_PY%" -m video_translate.cli ui --host "%HOST%" --port "%PORT%"
if errorlevel 1 (
  echo [ERROR] UI uygulamasi beklenmeyen sekilde sonlandi.
  goto :fail
)

goto :ok

:fail
echo.
pause
exit /b 1

:ok
exit /b 0
