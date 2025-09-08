#!/usr/bin/env python3
"""
s3dgraphy Publication Script
Handles building and publishing s3dgraphy to PyPI with version management.

Usage:
    python publish.py                    # Interactive publication
    python publish.py --test             # Publish to TestPyPI
    python publish.py --dry-run          # Show what would be done
    python publish.py --version patch    # Auto-increment version
    python publish.py --force            # Skip safety checks
    python publish.py --setup            # Setup virtual environment
"""

import os
import sys
import subprocess
import shutil
import argparse
import re
from pathlib import Path
import json
import venv

class S3dGraphyPublisher:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.pyproject_file = self.root_dir / "pyproject.toml"
        self.setup_file = self.root_dir / "setup.py"
        self.venv_dir = self.root_dir / "publish_env"
        
    def setup_environment(self, force=False):
        """Setup virtual environment for publishing"""
        print("🔧 Setting up publishing environment...")
        
        # Check if venv already exists
        if self.venv_dir.exists():
            if not force:
                print(f"✅ Virtual environment already exists at {self.venv_dir}")
                print("   Use --force to recreate it")
                return self._check_venv_dependencies()
            else:
                print(f"🗑️  Removing existing environment at {self.venv_dir}")
                shutil.rmtree(self.venv_dir)
        
        # Create virtual environment
        print(f"📦 Creating virtual environment at {self.venv_dir}")
        try:
            venv.create(self.venv_dir, with_pip=True)
        except Exception as e:
            print(f"❌ Failed to create virtual environment: {e}")
            return False
        
        # Install required packages
        pip_path = self._get_venv_pip()
        if not pip_path:
            print("❌ Could not find pip in virtual environment")
            return False
        
        packages = ["twine>=4.0.0", "requests>=2.25.0", "build>=0.7.0"]
        
        print("📥 Installing required packages...")
        for package in packages:
            print(f"   Installing {package}...")
            try:
                result = subprocess.run([
                    str(pip_path), "install", package
                ], check=True, capture_output=True, text=True)
                print(f"   ✅ {package} installed successfully")
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Failed to install {package}: {e}")
                print(f"      Error output: {e.stderr}")
                return False
        
        print("✅ Publishing environment setup complete!")
        print(f"   Location: {self.venv_dir}")
        print(f"   Python: {self._get_venv_python()}")
        print("   Packages installed: twine, requests, build")
        
        return True
    
    def _get_venv_python(self):
        """Get path to Python executable in virtual environment"""
        if os.name == 'nt':  # Windows
            return self.venv_dir / "Scripts" / "python.exe"
        else:  # Unix/Linux/macOS
            return self.venv_dir / "bin" / "python"
    
    def _get_venv_pip(self):
        """Get path to pip executable in virtual environment"""
        if os.name == 'nt':  # Windows
            return self.venv_dir / "Scripts" / "pip.exe"
        else:  # Unix/Linux/macOS
            return self.venv_dir / "bin" / "pip"
    
    def _check_venv_dependencies(self):
        """Check if required dependencies are installed in venv"""
        pip_path = self._get_venv_pip()
        if not pip_path or not pip_path.exists():
            print("❌ Virtual environment pip not found")
            return False
        
        required_packages = ["twine", "requests", "build"]
        missing_packages = []
        
        for package in required_packages:
            try:
                result = subprocess.run([
                    str(pip_path), "show", package
                ], check=True, capture_output=True, text=True)
                print(f"   ✅ {package} is available")
            except subprocess.CalledProcessError:
                missing_packages.append(package)
                print(f"   ❌ {package} is missing")
        
        if missing_packages:
            print(f"⚠️  Missing packages: {', '.join(missing_packages)}")
            print("   Run with --setup --force to reinstall environment")
            return False
        
        return True
    
    def _use_venv_python(self):
        """Check if we should use virtual environment Python"""
        venv_python = self._get_venv_python()
        if venv_python.exists():
            return str(venv_python)
        return sys.executable
    
    def check_dependencies(self):
        """Check if required dependencies are available"""
        print("🔍 Checking dependencies...")
        
        # If venv exists, check it
        if self.venv_dir.exists():
            print("📦 Using virtual environment")
            return self._check_venv_dependencies()
        
        # Otherwise check system-wide
        print("🌐 Checking system-wide packages")
        required_packages = ["twine", "requests", "build"]
        missing_packages = []
        
        for package in required_packages:
            try:
                result = subprocess.run([
                    sys.executable, "-m", "pip", "show", package
                ], check=True, capture_output=True, text=True)
                print(f"   ✅ {package} is available")
            except subprocess.CalledProcessError:
                missing_packages.append(package)
                print(f"   ❌ {package} is missing")
        
        if missing_packages:
            print(f"⚠️  Missing packages: {', '.join(missing_packages)}")
            print("   Run --setup to create isolated publishing environment")
            return False
        
        return True
        
    def check_git_status(self, force=False):
        """Check if git working directory is clean"""
        if force:
            print("⚠️  Skipping git status check (--force)")
            return True
            
        try:
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  cwd=self.root_dir,
                                  capture_output=True, text=True, check=True)
            if result.stdout.strip():
                print("❌ You have uncommitted changes:")
                print(result.stdout)
                print("\nCommit your changes first, or use --force to skip this check")
                return False
            
            print("✅ Git working directory is clean")
            return True
            
        except subprocess.CalledProcessError:
            print("⚠️  Could not check git status")
            return True
    
    def get_current_version(self):
        """Get current version from pyproject.toml or setup.py"""
        # Try pyproject.toml first
        if self.pyproject_file.exists():
            try:
                with open(self.pyproject_file, 'r') as f:
                    content = f.read()
                    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        return match.group(1)
            except Exception as e:
                print(f"⚠️  Could not read version from pyproject.toml: {e}")
        
        # Fallback to setup.py
        if self.setup_file.exists():
            try:
                with open(self.setup_file, 'r') as f:
                    content = f.read()
                    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        return match.group(1)
            except Exception as e:
                print(f"⚠️  Could not read version from setup.py: {e}")
        
        return None
    
    def increment_version(self, current_version, increment_type):
        """Increment version number"""
        try:
            parts = current_version.split('.')
            if len(parts) < 3:
                # Pad with zeros if needed
                parts.extend(['0'] * (3 - len(parts)))
            
            major, minor, patch = [int(x) for x in parts[:3]]
            
            if increment_type == "major":
                major += 1
                minor = 0
                patch = 0
            elif increment_type == "minor":
                minor += 1
                patch = 0
            elif increment_type == "patch":
                patch += 1
            else:
                print(f"❌ Unknown increment type: {increment_type}")
                return None
            
            new_version = f"{major}.{minor}.{patch}"
            
            # Preserve any additional parts (like pre-release identifiers)
            if len(parts) > 3:
                new_version += "." + ".".join(parts[3:])
            
            return new_version
            
        except Exception as e:
            print(f"❌ Could not increment version: {e}")
            return None
    
    def update_version(self, new_version):
        """Update version in pyproject.toml or setup.py"""
        updated = False
        
        # Update pyproject.toml
        if self.pyproject_file.exists():
            try:
                with open(self.pyproject_file, 'r') as f:
                    content = f.read()
                
                # More specific regex that only matches the version in [project] section
                # Look for version = "..." in the [project] section specifically
                new_content = re.sub(
                    r'(\[project\].*?)\nversion\s*=\s*["\']([^"\']+)["\']',
                    rf'\1\nversion = "{new_version}"',
                    content,
                    flags=re.DOTALL
                )
                
                # If the above doesn't work, try a more targeted approach
                if new_content == content:
                    # Split by sections and only update the project section
                    lines = content.split('\n')
                    in_project_section = False
                    
                    for i, line in enumerate(lines):
                        if line.strip() == '[project]':
                            in_project_section = True
                        elif line.strip().startswith('[') and line.strip() != '[project]':
                            in_project_section = False
                        elif in_project_section and re.match(r'\s*version\s*=', line):
                            lines[i] = f'version = "{new_version}"'
                            break
                    
                    new_content = '\n'.join(lines)
                
                if new_content != content:
                    with open(self.pyproject_file, 'w') as f:
                        f.write(new_content)
                    print(f"✅ Updated version in pyproject.toml")
                    updated = True
                    
            except Exception as e:
                print(f"⚠️  Could not update pyproject.toml: {e}")
        
        # Update setup.py
        if self.setup_file.exists():
            try:
                with open(self.setup_file, 'r') as f:
                    content = f.read()
                
                # More specific regex for setup.py - only in setup() call context
                new_content = re.sub(
                    r'(setup\s*\([^)]*?)version\s*=\s*["\']([^"\']+)["\']',
                    rf'\1version="{new_version}"',
                    content,
                    flags=re.DOTALL
                )
                
                if new_content != content:
                    with open(self.setup_file, 'w') as f:
                        f.write(new_content)
                    print(f"✅ Updated version in setup.py")
                    updated = True
                    
            except Exception as e:
                print(f"⚠️  Could not update setup.py: {e}")
        
        return updated
    
    def get_pypi_version(self, test=False):
        """Get latest version from PyPI"""
        try:
            import requests
            
            url = "https://test.pypi.org/pypi/s3dgraphy/json" if test else "https://pypi.org/pypi/s3dgraphy/json"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data["info"]["version"]
            elif response.status_code == 404:
                return None  # Package not found
            else:
                print(f"⚠️  Could not check PyPI: HTTP {response.status_code}")
                return "unknown"
                
        except ImportError:
            print("⚠️  requests not available, cannot check PyPI version")
            return "unknown"
        except Exception as e:
            print(f"⚠️  Could not check PyPI version: {e}")
            return "unknown"
    
    def clean_build_artifacts(self):
        """Clean build artifacts"""
        print("🧹 Cleaning build artifacts...")
        
        dirs_to_clean = ["build", "dist", "*.egg-info"]
        
        for pattern in dirs_to_clean:
            if "*" in pattern:
                # Use glob for patterns
                from glob import glob
                for path in glob(pattern):
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                        print(f"   Removed {path}")
            else:
                path = Path(pattern)
                if path.exists():
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    print(f"   Removed {path}")
    
    def build_package(self):
        """Build the package using the appropriate Python"""
        print("🔨 Building package...")
        
        python_exec = self._use_venv_python()
        
        try:
            result = subprocess.run([
                python_exec, "-m", "build"
            ], cwd=self.root_dir, check=True, capture_output=True, text=True)
            
            print("✅ Package built successfully")
            print("   Output:", result.stdout.strip())
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Build failed: {e}")
            print(f"   Error output: {e.stderr}")
            return False
    
    def check_build_artifacts(self):
        """Check if build artifacts were created"""
        dist_dir = self.root_dir / "dist"
        
        if not dist_dir.exists():
            print("❌ No dist/ directory found")
            return False
        
        files = list(dist_dir.glob("*"))
        if not files:
            print("❌ No files found in dist/")
            return False
        
        print(f"✅ Build artifacts found:")
        for file in files:
            print(f"   📦 {file.name}")
        
        return True
    
    def upload_to_pypi(self, test=False, dry_run=False):
        """Upload package to PyPI using the appropriate Python"""
        if dry_run:
            print("🔍 DRY RUN: Would upload to", "TestPyPI" if test else "PyPI")
            return True
        
        print(f"📤 Uploading to {'TestPyPI' if test else 'PyPI'}...")
        
        python_exec = self._use_venv_python()
        
        # Build twine command
        cmd = [python_exec, "-m", "twine", "upload"]
        
        if test:
            cmd.extend(["--repository", "testpypi"])
        
        cmd.append("dist/*")
        
        try:
            result = subprocess.run(cmd, cwd=self.root_dir, check=True)
            print("✅ Upload successful")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Upload failed: {e}")
            return False
    
    def create_git_tag(self, version, dry_run=False):
        """Create and push git tag"""
        if dry_run:
            print(f"🔍 DRY RUN: Would create git tag v{version}")
            return True
        
        print(f"🏷️  Creating git tag v{version}...")
        
        try:
            # Create tag
            subprocess.run(['git', 'tag', f'v{version}'], 
                         cwd=self.root_dir, check=True)
            
            # Push tag
            subprocess.run(['git', 'push', 'origin', f'v{version}'], 
                         cwd=self.root_dir, check=True)
            
            print(f"✅ Git tag v{version} created and pushed")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Git tag failed: {e}")
            return False
    
    def show_success_message(self, version, test=False):
        """Show success message with next steps"""
        print("\n" + "="*50)
        print("🎉 PUBLICATION SUCCESSFUL!")
        print("="*50)
        
        if test:
            print("\n🧪 Test installation:")
            print("pip install --index-url https://test.pypi.org/simple/ s3dgraphy")
        else:
            print("\n📥 Installation:")
            print("pip install s3dgraphy")
            print(f"pip install s3dgraphy>={version}")
            
            print("\n🔄 To update EMtools:")
            print("cd path/to/EM-blender-tools/")
            print("em s3d off        # Remove dev version")
            print("em setup force    # Download latest from PyPI")
        
        print(f"\n📋 What was done:")
        print(f"   ✅ Version updated to {version}")
        print(f"   ✅ Package built and uploaded")
        print(f"   ✅ Git tag v{version} created and pushed")
    
    def publish(self, test=False, dry_run=False, force=False, auto_version=None):
        """Main publication workflow"""
        print("🚀 Starting s3dgraphy publication process...")
        print(f"   Target: {'TestPyPI' if test else 'PyPI'}")
        print(f"   Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        
        # 1. Check git status
        if not self.check_git_status(force):
            return False
        
        # 2. Get current version
        current_version = self.get_current_version()
        if not current_version:
            print("❌ Could not determine current version")
            return False
        
        print(f"📋 Current version: {current_version}")
        
        # 3. Handle version increment
        new_version = current_version
        if auto_version:
            new_version = self.increment_version(current_version, auto_version)
            if not new_version:
                return False
            
            print(f"📈 Auto-incrementing version: {current_version} → {new_version}")
            
            if not dry_run:
                if not self.update_version(new_version):
                    print("❌ Failed to update version")
                    return False
        
        # 4. Check PyPI version conflict
        pypi_version = self.get_pypi_version(test)
        if pypi_version and pypi_version != "unknown":
            print(f"📊 PyPI version: {pypi_version}")
            
            if new_version == pypi_version and not force:
                print("❌ Version conflict! Local version matches PyPI version")
                print("   Use --version to increment, or --force to override")
                return False
        else:
            print("📊 Package not found on PyPI (first release?)")
        
        # 5. Clean build artifacts
        self.clean_build_artifacts()
        
        # 6. Build package
        if not dry_run:
            if not self.build_package():
                return False
            
            if not self.check_build_artifacts():
                return False
        
        # 7. Upload to PyPI
        if not self.upload_to_pypi(test, dry_run):
            return False
        
        # 8. Create git tag
        if not self.create_git_tag(new_version, dry_run):
            return False
        
        # 9. Show success message
        if not dry_run:
            self.show_success_message(new_version, test)
        
        return True


def main():
    parser = argparse.ArgumentParser(description="s3dgraphy Publication Tool")
    parser.add_argument("--test", action="store_true", 
                       help="Publish to TestPyPI instead of PyPI")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without executing")
    parser.add_argument("--force", action="store_true",
                       help="Skip safety checks")
    parser.add_argument("--version", choices=["patch", "minor", "major"],
                       help="Auto-increment version before publishing")
    parser.add_argument("--setup", action="store_true",
                       help="Setup virtual environment for publishing")
    
    args = parser.parse_args()
    
    publisher = S3dGraphyPublisher()
    
    # Handle setup command
    if args.setup:
        success = publisher.setup_environment(force=args.force)
        if success:
            print("\n🎉 Setup complete! You can now run publication commands.")
            print("   The virtual environment will be used automatically.")
        else:
            print("\n❌ Setup failed!")
        sys.exit(0 if success else 1)
    
    # Check dependencies before proceeding
    if not publisher.check_dependencies():
        print("\n💡 Suggestion: Run --setup to create an isolated publishing environment")
        sys.exit(1)
    
    # Continue with publication...
    success = publisher.publish(
        test=args.test,
        dry_run=args.dry_run,
        force=args.force,
        auto_version=args.version
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()