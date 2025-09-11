#!/usr/bin/env python3
"""
Setup bump2version per s3dgraphy
"""
import subprocess
import sys
from pathlib import Path
import re

def check_current_version():
    """Controlla la versione attuale in pyproject.toml"""
    pyproject_file = Path("pyproject.toml")
    if not pyproject_file.exists():
        print("❌ pyproject.toml not found!")
        return None
    
    content = pyproject_file.read_text()
    match = re.search(r'version = "([^"]+)"', content)
    if match:
        return match.group(1)
    
    print("❌ Version not found in pyproject.toml")
    return None

def check_init_file():
    """Controlla e crea se necessario __init__.py con versione"""
    init_file = Path("src/s3dgraphy/__init__.py")
    
    if not init_file.parent.exists():
        print(f"❌ Directory {init_file.parent} not found!")
        print("   Create the s3dgraphy package structure first")
        return False
    
    current_version = check_current_version()
    if not current_version:
        return False
    
    if not init_file.exists():
        print(f"⚠️  {init_file} not found, creating it...")
        init_content = f'''"""
s3dgraphy - 3D Stratigraphic Graph Management Library
"""

__version__ = "{current_version}"
__author__ = "Emanuel Demetrescu"
__email__ = "emanuel.demetrescu@cnr.it"

# Expose main classes
# from .core import StratigraphicGraph
# from .nodes import US, USV, SF, Actor

__all__ = [
    "__version__",
    # "StratigraphicGraph",
    # "US", "USV", "SF", "Actor"
]
'''
        init_file.write_text(init_content)
        print(f"✅ Created {init_file}")
    else:
        # Controlla se ha __version__
        content = init_file.read_text()
        if '__version__' not in content:
            print(f"⚠️  Adding __version__ to {init_file}...")
            # Aggiungi __version__ all'inizio
            new_content = f'__version__ = "{current_version}"\n\n' + content
            init_file.write_text(new_content)
            print(f"✅ Added __version__ to {init_file}")
        else:
            print(f"✅ {init_file} looks good")
    
    return True

def install_bump2version():
    """Installa bump2version"""
    print("📦 Installing bump2version...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "bump2version"], 
                      check=True, capture_output=True)
        print("✅ bump2version installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install bump2version: {e}")
        return False

def test_bump2version():
    """Testa bump2version"""
    print("🧪 Testing bump2version...")
    try:
        result = subprocess.run(["bump2version", "--dry-run", "patch"], 
                              capture_output=True, text=True, cwd=Path.cwd())
        if result.returncode == 0:
            print("✅ bump2version test successful")
            print("\n📋 What would happen with 'bump2version patch':")
            print(result.stdout)
            return True
        else:
            print("❌ bump2version test failed:")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
    except FileNotFoundError:
        print("❌ bump2version command not found")
        return False

def check_git_repo():
    """Controlla se siamo in un repo git"""
    try:
        result = subprocess.run(["git", "status"], capture_output=True, check=True)
        print("✅ Git repository detected")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Not in a git repository or git not found")
        return False

def main():
    print("🔧 s3dgraphy Versioning Setup")
    print("=" * 40)
    
    # Controlla se siamo nella root corretta
    if not Path("pyproject.toml").exists():
        print("❌ Run this script from s3dgraphy root directory")
        print(f"   Current: {Path.cwd()}")
        return 1
    
    print(f"📍 Working in: {Path.cwd()}")
    
    # Controlla versione attuale
    current_version = check_current_version()
    if current_version:
        print(f"📋 Current version: {current_version}")
    else:
        return 1
    
    # Controlla struttura __init__.py
    if not check_init_file():
        return 1
    
    # Controlla git
    check_git_repo()
    
    # Controlla .bumpversion.cfg
    bumpversion_cfg = Path(".bumpversion.cfg")
    if bumpversion_cfg.exists():
        print("✅ .bumpversion.cfg found")
        # Controlla se ha la versione corretta
        content = bumpversion_cfg.read_text()
        if f"current_version = {current_version}" in content:
            print(f"✅ .bumpversion.cfg has correct version: {current_version}")
        else:
            print(f"⚠️  .bumpversion.cfg version mismatch, updating...")
            # Aggiorna la versione nel file
            new_content = re.sub(
                r'current_version = [^\n]+',
                f'current_version = {current_version}',
                content
            )
            bumpversion_cfg.write_text(new_content)
            print(f"✅ Updated .bumpversion.cfg to version {current_version}")
    else:
        print("❌ .bumpversion.cfg not found!")
        print("   Create it with the config from the guide")
        return 1
    
    # Installa bump2version se non presente
    try:
        subprocess.run(["bump2version", "--version"], 
                      capture_output=True, check=True)
        print("✅ bump2version already installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        if not install_bump2version():
            return 1
    
    # Testa bump2version
    if not test_bump2version():
        return 1
    
    print("\n" + "=" * 50)
    print("🎉 SETUP COMPLETE!")
    print("=" * 50)
    print("\n📋 Available commands:")
    print("  bump2version patch   # 0.1.0 → 0.1.1")
    print("  bump2version minor   # 0.1.1 → 0.2.0")
    print("  bump2version major   # 0.2.0 → 1.0.0")
    print("\n🚀 Complete workflow:")
    print("  1. bump2version patch")
    print("  2. git push --follow-tags")
    print("  3. GitHub → Releases → Create release")
    print("  4. Auto-publish to PyPI! 🎯")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())