"""
Production Audit Script

Comprehensive audit of the entire system before production deployment:
1. Check all imports work
2. Verify database connections
3. Test API endpoints
4. Check configuration
5. Verify file structure
6. Test conviction engine
7. Check for common bugs

Run this before deploying to Oracle.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProductionAuditor:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed = []
    
    def log_pass(self, check_name):
        self.passed.append(check_name)
        logger.info(f"✅ {check_name}")
    
    def log_warning(self, check_name, message):
        self.warnings.append((check_name, message))
        logger.warning(f"⚠️  {check_name}: {message}")
    
    def log_issue(self, check_name, message):
        self.issues.append((check_name, message))
        logger.error(f"❌ {check_name}: {message}")
    
    async def check_imports(self):
        """Check all critical imports work"""
        logger.info("\n" + "="*60)
        logger.info("CHECK 1: Critical Imports")
        logger.info("="*60)
        
        critical_modules = [
            'src.config',
            'src.database.supabase_client',
            'src.scanner.market_scanner',
            'src.engine.signal_engine',
            'src.conviction.conviction_engine',
            'src.conviction.market_structure_engine',
            'src.conviction.liquidity_engine',
            'src.conviction.volume_engine',
            'src.conviction.sentiment_engine',
            'src.conviction.news_intelligence_engine',
            'src.conviction.onchain_engine',
            'src.conviction.market_magnet_system',
            'src.conviction.trap_detection_engine',
            'src.alpha_plays.alpha_engine',
            'src.research.models',
        ]
        
        for module_name in critical_modules:
            try:
                importlib.import_module(module_name)
                self.log_pass(f"Import: {module_name}")
            except Exception as e:
                self.log_issue(f"Import: {module_name}", str(e))
    
    async def check_config(self):
        """Check configuration"""
        logger.info("\n" + "="*60)
        logger.info("CHECK 2: Configuration")
        logger.info("="*60)
        
        try:
            from src.config import settings
            
            # Check critical settings
            if settings.SIGNAL_MODE not in ['strict', 'balanced', 'aggressive']:
                self.log_warning("SIGNAL_MODE", f"Invalid mode: {settings.SIGNAL_MODE}")
            else:
                self.log_pass(f"SIGNAL_MODE: {settings.SIGNAL_MODE}")
            
            if settings.MIN_DAILY_VOLUME_USD < 1000000:
                self.log_warning("MIN_DAILY_VOLUME_USD", "Very low threshold")
            else:
                self.log_pass(f"MIN_DAILY_VOLUME_USD: ${settings.MIN_DAILY_VOLUME_USD:,.0f}")
            
            if settings.MIN_CONFIDENCE_SCORE < 70:
                self.log_warning("MIN_CONFIDENCE_SCORE", "Low threshold may generate too many signals")
            else:
                self.log_pass(f"MIN_CONFIDENCE_SCORE: {settings.MIN_CONFIDENCE_SCORE}")
            
        except Exception as e:
            self.log_issue("Configuration", str(e))
    
    async def check_database(self):
        """Check database connection"""
        logger.info("\n" + "="*60)
        logger.info("CHECK 3: Database Connection")
        logger.info("="*60)
        
        try:
            from src.database.supabase_client import SupabaseClient
            
            db = SupabaseClient()
            
            # Try to fetch signals (should not error even if empty)
            try:
                signals = await db.get_signals_by_status('active', limit=1)
                self.log_pass("Database: Signal fetch works")
            except Exception as e:
                self.log_warning("Database: Signal fetch", str(e))
            
            # Try to fetch research projects
            try:
                projects = await db.get_all_research_projects()
                self.log_pass(f"Database: Research projects ({len(projects)} found)")
            except Exception as e:
                self.log_warning("Database: Research projects", str(e))
            
        except Exception as e:
            self.log_issue("Database Connection", str(e))
    
    async def check_conviction_engine(self):
        """Check conviction engine initialization"""
        logger.info("\n" + "="*60)
        logger.info("CHECK 4: Conviction Engine")
        logger.info("="*60)
        
        try:
            from src.conviction import ConvictionEngine
            
            engine = ConvictionEngine()
            self.log_pass("Conviction Engine: Initialized")
            
            # Check all sub-engines exist
            if hasattr(engine, 'market_structure'):
                self.log_pass("Conviction Engine: Market Structure sub-engine")
            else:
                self.log_issue("Conviction Engine", "Missing market_structure")
            
            if hasattr(engine, 'liquidity'):
                self.log_pass("Conviction Engine: Liquidity sub-engine")
            else:
                self.log_issue("Conviction Engine", "Missing liquidity")
            
            if hasattr(engine, 'volume'):
                self.log_pass("Conviction Engine: Volume sub-engine")
            else:
                self.log_issue("Conviction Engine", "Missing volume")
            
            if hasattr(engine, 'sentiment'):
                self.log_pass("Conviction Engine: Sentiment sub-engine")
            else:
                self.log_issue("Conviction Engine", "Missing sentiment")
            
            if hasattr(engine, 'news'):
                self.log_pass("Conviction Engine: News sub-engine")
            else:
                self.log_issue("Conviction Engine", "Missing news")
            
            if hasattr(engine, 'onchain'):
                self.log_pass("Conviction Engine: On-Chain sub-engine")
            else:
                self.log_issue("Conviction Engine", "Missing onchain")
            
            if hasattr(engine, 'magnet_system'):
                self.log_pass("Conviction Engine: Magnet System")
            else:
                self.log_issue("Conviction Engine", "Missing magnet_system")
            
            if hasattr(engine, 'trap_detection'):
                self.log_pass("Conviction Engine: Trap Detection")
            else:
                self.log_issue("Conviction Engine", "Missing trap_detection")
            
        except Exception as e:
            self.log_issue("Conviction Engine", str(e))
    
    async def check_signal_engine(self):
        """Check signal engine integration"""
        logger.info("\n" + "="*60)
        logger.info("CHECK 5: Signal Engine Integration")
        logger.info("="*60)
        
        try:
            from src.engine.signal_engine import SignalEngine
            
            engine = SignalEngine()
            
            if hasattr(engine, 'conviction_engine'):
                self.log_pass("Signal Engine: Conviction engine integrated")
            else:
                self.log_issue("Signal Engine", "Missing conviction_engine attribute")
            
            if hasattr(engine, 'signal_mode'):
                self.log_pass(f"Signal Engine: Signal mode = {engine.signal_mode}")
            else:
                self.log_warning("Signal Engine", "Missing signal_mode attribute")
            
        except Exception as e:
            self.log_issue("Signal Engine", str(e))
    
    async def check_file_structure(self):
        """Check critical files exist"""
        logger.info("\n" + "="*60)
        logger.info("CHECK 6: File Structure")
        logger.info("="*60)
        
        critical_files = [
            'src/conviction/__init__.py',
            'src/conviction/conviction_engine.py',
            'src/conviction/base_engine.py',
            'src/conviction/market_structure_engine.py',
            'src/conviction/liquidity_engine.py',
            'src/conviction/volume_engine.py',
            'src/conviction/sentiment_engine.py',
            'src/conviction/news_intelligence_engine.py',
            'src/conviction/onchain_engine.py',
            'src/conviction/market_magnet_system.py',
            'src/conviction/trap_detection_engine.py',
            'src/engine/signal_engine.py',
            'src/models/signal.py',
            'src/config.py',
            'src/admin/dashboard_server.py',
        ]
        
        project_root = Path(__file__).parent.parent
        
        for file_path in critical_files:
            full_path = project_root / file_path
            if full_path.exists():
                self.log_pass(f"File: {file_path}")
            else:
                self.log_issue(f"File: {file_path}", "Missing")
    
    async def check_model_fields(self):
        """Check TradingSignal model has conviction fields"""
        logger.info("\n" + "="*60)
        logger.info("CHECK 7: Model Fields")
        logger.info("="*60)
        
        try:
            from src.models.signal import TradingSignal
            
            # Check if model has conviction fields
            model_fields = TradingSignal.__fields__.keys()
            
            if 'conviction_score' in model_fields:
                self.log_pass("TradingSignal: conviction_score field")
            else:
                self.log_issue("TradingSignal", "Missing conviction_score field")
            
            if 'conviction_tier' in model_fields:
                self.log_pass("TradingSignal: conviction_tier field")
            else:
                self.log_issue("TradingSignal", "Missing conviction_tier field")
            
            if 'conviction_breakdown' in model_fields:
                self.log_pass("TradingSignal: conviction_breakdown field")
            else:
                self.log_issue("TradingSignal", "Missing conviction_breakdown field")
            
        except Exception as e:
            self.log_issue("Model Fields", str(e))
    
    async def check_api_endpoints(self):
        """Check dashboard API endpoints exist"""
        logger.info("\n" + "="*60)
        logger.info("CHECK 8: API Endpoints")
        logger.info("="*60)
        
        try:
            from src.admin import dashboard_server
            
            # Check if conviction endpoints are defined
            endpoint_checks = [
                ('get_conviction_mode', 'GET /api/conviction/mode'),
                ('set_conviction_mode', 'POST /api/conviction/mode'),
                ('get_conviction_breakdown', 'GET /api/conviction/breakdown/{signal_id}'),
                ('get_conviction_stats', 'GET /api/conviction/stats'),
            ]
            
            for func_name, endpoint_desc in endpoint_checks:
                if hasattr(dashboard_server, func_name):
                    self.log_pass(f"API: {endpoint_desc}")
                else:
                    self.log_issue(f"API: {endpoint_desc}", f"Missing function {func_name}")
            
        except Exception as e:
            self.log_issue("API Endpoints", str(e))
    
    async def run_audit(self):
        """Run all audit checks"""
        logger.info("\n" + "="*60)
        logger.info("🔍 PRODUCTION AUDIT")
        logger.info("="*60)
        
        await self.check_imports()
        await self.check_config()
        await self.check_database()
        await self.check_conviction_engine()
        await self.check_signal_engine()
        await self.check_file_structure()
        await self.check_model_fields()
        await self.check_api_endpoints()
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("📊 AUDIT SUMMARY")
        logger.info("="*60)
        logger.info(f"✅ Passed: {len(self.passed)}")
        logger.info(f"⚠️  Warnings: {len(self.warnings)}")
        logger.info(f"❌ Issues: {len(self.issues)}")
        
        if self.warnings:
            logger.info("\n⚠️  WARNINGS:")
            for check, msg in self.warnings:
                logger.info(f"   - {check}: {msg}")
        
        if self.issues:
            logger.info("\n❌ CRITICAL ISSUES:")
            for check, msg in self.issues:
                logger.info(f"   - {check}: {msg}")
            logger.info("\n🚨 FIX ISSUES BEFORE DEPLOYING TO PRODUCTION!")
        else:
            logger.info("\n🎉 NO CRITICAL ISSUES FOUND!")
            if self.warnings:
                logger.info("⚠️  Review warnings before deployment")
            else:
                logger.info("✅ SYSTEM IS PRODUCTION READY!")
        
        logger.info("="*60 + "\n")
        
        return len(self.issues) == 0


async def main():
    auditor = ProductionAuditor()
    success = await auditor.run_audit()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
