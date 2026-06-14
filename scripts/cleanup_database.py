"""
Database Cleanup Script
Removes duplicate and corrupted alpha plays from the database
"""
import asyncio
from supabase import create_client
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')


async def cleanup_duplicate_alpha_plays():
    """Remove duplicate alpha plays, keeping only the oldest entry"""
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    print("🔍 Finding duplicate alpha plays...")
    
    # Get all alpha plays
    response = client.table('alpha_plays').select('*').execute()
    plays = response.data
    
    print(f"📊 Total alpha plays in database: {len(plays)}")
    
    # Group by symbol to find duplicates
    symbol_groups = {}
    for play in plays:
        symbol = play.get('symbol')
        if symbol:
            if symbol not in symbol_groups:
                symbol_groups[symbol] = []
            symbol_groups[symbol].append(play)
    
    # Find and remove duplicates
    duplicates_removed = 0
    for symbol, group in symbol_groups.items():
        if len(group) > 1:
            print(f"\n⚠️  Found {len(group)} entries for {symbol}")
            
            # Sort by created_at, keep the oldest
            group.sort(key=lambda x: x.get('created_at', ''))
            keep = group[0]
            remove = group[1:]
            
            print(f"  ✅ Keeping: {keep['id']} (created: {keep.get('created_at')})")
            
            for dup in remove:
                print(f"  🗑️  Removing: {dup['id']} (created: {dup.get('created_at')})")
                client.table('alpha_plays').delete().eq('id', dup['id']).execute()
                duplicates_removed += 1
    
    print(f"\n✅ Removed {duplicates_removed} duplicate alpha plays")
    return duplicates_removed


async def cleanup_corrupted_alpha_plays():
    """Remove alpha plays with invalid data (entry=0, sl=0, etc.)"""
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    print("\n🔍 Finding corrupted alpha plays...")
    
    # Get all alpha plays
    response = client.table('alpha_plays').select('*').execute()
    plays = response.data
    
    corrupted_removed = 0
    for play in plays:
        is_corrupted = False
        reasons = []
        
        # Check for zero values
        if play.get('entry_price') == 0 or play.get('entry_price') is None:
            is_corrupted = True
            reasons.append("entry_price=0")
        
        if play.get('stop_loss') == 0 or play.get('stop_loss') is None:
            is_corrupted = True
            reasons.append("stop_loss=0")
        
        if play.get('exit_price') == 0 and play.get('status') == 'closed':
            is_corrupted = True
            reasons.append("exit_price=0 but status=closed")
        
        if is_corrupted:
            print(f"⚠️  Corrupted: {play.get('symbol')} (id: {play['id']}) - {', '.join(reasons)}")
            client.table('alpha_plays').delete().eq('id', play['id']).execute()
            corrupted_removed += 1
    
    print(f"\n✅ Removed {corrupted_removed} corrupted alpha plays")
    return corrupted_removed


async def add_unique_constraint():
    """Add database constraint to prevent future duplicates"""
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    print("\n🔧 Adding unique constraint to prevent future duplicates...")
    
    # Note: This requires direct SQL execution in Supabase dashboard
    sql = """
    -- Add unique constraint on symbol + status for active plays
    -- This prevents multiple active plays for the same symbol
    CREATE UNIQUE INDEX IF NOT EXISTS unique_active_alpha_play 
    ON alpha_plays (symbol) 
    WHERE status IN ('active', 'pending');
    """
    
    print("⚠️  SQL constraint must be run manually in Supabase SQL Editor:")
    print(sql)
    print("\n📝 Instructions:")
    print("1. Go to Supabase Dashboard > SQL Editor")
    print("2. Paste the SQL above")
    print("3. Click 'Run'")
    
    return sql


async def main():
    """Run all cleanup tasks"""
    print("=" * 60)
    print("DATABASE CLEANUP SCRIPT")
    print("=" * 60)
    
    try:
        # Cleanup duplicates
        dup_count = await cleanup_duplicate_alpha_plays()
        
        # Cleanup corrupted entries
        cor_count = await cleanup_corrupted_alpha_plays()
        
        # Show SQL for constraint
        await add_unique_constraint()
        
        print("\n" + "=" * 60)
        print("CLEANUP COMPLETE")
        print("=" * 60)
        print(f"📊 Summary:")
        print(f"  - Duplicates removed: {dup_count}")
        print(f"  - Corrupted entries removed: {cor_count}")
        print(f"  - Total cleaned: {dup_count + cor_count}")
        print("\n✅ Database is now clean!")
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
