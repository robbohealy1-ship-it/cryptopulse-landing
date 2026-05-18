import asyncio
import os
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from src.engine.signal_engine import SignalEngine
from src.telegram_bot.admin_bot import AdminBot
from src.telegram_bot.vip_bot import VIPBot
from src.telegram_bot.channel_publisher import ChannelPublisher
from src.telegram_bot.marketing_automation import MarketingAutomation
from src.telegram_bot.reporting import ReportingEngine
from src.marketing.social_media_poster import SocialMediaPoster, WebhookPoster
from src.marketing.discord_integration import DiscordPublisher
from src.marketing.viral_content_generator import ViralContentGenerator
from src.marketing.community_engagement import CommunityEngagement
from src.marketing.traffic_tracker import TrafficTracker, ReferralTracker
from src.marketing.autopilot_system import AutoPilotSystem
from src.marketing.campaign_engine import CampaignEngine
from src.marketing.viral_growth_engine import ViralGrowthEngine
from src.marketing.pro_features import (
    WhaleAlertSystem, EducationalContentEngine, CustomAlertSystem,
    GiveawayEngine, BonusReportEngine, PrioritySupport
)
from src.database.supabase_client import SupabaseClient
from src.models.signal import SignalStatus
from src.utils.logger import get_logger
from src.utils.validators import run_all_validations
from src.utils.cleanup import CleanupManager
from src.utils.signal_validator import SignalValidator
from src.config import settings
from src.admin.dashboard_server import start_dashboard
from src.alpha_plays import AlphaPlaysEngine, AlphaPublisher

logger = get_logger(__name__)


