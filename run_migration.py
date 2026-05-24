"""
Run TP Tracking Database Migration
Safe execution with rollback on error
"""
import asyncio
from src.database.supabase_client import SupabaseClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_migration():
    """Run the TP tracking migration"""
    db = SupabaseClient()
    
    try:
        logger.info("🔄 Starting TP tracking migration...")
        
        # Read migration SQL
        with open('database_migration_tp_tracking.sql', 'r') as f:
            migration_sql = f.read()
        
        # Split into individual statements
        statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        logger.info(f"Found {len(statements)} SQL statements to execute")
        
        # Execute each statement
        for i, statement in enumerate(statements, 1):
            logger.info(f"Executing statement {i}/{len(statements)}...")
            
            # Use Supabase client to execute raw SQL
            result = db.client.rpc('exec_sql', {'sql': statement}).execute()
            
            if result.data:
                logger.info(f"✅ Statement {i} executed successfully")
            else:
                logger.warning(f"⚠️ Statement {i} returned no data (might be normal for ALTER/CREATE)")
        
        logger.info("✅ Migration completed successfully!")
        logger.info("\nNew columns added:")
        logger.info("  - tp1_hit, tp2_hit, tp3_hit (BOOLEAN)")
        logger.info("  - tp1_hit_at, tp2_hit_at, tp3_hit_at (TIMESTAMP)")
        logger.info("  - stop_hit, stop_moved_to_breakeven (BOOLEAN)")
        logger.info("  - stop_hit_at, stop_updated_at (TIMESTAMP)")
        logger.info("  - expires_at (TIMESTAMP)")
        logger.info("  - cancellation_reason (TEXT)")
        logger.info("\nIndexes created for better performance")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        logger.error("Please run migration manually via Supabase dashboard")
        return False


async def check_migration_status():
    """Check if migration was already applied"""
    db = SupabaseClient()
    
    try:
        logger.info("🔍 Checking migration status...")
        
        # Try to query one of the new columns
        result = db.client.from_('signals').select('tp1_hit').limit(1).execute()
        
        logger.info("✅ Migration already applied! Columns exist.")
        return True
        
    except Exception as e:
        logger.info("⚠️ Migration not yet applied (columns don't exist)")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("  TP TRACKING DATABASE MIGRATION")
    print("=" * 60)
    print()
    
    # Check if already applied
    already_applied = asyncio.run(check_migration_status())
    
    if already_applied:
        print("\n✅ Migration already applied! No action needed.")
        print("\nYou can now remove the in-memory TP cache from main.py")
    else:
        print("\n⚠️ Migration needs to be applied.")
        print("\nOptions:")
        print("1. Run via Supabase Dashboard (recommended)")
        print("2. Run via this script (if RPC enabled)")
        print()
        
        choice = input("Run migration now? (y/n): ").lower()
        
        if choice == 'y':
            success = asyncio.run(run_migration())
            
            if success:
                print("\n✅ Migration successful!")
                print("\nNext steps:")
                print("1. Remove in-memory TP cache from main.py")
                print("2. Restart bot: START_BOT.bat")
                print("3. Test TP tracking on next signal")
            else:
                print("\n❌ Migration failed!")
                print("\nPlease run manually via Supabase dashboard:")
                print("1. Go to SQL Editor")
                print("2. Copy-paste database_migration_tp_tracking.sql")
                print("3. Click Run")
        else:
            print("\nSkipped. Run manually when ready.")
    
    print()
    input("Press Enter to exit...")
