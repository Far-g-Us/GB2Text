"""
Diagnostic tools for GB2Text.

Usage:
    python scripts/diagnostics.py [--full]
"""

import sys
import os
import platform
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_python_environment():
    """Check Python environment setup."""
    print("\n=== Python Environment ===")
    print(f"Python Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.machine()}")
    print(f"OS: {platform.system()}")


def check_dependencies():
    """Check installed dependencies."""
    print("\n=== Dependencies ===")
    
    required = [
        'pytest',
        'requests',
        'pillow',
        'tkinter',
        'scikit-learn',
    ]
    
    optional = [
        'googletrans',
        'deepl',
        'pyinstaller',
        'coverage',
    ]
    
    print("\nRequired packages:")
    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
            print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  ✗ {pkg} - NOT INSTALLED")
    
    print("\nOptional packages:")
    for pkg in optional:
        try:
            __import__(pkg.replace('-', '_'))
            print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  ○ {pkg} - not installed (optional)")


def check_gb2text_modules():
    """Check GB2Text core modules."""
    print("\n=== GB2Text Modules ===")
    
    modules = [
        'core.rom',
        'core.scanner',
        'core.decoder',
        'core.encoder',
        'core.extractor',
        'core.injector',
        'core.tmx',
        'core.charset',
        'core.database',
        'core.plugin_manager',
        'core.i18n',
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"  ✓ {module}")
        except ImportError as e:
            print(f"  ✗ {module} - {e}")


def check_plugins():
    """Check plugin system."""
    print("\n=== Plugin System ===")
    
    from core.plugin_manager import PluginManager
    
    manager = PluginManager()
    manager.discover_plugins()
    plugins = manager.get_all_plugins()
    
    print(f"  Found {len(plugins)} plugins:")
    for plugin in plugins:
        print(f"    - {plugin}")


def check_configuration():
    """Check configuration files."""
    print("\n=== Configuration Files ===")
    
    config_files = [
        ('pytest.ini', 'pytest'),
        ('.coveragerc', 'coverage'),
        ('ruff.toml', 'ruff'),
        ('mypy.ini', 'mypy'),
        ('requirements.txt', 'requirements'),
        ('requirements-dev.txt', 'dev requirements'),
    ]
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    for filename, desc in config_files:
        path = os.path.join(base_dir, filename)
        if os.path.exists(path):
            print(f"  ✓ {filename} ({desc})")
        else:
            print(f"  ○ {filename} ({desc}) - not found")


def check_github_workflows():
    """Check GitHub workflows."""
    print("\n=== GitHub Workflows ===")
    
    workflow_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.github', 'workflows'
    )
    
    if os.path.exists(workflow_dir):
        workflows = [f for f in os.listdir(workflow_dir) if f.endswith('.yml')]
        print(f"  Found {len(workflows)} workflows:")
        for wf in sorted(workflows):
            print(f"    - {wf}")
    else:
        print("  ○ .github/workflows/ - not found")


def check_test_environment():
    """Check test environment."""
    print("\n=== Test Environment ===")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_dir = os.path.join(base_dir, 'tests')
    
    if os.path.exists(test_dir):
        test_files = [f for f in os.listdir(test_dir) if f.startswith('test_') and f.endswith('.py')]
        print(f"  Found {len(test_files)} test files:")
        for tf in sorted(test_files)[:10]:
            print(f"    - {tf}")
        if len(test_files) > 10:
            print(f"    ... and {len(test_files) - 10} more")
    else:
        print("  ○ tests/ - not found")


def check_guides():
    """Check guides directory."""
    print("\n=== Guides ===")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    guides_dir = os.path.join(base_dir, 'guides')
    
    if os.path.exists(guides_dir):
        guides = [f for f in os.listdir(guides_dir) if f.endswith('.rating')]
        print(f"  Found {len(guides)} rating guides:")
        for g in sorted(guides)[:5]:
            print(f"    - {g}")
        if len(guides) > 5:
            print(f"    ... and {len(guides) - 5} more")
    else:
        print("  ○ guides/ - not found")


def run_performance_check():
    """Run basic performance checks."""
    print("\n=== Performance Check ===")
    
    import time
    
    # Test import speed
    start = time.perf_counter()
    import core.rom
    end = time.perf_counter()
    print(f"  Module import time: {(end - start) * 1000:.2f}ms")
    
    # Test core import
    start = time.perf_counter()
    import core.scanner
    import core.decoder
    end = time.perf_counter()
    print(f"  Core modules import time: {(end - start) * 1000:.2f}ms")


def run_full_diagnostics():
    """Run all diagnostic checks."""
    print("="*60)
    print("GB2Text Diagnostic Report")
    print("="*60)
    print(f"Generated: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]}")
    
    check_python_environment()
    check_dependencies()
    check_gb2text_modules()
    check_plugins()
    check_configuration()
    check_github_workflows()
    check_test_environment()
    check_guides()
    run_performance_check()
    
    print("\n" + "="*60)
    print("Diagnostic Complete")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description='GB2Text Diagnostic Tools')
    parser.add_argument('--full', '-f', action='store_true',
                        help='Run full diagnostic report')
    parser.add_argument('--quick', '-q', action='store_true',
                        help='Run quick diagnostic check')
    
    args = parser.parse_args()
    
    if args.quick:
        check_python_environment()
        check_dependencies()
    else:
        run_full_diagnostics()


if __name__ == '__main__':
    main()