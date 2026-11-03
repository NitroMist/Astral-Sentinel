@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Astral Sentinel - Local Observatory

rem Prefer a working Python executable rather than the Windows py launcher.
rem The py launcher can contain stale paths from an uninstalled Python version.
set "PYTHON_CMD="
python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"
if defined PYTHON_CMD goto :python_found

python3 -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python3"
if defined PYTHON_CMD goto :python_found

rem Probe each installed version directly; don't trust 'py -3' to select a valid one.
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PYTHON_CMD (
        py -%%V -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=py -%%V"
    )
)
if defined PYTHON_CMD goto :python_found

rem On some machines, 'py -3' works even if the version-specific lookup does not.
py -3 -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"
if defined PYTHON_CMD goto :python_found

echo.
echo [ERROR] No working supported Python 3.10-3.13 installation was found.
echo Check which version works in a Command Prompt:
echo     python --version
echo     py -0p
echo.
echo If 'py -0p' points to an old folder, use the working 'python' installation
echo or repair the Python Launcher / Python installation.
goto :error

:python_found
echo Using Python command: %PYTHON_CMD%
%PYTHON_CMD% -c "import sys; print('Python version:',sys.version.split()[0]); print('Location:',sys.executable)"
if errorlevel 1 goto :error

rem The pysweph 3.12/3.13 Windows binary wheels are 64-bit only.
%PYTHON_CMD% -c "import sys,struct; sys.exit(0 if sys.version_info[:2] < (3,12) or struct.calcsize('P')*8 == 64 else 1)" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.12/3.13 needs a 64-bit installation for the prebuilt ephemeris.
    echo Install 64-bit Python 3.12 or 3.13, or use Python 3.11.
    goto :error
)

rem The app creates and owns its own .venv; safely replace only if incomplete.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
    if errorlevel 1 goto :remove_broken_venv
) else (
    if exist ".venv" goto :remove_broken_venv
)
goto :ensure_venv

:remove_broken_venv
echo Repairing an incomplete Astral Sentinel Python environment...
rmdir /s /q ".venv"
if exist ".venv" goto :error

:ensure_venv
if not exist ".venv\Scripts\python.exe" (
    echo Creating local Python environment...
    %PYTHON_CMD% -m venv ".venv"
    if errorlevel 1 goto :error
)
if not exist ".venv\Scripts\python.exe" goto :error

".venv\Scripts\python.exe" -c "import swisseph, tzdata, sys, importlib.metadata as md; md.version('pysweph' if sys.version_info >= (3,12) else 'pyswisseph')" >nul 2>nul
if errorlevel 1 (
    echo Installing one-time dependencies; internet required for initial setup.
    rem Require prebuilt wheels: never attempt a Visual Studio C++ source compilation.
    ".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] No compatible prebuilt dependency wheel could be installed.
        echo For Python 3.12/3.13, use a 64-bit Python installation.
        echo Confirm that you have an internet connection on first setup.
        goto :error
    )
)

echo.
echo Launching Astral Sentinel. Open http://127.0.0.1:8765 in Firefox.
echo Keep this window open while using the app.
".venv\Scripts\python.exe" server.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Setup could not finish. Copy the messages above if you need help.
pause
exit /b 1
