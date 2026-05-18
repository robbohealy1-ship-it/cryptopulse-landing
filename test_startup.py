"""Quick syntax check for all modified files."""
import py_compile
import sys

files = [
    "src/main.py",
    "src/marketing/community_engagement.py",
    "src/marketing/campaign_engine.py",
    "src/admin/dashboard_server.py",
    "src/telegram_bot/channel_publisher.py",
    "src/telegram_bot/admin_bot.py",
]

all_ok = True
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  OK: {f}")
    except py_compile.PyCompileError as e:
        print(f"FAIL: {f}")
        print(f"      {e}")
        all_ok = False

if all_ok:
    print("\nAll files syntax OK. Trying to import main...")
    try:
        import src.main
        print("Import OK")
    except Exception as e:
        print(f"Import FAILED: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\nFix syntax errors before running.")
    sys.exit(1)
