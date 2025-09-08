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
"""

import os
import sys
import subprocess
import shutil
import argparse
import re
from pathlib import Path
import json

class S3dGraphyPublisher:
    def __init__(self):
        self.root_dir = Path(__file__).parent
        self.pyproject_file = self.root_dir / "pyproject.toml"
        self.setup_file = self.root_dir / "setup.py"
        
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
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            
            if increment_type == 'major':
                return f"{major + 1}.0.0"
            elif increment_type == 'minor':
                return f"{major}.{minor + 1}.0"
            elif increment_type == 'patch':
                return f"{major}.{minor}.{patch + 1}"
            else:
                print(f"❌ Invalid increment type: {increment_type}")
                return None
                
        except (ValueError, IndexError):
            print(f"❌ Invalid version format: {current_version}")
            return None
    
    def update_version(self, new_version):
        """Update version in pyproject.toml or setup.py"""
        updated = False
        
        # Update pyproject.toml
        if self.pyproject_file.exists():
            try:
                with open(self.pyproject_file, 'r') as f:
                    content = f.read()
                
                new_content = re.sub(
                    r'version\s*=\s*["\'][^"\']+["\']',
                    f'version = "{new_version}"',
                    content
                )
                
                if new_content != content:
                    with open(self.pyproject_file, 'w') as f:
                        f.write(new_content)
                    print(f"✅ Updated version in pyproject.toml to {new_version}")
                    updated = True
                    
            except Exception as e:
                print(f"❌ Could not update pyproject.toml: {e}")
        
        # Update setup.py if it exists
        if self.setup_file.exists():
            try:
                with open(self.setup_file, 'r') as f:
                    content = f.read()
                
                new_content = re.sub(
                    r'version\s*=\s*["\'][^"\']+["\']',
                    f'version="{new_version}"',
                    content
                )
                
                if new_content != content:
                    with open(self.setup_file, 'w') as f:
                        f.write(new_content)
                    print(f"✅ Updated version in setup.py to {new_version}")
                    updated = True
                    
            except Exception as e:
                print(f"❌ Could not update setup.py: {e}")
        
        return updated
    
    def get_pypi_version(self, test=False):
        """Get current version on PyPI"""
        try:
            import requests
            url = "https://test.pypi.org/pypi/s3dgraphy/json" if test else "https://pypi.org/pypi/s3dgraphy/json"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data["info"]["version"]
            elif response.status_code == 404:
                return None  # Package doesn't exist yet
        except Exception as e:
            print(f"⚠️  Could not check PyPI version: {e}")
        return "unknown"
    
    def clean_build_artifacts(self):
        """Clean previous build artifacts"""
        build_dirs = ["build", "dist", "*.egg-info"]
        
        for pattern in build_dirs:
            for path in self.root_dir.glob(pattern):
                if path.is_dir():
                    print(f"🧹 Removing: {path}")
                    shutil.rmtree(path)
                elif path.is_file():
                    print(f"🧹 Removing: {path}")
                    path.unlink()
    
    def build_package(self):
        """Build wheel and source distribution"""
        print("🔨 Building distribution packages...")
        
        # Try modern build first
        build_commands = [
            [sys.executable, "-m", "build"],
            [sys.executable, "setup.py", "sdist", "bdist_wheel"]
        ]
        
        for cmd in build_commands:
            try:
                result = subprocess.run(
                    cmd, 
                    cwd=self.root_dir,
                    capture_output=True, 
                    text=True, 
                    check=True
                )
                print("✅ Package built successfully")
                return True
                
            except subprocess.CalledProcessError as e:
                print(f"⚠️  Build command failed: {' '.join(cmd)}")
                print(f"   stdout: {e.stdout}")
                print(f"   stderr: {e.stderr}")
                continue
            except FileNotFoundError:
                print(f"⚠️  Command not found: {' '.join(cmd)}")
                continue
        
        print("❌ All build commands failed!")
        return False
    
    def check_build_artifacts(self):
        """Check that build artifacts were created"""
        dist_dir = self.root_dir / "dist"
        
        if not dist_dir.exists():
            print("❌ No dist directory found!")
            return False
        
        artifacts = list(dist_dir.glob("*"))
        if not artifacts:
            print("❌ No distribution artifacts found!")
            return False
        
        print(f"📦 Found {len(artifacts)} distribution artifacts:")
        for artifact in artifacts:
            size_mb = artifact.stat().st_size / (1024 * 1024)
            print(f"   - {artifact.name} ({size_mb:.2f} MB)")
        
        return True
    
    def upload_to_pypi(self, test=False, dry_run=False):
        """Upload package to PyPI"""
        target = "TestPyPI" if test else "PyPI"
        
        if dry_run:
            print(f"🧪 DRY RUN: Would upload to {target}")
            return True
        
        print(f"📤 Uploading to {target}...")
        
        cmd = [sys.executable, "-m", "twine", "upload"]
        
        if test:
            cmd.extend(["--repository", "testpypi"])
        
        cmd.append("dist/*")
        
        try:
            result = subprocess.run(cmd, cwd=self.root_dir, check=True)
            print(f"✅ Successfully uploaded to {target}!")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Upload failed: {e}")
            print("\n💡 Common issues:")
            print("   1. Install twine: pip install twine")
            print("   2. Configure PyPI credentials")
            print("   3. Version already exists on PyPI")
            return False
        except FileNotFoundError:
            print("❌ twine not found! Install with: pip install twine")
            return False
    
    def create_git_tag(self, version, dry_run=False):
        """Create and push git tag"""
        tag = f"v{version}"
        
        if dry_run:
            print(f"🧪 DRY RUN: Would create tag {tag}")
            return True
        
        try:
            # Create tag
            subprocess.run(['git', 'tag', tag], cwd=self.root_dir, check=True)
            print(f"🏷️  Created tag: {tag}")
            
            # Push tag
            subprocess.run(['git', 'push', 'origin', tag], cwd=self.root_dir, check=True)
            print(f"🚀 Pushed tag: {tag}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Git tag failed: {e}")
            return False
    
    def show_post_publish_info(self, version, test=False):
        """Show information after successful publication"""
        print(f"\n🎉 s3dgraphy v{version} published successfully!")
        
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
        
        # 9. Show post-publish information
        if not dry_run:
            self.show_post_publish_info(new_version, test)
        
        return True

def main():
    parser = argparse.ArgumentParser(
        description="Publish s3dgraphy to PyPI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python publish.py                      # Interactive publication to PyPI
  python publish.py --test               # Publish to TestPyPI
  python publish.py --dry-run            # Show what would be done
  python publish.py --version patch      # Auto-increment patch version
  python publish.py --version minor      # Auto-increment minor version
  python publish.py --force              # Skip safety checks
  python publish.py --test --version patch  # Test with version bump
        """
    )
    
    parser.add_argument(
        "--test", 
        action="store_true",
        help="Publish to TestPyPI instead of PyPI"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be done without actually doing it"
    )
    parser.add_argument(
        "--force", 
        action="store_true",
        help="Skip safety checks (git status, version conflicts)"
    )
    parser.add_argument(
        "--version", 
        choices=["patch", "minor", "major"],
        help="Auto-increment version before publishing"
    )
    
    args = parser.parse_args()
    
    publisher = S3dGraphyPublisher()
    success = publisher.publish(
        test=args.test,
        dry_run=args.dry_run,
        force=args.force,
        auto_version=args.version
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
