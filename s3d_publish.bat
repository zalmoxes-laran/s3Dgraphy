@echo off
setlocal enabledelayedexpansion

REM s3dgraphy Publication Script (Windows wrapper)
REM ===============================================

cd /d "%~dp0"

REM If no arguments, show interactive mode
if "%1"=="" goto :interactive_mode

REM Check for specific commands
if "%1"=="help" goto :show_help
if "%1"=="-h" goto :show_help
if "%1"=="--help" goto :show_help
if "%1"=="check" goto :check_status
if "%1"=="setup" goto :setup_environment
if "%1"=="version" goto :show_version_info
if "%1"=="--version" goto :show_version_info
if "%1"=="clean" goto :clean_build
if "%1"=="interactive" goto :interactive_mode
if "%1"=="-i" goto :interactive_mode
if "%1"=="publish" goto :publish_cmd
if "%1"=="test" goto :test_cmd
if "%1"=="dry-run" goto :dry_run_cmd
if "%1"=="patch" goto :patch_cmd
if "%1"=="minor" goto :minor_cmd
if "%1"=="major" goto :major_cmd

REM Unknown command
echo ❌ Unknown command: %1
echo.
goto :show_help

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
echo   setup                Setup virtual environment for publishing
echo   help                 Show this help
echo.
echo VERSION MANAGEMENT:
echo   patch                Auto-increment patch version and publish
echo   minor                Auto-increment minor version and publish
echo   major                Auto-increment major version and publish
echo.
echo SETUP OPTIONS:
echo   setup                Create publishing virtual environment
echo   setup --force        Recreate existing virtual environment
echo.
echo EXAMPLES:
echo   publish.bat setup               # Setup publishing environment
echo   publish.bat publish             # Publish current version to PyPI
echo   publish.bat test                # Test publish to TestPyPI
echo   publish.bat patch               # Increment patch and publish
echo   publish.bat dry-run             # Show what would happen
echo   publish.bat check               # Check status
echo.
echo ADVANCED:
echo   publish.bat publish --force     # Skip safety checks
echo   publish.bat test patch          # Test with patch increment
echo   publish.bat setup --force       # Recreate virtual environment
echo   publish.bat interactive         # Interactive mode
echo   publish.bat clean               # Clean build artifacts
echo   publish.bat version             # Show version info
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

REM Check for virtual environment
if exist "publish_env" (
    echo 📦 Virtual environment: Available
    echo    Location: .\publish_env
    
    if exist "publish_env\Scripts\python.exe" (
        echo    Status: Ready for publishing
        
        REM Check individual packages
        echo    Dependencies:
        for %%p in (twine requests build) do (
            publish_env\Scripts\python.exe -m pip show %%p >nul 2>&1
            if !errorlevel! equ 0 (
                echo      ✅ %%p
            ) else (
                echo      ❌ %%p
            )
        )
    ) else (
        echo    Status: Corrupted (run setup --force)
    )
) else (
    echo 📦 Virtual environment: Not found
    echo    Run: publish.bat setup
)

REM Get current version (simplified for batch)
echo 📋 Checking current version...
for /f "tokens=3" %%v in ('python s3d_publish.py --dry-run 2^>nul ^| findstr "Current version:"') do (
    echo 📋 Current version: %%v
    set CURRENT_VERSION=%%v
)

REM Check git status
git status --porcelain >nul 2>&1
if !errorlevel! equ 0 (
    for /f %%i in ('git status --porcelain ^| find /c /v ""') do set CHANGES=%%i
    if !CHANGES! gtr 0 (
        echo ⚠️  Git status: Uncommitted changes
        git status --porcelain
    ) else (
        echo ✅ Git status: Clean
    )
    
    REM Check for git tags
    git tag --list | findstr "v!CURRENT_VERSION!" >nul 2>&1
    if !errorlevel! equ 0 (
        echo 🏷️  Git tag: v!CURRENT_VERSION! exists
    ) else (
        echo 🏷️  Git tag: v!CURRENT_VERSION! not found
    )
) else (
    echo ⚠️  Could not check git status
)

echo.
echo 🔧 System tools:

REM Check Python
python --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo    ✅ Python: %%v
) else (
    echo    ❌ Python not found
)

REM Check git
git --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=3" %%v in ('git --version 2^>^&1') do echo    ✅ Git: %%v
) else (
    echo    ❌ Git not found
)

REM Check system packages (if no venv)
if not exist "publish_env" (
    echo.
    echo 🌐 System packages:
    for %%p in (build twine requests) do (
        python -m pip show %%p >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "tokens=2" %%v in ('python -m pip show %%p ^| findstr "Version:"') do (
                echo    ✅ %%p: %%v
            )
        ) else (
            echo    ❌ %%p: missing (install: pip install %%p)
        )
    )
)

REM Check PyPI connectivity
echo.
echo 🌍 PyPI connectivity:
curl -s --connect-timeout 5 https://pypi.org >nul 2>&1
if !errorlevel! equ 0 (
    echo    ✅ PyPI: Reachable
) else (
    echo    ⚠️  PyPI: Connection issue
)

