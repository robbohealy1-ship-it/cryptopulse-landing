#!/usr/bin/env python3
"""
CRYPTO PULSE SIGNALS - Easy Launcher
Simple script to start the platform
"""

import sys
import subprocess
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

def main():
    print("=" * 60)
    print("🚀 CRYPTO PULSE SIGNALS - LAUNCHER")
    print("=" * 60)
    print()
    
    # Check we're in the right directory
    if not Path('src/main.py').exists():
        print("❌ Error: Must run from project root directory")
        print("   cd to: C:\\CascadeProjects\\windsurf-project\\CryptoPulse-Signals")
        return 1
    
    # Check .env exists
    if not Path('.env').exists():
        print("❌ Error: .env file not found")
        print("   Copy .env.example to .env and fill in your credentials")
        return 1
    
    print("✅ Starting CRYPTO PULSE SIGNALS...")
    print()
    print("📊 The system will:")
    print("   • Scan 15m / 1h / 4h / Daily timeframes")
    print("   • Generate institutional-grade trading signals")
    print("   • Send signals to you for approval via Telegram")
    print("   • Publish approved signals to your channels")
    print()
    print("🔴 Press Ctrl+C to stop")
    print()
    print("-" * 60)
    print()
    
    try:
        # Run the main application
        subprocess.run([sys.executable, 'src/main.py'], check=True)
    except KeyboardInterrupt:
        print()
        print()
        print("=" * 60)
        print("👋 CRYPTO PULSE SIGNALS STOPPED")
        print("=" * 60)
        return 0
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 60)
        print(f"❌ ERROR: Application exited with code {e.returncode}")
        print("=" * 60)
        print()
        print("Check logs/cryptopulse_*.log for details")
        return e.returncode
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ ERROR: {e}")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
