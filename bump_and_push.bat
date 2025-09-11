@echo off
setlocal enabledelayedexpansion

:: bump_and_push.bat - Automated version bump and push for s3dgraphy
:: Usage: bump_and_push.bat [patch|minor|major]

:: Check if argument provided
if "%1"=="" (
    echo ❌ Error: No bump type specified
    goto :show_help
)

set "BUMP_TYPE=%1"

:: Validate bump type
if not "%BUMP_TYPE%"=="patch" if not "%BUMP_TYPE%"=="minor" if not "%BUMP_TYPE%"=="major" (
    echo ❌ Error: Invalid bump type '%BUMP_TYPE%'
    goto :show_help
)

:: Check if we're in a git repository
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Not in a git repository
    pause
    exit /b 1
)

:: Check if working directory is clean
git diff --quiet >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Warning: Working directory has uncommitted changes
    set /p "continue=Continue anyway? (y/N): "
    if /i not "!continue!"=="y" (
        echo Aborted.
        pause
        exit /b 1
    )
)

:: Check if bump2version is installed
bump2version --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: bump2version not found
    echo Install with: pip install bump2version
    pause
    exit /b 1
)

:: Get current version before bump
echo 📋 Getting current version...
for /f "tokens=3" %%v in ('findstr "current_version = " .bumpversion.cfg') do set "CURRENT_VERSION=%%v"
echo Current version: %CURRENT_VERSION%

:: Perform version bump
echo 🔢 Bumping %BUMP_TYPE% version...
bump2version %BUMP_TYPE%
if errorlevel 1 (
    echo ❌ Version bump failed
    pause
    exit /b 1
)
echo ✅ Version bump successful

:: Get new version after bump
for /f "tokens=3" %%v in ('findstr "current_version = " .bumpversion.cfg') do set "NEW_VERSION=%%v"
echo New version: %NEW_VERSION%

:: Push commits and tags
echo 📤 Pushing to GitHub...
git push
if errorlevel 1 (
    echo ❌ Push failed
    pause
    exit /b 1
)

git push --tags
if errorlevel 1 (
    echo ❌ Tag push failed
    pause
    exit /b 1
)

echo ✅ Push successful

:: Success message
echo.
echo 🎉 SUCCESS!
echo Version bumped: %CURRENT_VERSION% → %NEW_VERSION%
echo Tag created and pushed: v%NEW_VERSION%
echo.
echo 📝 Next steps:
echo 1. Go to GitHub → Releases → Create new release
echo 2. Tag: v%NEW_VERSION%
echo 3. Publish release → Auto-publish to PyPI!
echo.
pause
goto :end

:show_help
echo Usage: %0 [patch^|minor^|major]
echo.
echo Automated version bump and push for s3dgraphy
echo.
echo Commands:
echo   patch    Increment patch version (1.0.0 → 1.0.1)
echo   minor    Increment minor version (1.0.1 → 1.1.0)
echo   major    Increment major version (1.1.0 → 2.0.0)
echo.
echo Examples:
echo   %0 patch
echo   %0 minor
echo.
pause

:end