curl -s --connect-timeout 5 https://test.pypi.org >nul 2>&1
if !errorlevel! equ 0 (
    echo    ✅ TestPyPI: Reachable
) else (
    echo    ⚠️  TestPyPI: Connection issue
)

goto :end

:setup_environment
echo.
echo Setting up publishing environment...

set FORCE_FLAG=
REM Check for --force in any position
for %%a in (%*) do (
    if "%%a"=="--force" set FORCE_FLAG=--force
)

if not "!FORCE_FLAG!"=="" (
    echo Force mode: Will recreate existing environment
)

python s3d_publish.py --setup !FORCE_FLAG!

if !errorlevel! equ 0 (
    echo.
    echo ✅ Setup completed successfully!
    echo Next steps:
    echo   publish.bat check     # Verify setup
    echo   publish.bat test      # Test publication
    echo   publish.bat publish   # Publish to PyPI
) else (
    echo.
    echo ❌ Setup failed!
    echo Check the error messages above for details.
    exit /b 1
)

goto :end

:clean_build
echo.
echo Cleaning build artifacts...

REM Remove build directories
for %%d in (build dist) do (
    if exist "%%d" (
        rmdir /s /q "%%d"
        echo    Removed %%d
    )
)

REM Remove egg-info directories
for /d %%d in (*.egg-info) do (
    if exist "%%d" (
        rmdir /s /q "%%d"
        echo    Removed %%d
    )
)

REM Remove Python cache
for /d /r %%d in (__pycache__) do (
    if exist "%%d" (
        rmdir /s /q "%%d" 2>nul
    )
)

for /r %%f in (*.pyc) do (
    if exist "%%f" del "%%f" 2>nul
)

echo    Build artifacts cleaned

goto :end

:show_version_info
echo.
echo Version Information
echo ===================

REM Current version from file
for /f "tokens=3" %%v in ('python s3d_publish.py --dry-run 2^>nul ^| findstr "Current version:"') do (
    echo 📋 Local version: %%v
    set CURRENT_VERSION=%%v
)

REM Check git tags
echo 🔍 Checking git information...
git rev-parse --git-dir >nul 2>&1
if !errorlevel! equ 0 (
    for /f %%t in ('git describe --tags --abbrev=0 2^>nul') do (
        echo 🏷️  Latest git tag: %%t
    )
    if errorlevel 1 (
        echo 🏷️  Latest git tag: none
    )
) else (
    echo 🏷️  Not a git repository
)

goto :end

:interactive_mode
echo.
echo s3dgraphy Interactive Publication
echo ================================
echo.

call :show_version_info
echo.

echo What would you like to do?
echo   1) Check status
echo   2) Setup environment  
echo   3) Test publish (TestPyPI)
echo   4) Publish to PyPI
echo   5) Increment version and publish
echo   6) Clean build artifacts
echo   7) Show version info
echo   8) Exit
echo.

set /p choice="Enter your choice (1-8): "

if "%choice%"=="1" call :check_status
if "%choice%"=="2" call :setup_environment
if "%choice%"=="3" (
    echo Starting test publication...
    python s3d_publish.py --test
)
if "%choice%"=="4" (
    echo Starting production publication...
    python s3d_publish.py
)
if "%choice%"=="5" (
    echo Choose version increment:
    echo   1) Patch (x.x.X)
    echo   2) Minor (x.X.x)
    echo   3) Major (X.x.x)
    set /p ver_choice="Enter choice (1-3): "
    
    if "!ver_choice!"=="1" python s3d_publish.py --version patch
    if "!ver_choice!"=="2" python s3d_publish.py --version minor
    if "!ver_choice!"=="3" python s3d_publish.py --version major
    if not "!ver_choice!"=="1" if not "!ver_choice!"=="2" if not "!ver_choice!"=="3" echo Invalid choice
)
if "%choice%"=="6" call :clean_build
if "%choice%"=="7" call :show_version_info
if "%choice%"=="8" (
    echo Goodbye!
    goto :end
)

if not "%choice%"=="1" if not "%choice%"=="2" if not "%choice%"=="3" if not "%choice%"=="4" if not "%choice%"=="5" if not "%choice%"=="6" if not "%choice%"=="7" if not "%choice%"=="8" (
    echo Invalid choice
    exit /b 1
)

goto :end

:publish_cmd
shift
echo Publishing to PyPI...
python s3d_publish.py %*
goto :end

:test_cmd
shift
echo Publishing to TestPyPI...
python s3d_publish.py --test %*
goto :end

:dry_run_cmd
shift
echo Dry run mode...
python s3d_publish.py --dry-run %*
goto :end

:patch_cmd
shift
echo Incrementing patch version...
python s3d_publish.py --version patch %*
goto :end

:minor_cmd
shift
echo Incrementing minor version...
python s3d_publish.py --version minor %*
goto :end

:major_cmd
shift
echo Incrementing major version...
python s3d_publish.py --version major %*
goto :end

:end