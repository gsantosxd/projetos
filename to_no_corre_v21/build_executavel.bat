@echo off
cd /d "%~dp0"
set "PYTHON_CMD=python"
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=py"

%PYTHON_CMD% -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 goto :erro

%PYTHON_CMD% -m PyInstaller --noconfirm --clean ToNoCorre.spec
if errorlevel 1 goto :erro

copy /y README_INICIO.txt dist\ToNoCorre\README_INICIO.txt >nul
copy /y PRIVACIDADE.md dist\ToNoCorre\PRIVACIDADE.md >nul
echo.
echo Executavel criado em dist\ToNoCorre\ToNoCorre.exe
pause
exit /b 0

:erro
echo.
echo Nao foi possivel gerar o executavel.
pause
exit /b 1
