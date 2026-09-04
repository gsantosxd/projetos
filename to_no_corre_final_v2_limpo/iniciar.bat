@echo off
cd /d "%~dp0"
set "PYTHON_CMD=python"
where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py"
)

echo Verificando dependencias...
%PYTHON_CMD% -c "import requests, bs4, googlesearch, playwright, pypdf, docx" >nul 2>nul
if errorlevel 1 (
  echo Instalando dependencias necessarias...
  %PYTHON_CMD% -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 goto :erro
)

%PYTHON_CMD% app.py
if errorlevel 1 pause
exit /b

:erro
echo.
echo Nao foi possivel instalar as dependencias. Verifique sua internet e tente novamente.
pause
