from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def validate_environment():
    """Validate all required environment variables are set"""
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_ADMIN_CHAT_ID',
        'TELEGRAM_FREE_CHANNEL_ID',
        'TELEGRAM_VIP_CHANNEL_ID',
        'SUPABASE_URL',
        'SUPABASE_KEY',
        'SUPABASE_SERVICE_KEY',
    ]
    
    optional_vars = [
        'STRIPE_SECRET_KEY',
        'STRIPE_PUBLISHABLE_KEY',
        'STRIPE_WEBHOOK_SECRET',
        'STRIPE_VIP_PRICE_ID',
        'NEWS_API_KEY',
    ]
    
    missing = []
    for var in required_vars:
        try:
            value = getattr(settings, var)
            if not value or value == f'your_{var.lower()}_here' or value.startswith('your_'):
                missing.append(var)
        except AttributeError:
            missing.append(var)
    
    if missing:
        logger.error(f"❌ Missing or invalid required variables: {', '.join(missing)}")
        logger.error("Please configure these in your .env file")
        return False
    
    # Warn about optional vars but don't fail
    for var in optional_vars:
        try:
            value = getattr(settings, var)
            if not value or value.startswith('your_'):
                logger.warning(f"⚠️  Optional {var} not set - some features may be limited")
        except AttributeError:
            pass
    
    logger.info("✅ All required environment variables are set")
    return True


def validate_telegram_ids():
    """Validate Telegram IDs are in correct format"""
    try:
        admin_id = settings.TELEGRAM_ADMIN_CHAT_ID
        if not admin_id.isdigit() and not admin_id.startswith('-'):
            logger.warning(f"⚠️  Admin chat ID may be invalid: {admin_id}")
            return False
        
        vip_id = settings.TELEGRAM_VIP_CHANNEL_ID
        if not (vip_id.startswith('@') or vip_id.startswith('-100')):
            logger.warning(f"⚠️  VIP channel ID format may be invalid: {vip_id}")
            return False
        
        logger.info("✅ Telegram IDs format validated")
        return True
        
    except Exception as e:
        logger.error(f"Error validating Telegram IDs: {e}")
        return False


def validate_numeric_settings():
    """Validate numeric settings are within reasonable ranges"""
    try:
        if settings.MIN_CONFIDENCE_SCORE < 0 or settings.MIN_CONFIDENCE_SCORE > 100:
            logger.error(f"❌ MIN_CONFIDENCE_SCORE must be between 0-100, got {settings.MIN_CONFIDENCE_SCORE}")
            return False
        
        if settings.MAX_SIGNALS_PER_DAY < 1 or settings.MAX_SIGNALS_PER_DAY > 50:
            logger.error(f"❌ MAX_SIGNALS_PER_DAY must be between 1-50, got {settings.MAX_SIGNALS_PER_DAY}")
            return False
        
        if settings.MIN_RISK_REWARD < 1.0:
            logger.error(f"❌ MIN_RISK_REWARD must be >= 1.0, got {settings.MIN_RISK_REWARD}")
            return False
        
        logger.info("✅ Numeric settings validated")
        return True
        
    except Exception as e:
        logger.error(f"Error validating numeric settings: {e}")
        return False


def run_all_validations():
    """Run all validation checks"""
    logger.info("Running environment validations...")
    
    checks = [
        ("Environment Variables", validate_environment()),
        ("Telegram IDs", validate_telegram_ids()),
        ("Numeric Settings", validate_numeric_settings()),
    ]
    
    failed = [name for name, result in checks if not result]
    
    if failed:
        logger.error(f"❌ Validation failed for: {', '.join(failed)}")
        return False
    
    logger.info("✅ All validations passed")
    return True
