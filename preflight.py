"""Pre-flight check - runs before main system to verify environment."""
import sys
import subprocess

def check():
    print("=" * 50)
    print("CRYPTO PULSE - Pre-flight Check")
    print("=" * 50)
    print()
    
    # Check Python version
    print(f"Python: {sys.version}")
    print(f"Executable: {sys.executable}")
    print()
    
    # Check required packages
    required = [
        ("apscheduler", "APScheduler"),
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("telegram", "python-telegram-bot"),
        ("httpx", "httpx"),
        ("supabase", "supabase"),
    ]
    
    missing = []
    for module, package in required:
        try:
            __import__(module)
            print(f"  [OK] {package}")
        except ImportError:
            print(f"  [MISSING] {package}")
            missing.append(package)
    
    print()
    if missing:
        print("MISSING PACKAGES DETECTED!")
        print("Attempting auto-install...")
        print()
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "-r", "requirements.txt", "--no-cache-dir"
            ])
            print()
            print("Packages installed successfully!")
            return 0
        except Exception as e:
            print(f"FAILED to install: {e}")
            print()
            print("Your Python installation may be broken.")
            print("Solution: Install Python 3.11 from python.org")
            return 1
    else:
        print("All packages OK - ready to start!")
        return 0

if __name__ == "__main__":
    sys.exit(check())