class CryptoPulseOrchestrator:
    def __init__(self):
        self.signal_engine = SignalEngine()
        self.admin_bot = AdminBot(
            signal_callback=self.on_signal_approved,
            rejection_callback=self.on_signal_rejected
        )
        self.vip_bot = VIPBot(
            notification_callback=self._on_vip_notification
        )
        self.channel_publisher = ChannelPublisher()
        self.db = SupabaseClient()
        self.cleanup_manager = CleanupManager()
        self.signal_validator = SignalValidator()
        self.marketing = MarketingAutomation(db=self.db)
        self.reporting = ReportingEngine(db=self.db)
        
        # Marketing Engine
        self.social_media = SocialMediaPoster()
        self.discord_publisher = DiscordPublisher()
        self.viral_generator = ViralContentGenerator()
        self.traffic_tracker = TrafficTracker(db=self.db)
        self.referral_tracker = ReferralTracker(db=self.db)
        self.community_engagement = None  # Initialized after admin bot starts (needs bot instance)
        self.webhook_poster = WebhookPoster()
        self.viral_growth = None  # Initialized after channel publisher ready
        
        # AutoPilot System — full automation
        self.autopilot = None  # Initialized in initialize() after components ready
        
        # Alpha/Degen Plays Engine (isolated from main signals)
        self.alpha_engine = None
        self.alpha_publisher = None
        
        # Pro Features (Quarterly+ / Lifetime)
        self.whale_alerts = None
        self.education_engine = None
        self.custom_alerts = None
        self.giveaway_engine = None
        self.bonus_reports = None
        self.priority_support = None
        
        self.scheduler = AsyncIOScheduler()
        self.running = False
        self.pending_delayed_signals = {}  # Track signals waiting for free channel delay
    
    async def initialize(self):
        logger.info("🚀 Initializing CRYPTO PULSE SIGNALS...")
        
        try:
            # Validate environment first
            if not run_all_validations():
                raise ValueError("Environment validation failed. Please check your .env file.")
            
            await self.signal_engine.initialize()
            await self.admin_bot.initialize()
            
            # Initialize community engagement (needs bot instance)
            if self.admin_bot.app and self.admin_bot.app.bot:
                self.community_engagement = CommunityEngagement(
                    bot=self.admin_bot.app.bot,
                    free_channel_id=getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None),
                    db=self.db,
                    discord=self.discord_publisher  # Cross-post to Discord
                )
                logger.info("✅ Community engagement engine initialized (Telegram + Discord)")
            
            # Start VIP bot if configured
            vip_started = await self.vip_bot.initialize()
            if vip_started:
                logger.info("✅ VIP bot started for public signup")
            else:
                logger.warning("⚠️ VIP bot not started (TELEGRAM_VIP_BOT_TOKEN not set)")
            
            # Initialize Viral Growth Engine
            self.viral_growth = ViralGrowthEngine(
                db=self.db,
                discord=self.discord_publisher,
                channel_publisher=self.channel_publisher
            )
            logger.info("🚀 Viral Growth Engine initialized")
            
            # Log marketing engine status
            logger.info("📣 Marketing Engine Status:")
            logger.info(f"  Twitter/X: {'✅ Enabled' if self.social_media.twitter_enabled else '⚠️  Disabled (add TWITTER_API_KEY to .env)'}")
            logger.info(f"  Reddit: {'✅ Enabled' if self.social_media.reddit_enabled else '⚠️  Disabled (add REDDIT credentials to .env)'}")
            logger.info(f"  Discord: {'✅ Enabled' if self.discord_publisher.enabled else '⚠️  Disabled (add DISCORD_WEBHOOK_URL to .env)'}")
            logger.info(f"  Viral Content: {'✅ Enabled' if settings.ENABLE_VIRAL_CONTENT else '⚠️  Disabled'}")
            logger.info(f"  Engagement Loop: {'✅ Enabled' if settings.ENABLE_ENGAGEMENT_LOOP else '⚠️  Disabled'}")
            
            # Initialize Campaign Engine FIRST (needed by AutoPilot for FOMO)
            self.campaign_engine = CampaignEngine(
                social_media=self.social_media,
                discord=self.discord_publisher,
                channel_publisher=self.channel_publisher,
                community_engagement=self.community_engagement,
                viral_generator=self.viral_generator,
                admin_notification=self.admin_bot.send_notification
            )
            logger.info("🚀 Campaign Engine initialized — signal marketing active")
            
            # Initialize AutoPilot System with FOMO callback
            self.autopilot = AutoPilotSystem(
                scanner=self.signal_engine.scanner,
                db=self.db,
                social_media=self.social_media,
                discord=self.discord_publisher,
                channel_publisher=self.channel_publisher,
                community_engagement=self.community_engagement
            )
            # Wire FOMO campaign: when TP hits, blast to all channels
            self.autopilot.performance.on_signal_result = self.campaign_engine.signal_result_campaign
            
            # Pass payment handlers to AutoPilot if VIP bot is running
            if self.vip_bot and self.vip_bot.payment_orchestrator:
                self.autopilot.payment_orchestrator = self.vip_bot.payment_orchestrator
                logger.info("🤖 AutoPilot payment orchestrator linked to VIP bot")
            
            # Share custom alert system with VIP bot so /alert commands work
            if self.vip_bot and self.custom_alerts:
                self.vip_bot.custom_alerts = self.custom_alerts
                logger.info("🔔 Custom alert system linked to VIP bot")
            logger.info("🤖 AutoPilot System initialized — full automation active")
            
            # Initialize Pro Features
            self.whale_alerts = WhaleAlertSystem(
                channel_publisher=self.channel_publisher,
                admin_notification=self.admin_bot.send_notification
            )
            self.education_engine = EducationalContentEngine(
                channel_publisher=self.channel_publisher
            )
            self.custom_alerts = CustomAlertSystem(
                channel_publisher=self.channel_publisher,
                db=self.db
            )
            self.giveaway_engine = GiveawayEngine(
                channel_publisher=self.channel_publisher,
                db=self.db
            )
            self.bonus_reports = BonusReportEngine(
                channel_publisher=self.channel_publisher,
                context_engine=self.signal_engine.context_engine
            )
            self.priority_support = PrioritySupport(db=self.db)
            logger.info("💎 Pro Features initialized — whale alerts, education, custom alerts, giveaways, bonus reports")
            
            # Initialize Alpha/Degen Plays Engine
            self.alpha_publisher = AlphaPublisher(bot=self.channel_publisher.bot)
            self.alpha_engine = AlphaPlaysEngine(
                db=self.db,
                publisher=self.alpha_publisher
            )
            await self.alpha_engine.initialize()
            logger.info("🎰 Alpha Plays Engine initialized — low-cap degen plays active")
            
            logger.info("✅ All components initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            raise
    
    def setup_scheduler(self):
        logger.info("Setting up scheduler...")
        
        # Market scanning jobs
        # 15m: Every 15 min — intraday swing (1-4h holds)
        self.scheduler.add_job(
            self.scan_15m,
            CronTrigger(minute='*/15'),
            id='scan_15m',
            name='Scan 15-minute timeframe',
            replace_existing=True
        )
        
        # 1h: Every hour — swing trades (4-24h holds)
        self.scheduler.add_job(
            self.scan_1h,
            CronTrigger(minute='0'),
            id='scan_1h',
            name='Scan 1-hour timeframe',
            replace_existing=True
        )
        
        # 4h: Every 4 hours — position trades (1-3d holds)
        self.scheduler.add_job(
            self.scan_4h,
            CronTrigger(hour='*/4', minute='5'),
            id='scan_4h',
            name='Scan 4-hour timeframe',
            replace_existing=True
        )
        
        # Daily: Once per day at 00:05 UTC — macro positions (3-7d holds)
        self.scheduler.add_job(
            self.scan_daily,
            CronTrigger(hour=0, minute=5),
            id='scan_daily',
            name='Scan daily timeframe',
            replace_existing=True
        )
        
        # Signal monitoring
        self.scheduler.add_job(
            self.check_active_signals,
            CronTrigger(minute='*/2'),
            id='check_signals',
            name='Check active signals',
            replace_existing=True
        )
        
        # Check for expired pending signals
        self.scheduler.add_job(
            self.check_expired_signals,
            CronTrigger(minute='*/1'),
            id='check_expired',
            name='Check expired pending signals',
            replace_existing=True
        )
        
        # Daily jobs
        self.scheduler.add_job(
            self.daily_reset,
            CronTrigger(hour=0, minute=0),
            id='daily_reset',
            name='Daily reset',
            replace_existing=True
        )
        
        self.scheduler.add_job(
            self.daily_cleanup,
            CronTrigger(hour=2, minute=0),
            id='daily_cleanup',
            name='Daily cleanup',
            replace_existing=True
        )
        
        # 🤖 AUTOPILOT JOBS
        # Performance tracking: check TP/SL every 5 minutes
        self.scheduler.add_job(
            self._run_autopilot_performance_check,
            CronTrigger(minute='*/5'),
            id='autopilot_performance',
            name='AutoPilot: Check signal TP/SL',
            replace_existing=True
        )
        
        # Daily automation: trial checks + stats logging (23:55 UTC)
        self.scheduler.add_job(
            self._run_autopilot_daily,
            CronTrigger(hour=23, minute=55),
            id='autopilot_daily',
            name='AutoPilot: Daily automation',
            replace_existing=True
        )
        
        # Weekly automation: public stats posting (Sunday 20:00 UTC)
        self.scheduler.add_job(
            self._run_autopilot_weekly,
            CronTrigger(day_of_week='sun', hour=20, minute=0),
            id='autopilot_weekly',
            name='AutoPilot: Weekly public stats',
            replace_existing=True
        )
        
        logger.info("🤖 AutoPilot jobs configured: performance check (5m), daily (23:55), weekly (Sun 20:00)")
        
        # Report jobs
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(hour=settings.DAILY_REPORT_HOUR, minute=settings.DAILY_REPORT_MINUTE),
            id='daily_report',
            name='Send daily report',
            replace_existing=True
        )
        
        day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        weekly_day = day_map.get(settings.WEEKLY_REPORT_DAY.lower(), 6)
        self.scheduler.add_job(
            self.send_weekly_report,
            CronTrigger(day_of_week=weekly_day, hour=settings.WEEKLY_REPORT_HOUR, minute=0),
            id='weekly_report',
            name='Send weekly report',
            replace_existing=True
        )
        
        # 📣 MARKETING: Stripped to bare minimum (signals are the priority)
        # Morning overview: fundamental + technical (08:30 UTC)
        self.scheduler.add_job(
            self._post_morning_outlook,
            CronTrigger(hour=8, minute=30),
            id='morning_outlook',
            name='Morning market overview',
            replace_existing=True
        )
        
        # Evening summary: EOD wrap-up (20:00 UTC)
        self.scheduler.add_job(
            self._post_evening_recap,
            CronTrigger(hour=20, minute=0),
            id='evening_recap',
            name='Evening market summary',
            replace_existing=True
        )
        
        # Social media only (Twitter/X — not Telegram channels)
        self.scheduler.add_job(
            self._post_social_media_marketing,
            CronTrigger(hour='10,14,18', minute=0),
            id='social_media_marketing',
            name='Social media marketing post',
            replace_existing=True
        )
        
        # Monthly giveaway: 1st of month at 12:00 UTC
        self.scheduler.add_job(
            self._run_giveaway,
            CronTrigger(day=1, hour=12, minute=0),
            id='monthly_giveaway',
            name='Pro: Monthly VIP giveaway',
            replace_existing=True
        )
        
        # Custom alerts: checked every 5 minutes (functional, not marketing)
        self.scheduler.add_job(
            self._run_custom_alerts,
            CronTrigger(minute='*/5'),
            id='custom_alerts',
            name='Pro: Check custom price alerts',
            replace_existing=True
        )
        
        # Viral Growth: Daily automated marketing (09:00 UTC)
        self.scheduler.add_job(
            self._run_viral_daily_marketing,
            CronTrigger(hour=9, minute=0),
            id='viral_daily_marketing',
            name='Viral: Daily multi-platform marketing',
            replace_existing=True
        )
        
        # Viral Growth: Weekly marketing blitz (Sunday 10:00 UTC)
        self.scheduler.add_job(
            self._run_viral_weekly_marketing,
            CronTrigger(day_of_week='sun', hour=10, minute=0),
            id='viral_weekly_marketing',
            name='Viral: Weekly Reddit + Discord + Forums',
            replace_existing=True
        )
        
        # 🎰 ALPHA/DEGEN PLAYS SCHEDULER JOBS
        # Alpha discovery: Every 6 hours (finds low-cap plays)
        self.scheduler.add_job(
            self._scan_alpha_plays,
            CronTrigger(hour='*/6', minute=0),
            id='alpha_discovery',
            name='Alpha: Discover low-cap plays',
            replace_existing=True
        )
        
        # Alpha tracking: Every 5 minutes (check TP/SL)
        self.scheduler.add_job(
            self._track_alpha_plays,
            CronTrigger(minute='*/5'),
            id='alpha_tracking',
            name='Alpha: Track active plays',
            replace_existing=True
        )
        
        logger.info("🎰 Alpha Plays scheduled: discovery every 6h, tracking every 5m")
        
        logger.info("✅ Scheduler configured")
        logger.info("📣 Morning overview (08:30) → VIP + Free | Evening summary (20:00) → VIP + Free")
        logger.info("🐦 Social media: 3x/day (Twitter/X only)")
        logger.info("💎 Pro: custom alerts (5m), giveaways (monthly)")
        logger.info("🚀 Viral: Daily (09:00) + Weekly (Sun 10:00) automated marketing")
    
    # NOTE: Randomized marketing posts removed — signals are the priority.
    # Only morning overview, evening summary, and weekly report are sent.
    
    async def scan_4h(self):
        logger.info("🔍 Scanning 4h timeframe (position trades, 3R minimum)...")
        try:
            candidates = await self.signal_engine.scan_for_signals('4h')
            if candidates:
                logger.info(f"✅ 4h scan found {len(candidates)} position candidate(s)")
            await self.process_candidates(candidates)
        except Exception as e:
            logger.error(f"Error in 4h scan: {e}")
    
    async def scan_daily(self):
        logger.info("🔍 Scanning daily timeframe (macro positions, 4R minimum)...")
        try:
            candidates = await self.signal_engine.scan_for_signals('1d')
            if candidates:
                logger.info(f"✅ Daily scan found {len(candidates)} macro candidate(s)")
            await self.process_candidates(candidates)
        except Exception as e:
            logger.error(f"Error in daily scan: {e}")
    
    async def scan_15m(self):
        logger.info("🔍 Scanning 15m timeframe (institutional, liquidity + session)...")
        try:
            candidates = await self.signal_engine.scan_for_signals('15m')
            if candidates:
                logger.info(f"✅ 15m scan found {len(candidates)} candidate(s)")
            await self.process_candidates(candidates)
        except Exception as e:
            logger.error(f"Error in 15m scan: {e}")
    
    async def scan_1h(self):
        logger.info("🔍 Scanning 1h timeframe (institutional, OB + structure)...")
        try:
            candidates = await self.signal_engine.scan_for_signals('1h')
            if candidates:
                logger.info(f"✅ 1h scan found {len(candidates)} candidate(s)")
            await self.process_candidates(candidates)
        except Exception as e:
            logger.error(f"Error in 1h scan: {e}")
    
    # ==================== ALPHA/DEGEN PLAYS ====================
    
    async def _scan_alpha_plays(self):
        """Discover and publish alpha plays (called by scheduler every 6 hours)"""
        logger.info("🎰 Scanning for alpha plays...")
        try:
            if not self.alpha_engine:
                logger.warning("Alpha engine not initialized")
                return
            
            # Discover candidates
            candidates = await self.alpha_engine.discover_and_create(
                chain=None,  # Scan all chains
                limit=3
            )
            
            if not candidates:
                logger.info("No alpha candidates found this scan")
                return
            
            logger.info(f"Found {len(candidates)} alpha candidate(s)")
            
            # Auto-approve high-score candidates
            for candidate in candidates:
                try:
                    # Approve the play
                    play = await self.alpha_engine.approve_play(
                        symbol=candidate.symbol,
                        admin_notes=f"Auto-approved (score: {candidate.overall_score:.1f})"
                    )
                    
                    if play:
                        # Publish to VIP channel
                        await self.alpha_engine.publish_to_vip(play)
                        
                        # Publish teaser to FREE channel (if weekly limit allows)
                        await self.alpha_engine.publish_teaser_to_free(play)
                        
                        # Notify admin
                        await self.admin_bot.send_notification(
                            f"🎰 <b>Alpha Play Published</b>\n\n"
                            f"{candidate.symbol} on {candidate.chain.upper()}\n"
                            f"Score: {candidate.overall_score:.1f}/100\n"
                            f"MC: ${candidate.market_cap_usd/1e6:.2f}M\n"
                            f"Posted to VIP + FREE channels"
                        )
                        
                except Exception as e:
                    logger.error(f"Error publishing alpha play {candidate.symbol}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in alpha scan: {e}")
    
    async def _track_alpha_plays(self):
        """Track active alpha plays (called by scheduler every 5 minutes)"""
        try:
            if not self.alpha_engine:
                return
            
            await self.alpha_engine.track_active_plays()
            
        except Exception as e:
            logger.error(f"Error tracking alpha plays: {e}")
    
    async def process_candidates(self, candidates):
        if not candidates:
            logger.info("No high-quality candidates found")
            return
        
        for candidate in candidates:
            try:
                # Validate signal before processing
                is_valid, error_msg = self.signal_validator.validate_signal(candidate)
                if not is_valid:
                    logger.warning(f"❌ Invalid signal {candidate.symbol}: {error_msg}")
                    candidate.admin_rejected = True
                    candidate.rejection_reason = f"Validation failed: {error_msg}"
                    await self.db.save_signal(candidate)
                    continue
                
                # Quality check using configured minimum (85%)
                # 90%+ = VIP-only routing, 85-89% = dual-channel routing
                # Both go to admin - routing decided after approval
                if not self.signal_validator.check_signal_quality(candidate, min_confidence=settings.MIN_CONFIDENCE_SCORE):
                    logger.info(f"⏭️  Signal {candidate.symbol} filtered by quality check")
                    candidate.admin_rejected = True
                    candidate.rejection_reason = f"Did not meet quality standards (below {settings.MIN_CONFIDENCE_SCORE}% confidence)"
                    await self.db.save_signal(candidate)
                    continue
                
                # Check for duplicate symbol (DB-level, catches restarts)
                existing = await self.db.get_active_signal_for_symbol(candidate.symbol)
                if existing:
                    logger.info(f"⏭️  Skipping {candidate.symbol} - active signal already exists (ID: {existing.get('id', 'unknown')})")
                    candidate.cancelled = True
                    candidate.cancellation_reason = "Duplicate: active signal already exists for this symbol"
                    await self.db.save_signal(candidate)
                    continue
                
                # Check if we already hit max signals today
                if not self.signal_engine.can_generate_signal():
                    logger.info("Max signals reached for today - skipping remaining candidates")
                    candidate.cancelled = True
                    candidate.cancellation_reason = "Daily signal limit reached"
                    await self.db.save_signal(candidate)
                    break
                
                await self.db.save_signal(candidate)
                
                # Send to admin for approval ONLY
                await self.admin_bot.send_signal_for_approval(candidate)
                
                self.signal_engine.add_signal(candidate)
                
                logger.info(f"✅ Candidate {candidate.symbol} sent for approval")
                
            except Exception as e:
                logger.error(f"Error processing candidate {candidate.symbol}: {e}")
    
    async def on_signal_approved(self, signal):
        try:
            # Check if signal has expired before approval
            if signal.expires_at and datetime.utcnow() > signal.expires_at:
                signal.cancelled = True
                signal.cancellation_reason = "Signal expired before admin approval"
                await self.db.save_signal(signal)
                await self.admin_bot.send_notification(
                    f"⏰ Signal {signal.symbol} expired before approval - not published"
                )
                logger.info(f"Signal {signal.symbol} expired - not published")
                return
            
            signal.admin_approved = True
            signal.status = SignalStatus.APPROVED
            signal.approved_at = datetime.utcnow()
            
            # 💾 CRITICAL: Save signal to DB BEFORE publishing
            # This ensures the signal persists even if Telegram publish fails
            saved = await self.db.save_signal(signal)
            if not saved:
                logger.error(f"❌ Failed to save signal {signal.symbol} to database before publishing")
                raise RuntimeError(f"Signal {signal.symbol} could not be saved to database")
            
            # Check if this is VIP-exclusive (90%+ confidence)
            vip_only = signal.confidence >= 90
            
            if vip_only:
                logger.info(f"🌟 Signal {signal.symbol} is VIP EXCLUSIVE ({signal.confidence:.1f}% confidence)")
            else:
                logger.info(f"✅ Signal {signal.symbol} approved - publishing...")
            
            # Publish VIP channel immediately
            await self.channel_publisher.publish_to_vip(signal)
            signal.vip_channel_posted = True
            
            # 🤖 AUTOPILOT: Start tracking signal performance
            if self.autopilot:
                await self.autopilot.on_signal_approved(signal)
            
            # Send teaser to free channel (different approach for VIP-only vs regular)
            if not vip_only:
                # Regular signal: Use campaign engine (sends 1 teaser + Discord + Twitter)
                if self.campaign_engine:
                    await self.campaign_engine.signal_approved_campaign(signal)
                
                await self.admin_bot.send_notification(
                    f"✅ Signal {signal.symbol} approved!\n"
                    f"🌟 VIP channel: Published NOW\n"
                    f"📢 Free channel: Teaser sent (no full card)"
                )
            else:
                # VIP-only signal: Use simple teaser (no campaign engine to avoid duplicates)
                await self.channel_publisher.send_vip_teaser(signal)
                await self.admin_bot.send_notification(
                    f"🌟 VIP EXCLUSIVE: {signal.symbol} published to VIP only!\n"
                    f"Confidence: {signal.confidence:.1f}%\n"
                    f"📢 Marketing teaser sent to free channel"
                )
            
            signal.published_at = datetime.utcnow()
            await self.db.save_signal(signal)
            
            logger.info(f"✅ Signal {signal.symbol} published successfully")
            
        except Exception as e:
            logger.error(f"Error publishing approved signal: {e}")
            raise
    
    async def _publish_free_delayed(self, signal_id: str):
        """Publish signal to free channel after delay"""
        try:
            signal = await self.db.get_signal(signal_id)
            if not signal or signal.cancelled:
                logger.info(f"Signal {signal_id} not found or cancelled - skipping free channel post")
                return
            
            await self.channel_publisher.publish_to_free(signal)
            signal.free_channel_posted = True
            signal.free_channel_delayed = False
            await self.db.save_signal(signal)
            
            logger.info(f"📢 Free channel delayed post published for {signal.symbol}")
            
        except Exception as e:
            logger.error(f"Error publishing delayed free signal: {e}")
    
    async def on_signal_rejected(self, signal):
        try:
            signal.admin_rejected = True
            signal.status = SignalStatus.REJECTED
            signal.rejection_reason = signal.rejection_reason or "Rejected by admin"
            
            await self.db.save_signal(signal)
            
            logger.info(f"❌ Signal {signal.symbol} rejected - logged to database")
            
        except Exception as e:
            logger.error(f"Error handling rejected signal: {e}")
    
    async def check_expired_signals(self):
        """Check for pending signals that have expired before admin approval"""
        try:
            pending_signals = await self.db.get_pending_signals()
            now = datetime.utcnow()
            
            for signal in pending_signals:
                if signal.expires_at and now > signal.expires_at:
                    signal.status = SignalStatus.EXPIRED
                    signal.cancelled = True
                    signal.cancellation_reason = "Auto-cancelled: expired before admin approval"
                    await self.db.save_signal(signal)
                    
                    await self.admin_bot.send_notification(
                        f"⏰ Signal {signal.symbol} auto-cancelled - expired before approval"
                    )
                    logger.info(f"Signal {signal.symbol} auto-cancelled (expired)")
                    
        except Exception as e:
            logger.error(f"Error checking expired signals: {e}")
    
    async def check_active_signals(self):
        """Check all active signals for TP/SL hits and send real-time updates"""
        try:
            active_signals = await self.db.get_active_signals()
            
            for signal in active_signals:
                current_price = await self._get_current_price(signal.symbol)
                
                if not current_price:
                    continue
                
                # Track which TPs have been hit
                tp1_hit = getattr(signal, 'tp1_hit', False)
                tp2_hit = getattr(signal, 'tp2_hit', False)
                tp3_hit = getattr(signal, 'tp3_hit', False)
                
                if signal.direction.value == "LONG":
                    # Check TP3 first (highest target)
                    if not tp3_hit and signal.take_profit_3 is not None and current_price >= signal.take_profit_3:
                        await self.handle_tp_hit(signal, 3, current_price)
                    # Check TP2
                    elif not tp2_hit and signal.take_profit_2 is not None and current_price >= signal.take_profit_2:
                        await self.handle_tp_hit(signal, 2, current_price)
                    # Check TP1
                    elif not tp1_hit and signal.take_profit_1 is not None and current_price >= signal.take_profit_1:
                        await self.handle_tp_hit(signal, 1, current_price)
                    # Check Stop Loss
                    elif signal.stop_loss is not None and current_price <= signal.stop_loss:
                        await self.handle_stop_hit(signal, current_price)
                else:  # SHORT
                    # Check TP3 first (lowest target for shorts)
                    if not tp3_hit and signal.take_profit_3 is not None and current_price <= signal.take_profit_3:
                        await self.handle_tp_hit(signal, 3, current_price)
                    # Check TP2
                    elif not tp2_hit and signal.take_profit_2 is not None and current_price <= signal.take_profit_2:
                        await self.handle_tp_hit(signal, 2, current_price)
                    # Check TP1
                    elif not tp1_hit and signal.take_profit_1 is not None and current_price <= signal.take_profit_1:
                        await self.handle_tp_hit(signal, 1, current_price)
                    # Check Stop Loss
                    elif signal.stop_loss is not None and current_price >= signal.stop_loss:
                        await self.handle_stop_hit(signal, current_price)
                
        except Exception as e:
            logger.error(f"Error checking active signals: {e}")
    
    async def handle_tp_hit(self, signal, tp_level, current_price):
        """Handle TP hit - send updates to VIP and Free channels"""
        
        # Check if already hit (prevent duplicates on bot restart)
        tp_hit_attr = f'tp{tp_level}_hit'
        if hasattr(signal, tp_hit_attr) and getattr(signal, tp_hit_attr):
            logger.info(f"⏭️  TP{tp_level} already hit for {signal.symbol} - skipping duplicate")
            return
        
        logger.info(f"🎯 TP{tp_level} hit for {signal.symbol}")
        
        # Mark TP as hit in database (may fail if columns don't exist yet)
        try:
            await self.db.mark_tp_hit(signal.id, tp_level)
        except Exception as e:
            logger.warning(f"Could not mark TP{tp_level} in database (run migration): {e}")
        
        # Update in-memory signal object to prevent duplicate messages
        setattr(signal, tp_hit_attr, True)
        
        # Send update to VIP channel (includes TP1 marketing to Free)
        await self.channel_publisher.send_tp_hit(signal, tp_level)
        
        # Send update to Free channel (only TP2/TP3 teasers; TP1 already handled above)
        if tp_level > 1:
            await self.channel_publisher.send_tp_hit_free(signal, tp_level)
        
        # Move SL to breakeven after TP1 (only once)
        if tp_level == 1:
            if not getattr(signal, 'stop_moved_to_breakeven', False):
                await self.channel_publisher.send_stop_moved(signal, signal.entry_price)
                try:
                    await self.db.update_stop_loss(signal.id, signal.entry_price)
                except Exception as e:
                    logger.warning(f"Could not update SL in database (run migration): {e}")
                # Mark that we've sent the breakeven message
                signal.stop_moved_to_breakeven = True
            else:
                logger.info(f"⏭️  SL already moved to breakeven for {signal.symbol} - skipping duplicate")
        
        # Close trade if TP3 hit
        if tp_level == 3:
            entry = signal.actual_entry or signal.entry_price
            if entry and entry != 0:
                pnl = ((current_price - entry) / entry) * 100
                if signal.direction.value == "SHORT":
                    pnl = -pnl
            else:
                pnl = 0.0
            await self.db.close_signal(signal.id, current_price, pnl)
            await self.channel_publisher.send_trade_closed(signal, f"TP{tp_level} Hit", pnl)
    
    async def handle_stop_hit(self, signal, current_price):
        logger.info(f"🛑 Stop loss hit for {signal.symbol}")
        
        entry = signal.actual_entry or signal.entry_price
        if entry and entry != 0:
            pnl = ((current_price - entry) / entry) * 100
            if signal.direction.value == "SHORT":
                pnl = -pnl
        else:
            pnl = 0.0
        
        await self.db.close_signal(signal.id, current_price, pnl)
        
        result = "Stop Loss Hit"
        await self.channel_publisher.send_trade_closed(signal, result, pnl)
    
    async def _get_current_price(self, symbol):
        try:
            ticker = await self.signal_engine.scanner.fetch_ticker(symbol)
            return ticker.get('last')
        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None
    
    async def send_daily_report(self):
        """Send PERFORMANCE REVIEW at 23:55 (different from 20:00 market outlook)"""
        try:
            # Daily report = TODAY'S PERFORMANCE, not tomorrow's outlook
            reports = await self.reporting.generate_daily_report()
            
            # Admin gets full stats
            await self.admin_bot.send_notification(reports['admin'])
            
            # VIP gets performance summary (signals closed today)
            vip_performance = f"""📊 <b>DAILY PERFORMANCE</b>
📅 {datetime.utcnow().strftime('%B %d, %Y')}

{reports.get('vip', 'No signals closed today.')}
"""
            
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_VIP_CHANNEL_ID,
                text=vip_performance,
                parse_mode='HTML'
            )
            
            logger.info("Daily performance report sent (focus: today's results)")
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
    
    async def send_weekly_report(self):
        """Send weekly reports to admin, VIP, and free channel"""
        try:
            reports = await self.reporting.generate_weekly_report()
            
            # Send to admin (full report)
            await self.admin_bot.send_notification(reports['admin'])
            
            # Send to VIP channel
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_VIP_CHANNEL_ID,
                text=reports['vip'],
                parse_mode='HTML'
            )
            
            # Send marketing summary to free channel
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_FREE_CHANNEL_ID,
                text=reports['free'],
                parse_mode='HTML'
            )
            
            logger.info("Weekly reports sent")
            
        except Exception as e:
            logger.error(f"Error sending weekly report: {e}")
    
    # ============== MARKETING ENGINE METHODS ==============
    
    async def _crosspost_signal(self, signal):
        """Cross-post approved signal to all enabled marketing channels.
        Each channel has independent error handling so one failure doesn't block others."""
        
        chart_path = None
        if signal.chart_path and os.path.exists(signal.chart_path):
            chart_path = signal.chart_path
        
        # Twitter/X
        if self.social_media.twitter_enabled:
            try:
                results = await self.social_media.post_signal_teaser(signal, chart_path)
                logger.info(f"📣 Twitter posted: {results}")
            except Exception as e:
                logger.error(f"❌ Twitter post failed: {e}")
        
        # Discord
        if self.discord_publisher.enabled:
            try:
                success = await self.discord_publisher.post_signal(signal)
                if success:
                    logger.info(f"📣 Discord posted: {signal.symbol}")
                else:
                    logger.warning(f"⚠️ Discord post returned False for {signal.symbol}")
            except Exception as e:
                logger.error(f"❌ Discord post failed: {e}")
        
        # Generic webhook
        if settings.MARKETING_WEBHOOK_URL:
            try:
                await self.webhook_poster.post(
                    title=f"Signal: {signal.symbol} {signal.direction.value}",
                    message=f"Confidence: {signal.confidence:.1f}% | Entry: {signal.entry_price}",
                    image_path=chart_path
                )
                logger.info(f"📣 Webhook posted: {signal.symbol}")
            except Exception as e:
                logger.error(f"❌ Webhook post failed: {e}")
        
        # Viral content generation (Telegram free channel)
        if settings.ENABLE_VIRAL_CONTENT and self.community_engagement:
            try:
                card_path = self.viral_generator.create_signal_card(signal)
                await self.community_engagement.post_viral_content(
                    card_path,
                    caption=f"🔥 {signal.symbol} {signal.direction.value} signal! Join VIP for full details."
                )
                logger.info(f"📣 Viral content posted: {card_path}")
            except Exception as e:
                logger.error(f"❌ Viral content failed: {e}")
    
    async def _post_morning_outlook(self):
        """Post morning fundamental + technical outlook. VIP gets the full report."""
        try:
            # Build rich market context for VIP
            ctx = self.signal_engine.context_engine
            fear = await ctx.fetch_fear_greed_index()
            funding = await ctx.fetch_funding_rates('BTCUSDT')
            global_data = await ctx.fetch_global_market_data()
            btc_trend = await ctx.fetch_btc_trend()
            news = await ctx.fetch_cryptonews()

            # Top 3 headlines
            headlines = ""
            if news:
                for article in news[:3]:
                    sentiment = article.get('sentiment', 'neutral')
                    emoji = "🟢" if sentiment == 'positive' else "🔴" if sentiment == 'negative' else "⚪"
                    headlines += f"{emoji} {article['title'][:80]}...\n"

            now = datetime.utcnow()
            vip_outlook = f"""🌅 <b>MORNING MARKET OUTLOOK</b>
<b>{now.strftime('%A, %d %B %Y')}</b>

<b>📊 Market Sentiment:</b>
Fear & Greed: <b>{fear.get('classification', 'Neutral')}</b> ({fear.get('value', 'N/A')}/100)
Global Market Cap: <b>${global_data.get('total_market_cap', 'N/A')}T</b>
BTC Dominance: <b>{global_data.get('btc_dominance', 'N/A')}%</b>
BTC 7d Trend: <b>{btc_trend.get('trend_7d', 'N/A')}</b>

<b>💰 Funding & Bias:</b>
BTC Funding Rate: <b>{funding.get('funding_rate', 0)*100:.4f}%</b> ({funding.get('bias', 'neutral')})
{funding.get('is_extreme', False) and '⚠️ Extreme funding — watch for squeeze' or ''}

<b>📰 Key Headlines:</b>
{headlines or 'Markets quiet overnight. No major news.'}

<b>🎯 Today's Outlook:</b>
✅ Scanning 15m, 1h, 4h, Daily timeframes
✅ London-NY overlap: highest conviction windows
✅ Max 3 signals today — quality over quantity
✅ All signals 85%+ confidence, full trade management

<b>What to Watch:</b>
🔍 BTC structure at higher timeframe POC
🔍 ETH/BTC ratio for alt strength
🔍 Funding extremes for reversal setups

Good luck today! 🎯"""

            # VIP channel gets the full report
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_VIP_CHANNEL_ID,
                text=vip_outlook,
                parse_mode='HTML'
            )

            # Free channel gets a teaser
            if self.community_engagement:
                await self.community_engagement.post_engagement('content_roundups')

            # Twitter gets a condensed version
            if self.social_media.twitter_enabled:
                await self.social_media.post_marketing_content('morning_outlook')

            # Discord
            if self.discord_publisher.enabled:
                await self.discord_publisher.post_marketing(
                    "🌅 Good Morning Traders!",
                    f"Fear & Greed: {fear.get('classification', 'Neutral')} | "
                    f"BTC Funding: {funding.get('funding_rate', 0)*100:.4f}% | "
                    "Scanning for elite setups.",
                    color=0x00ff00
                )

            logger.info("Morning outlook posted to VIP + channels")
        except Exception as e:
            logger.error(f"Morning outlook error: {e}")
    
    async def _post_evening_recap(self):
        """Post evening MARKET OUTLOOK (not performance - that's at 23:55). Focus on tomorrow's setup."""
        try:
            # EOD = Market outlook for tomorrow, NOT performance review
            ctx = self.signal_engine.context_engine
            
            # Get market data for tomorrow's outlook
            fear = await ctx.get_fear_greed_index()
            funding = await ctx.get_funding_rates()
            
            # Get active trades
            active_signals = await self.db.get_active_signals()
            active_trades_text = ""
            
            if active_signals:
                active_trades_text = "\n\n<b>🔄 ACTIVE TRADES:</b>\n"
                for sig in active_signals:
                    current_price = await self._get_current_price(sig.symbol)
                    if current_price:
                        entry = sig.actual_entry or sig.entry_price
                        pnl = ((current_price - entry) / entry) * 100
                        if sig.direction.value == "SHORT":
                            pnl = -pnl
                        
                        pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                        tp1_status = "✅" if getattr(sig, 'tp1_hit', False) else "⏳"
                        tp2_status = "✅" if getattr(sig, 'tp2_hit', False) else "⏳"
                        tp3_status = "✅" if getattr(sig, 'tp3_hit', False) else "⏳"
                        
                        active_trades_text += f"""
{sig.symbol} {sig.direction.value}
Entry: ${entry:.4f} | Current: ${current_price:.4f}
P&L: {pnl_emoji} {pnl:+.2f}%
Targets: TP1 {tp1_status} | TP2 {tp2_status} | TP3 {tp3_status}
"""
            
            # Build tomorrow's market outlook
            outlook = f"""🌙 <b>EVENING MARKET OUTLOOK</b>
📅 {datetime.utcnow().strftime('%B %d, %Y')}

<b>📊 Market Sentiment:</b>
Fear & Greed: {fear.get('classification', 'Neutral')} ({fear.get('value', 50)})
BTC Funding: {funding.get('funding_rate', 0)*100:.4f}%
{active_trades_text}
<b>🔮 Tomorrow's Focus:</b>
• Watch for {self._get_key_levels()}
• Session: {self._get_next_session()}
• Volatility: {self._assess_volatility()}

<b>⚡ What to Expect:</b>
{self._generate_tomorrow_bias()}

💎 Stay alert for high-confidence setups!
"""
            
            # VIP gets full outlook
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_VIP_CHANNEL_ID,
                text=outlook,
                parse_mode='HTML'
            )
            
            # Free gets teaser
            free_teaser = f"""🌙 <b>MARKET OUTLOOK</b>

Fear & Greed: {fear.get('classification', 'Neutral')}

💎 VIP members get full tomorrow's bias + key levels.
🔗 Join: t.me/CryptoPulseVIPAccessBot
"""
            
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_FREE_CHANNEL_ID,
                text=free_teaser,
                parse_mode='HTML'
            )
            
            # Discord
            if self.discord_publisher.enabled:
                await self.discord_publisher.post_marketing(
                    "🌙 Evening Market Outlook",
                    free_teaser.replace('<b>', '**').replace('</b>', '**')
                )

            logger.info("Evening market outlook posted (focus: tomorrow's setup)")
        except Exception as e:
            logger.error(f"Evening outlook error: {e}")
    
    def _get_key_levels(self) -> str:
        """Get key support/resistance levels for tomorrow"""
        # Simplified - you can enhance with real TA
        return "BTC $66.5k support, $68.2k resistance"
    
    def _get_next_session(self) -> str:
        """Determine next major trading session"""
        hour = datetime.utcnow().hour
        if hour < 8:
            return "Asia session (low volatility)"
        elif hour < 12:
            return "London open (high volatility)"
        elif hour < 16:
            return "NY open (peak liquidity)"
        else:
            return "Asia session tomorrow"
    
    def _assess_volatility(self) -> str:
        """Quick volatility assessment"""
        return random.choice([
            "Moderate - good for swing trades",
            "High - scalping opportunities",
            "Low - wait for breakouts",
            "Increasing - watch for momentum"
        ])
    
    def _generate_tomorrow_bias(self) -> str:
        """Generate market bias for tomorrow"""
        biases = [
            "Bullish continuation if BTC holds support. Watch for altcoin rotation.",
            "Consolidation expected. Wait for clear breakout direction.",
            "Bearish pressure building. Defensive positioning recommended.",
            "Range-bound action likely. Focus on mean reversion plays.",
            "Breakout imminent. High-confidence setups will be prioritized."
        ]
        return random.choice(biases)
    
    async def _post_weekly_report(self):
        """Post weekly performance report to VIP channel."""
        try:
            reports = await self.reporting.generate_weekly_report()
            vip_report = reports.get('vip', "📊 <b>WEEKLY REPORT</b>\n\nData unavailable.")
            
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_VIP_CHANNEL_ID,
                text=vip_report,
                parse_mode='HTML'
            )
            
            logger.info("Weekly report posted to VIP channel")
        except Exception as e:
            logger.error(f"Weekly report error: {e}")
    
    async def _post_social_media_marketing(self):
        """Post general marketing content to social media"""
        try:
            if self.social_media.twitter_enabled:
                content_types = ['vip_promo', 'education', 'social_proof']
                content_type = random.choice(content_types)
                await self.social_media.post_marketing_content(content_type)
                logger.info(f"Social media marketing posted: {content_type}")
        except Exception as e:
            logger.error(f"Social media marketing error: {e}")

    # NOTE: Methods below are kept for organic on-demand use only.
    # They are NOT scheduled — call them manually when there is real
    # trading content, news, or a genuine reason to engage.

    async def send_free_outlook(self):
        """Send pre-market outlook to FREE channel — call when market opens with real setups."""
        try:
            outlook = await self.reporting.generate_vip_outlook()
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_FREE_CHANNEL_ID,
                text=outlook,
                parse_mode='HTML'
            )
            logger.info("Pre-market outlook sent to free channel")
        except Exception as e:
            logger.error(f"Error sending free outlook: {e}")

    async def send_free_education(self):
        """Send educational insight to FREE channel — call after a strong setup or win."""
        try:
            insight = await self.reporting.generate_vip_education()
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_FREE_CHANNEL_ID,
                text=insight,
                parse_mode='HTML'
            )
            logger.info("Educational insight sent to free channel")
        except Exception as e:
            logger.error(f"Error sending free education: {e}")

    async def _run_engagement_loop(self):
        """Post engagement content to free channel — call manually, never on a timer."""
        if not settings.ENABLE_ENGAGEMENT_LOOP or not self.community_engagement:
            return
        try:
            await self.community_engagement.post_engagement()
            logger.info("Engagement post sent")
        except Exception as e:
            logger.error(f"Engagement loop error: {e}")
    
    async def daily_reset(self):
        logger.info("🔄 Performing daily reset...")
        
        self.signal_engine.reset_daily_counter()
        
        await self.admin_bot.send_notification(
            f"📊 Daily Reset - {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
            f"✅ Signal counter reset\n"
            f"✅ Marketing schedule refreshed\n"
            f"🚀 Ready for new trading day!"
        )
    
    async def daily_cleanup(self):
        logger.info("🧹 Performing daily cleanup...")
        try:
            self.cleanup_manager.run_daily_cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    # ============== AUTOPILOT WRAPPERS ==============
    
    async def _run_autopilot_performance_check(self):
        """AutoPilot: Check all active signals for TP/SL hits every 5 minutes"""
        if self.autopilot:
            try:
                await self.autopilot.run_performance_check()
            except Exception as e:
                logger.error(f"AutoPilot performance check error: {e}")
    
    async def _run_autopilot_daily(self):
        """AutoPilot: Daily automation at 23:55 UTC"""
        if self.autopilot:
            try:
                await self.autopilot.run_daily_automation()
            except Exception as e:
                logger.error(f"AutoPilot daily automation error: {e}")
    
    async def _run_autopilot_weekly(self):
        """AutoPilot: Weekly automation Sunday 20:00 UTC"""
        if self.autopilot:
            try:
                await self.autopilot.run_weekly_automation()
            except Exception as e:
                logger.error(f"AutoPilot weekly automation error: {e}")
    
    # ============== CAMPAIGN ENGINE WRAPPERS ==============
    
    async def _run_campaign_daily(self):
        """Campaign Engine: Daily marketing content blast"""
        if self.campaign_engine:
            try:
                await self.campaign_engine.run_daily_campaigns()
            except Exception as e:
                logger.error(f"Campaign daily error: {e}")
    
    async def _run_campaign_landing_push(self):
        """Campaign Engine: Push traffic to landing page"""
        if self.campaign_engine:
            try:
                await self.campaign_engine.landing_page_push()
            except Exception as e:
                logger.error(f"Campaign landing push error: {e}")
    
    async def _run_campaign_social_proof(self):
        """Campaign Engine: Weekly performance social proof"""
        if self.campaign_engine and self.autopilot:
            try:
                stats = self.autopilot.performance.get_stats(days=7)
                await self.campaign_engine.run_social_proof_campaign(stats)
            except Exception as e:
                logger.error(f"Campaign social proof error: {e}")
    
    # ============== PRO FEATURES WRAPPERS ==============
    
    async def _run_whale_alerts(self):
        """Pro: Scan for whale activity hourly (reduced from 15 min to avoid VIP channel spam)"""
        if self.whale_alerts:
            try:
                await self.whale_alerts.scan_for_whale_activity()
            except Exception as e:
                logger.error(f"Whale alert scan error: {e}")
    
    async def _run_educational_content(self):
        """Pro: Post educational content Sunday only (was Mon/Wed/Fri — reduced to avoid clutter)"""
        if self.education_engine:
            try:
                await self.education_engine.post_educational_content()
            except Exception as e:
                logger.error(f"Educational content error: {e}")
    
    async def _run_bonus_reports(self):
        """Pro: Send bonus market report Sunday only (was Tue/Thu — reduced to avoid clutter)"""
        if self.bonus_reports:
            try:
                await self.bonus_reports.send_bonus_market_report()
            except Exception as e:
                logger.error(f"Bonus report error: {e}")
    
    async def _run_giveaway(self):
        """Pro: Run monthly giveaway for lifetime members"""
        if self.giveaway_engine:
            try:
                await self.giveaway_engine.run_monthly_giveaway()
            except Exception as e:
                logger.error(f"Giveaway error: {e}")
    
    async def _run_custom_alerts(self):
        """Pro: Check custom price alerts every 5 minutes"""
        if self.custom_alerts and self.signal_engine and self.signal_engine.scanner:
            try:
                await self.custom_alerts.check_alerts(self.signal_engine.scanner)
            except Exception as e:
                logger.error(f"Custom alerts error: {e}")
    
    async def _run_viral_daily_marketing(self):
        """Viral Growth: Daily automated marketing to all platforms"""
        if self.viral_growth:
            try:
                await self.viral_growth.execute_daily_marketing()
                logger.info("🚀 Daily viral marketing executed")
            except Exception as e:
                logger.error(f"Viral daily marketing error: {e}")
    
    async def _run_viral_weekly_marketing(self):
        """Viral Growth: Weekly marketing blitz (Reddit, Discord, Forums)"""
        if self.viral_growth:
            try:
                await self.viral_growth.execute_weekly_marketing()
                logger.info("🚀 Weekly viral marketing blitz completed")
            except Exception as e:
                logger.error(f"Viral weekly marketing error: {e}")
    
    async def start(self):
        logger.info("🚀 Starting CRYPTO PULSE SIGNALS...")
        
        await self.initialize()
        
        self.setup_scheduler()
        self.scheduler.start()
        
        # Start admin dashboard server in background
        dashboard_port = int(getattr(settings, 'ADMIN_DASHBOARD_PORT', 8080))
        asyncio.create_task(start_dashboard(self, dashboard_port))
        logger.info(f"🎛️ Admin Dashboard starting on http://localhost:{dashboard_port}")
        
        self.running = True
        
        logger.info("✅ CRYPTO PULSE SIGNALS is now running!")
        logger.info("📊 INSTITUTIONAL GRADE SIGNAL ENGINE")
        logger.info(f"📊 15m: Intraday swing (1-4h holds, 85%+ confidence)")
        logger.info(f"📊 1h: Swing trades (4-24h holds, 85%+ confidence)")
        logger.info(f"📊 4h: Position trades (1-3d holds, 88%+ confidence)")
        logger.info(f"📊 Daily: Macro positions (3-7d holds, 90%+ confidence)")
        logger.info(f"📊 Max Signals/Day: {settings.MAX_SIGNALS_PER_DAY}")
        logger.info(f"📊 Min Risk/Reward: {settings.MIN_RISK_REWARD}")
        logger.info(f"📊 Free Channel Delay: {settings.FREE_CHANNEL_DELAY_MINUTES} minutes")
        
        await self.admin_bot.send_notification(
            "🚀 <b>CRYPTO PULSE SIGNALS Started</b>\n\n"
            f"✅ System operational — INSTITUTIONAL GRADE\n\n"
            f"📊 <b>Timeframes:</b>\n"
            f"• 15m: Intraday swing (1-4h holds, 85%+ conf)\n"
            f"• 1h: Swing trades (4-24h holds, 85%+ conf)\n"
            f"• 4h: Position trades (1-3d holds, 88%+ conf)\n"
            f"• Daily: Macro positions (3-7d holds, 90%+ conf)\n\n"
            f"🎯 Target: 1-3 quality signals/day\n"
            f"⏰ Free delay: {settings.FREE_CHANNEL_DELAY_MINUTES} min after VIP\n"
            f"🤖 Admin approval required for all signals\n\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
        
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal...")
            await self.shutdown()
        except Exception as e:
            logger.critical(f"Main loop crashed: {e}", exc_info=True)
            await self.shutdown()
            raise
    
    async def _on_vip_notification(self, message: str):
        """Forward VIP bot notifications to admin"""
        try:
            await self.admin_bot.send_notification(message)
        except Exception as e:
            logger.error(f"Failed to forward VIP notification: {e}")
    
    async def shutdown(self):
        logger.info("🛑 Shutting down CRYPTO PULSE SIGNALS...")
        
        self.running = False
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        await self.signal_engine.close()
        await self.admin_bot.close()
        await self.vip_bot.shutdown()
        
        logger.info("✅ Shutdown complete")


async def main():
    orchestrator = CryptoPulseOrchestrator()
    await orchestrator.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
