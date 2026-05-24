import asyncio
import os
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta, timezone
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
from src.utils.ai_content_generator import AIContentGenerator
from src.config import settings
from src.admin.dashboard_server import start_dashboard
from src.alpha_plays import AlphaPlaysEngine, AlphaPublisher

logger = get_logger(__name__)


class CryptoPulseOrchestrator:
    def __init__(self):
        # Initialize DB first (needed by other components)
        self.db = SupabaseClient()
        
        self.signal_engine = SignalEngine(db=self.db)
        self.admin_bot = AdminBot(
            signal_callback=self.on_signal_approved,
            rejection_callback=self.on_signal_rejected,
            alpha_callback=self.on_alpha_approved,
            alpha_rejection_callback=self.on_alpha_rejected
        )
        self.vip_bot = VIPBot(
            notification_callback=self._on_vip_notification
        )
        self.channel_publisher = ChannelPublisher()
        self.cleanup_manager = CleanupManager()
        self.signal_validator = SignalValidator()
        self.marketing = MarketingAutomation(db=self.db)
        self.reporting = ReportingEngine(db=self.db)
        
        # Marketing Engine
        self.social_media = SocialMediaPoster()
        self.discord_publisher = DiscordPublisher()
        self.viral_generator = ViralContentGenerator()
        self.ai_generator = AIContentGenerator()
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
        self._pending_limit_extremes = {}  # Track price extremes for DB-loaded limit orders (survives restart via DB)
        
        # In-memory TP hit tracking (workaround until DB migration is run)
        # Format: {signal_id: {tp1_hit: True, tp2_hit: False, stop_moved: True}}
        self.tp_hit_cache = {}
    
    async def initialize(self, dashboard_only: bool = False):
        logger.info("🚀 Initializing CRYPTO PULSE SIGNALS...")
        self.dashboard_only = dashboard_only
        
        try:
            # Validate environment first
            if not run_all_validations():
                raise ValueError("Environment validation failed. Please check your .env file.")
            
            await self.signal_engine.initialize()
            if not dashboard_only:
                await self.admin_bot.initialize()
            else:
                # Dashboard-only: init admin bot for sending only (no polling, no conflict with Oracle)
                await self.admin_bot.initialize_send_only()
            
            # 🔄 Restore pending signals from database (survives restarts)
            if not dashboard_only:
                try:
                    pending_from_db = await self.db.get_pending_signals()
                    restored_count = 0
                    resent_count = 0
                    for signal in pending_from_db:
                        self.admin_bot.pending_signals[signal.id] = signal
                        restored_count += 1
                        # Re-send approval request to admin Telegram
                        if self.admin_bot.send_signal_for_approval:
                            try:
                                await self.admin_bot.send_signal_for_approval(signal)
                                resent_count += 1
                            except Exception as send_err:
                                logger.warning(f"Could not resend {signal.symbol} to admin: {send_err}")
                    if restored_count > 0:
                        logger.info(f"🔄 Restored {restored_count} pending signals from database")
                        if resent_count > 0:
                            logger.info(f"📩 Resent {resent_count} pending signals to admin for approval")
                except Exception as e:
                    logger.warning(f"Could not restore pending signals from DB: {e}")
            
            # 🔄 Restore ACTIVE signals to autopilot (survives restarts)
            if self.autopilot:
                try:
                    active_from_db = await self.db.get_active_signals()
                    restored_active = 0
                    for signal in active_from_db:
                        if signal.id not in self.autopilot.performance.active_signals:
                            await self.autopilot.performance.track_signal(signal)
                            restored_active += 1
                    if restored_active > 0:
                        logger.info(f"🎯 Restored {restored_active} active signals to autopilot tracking")
                except Exception as e:
                    logger.warning(f"Could not restore active signals to autopilot: {e}")
            
            # Initialize community engagement (needs bot instance)
            if not dashboard_only and self.admin_bot.app and self.admin_bot.app.bot:
                self.community_engagement = CommunityEngagement(
                    bot=self.admin_bot.app.bot,
                    free_channel_id=getattr(settings, 'TELEGRAM_FREE_CHANNEL_ID', None),
                    db=self.db,
                    discord=self.discord_publisher  # Cross-post to Discord
                )
                logger.info("✅ Community engagement engine initialized (Telegram + Discord)")
            
            # Start VIP bot if configured
            vip_started = False
            if not dashboard_only:
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
                admin_notification=self.admin_bot.send_notification if not dashboard_only else None
            )
            logger.info("🚀 Campaign Engine initialized — signal marketing active")
            
            # Initialize AutoPilot System with FOMO callback
            self.autopilot = AutoPilotSystem(
                scanner=self.signal_engine.scanner,
                db=self.db,
                social_media=self.social_media,
                discord=self.discord_publisher,
                channel_publisher=self.channel_publisher,
                community_engagement=self.community_engagement,
                on_channel_notification=self._on_autopilot_channel_notification
            )
            # Wire FOMO campaign: when TP hits, blast to all channels
            self.autopilot.performance.on_signal_result = self.campaign_engine.signal_result_campaign
            
            # Pass payment handlers to AutoPilot if VIP bot is running
            if self.vip_bot and self.vip_bot.payment_orchestrator:
                self.autopilot.payment_orchestrator = self.vip_bot.payment_orchestrator
                logger.info("🤖 AutoPilot payment orchestrator linked to VIP bot")
            
            logger.info("🤖 AutoPilot System initialized — full automation active")
            
            # Initialize Pro Features
            self.whale_alerts = WhaleAlertSystem(
                channel_publisher=self.channel_publisher,
                admin_notification=self.admin_bot.send_notification if not dashboard_only else None
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
            
            # Share custom alert system with VIP bot so /alert commands work
            if self.vip_bot and self.custom_alerts:
                self.vip_bot.custom_alerts = self.custom_alerts
                logger.info("🔔 Custom alert system linked to VIP bot")
            
            # Initialize Alpha/Degen Plays Engine
            self.alpha_publisher = AlphaPublisher(bot=self.channel_publisher.bot)
            self.alpha_engine = AlphaPlaysEngine(
                db=self.db,
                publisher=self.alpha_publisher,
                admin_notification=self.admin_bot.send_notification,
                admin_bot=self.admin_bot if not dashboard_only else None
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
        
        # Check for stale limit orders (approved but not filled within timeout)
        self.scheduler.add_job(
            self.check_stale_limit_orders,
            CronTrigger(hour='*/1'),
            id='check_stale_limits',
            name='Check stale limit orders',
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
        
        # Evening summary: EOD wrap-up (21:00 UTC = 10pm UK/BST)
        self.scheduler.add_job(
            self._post_evening_recap,
            CronTrigger(hour=21, minute=0),
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
        
        # 🧠 AI Content Generation (if enabled)
        if settings.AI_EDUCATION_ENABLED:
            self.scheduler.add_job(
                self._post_ai_education,
                CronTrigger(day_of_week='mon,wed,fri', hour=14, minute=0),
                id='ai_education',
                name='AI: Educational content post',
                replace_existing=True
            )
            logger.info("🧠 AI educational content scheduled: Mon/Wed/Fri 14:00 UTC")

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
        
        # Portfolio holds summary: Weekly (Sunday 18:00 UTC)
        self.scheduler.add_job(
            self._send_portfolio_summary,
            CronTrigger(day_of_week='sun', hour=18, minute=0),
            id='portfolio_summary',
            name='Alpha: Weekly portfolio summary',
            replace_existing=True
        )
        
        logger.info("🎰 Alpha Plays scheduled: discovery every 6h, tracking every 5m, portfolio summary weekly")
        
        logger.info("✅ Scheduler configured")
        logger.info("📣 Morning overview (08:30) → VIP + Free | Evening summary (21:00 UTC / 10pm UK) → VIP + Free")
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
                        
                        # Discord Alpha channel
                        if self.discord_publisher.alpha_enabled:
                            try:
                                await self.discord_publisher.post_alpha_signal(candidate)
                                logger.info(f"🎰 Discord Alpha posted: {candidate.symbol}")
                            except Exception as e:
                                logger.error(f"❌ Discord Alpha post failed: {e}")
                        
                        # Notify admin
                        await self.admin_bot.send_notification(
                            f"🎰 <b>Alpha Play Published</b>\n\n"
                            f"{candidate.symbol} on {candidate.chain.upper()}\n"
                            f"Score: {candidate.overall_score:.1f}/100\n"
                            f"MC: ${candidate.market_cap_usd/1e6:.2f}M\n"
                            f"Posted to VIP + FREE + Discord channels"
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
            await self.alpha_engine.track_portfolio_holds()
            
        except Exception as e:
            logger.error(f"Error tracking alpha plays: {e}")
    
    async def _send_portfolio_summary(self):
        """Send weekly portfolio holds summary to VIP (called by scheduler Sunday 18:00 UTC)"""
        try:
            if not self.alpha_engine or not self.alpha_engine.portfolio_holds:
                return
            
            holds = list(self.alpha_engine.portfolio_holds.values())
            total_pnl = sum(h.current_pnl for h in holds)
            
            if self.alpha_engine.publisher:
                await self.alpha_engine.publisher.send_portfolio_summary(holds, total_pnl)
                logger.info(f"📊 Weekly portfolio summary sent: {len(holds)} holds, {total_pnl:+.1f}% total P&L")
            
        except Exception as e:
            logger.error(f"Error sending portfolio summary: {e}")
    
    async def _dashboard_alpha_tracker(self):
        """Background task for dashboard-only mode: track alpha plays every 5 minutes"""
        logger.info("🎰 Dashboard alpha tracker started (5-min interval)")
        while self.running:
            try:
                await asyncio.sleep(300)  # 5 minutes
                if not self.running:
                    break
                if self.alpha_engine:
                    await self.alpha_engine.track_active_plays()
                    await self.alpha_engine.track_portfolio_holds()
                    logger.info(f"📊 Dashboard alpha tracker: checked {len(self.alpha_engine.active_plays)} active plays, {len(self.alpha_engine.portfolio_holds)} portfolio holds")
            except Exception as e:
                logger.error(f"Dashboard alpha tracker error: {e}")
                await asyncio.sleep(60)
    
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
                
                # Log quality score but DON'T auto-reject - admin decides approve/reject
                quality_passed = self.signal_validator.check_signal_quality(candidate, min_confidence=settings.MIN_CONFIDENCE_SCORE)
                if not quality_passed:
                    logger.info(f"⚠️  Signal {candidate.symbol} below auto-quality threshold ({candidate.confidence:.1f}%), sending to admin for manual review")
                else:
                    logger.info(f"✅ Signal {candidate.symbol} passed quality check ({candidate.confidence:.1f}%)")
                
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
                if not self.dashboard_only:
                    await self.admin_bot.send_signal_for_approval(candidate)
                
                self.signal_engine.add_signal(candidate)
                
                logger.info(f"✅ Candidate {candidate.symbol} sent for approval")
                
            except Exception as e:
                logger.error(f"Error processing candidate {candidate.symbol}: {e}")
    
    async def on_signal_approved(self, signal):
        logger.info(f"[APPROVE] on_signal_approved START for {signal.symbol} (status={signal.status.value}, source={'dashboard' if self.dashboard_only else 'telegram'})")
        try:
            # Guard against duplicate approvals — only skip if already ACTIVE (published)
            if signal.status == SignalStatus.ACTIVE or getattr(signal, 'vip_channel_posted', False):
                logger.warning(f"[APPROVE] Signal {signal.symbol} already ACTIVE/vip_channel_posted — SKIPPING")
                return
            
            # Admin manually approved — their judgment overrides auto-expiry
            expires_at = signal.expires_at
            if expires_at and expires_at.tzinfo:
                expires_at = expires_at.replace(tzinfo=None)
            if expires_at and datetime.utcnow() > expires_at:
                logger.warning(f"[APPROVE] Signal {signal.symbol} is past expiry but admin approved — publishing anyway")
                # Extend expiry to now so periodic check won't cancel it
                signal.expires_at = datetime.utcnow() + timedelta(minutes=30)
                if not self.dashboard_only:
                    await self.admin_bot.send_notification(
                        f"⚠️ Signal {signal.symbol} was past expiry but you approved it — published to channels"
                    )
            
            signal.admin_approved = True
            signal.status = SignalStatus.APPROVED
            signal.approved_at = datetime.utcnow()
            
            # Audit log: signal approved
            if self.db:
                await self.db.log_trade_event(
                    signal_id=signal.id,
                    event_type='signal_approved',
                    details={'symbol': signal.symbol, 'direction': signal.direction.value, 'setup_type': str(signal.setup_type), 'grade': signal.grade.value, 'confidence': signal.confidence},
                    price=signal.entry_price
                )
            
            logger.info(f"[APPROVE] Saving signal {signal.symbol} to DB with status=APPROVED")
            saved = await self.db.save_signal(signal)
            if not saved:
                logger.error(f"[APPROVE] ❌ DB save failed for {signal.symbol}")
                raise RuntimeError(f"Signal {signal.symbol} could not be saved to database")
            logger.info(f"[APPROVE] ✅ DB save OK for {signal.symbol}")
            
            vip_only = signal.confidence >= 90
            logger.info(f"[APPROVE] Signal {signal.symbol} vip_only={vip_only} (confidence={signal.confidence})")
            
            # Publish VIP channel immediately
            logger.info(f"[APPROVE] Calling channel_publisher.publish_to_vip for {signal.symbol}")
            await self.channel_publisher.publish_to_vip(signal)
            signal.vip_channel_posted = True
            logger.info(f"[APPROVE] ✅ VIP publish OK for {signal.symbol} (msg_id={signal.vip_channel_message_id})")
            
            # Set actual entry price and status for market orders
            if not signal.is_limit_order:
                try:
                    actual_price = await self._get_current_price(signal.symbol)
                    if actual_price and actual_price > 0:
                        signal.actual_entry = actual_price
                        logger.info(f"[APPROVE] Actual entry price for {signal.symbol}: ${actual_price:.4f}")
                except Exception as price_err:
                    logger.warning(f"[APPROVE] Could not fetch actual entry price for {signal.symbol}: {price_err}")
                # Market orders are active immediately after VIP publish
                signal.status = SignalStatus.ACTIVE
                if self.db:
                    await self.db.log_trade_event(
                        signal_id=signal.id,
                        event_type='signal_active',
                        details={'symbol': signal.symbol, 'reason': 'market_order', 'actual_entry': signal.actual_entry},
                        price=signal.actual_entry
                    )
            # Limit orders stay as APPROVED until the limit price is actually hit
            
            # AUTOPILOT: Start tracking
            if self.autopilot:
                logger.info(f"[APPROVE] Starting autopilot tracking for {signal.symbol}")
                await self.autopilot.on_signal_approved(signal)
            
            # Free channel teaser
            if not vip_only:
                logger.info(f"[APPROVE] Sending free channel teaser for {signal.symbol}")
                if self.campaign_engine:
                    await self.campaign_engine.signal_approved_campaign(signal)
                    logger.info(f"[APPROVE] ✅ Free teaser sent for {signal.symbol}")
                else:
                    logger.warning(f"[APPROVE] campaign_engine is None — free teaser NOT sent")
            else:
                logger.info(f"[APPROVE] Sending VIP-exclusive teaser for {signal.symbol}")
                await self.channel_publisher.send_vip_teaser(signal)
                logger.info(f"[APPROVE] ✅ VIP teaser sent for {signal.symbol}")
            
            # Admin notification (only in full mode)
            if not self.dashboard_only:
                await self.admin_bot.send_notification(
                    f"✅ Signal {signal.symbol} approved!\n"
                    f"🌟 VIP channel: Published NOW\n"
                    f"📢 Free channel: Teaser sent"
                )
            
            # Cross-post
            logger.info(f"[APPROVE] Cross-posting {signal.symbol}")
            await self._crosspost_signal(signal)
            
            signal.published_at = datetime.utcnow()
            await self.db.save_signal(signal)
            logger.info(f"[APPROVE] ✅ on_signal_approved COMPLETE for {signal.symbol}")
            
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
            
            if self.db:
                await self.db.log_trade_event(
                    signal_id=signal.id,
                    event_type='signal_rejected',
                    details={'symbol': signal.symbol, 'reason': signal.rejection_reason, 'grade': signal.grade.value if hasattr(signal.grade, 'value') else str(signal.grade)},
                    price=signal.entry_price
                )
            
            logger.info(f"❌ Signal {signal.symbol} rejected - logged to database")
            
        except Exception as e:
            logger.error(f"Error handling rejected signal: {e}")
    
    async def on_alpha_approved(self, candidate):
        """Alpha play approved from Telegram admin bot"""
        try:
            if self.alpha_engine:
                # Check if admin set this as a limit order via dashboard edits
                is_limit = getattr(candidate, 'is_limit_order', False)
                active_play = await self.alpha_engine.approve_alpha_play(candidate.symbol, is_limit_order=is_limit)
                if active_play:
                    if not is_limit:
                        await self.alpha_engine.publish_to_vip(active_play)
                        logger.info(f"🎰 Alpha play {candidate.symbol} approved from Telegram and published")
                    else:
                        logger.info(f"🎰 Alpha limit order {candidate.symbol} approved from Telegram — waiting for entry hit")
                else:
                    logger.warning(f"Alpha play {candidate.symbol} approval returned None")
            else:
                logger.warning("Alpha engine not initialized — cannot approve alpha play")
        except Exception as e:
            logger.error(f"Error handling alpha approval: {e}")
    
    async def on_alpha_rejected(self, candidate):
        """Alpha play rejected from Telegram admin bot"""
        try:
            logger.info(f"🎰 Alpha play {candidate.symbol} rejected from Telegram")
            if self.alpha_engine and candidate.symbol in self.alpha_engine.pending_plays:
                del self.alpha_engine.pending_plays[candidate.symbol]
        except Exception as e:
            logger.error(f"Error handling alpha rejection: {e}")
    
    async def check_expired_signals(self):
        """Check for pending signals that have expired before admin approval"""
        try:
            pending_signals = await self.db.get_pending_signals()
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            for signal in pending_signals:
                expires = signal.expires_at
                if expires:
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if now > expires:
                        signal.status = SignalStatus.EXPIRED
                        signal.cancelled = True
                        signal.cancellation_reason = "Auto-cancelled: expired before admin approval"
                        await self.db.save_signal(signal)
                        
                        if self.db:
                            await self.db.log_trade_event(
                                signal_id=signal.id,
                                event_type='signal_expired',
                                details={'symbol': signal.symbol, 'reason': 'expired_before_approval', 'expires_at': signal.expires_at.isoformat() if signal.expires_at else None}
                            )
                        
                        if not self.dashboard_only:
                            await self.admin_bot.send_notification(
                                f"⏰ Signal {signal.symbol} auto-cancelled - expired before approval"
                            )
                        logger.info(f"Signal {signal.symbol} auto-cancelled (expired)")
                    
        except Exception as e:
            logger.error(f"Error checking expired signals: {e}")
    
    async def check_stale_limit_orders(self):
        """Auto-cancel APPROVED limit orders that haven't filled within timeout"""
        try:
            all_active = await self.db.get_active_signals()
            stale = [s for s in all_active if getattr(s, 'is_limit_order', False) and s.status.value == 'approved']
            
            from datetime import timezone
            now = datetime.now(timezone.utc)
            timeout = getattr(settings, 'LIMIT_ORDER_TIMEOUT_HOURS', 24)
            
            for signal in stale:
                approved_at = getattr(signal, 'approved_at', None)
                if not approved_at:
                    continue
                if approved_at.tzinfo is None:
                    approved_at = approved_at.replace(tzinfo=timezone.utc)
                
                if (now - approved_at).total_seconds() > timeout * 3600:
                    signal.status = SignalStatus.EXPIRED
                    signal.cancelled = True
                    signal.cancellation_reason = f"Auto-cancelled: limit order not filled within {timeout}h"
                    await self.db.save_signal(signal)
                    
                    if self.db:
                        await self.db.log_trade_event(
                            signal_id=signal.id,
                            event_type='limit_expired',
                            details={'symbol': signal.symbol, 'reason': f'stale_limit_{timeout}h', 'approved_at': approved_at.isoformat() if approved_at else None}
                        )
                    
                    # Remove from autopilot pending if tracked
                    if self.autopilot and signal.id in self.autopilot.performance.pending_limit_orders:
                        del self.autopilot.performance.pending_limit_orders[signal.id]
                        self.autopilot.performance.pending_limit_extremes.pop(signal.id, None)
                    
                    if not self.dashboard_only:
                        await self.admin_bot.send_notification(
                            f"⏰ {signal.symbol} limit order auto-cancelled — not filled within {timeout}h"
                        )
                    logger.info(f"⏰ {signal.symbol} limit order auto-cancelled (stale > {timeout}h)")
                    
        except Exception as e:
            logger.error(f"Error checking stale limit orders: {e}")
    
    async def check_active_signals(self):
        """Check active signals for limit order fills. TP/SL tracking is handled exclusively by autopilot."""
        try:
            active_signals = await self.db.get_active_signals()
            
            for signal in active_signals:
                current_price = await self._get_current_price(signal.symbol)
                if not current_price:
                    continue
                
                is_limit = getattr(signal, 'is_limit_order', False)
                
                # --- LIMIT ORDER FILL DETECTION ---
                # Only for APPROVED limit orders that haven't filled yet
                if is_limit and signal.status.value != 'active':
                    # CRITICAL FIX: If actual_entry is already set, the limit was filled earlier
                    # (e.g., before a restart when in-memory extremes were lost). Activate immediately.
                    if getattr(signal, 'actual_entry', None) is not None:
                        signal.status = SignalStatus.ACTIVE
                        await self.db.update_signal_status(signal_id=signal.id, status=SignalStatus.ACTIVE)
                        logger.info(f"🎯 Limit order for {signal.symbol} already filled (actual_entry={signal.actual_entry}), activating")
                        if self.autopilot and signal.id not in self.autopilot.performance.active_signals:
                            try:
                                await self.autopilot.performance.track_signal(signal)
                            except Exception:
                                pass
                        continue
                    
                    sid = signal.id
                    extremes = self._pending_limit_extremes.get(sid, {'lowest': float('inf'), 'highest': 0.0})
                    extremes['lowest'] = min(extremes['lowest'], current_price)
                    extremes['highest'] = max(extremes['highest'], current_price)
                    self._pending_limit_extremes[sid] = extremes
                    
                    entry = signal.entry_price
                    limit_filled = False
                    fill_reason = ""
                    
                    # Check 1: Current price at or beyond entry (normal case)
                    if signal.direction.value == "LONG":
                        if current_price <= entry:
                            limit_filled = True
                            fill_reason = f"current_price ${current_price:.4f} <= entry ${entry:.4f}"
                        elif extremes['lowest'] <= entry:
                            limit_filled = True
                            fill_reason = f"extreme low ${extremes['lowest']:.4f} touched entry ${entry:.4f}"
                        # Check 2: Retrospective fill — price is now ABOVE entry, meaning it must have
                        # crossed UP through entry after dipping down to fill the limit (while bot was down)
                        elif current_price > entry * 1.003:
                            limit_filled = True
                            fill_reason = f"retrospective LONG fill — price ${current_price:.4f} now above entry ${entry:.4f} (must have crossed through)"
                            logger.info(f"🔄 Retrospective limit fill detected for {signal.symbol}: price now above LONG entry")
                    else:  # SHORT
                        if current_price >= entry:
                            limit_filled = True
                            fill_reason = f"current_price ${current_price:.4f} >= entry ${entry:.4f}"
                        elif extremes['highest'] >= entry:
                            limit_filled = True
                            fill_reason = f"extreme high ${extremes['highest']:.4f} touched entry ${entry:.4f}"
                        # Check 2: Retrospective fill — price is now ABOVE entry, meaning it must have
                        # crossed UP through entry after spiking to fill the SHORT limit (while bot was down)
                        elif current_price > entry * 1.003:
                            limit_filled = True
                            fill_reason = f"retrospective SHORT fill — price ${current_price:.4f} now above entry ${entry:.4f} (must have crossed through)"
                            logger.info(f"🔄 Retrospective limit fill detected for {signal.symbol}: price now above SHORT entry")
                    
                    if not limit_filled:
                        continue
                    
                    # Limit filled — update status and hand off to autopilot
                    signal.status = SignalStatus.ACTIVE
                    # For retrospective fills, use entry price as actual fill price
                    # (current price may be far from entry since fill happened while bot was down)
                    if "retrospective" in fill_reason:
                        signal.actual_entry = entry
                    else:
                        signal.actual_entry = current_price
                    await self.db.save_signal(signal)
                    self._pending_limit_extremes.pop(sid, None)
                    logger.info(f"🎯 Limit order filled for {signal.symbol} at ${signal.actual_entry:.4f} ({fill_reason})")
                    
                    # Notify VIP channel
                    if self.channel_publisher:
                        try:
                            dir_emoji = "🟢 LONG" if signal.direction.value == "LONG" else "🔴 SHORT"
                            msg = (
                                f"🎯 <b>LIMIT ORDER FILLED</b>\n\n"
                                f"{signal.symbol} {dir_emoji}\n"
                                f"Entry: ${signal.actual_entry:.8f}\n"
                                f"SL: ${signal.stop_loss:.8f}\n"
                                f"TP1: ${signal.take_profit_1:.8f}\n\n"
                                f"📊 Now tracking TP/SL automatically"
                            )
                            await self.channel_publisher.bot.send_message(
                                chat_id=self.channel_publisher.vip_channel_id,
                                text=msg,
                                parse_mode='HTML'
                            )
                        except Exception:
                            pass
                    
                    # Hand off to autopilot for TP/SL tracking
                    if self.autopilot:
                        try:
                            await self.autopilot.performance.track_signal(signal)
                        except Exception:
                            pass
                    continue
                
                # --- ACTIVE SIGNALS: ensure autopilot is tracking ---
                # TP/SL detection is handled exclusively by autopilot to avoid dual tracking
                # GUARD: skip signals that already have final targets hit (stale DB state)
                if getattr(signal, 'tp3_hit', False) or getattr(signal, 'stop_hit', False):
                    hit_type = 'TP3' if getattr(signal, 'tp3_hit', False) else 'SL'
                    logger.warning(f"🛡️ Skipping re-track for {signal.symbol}: already has {hit_type} hit flag. DB status should be CLOSED.")
                    # Attempt to fix DB status if it's still 'active'
                    if signal.status.value == 'active':
                        try:
                            await self.db.update_signal_status(signal_id=signal.id, status=SignalStatus.CLOSED)
                            logger.info(f"🔧 Fixed stale DB status for {signal.symbol}: marked as CLOSED")
                        except Exception:
                            pass
                    continue
                
                if self.autopilot and signal.id not in self.autopilot.performance.active_signals:
                    try:
                        await self.autopilot.performance.track_signal(signal)
                        logger.info(f"🎯 Handed off {signal.symbol} to autopilot tracking")
                    except Exception:
                        pass
                
        except Exception as e:
            logger.error(f"Error checking active signals: {e}")
    
    async def handle_tp_hit(self, signal, tp_level, current_price):
        """Handle TP hit - send updates to VIP and Free channels"""
        
        # Initialize cache entry if not exists
        if signal.id not in self.tp_hit_cache:
            self.tp_hit_cache[signal.id] = {}
        
        # Check cache first (persists across bot restarts in this session)
        tp_key = f'tp{tp_level}_hit'
        if self.tp_hit_cache[signal.id].get(tp_key, False):
            logger.info(f"⏭️  TP{tp_level} already hit for {signal.symbol} (cache) - skipping duplicate")
            return
        
        # Also check signal object (in case loaded from DB with columns)
        if hasattr(signal, tp_key) and getattr(signal, tp_key):
            logger.info(f"⏭️  TP{tp_level} already hit for {signal.symbol} (DB) - skipping duplicate")
            self.tp_hit_cache[signal.id][tp_key] = True  # Update cache
            return
        
        logger.info(f"🎯 TP{tp_level} hit for {signal.symbol}")
        
        # Mark TP as hit in database (may fail if columns don't exist yet)
        try:
            await self.db.mark_tp_hit(signal.id, tp_level)
        except Exception as e:
            logger.warning(f"Could not mark TP{tp_level} in database (run migration): {e}")
        
        # Update cache and signal object to prevent duplicate messages
        self.tp_hit_cache[signal.id][tp_key] = True
        setattr(signal, tp_key, True)
        
        # Send update to VIP channel (includes TP1 marketing to Free)
        await self.channel_publisher.send_tp_hit(signal, tp_level)
        
        # Send update to Free channel (only TP2/TP3 teasers; TP1 already handled above)
        if tp_level > 1:
            await self.channel_publisher.send_tp_hit_free(signal, tp_level)
        
        # Move SL to breakeven after TP1 (only once)
        if tp_level == 1:
            # Check cache for breakeven status
            if not self.tp_hit_cache[signal.id].get('stop_moved', False):
                await self.channel_publisher.send_stop_moved(signal, signal.entry_price)
                try:
                    await self.db.update_stop_loss(signal.id, signal.entry_price)
                except Exception as e:
                    logger.warning(f"Could not update SL in database (run migration): {e}")
                # Mark in cache and signal object
                self.tp_hit_cache[signal.id]['stop_moved'] = True
                signal.stop_moved_to_breakeven = True
            else:
                logger.info(f"⏭️  SL already moved to breakeven for {signal.symbol} (cache) - skipping duplicate")
        
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
            if not self.dashboard_only:
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
            if not self.dashboard_only:
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
        
        chart_path = getattr(signal, 'chart_path', None)
        if chart_path and os.path.exists(chart_path):
            pass  # chart_path is valid
        else:
            chart_path = None
        
        # Twitter/X
        if self.social_media.twitter_enabled:
            try:
                results = await self.social_media.post_signal_teaser(signal, chart_path)
                logger.info(f"📣 Twitter posted: {results}")
            except Exception as e:
                logger.error(f"❌ Twitter post failed: {e}")
        
        # Discord - Main signals channel
        if self.discord_publisher.enabled:
            try:
                success = await self.discord_publisher.post_signal(signal)
                if success:
                    logger.info(f"📣 Discord posted: {signal.symbol}")
                else:
                    logger.warning(f"⚠️ Discord post returned False for {signal.symbol}")
            except Exception as e:
                logger.error(f"❌ Discord post failed: {e}")
        
        # Discord - VIP lounge (full signals for VIP members)
        if self.discord_publisher.vip_enabled:
            try:
                success = await self.discord_publisher.post_vip_signal(signal)
                if success:
                    logger.info(f"💎 Discord VIP posted: {signal.symbol}")
            except Exception as e:
                logger.error(f"❌ Discord VIP post failed: {e}")
        
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
        
        # Viral content generation disabled for Telegram free channel
        # Signal cards contain entry/SL/TP details - must not go to free channel
        # (campaign_engine._free_channel_teaser already handles free channel teaser)
    
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
            market_data = {
                'fear_class': fear.get('classification', 'Neutral'),
                'fear_value': fear.get('value', 'N/A'),
                'total_market_cap': global_data.get('total_market_cap', 'N/A'),
                'btc_dominance': global_data.get('btc_dominance', 'N/A'),
                'btc_price': global_data.get('btc_price'),
                'btc_24h': global_data.get('btc_24h_change', 0),
                'funding_rate': funding.get('funding_rate', 0),
            }

            # Try AI-generated summary first (if enabled & API key available)
            ai_summary = None
            if hasattr(self, 'ai_generator') and self.ai_generator:
                ai_summary = await self.ai_generator.generate_daily_summary(market_data)

            if ai_summary:
                vip_outlook = f"🌅 <b>AI MORNING OUTLOOK</b>\n<b>{now.strftime('%A, %d %B %Y')}</b>\n\n{ai_summary}"
                logger.info("Posted AI-generated morning outlook")
            else:
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
        """Post evening MARKET OUTLOOK with real data. Focus on tomorrow's setup."""
        try:
            # Fetch real market context
            mctx = await self._get_real_market_context()
            
            fear_class = mctx.get('fear_class', 'Neutral')
            fear_value = mctx.get('fear_value', 50)
            btc_price = mctx.get('btc_price', 0)
            btc_24h = mctx.get('btc_24h', 0)
            funding_rate = mctx.get('funding_rate', 0)
            market_change = mctx.get('market_change', 0)
            btc_dominance = mctx.get('btc_dominance', 0)
            
            # Get active trades
            active_signals = await self.db.get_active_signals()
            active_trades_text = ""
            
            if active_signals:
                active_trades_text = "\n\n<b>🔄 ACTIVE TRADES:</b>\n"
                for sig in active_signals:
                    current_price = await self._get_current_price(sig.symbol)
                    
                    if current_price:
                        entry = sig.actual_entry or sig.entry_price or 0
                        if entry and entry > 0:
                            pnl = ((current_price - entry) / entry) * 100
                        else:
                            pnl = 0
                        if sig.direction.value == "SHORT":
                            pnl = -pnl
                        
                        pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                        tp1_status = "✅" if getattr(sig, 'tp1_hit', False) else "⏳"
                        tp2_status = "✅" if getattr(sig, 'tp2_hit', False) else "⏳"
                        tp3_status = "✅" if getattr(sig, 'tp3_hit', False) else "⏳"
                        
                        entry_str = f"${entry:.4f}" if entry else "N/A"
                        active_trades_text += f"""
{sig.symbol} {sig.direction.value}
Entry: {entry_str} | Current: ${current_price:.4f}
P&L: {pnl_emoji} {pnl:+.2f}%
Targets: TP1 {tp1_status} | TP2 {tp2_status} | TP3 {tp3_status}
"""
            
            # Get active alpha plays
            alpha_plays_text = ""
            if self.alpha_engine and self.alpha_engine.active_plays:
                alpha_plays_text = "\n\n<b>🎰 ALPHA PLAYS:</b>\n"
                for play in self.alpha_engine.active_plays.values():
                    pnl = play.current_pnl
                    pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                    tp1_status = "✅" if play.tp1_hit_at else "⏳"
                    tp2_status = "✅" if play.tp2_hit_at else "⏳"
                    sl_status = "🛑" if play.sl_hit_at else "🛡"
                    entry_p = play.entry_price if play.entry_price else 0
                    curr_p = play.current_price if play.current_price else 0
                    alpha_plays_text += f"""{play.candidate.symbol} ({play.candidate.chain.upper()})
Entry: ${entry_p:.6f} | Current: ${curr_p:.6f}
P&L: {pnl_emoji} {pnl:+.2f}%
Targets: TP1 {tp1_status} | TP2 {tp2_status} | SL {sl_status}
"""
            
            # Get performance data for today, week, and month
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=7)
            month_start = now - timedelta(days=30)
            
            closed_signals = await self.db.get_closed_signals(days=30)
            
            def _filter_by_close_time(signals, start_time):
                filtered = []
                for s in signals:
                    close_time = getattr(s, 'closed_at', None) or getattr(s, 'updated_at', None) or getattr(s, 'created_at', None)
                    if close_time and isinstance(close_time, datetime):
                        try:
                            # Convert both to UTC timestamps for timezone-agnostic comparison
                            if close_time.tzinfo is not None:
                                close_ts = close_time.timestamp()
                            else:
                                close_ts = close_time.replace(tzinfo=timezone.utc).timestamp()
                            
                            if start_time.tzinfo is not None:
                                start_ts = start_time.timestamp()
                            else:
                                start_ts = start_time.replace(tzinfo=timezone.utc).timestamp()
                            
                            if close_ts >= start_ts:
                                filtered.append(s)
                        except Exception:
                            # Fallback: strip timezone and compare naively
                            try:
                                close_naive = close_time.replace(tzinfo=None) if close_time.tzinfo else close_time
                                start_naive = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
                                if close_naive >= start_naive:
                                    filtered.append(s)
                            except Exception:
                                pass
                return filtered
            
            today_signals = _filter_by_close_time(closed_signals, today_start)
            week_signals = _filter_by_close_time(closed_signals, week_start)
            month_signals = closed_signals
            
            def _format_performance(signals, label):
                if not signals:
                    return f"📈 {label}: No closed trades"
                wins = [s for s in signals if s.pnl_percent > 0]
                losses = [s for s in signals if s.pnl_percent <= 0]
                total_pnl = sum(s.pnl_percent for s in signals)
                win_rate = (len(wins) / len(signals)) * 100 if signals else 0
                emoji = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪"
                return (
                    f"📈 {label}: {len(wins)}W/{len(losses)}L | "
                    f"Win Rate: {win_rate:.0f}% | Total P&L: {emoji} {total_pnl:+.2f}%"
                )
            
            # List individual closed trades for today
            closed_trades_text = ""
            if today_signals:
                closed_trades_text = "\n<b>📋 TODAY'S CLOSED TRADES:</b>\n"
                for s in today_signals:
                    entry = s.actual_entry or s.entry_price or 0
                    exit_p = s.actual_exit or s.entry_price or 0
                    pnl = s.pnl_percent or 0
                    pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                    result = "TP Hit" if pnl > 0 else "SL Hit" if pnl < 0 else "Closed"
                    entry_str = f"${entry:.4f}" if entry else "N/A"
                    exit_str = f"${exit_p:.4f}" if exit_p else "N/A"
                    closed_trades_text += f"{pnl_emoji} {s.symbol} {s.direction.value} | Entry: {entry_str} → Exit: {exit_str} | P&L: {pnl:+.2f}% ({result})\n"
            
            performance_text = "\n".join([
                "",
                "<b>📊 PERFORMANCE:</b>",
                _format_performance(today_signals, "TODAY"),
                _format_performance(week_signals, "THIS WEEK"),
                _format_performance(month_signals, "THIS MONTH"),
            ])
            
            # Key levels from real data
            key_levels = self._get_key_levels(btc_price, btc_24h)
            session = self._get_next_session()
            volatility = self._assess_volatility(btc_24h, market_change)
            bias = self._generate_tomorrow_bias(mctx)
            
            # Try AI-generated evening recap first
            ai_recap = None
            if hasattr(self, 'ai_generator') and self.ai_generator:
                pnl_today = sum(s.pnl_percent for s in today_signals) if today_signals else 0
                closed_meta = [{'symbol': s.symbol, 'pnl_percent': s.pnl_percent, 'result': 'TP Hit' if s.pnl_percent > 0 else 'SL Hit' if s.pnl_percent < 0 else 'Closed'} for s in today_signals[:5]]
                ai_recap = await self.ai_generator.generate_evening_recap(mctx, closed_meta, pnl_today)

            if ai_recap:
                outlook = f"🌙 <b>AI EVENING RECAP</b>\n📅 {datetime.utcnow().strftime('%A, %B %d, %Y')}\n\n{ai_recap}"
                logger.info("Posted AI-generated evening recap")
            else:
                # Build tomorrow's market outlook
                outlook = f"""🌙 <b>EVENING MARKET OUTLOOK</b>
📅 {datetime.utcnow().strftime('%A, %B %d, %Y')}

<b>📊 Market Sentiment:</b>
Fear & Greed: <b>{fear_class}</b> ({fear_value}/100)
BTC Price: <b>${btc_price:,.2f}</b> ({btc_24h:+.2f}% 24h)
BTC Dominance: <b>{btc_dominance:.1f}%</b>
Funding Rate: <b>{funding_rate*100:.4f}%</b>
{active_trades_text}{alpha_plays_text}{closed_trades_text}{performance_text}

<b>🔮 Tomorrow's Focus:</b>
• {key_levels}
• {session}
• {volatility}

<b>⚡ What to Expect:</b>
{bias}

💎 Stay alert for high-confidence setups!
"""
            
            # VIP gets full outlook
            await self.channel_publisher.bot.send_message(
                chat_id=settings.TELEGRAM_VIP_CHANNEL_ID,
                text=outlook,
                parse_mode='HTML'
            )
            
            # Free gets teaser with more value
            # Brief performance for free channel
            free_perf = ""
            if today_signals:
                total_pnl_today = sum(s.pnl_percent for s in today_signals)
                free_perf = f"📈 Today's VIP Signals: {total_pnl_today:+.2f}% P&L\n"
            elif week_signals:
                total_pnl_week = sum(s.pnl_percent for s in week_signals)
                free_perf = f"📈 This Week: {total_pnl_week:+.2f}% P&L\n"
            
            free_teaser = f"""🌙 <b>MARKET OUTLOOK</b>

<b>📊 Current Conditions:</b>
Fear & Greed: <b>{fear_class}</b> ({fear_value}/100)
BTC: <b>${btc_price:,.0f}</b> ({btc_24h:+.2f}%)
{free_perf}
<b>⚡ Tomorrow's Bias:</b>
{self._generate_tomorrow_bias(mctx)[:120]}...

💎 VIP members get:
✅ Exact support/resistance levels
✅ Active trade updates
✅ Full daily bias + session timing

🔗 Join: t.me/CryptoPulseVIPAccessBot
"""
            
            # Discord
            if self.discord_publisher.enabled:
                await self.discord_publisher.post_marketing(
                    "🌙 Evening Market Outlook",
                    free_teaser.replace('<b>', '**').replace('</b>', '**')
                )

            logger.info("Evening market outlook posted (focus: tomorrow's setup)")
        except Exception as e:
            logger.error(f"Evening outlook error: {e}")
    
    async def _get_real_market_context(self) -> dict:
        """Fetch real market data for evening outlook."""
        ctx = self.signal_engine.context_engine
        try:
            btc = await ctx.fetch_btc_trend()
            fear = await ctx.fetch_fear_greed_index()
            funding = await ctx.fetch_funding_rates('BTCUSDT')
            market = await ctx.fetch_market_data()
            
            return {
                'btc_price': btc.get('current_price', 0),
                'btc_24h': btc.get('change_24h', 0),
                'btc_7d': btc.get('change_7d', 0),
                'btc_trend': btc.get('trend', 'neutral'),
                'fear_value': fear.get('value', 50),
                'fear_class': fear.get('classification', 'Neutral'),
                'funding_rate': funding.get('funding_rate', 0),
                'global_mcap': market.get('total_market_cap', 0),
                'btc_dominance': market.get('btc_dominance', 0),
                'market_change': market.get('market_cap_change_24h', 0)
            }
        except Exception as e:
            logger.warning(f"Could not fetch full market context: {e}")
            return {}
    
    def _get_key_levels(self, btc_price: float = 0, btc_24h: float = 0) -> str:
        """Calculate key support/resistance from real BTC price data"""
        if btc_price <= 0:
            return "Monitor BTC for key level breaks"
        
        # Calculate rough S/R based on current price and 24h change
        # Support = today's low estimate, Resistance = today's high estimate
        price_range = abs(btc_price * (btc_24h / 100)) if btc_24h != 0 else btc_price * 0.02
        support = btc_price - price_range * 1.2
        resistance = btc_price + price_range * 0.8
        
        # Round to clean levels
        if btc_price > 10000:
            support = round(support / 100) * 100
            resistance = round(resistance / 100) * 100
        
        return f"BTC ${support:,.0f} support, ${resistance:,.0f} resistance (current: ${btc_price:,.2f})"
    
    def _get_next_session(self) -> str:
        """Determine next major trading session based on actual UTC time"""
        hour = datetime.utcnow().hour
        if 0 <= hour < 6:
            return "Asia session (Tokyo) - watch for yen pairs & BTC"
        elif 6 <= hour < 14:
            return "London open - forex majors & crypto volatility"
        elif 14 <= hour < 22:
            return "NY session - peak liquidity & institutional moves"
        else:
            return "Asia session approaching - lower volatility expected"
    
    def _assess_volatility(self, btc_24h: float = 0, market_change: float = 0) -> str:
        """Assess volatility from real market data"""
        vol_score = abs(btc_24h) + abs(market_change)
        
        if vol_score > 8:
            return f"High volatility ({vol_score:.1f}% combined) - wide stops recommended"
        elif vol_score > 4:
            return f"Moderate volatility ({vol_score:.1f}% combined) - standard risk management"
        elif vol_score > 1:
            return f"Low volatility ({vol_score:.1f}% combined) - tighter entries, smaller positions"
        else:
            return "Very low volatility - expect range-bound action"
    
    def _generate_tomorrow_bias(self, ctx: dict) -> str:
        """Generate market bias from real data (not random)"""
        fear_value = ctx.get('fear_value', 50)
        btc_24h = ctx.get('btc_24h', 0)
        btc_7d = ctx.get('btc_7d', 0)
        funding = ctx.get('funding_rate', 0)
        trend = ctx.get('btc_trend', 'neutral')
        
        parts = []
        
        # Trend bias
        if btc_24h > 3 and btc_7d > 5:
            parts.append("Strong bullish momentum. Favor LONG setups on pullbacks.")
        elif btc_24h > 1.5:
            parts.append("Bullish bias. Look for continuation on dips to support.")
        elif btc_24h < -3 and btc_7d < -5:
            parts.append("Bearish trend. Favor SHORT setups on rallies to resistance.")
        elif btc_24h < -1.5:
            parts.append("Bearish bias. Defensive positioning. Breakdown shorts preferred.")
        else:
            parts.append("Neutral/choppy. Range trading between key levels until breakout.")
        
        # Fear/greed insight
        if fear_value < 25:
            parts.append("Extreme fear = contrarian buying opportunity for patient traders.")
        elif fear_value > 75:
            parts.append("Extreme greed = take profits. Reversal risk elevated.")
        
        # Funding insight
        if funding > 0.0003:
            parts.append("High funding = longs overleveraged. Caution on fresh longs.")
        elif funding < -0.0003:
            parts.append("Negative funding = shorts overleveraged. Squeeze potential.")
        
        return " ".join(parts)
    
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
        
        if not self.dashboard_only:
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
    
    async def _post_ai_education(self):
        """AI-generated educational content for the free channel."""
        if not hasattr(self, 'ai_generator') or not self.ai_generator:
            return
        try:
            post = await self.ai_generator.generate_educational_post()
            if post and self.channel_publisher and self.channel_publisher.bot:
                await self.channel_publisher.bot.send_message(
                    chat_id=settings.TELEGRAM_FREE_CHANNEL_ID,
                    text=post,
                    parse_mode='HTML'
                )
                logger.info("🧠 AI educational post sent to free channel")
        except Exception as e:
            logger.error(f"AI education post error: {e}")

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
    
    async def start(self, dashboard_only: bool = False):
        logger.info("🚀 Starting CRYPTO PULSE SIGNALS...")
        
        if dashboard_only:
            logger.info("🎛️ DASHBOARD-ONLY mode — no Telegram bots will start")
        
        await self.initialize(dashboard_only=dashboard_only)
        
        if not dashboard_only:
            self.setup_scheduler()
            self.scheduler.start()
        else:
            # Dashboard-only: start minimal background tracking for alpha plays
            asyncio.create_task(self._dashboard_alpha_tracker())
            logger.info("🎰 Alpha tracking background task started (dashboard-only)")
        
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
        
        if not dashboard_only:
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
            if not self.dashboard_only:
                await self.admin_bot.send_notification(message)
        except Exception as e:
            logger.error(f"Failed to forward VIP notification: {e}")
    
    async def _on_autopilot_channel_notification(self, signal, tp_level: int, sl_hit: bool, current_price: float):
        """Send channel notifications when autopilot detects TP/SL hit.
        Deduplication is handled in ChannelPublisher to prevent stale recovery duplicates."""
        try:
            if sl_hit:
                entry = signal.actual_entry or signal.entry_price
                pnl = 0.0
                if entry and entry != 0:
                    pnl = ((current_price - entry) / entry) * 100
                    if signal.direction.value == "SHORT":
                        pnl = -pnl
                await self.channel_publisher.send_trade_closed(signal, "Stop Loss Hit", pnl)
                return
            
            # TP3: trade is closing — just send close message (no separate TP3 hit)
            if tp_level == 3:
                entry = signal.actual_entry or signal.entry_price
                pnl = 0.0
                if entry and entry != 0:
                    pnl = ((current_price - entry) / entry) * 100
                    if signal.direction.value == "SHORT":
                        pnl = -pnl
                await self.channel_publisher.send_trade_closed(signal, "TP3 Hit", pnl)
                return
            
            # TP1 / TP2: send hit update
            await self.channel_publisher.send_tp_hit(signal, tp_level)
            
            # Free channel teasers for TP2
            if tp_level == 2:
                await self.channel_publisher.send_tp_hit_free(signal, tp_level)
            
            # Breakeven SL move after TP1
            if tp_level == 1:
                await self.channel_publisher.send_stop_moved(signal, signal.entry_price)
                try:
                    await self.db.update_stop_loss(signal.id, signal.entry_price)
                except Exception:
                    pass
                
        except Exception as e:
            logger.error(f"Failed to send channel notification: {e}")
    
    async def shutdown(self):
        logger.info("🛑 Shutting down CRYPTO PULSE SIGNALS...")
        
        self.running = False
        
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
        
        await self.signal_engine.close()
        
        if hasattr(self, 'admin_bot') and self.admin_bot:
            await self.admin_bot.close()
        if hasattr(self, 'vip_bot') and self.vip_bot:
            await self.vip_bot.shutdown()
        
        logger.info("✅ Shutdown complete")


async def main():
    import sys
    dashboard_only = '--dashboard-only' in sys.argv
    
    orchestrator = CryptoPulseOrchestrator()
    await orchestrator.start(dashboard_only=dashboard_only)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
