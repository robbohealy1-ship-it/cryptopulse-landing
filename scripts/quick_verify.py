#!/usr/bin/env python3
"""
CRYPTO PULSE SIGNALS - Quick Verification
Works without all dependencies installed
"""

import os
import sys
from pathlib import Path


def check_env_file():
    """Check .env file is filled in"""
    print("🔍 Checking .env file...")
    
    env_path = Path('.env')
    if not env_path.exists():
        print("❌ .env file not found!")
        return False
    
    with open(env_path) as f:
        content = f.read()
    
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_ADMIN_CHAT_ID',
        'TELEGRAM_FREE_CHANNEL_ID',
        'TELEGRAM_VIP_CHANNEL_ID',
        'SUPABASE_URL',
        'SUPABASE_KEY',
        'SUPABASE_SERVICE_KEY',
        'STRIPE_SECRET_KEY',
        'STRIPE_PUBLISHABLE_KEY',
        'STRIPE_VIP_PRICE_ID',
        'NEWS_API_KEY',
    ]
    
    missing = []
    filled = []
    
    for var in required_vars:
        for line in content.split('\n'):
            if line.startswith(var + '='):
                value = line.split('=', 1)[1].strip()
                if not value or value.startswith('your_') or value.startswith('YOUR_'):
                    missing.append(var)
                else:
                    filled.append(var)
                break
        else:
            missing.append(var)
    
    if missing:
        print(f"❌ Missing/Unfilled: {', '.join(missing)}")
        print("   → Fill these in your .env file")
        return False
    
    print(f"✅ All {len(filled)} variables filled in")
    return True


def check_directories():
    """Check required directories exist"""
    print("\n🔍 Checking directories...")
    
    required = ['logs', 'data', 'charts', 'assets']
    missing = []
    
    for dir_name in required:
        if not Path(dir_name).exists():
            missing.append(dir_name)
    
    if missing:
        print(f"❌ Missing directories: {', '.join(missing)}")
        print("   → Creating them now...")
        for d in missing:
            Path(d).mkdir(parents=True, exist_ok=True)
            print(f"   ✓ Created: {d}")
    else:
        print("✅ All directories exist")
    
    return True


def check_files():
    """Check key files exist"""
    print("\n🔍 Checking files...")
    
    required = ['src/main.py', 'requirements.txt', '.env']
    missing = []
    
    for file in required:
        if not Path(file).exists():
            missing.append(file)
    
    if missing:
        print(f"❌ Missing files: {', '.join(missing)}")
        return False
    
    print("✅ All key files present")
    return True


def check_telegram_ids():
    """Check Telegram IDs are in correct format"""
    print("\n🔍 Checking Telegram IDs format...")
    
    env_path = Path('.env')
    with open(env_path) as f:
        content = f.read()
    
    issues = []
    
    for line in content.split('\n'):
        if line.startswith('TELEGRAM_ADMIN_CHAT_ID='):
            value = line.split('=', 1)[1].strip()
            if not value.isdigit():
                issues.append("Admin Chat ID should be a number (no @ or -)")
        
        elif line.startswith('TELEGRAM_FREE_CHANNEL_ID='):
            value = line.split('=', 1)[1].strip()
            if not (value.startswith('@') or value.startswith('-100')):
                issues.append("Free Channel ID should start with @ or -100")
        
        elif line.startswith('TELEGRAM_VIP_CHANNEL_ID='):
            value = line.split('=', 1)[1].strip()
            if not value.startswith('-100'):
                issues.append("VIP Channel ID should start with -100")
    
    if issues:
        for issue in issues:
            print(f"⚠️  {issue}")
        return False
    
    print("✅ Telegram ID formats look correct")
    return True


def check_python_version():
    """Check Python version"""
    print("\n🔍 Checking Python version...")
    
    version = sys.version_info
    print(f"   Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 14:
        print("⚠️  Python 3.14+ detected - some packages may not have wheels yet")
        print("   💡 Recommendation: Use Python 3.11 or 3.12 for best compatibility")
        print("   Download from: https://python.org/downloads")
        return False
    elif version.major == 3 and version.minor >= 11:
        print("✅ Python version is good")
        return True
    else:
        print("⚠️  Python version may be too old - consider upgrading to 3.11+")
        return True


def main():
    print("=" * 60)
    print("CRYPTO PULSE SIGNALS - Quick Verification")
    print("=" * 60)
    print()
    
    results = {
        'Environment File': check_env_file(),
        'Directories': check_directories(),
        'Key Files': check_files(),
        'Telegram IDs': check_telegram_ids(),
        'Python Version': check_python_version(),
    }
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL CHECKS PASSED!")
        print()
        print("Next steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Run: python src/main.py")
        print()
    else:
        print("⚠️  SOME CHECKS FAILED")
        print()
        print("Please fix the issues above before proceeding.")
        print()
        print("If Python version is the issue:")
        print("1. Install Python 3.11 from https://python.org/downloads")
        print("2. Run: py -3.11 -m pip install -r requirements.txt")
        print("3. Run: py -3.11 src/main.py")
        print()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
