@echo off
cd /d "%~dp0"
set "PYTHON_CMD=python"
set "GUI_CMD=pythonw"
where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py"
  set "GUI_CMD=pyw"
)

echo Verificando dependencias...
%PYTHON_CMD% -c "import requests, bs4, googlesearch, playwright, pypdf, docx" >nul 2>nul
if errorlevel 1 (
  echo Instalando dependencias necessarias...
  %PYTHON_CMD% -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 goto :erro
)

start "" /b %GUI_CMD% app.py
exit /b

:erro
echo.
echo Nao foi possivel instalar as dependencias. Verifique sua internet e tente novamente.
pause
