@echo off
cd /d "%~dp0"
echo Preparando automacao com Brave...
where py >nul 2>nul
if %errorlevel%==0 (
  py -m pip install --disable-pip-version-check -q playwright requests beautifulsoup4 googlesearch-python
) else (
  python -m pip install --disable-pip-version-check -q playwright requests beautifulsoup4 googlesearch-python
)
echo.
echo Pronto. O programa tentara localizar o Brave automaticamente.
echo Nao e necessario instalar o Chromium do Playwright.
pause
