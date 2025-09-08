@echo off
setlocal enabledelayedexpansion

REM s3dgraphy Publication Script (Windows wrapper)
REM ===============================================

cd /d "%~dp0"

if "%1"=="" goto :show_help
if "%1"=="help" goto :show_help
if "%1"=="-h" goto :show_help
if "%1"=="--help" goto :show_help

REM ============================================
REM FUNCTIONS
REM ============================================

:show_help
echo.
echo s3dgraphy Publication Tool
echo ==========================
echo.
echo Usage: publish.bat [command] [options]
echo.
echo COMMANDS:
echo   publish              Publish to PyPI (production)
echo   test                 Publish to TestPyPI
echo   dry-run              Show what would be done
echo   check                Check current status
echo   help                 Show this help
echo.
echo VERSION MANAGEMENT:
echo   patch                Auto-increment patch version and publish
echo   minor                Auto-increment minor version and publish
echo   major                Auto-increment major version and publish
echo.
echo EXAMPLES:
echo   publish.bat publish         # Publish current version to PyPI
echo   publish.bat test            # Test publish to TestPyPI
echo   publish.bat patch           # Increment patch and publish
echo   publish.bat dry-run         # Show what would happen
echo   publish.bat check           # Check status
echo.
echo ADVANCED:
echo   publish.bat publish --force # Skip safety checks
echo   publish.bat test patch      # Test with patch increment
echo.
goto :end

:check_status
echo.
echo s3dgraphy Publication Status
echo ============================
echo.

REM Check if we're in the right directory
if not exist "pyproject.toml" (
    if not exist "setup.py" (
        echo ❌ Not in s3dgraphy root directory
        echo    Missing pyproject.toml or setup.py
        exit /b 1
    )
)

REM Get current version (simplified for batch)
echo 📋 Checking current version...

REM Check git status
git status --porcelain >nul 2>&1
if !errorlevel! equ 0 (
    for /f %%i in ('git status --porcelain ^| find /c /v ""') do set CHANGES=%%i
    if !CHANGES! gtr 0 (
        echo ⚠️  Uncommitted changes present
        git status --porcelain
    ) else (
        echo ✅ Git working directory clean
    )
) else (
    echo ⚠️  Could not check git status
)

echo.
echo 🔧 Tool availability:

REM Check Python
python --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo    ✅ Python: %%v
) else (
    echo    ❌ Python not found
)

REM Check build module
python -m pip show build >nul 2>&1
if !errorlevel! equ 0 (
    echo    ✅ build module available
) else (
    echo    ⚠️  build module missing (install: pip install build)
)

REM Check twine
python -m pip show twine >nul 2>&1
if !errorlevel! equ 0 (
    echo    ✅ twine available
) else (
    echo    ⚠️  twine missing (install: pip install twine)
)

REM Check git
git --version >nul 2>&1
if !errorlevel! equ 0 (
    echo    ✅ git available
) else (
    echo    ❌ git not found
)

echo.
goto :end

REM ============================================
REM MAIN COMMAND PROCESSING
REM ============================================

if "%1"=="check" goto :check_status
if "%1"=="status" goto :check_status

if "%1"=="publish" (
    echo.
    echo 🚀 Publishing to PyPI...
    shift
    python publish.py %1 %2 %3 %4 %5
    goto :end
)

if "%1"=="test" (
    echo.
    echo 🧪 Publishing to TestPyPI...
    shift
    python publish.py --test %1 %2 %3 %4 %5
    goto :end
)

if "%1"=="dry-run" (
    echo.
    echo 🧪 Dry run mode...
    shift
    python publish.py --dry-run %1 %2 %3 %4 %5
    goto :end
)

if "%1"=="dry" (
    echo.
    echo 🧪 Dry run mode...
    shift
    python publish.py --dry-run %1 %2 %3 %4 %5
    goto :end
)

if "%1"=="patch" (
    echo.
    echo 📈 Incrementing patch version and publishing...
    shift
    python publish.py --version patch %1 %2 %3 %4 %5
    goto :end
)

if "%1"=="minor" (
    echo.
    echo 📈 Incrementing minor version and publishing...
    shift
    python publish.py --version minor %1 %2 %3 %4 %5
    goto :end
)

if "%1"=="major" (
    echo.
    echo 📈 Incrementing major version and publishing...
    shift
    python publish.py --version major %1 %2 %3 %4 %5
    goto :end
)

echo ❌ Unknown command: %1
echo.
goto :show_help

:end
echo.
