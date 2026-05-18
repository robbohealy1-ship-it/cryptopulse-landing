"""
Traffic & Conversion Tracker
Track where VIP signups come from to optimize marketing spend
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TrafficSource(str, Enum):
    """Sources that can drive traffic"""
    TELEGRAM_FREE = "telegram_free"
    TELEGRAM_ORGANIC = "telegram_organic"
    TWITTER = "twitter"
    REDDIT = "reddit"
    DISCORD = "discord"
    LANDING_PAGE = "landing_page"
    REFERRAL = "referral"
    DIRECT = "direct"
    OTHER = "other"


class TrafficTracker:
    """Track marketing attribution and conversion funnel"""
    
    def __init__(self, db=None):
        self.db = db
        self._local_cache = {
            'clicks': {},
            'signups': {},
            'conversions': {},
        }
    
    async def track_click(self, source: TrafficSource, medium: str = None, 
                         campaign: str = None, user_id: str = None) -> str:
        """Track a click from a marketing channel"""
        click_id = f"clk_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{source.value}"
        
        data = {
            'click_id': click_id,
            'source': source.value,
            'medium': medium or 'organic',
            'campaign': campaign or 'default',
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        self._local_cache['clicks'][click_id] = data
        
        # Store in DB if available
        if self.db:
            try:
                await self.db.save_traffic_event(data)
            except Exception as e:
                logger.debug(f"DB track_click error: {e}")
        
        logger.info(f"Tracked click: {source.value} ({click_id})")
        return click_id
    
    async def track_signup(self, user_id: str, click_id: str = None,
                          source: TrafficSource = None) -> bool:
        """Track a VIP signup with attribution"""
        data = {
            'user_id': user_id,
            'click_id': click_id,
            'source': source.value if source else 'unknown',
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        self._local_cache['signups'][user_id] = data
        
        if self.db:
            try:
                await self.db.update_subscriber_source(user_id, data)
            except Exception as e:
                logger.debug(f"DB track_signup error: {e}")
        
        logger.info(f"Tracked signup: {user_id} from {data['source']}")
        return True
    
    async def get_attribution_report(self, days: int = 7) -> Dict:
        """Get conversion attribution report"""
        since = datetime.utcnow() - timedelta(days=days)
        
        report = {
            'period_days': days,
            'total_clicks': 0,
            'total_signups': 0,
            'conversion_rate': 0.0,
            'by_source': {},
            'top_performing': None,
        }
        
        # Aggregate from cache
        for click in self._local_cache['clicks'].values():
            click_time = datetime.fromisoformat(click['timestamp'])
            if click_time >= since:
                report['total_clicks'] += 1
                src = click['source']
                if src not in report['by_source']:
                    report['by_source'][src] = {'clicks': 0, 'signups': 0}
                report['by_source'][src]['clicks'] += 1
        
        for signup in self._local_cache['signups'].values():
            signup_time = datetime.fromisoformat(signup['timestamp'])
            if signup_time >= since:
                report['total_signups'] += 1
                src = signup['source']
                if src not in report['by_source']:
                    report['by_source'][src] = {'clicks': 0, 'signups': 0}
                report['by_source'][src]['signups'] += 1
        
        # Calculate conversion rates
        for src, data in report['by_source'].items():
            if data['clicks'] > 0:
                data['conversion_rate'] = (data['signups'] / data['clicks']) * 100
            else:
                data['conversion_rate'] = 0.0
        
        if report['total_clicks'] > 0:
            report['conversion_rate'] = (report['total_signups'] / report['total_clicks']) * 100
        
        # Find top source
        if report['by_source']:
            report['top_performing'] = max(
                report['by_source'].items(),
                key=lambda x: x[1].get('signups', 0)
            )[0]
        
        return report
    
    def get_tracking_link(self, base_url: str, source: TrafficSource, 
                         campaign: str = None) -> str:
        """Generate a tracking link with UTM parameters"""
        utm = f"?utm_source={source.value}"
        if campaign:
            utm += f"&utm_campaign={campaign}"
        
        # Clean base URL
        if '?' in base_url:
            base_url = base_url.split('?')[0]
        
        return base_url + utm
    
    def get_vip_bot_link(self, source: TrafficSource) -> str:
        """Get VIP bot link with tracking"""
        return f"https://t.me/CryptoPulseVIPAccessBot?start={source.value}"
    
    async def generate_weekly_report(self) -> str:
        """Generate a weekly marketing performance report"""
        report = await self.get_attribution_report(days=7)
        
        text = (
            f"📊 <b>MARKETING PERFORMANCE (7 DAYS)</b>\n\n"
            f"👥 Total Clicks: {report['total_clicks']}\n"
            f"💎 VIP Signups: {report['total_signups']}\n"
            f"📈 Conversion Rate: {report['conversion_rate']:.2f}%\n\n"
            f"<b>By Source:</b>\n"
        )
        
        for src, data in sorted(report['by_source'].items(), 
                               key=lambda x: x[1].get('signups', 0), reverse=True):
            text += f"• {src}: {data['signups']} signups ({data['conversion_rate']:.1f}%)\n"
        
        if report['top_performing']:
            text += f"\n🏆 Top Source: {report['top_performing']}"
        
        return text


class ReferralTracker:
    """Track invite referrals for contests and rewards"""
    
    def __init__(self, db=None):
        self.db = db
        self._referrals = {}  # referrer_id -> list of referred user_ids
        self._rewards = {
            3: "1 week free VIP",
            5: "50% off VIP",
            10: "1 month free VIP",
            25: "Lifetime VIP",
        }
    
    async def track_invite(self, referrer_id: str, invited_user_id: str) -> bool:
        """Track when a user invites someone"""
        if referrer_id not in self._referrals:
            self._referrals[referrer_id] = []
        
        if invited_user_id not in self._referrals[referrer_id]:
            self._referrals[referrer_id].append(invited_user_id)
            
            # Check for reward milestones
            count = len(self._referrals[referrer_id])
            for milestone, reward in sorted(self._rewards.items()):
                if count == milestone:
                    logger.info(f"User {referrer_id} earned: {reward} ({count} invites)")
                    # TODO: Send reward notification
                    break
            
            logger.info(f"Tracked invite: {referrer_id} -> {invited_user_id} (total: {count})")
            return True
        
        return False
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get invite leaderboard"""
        sorted_refs = sorted(
            self._referrals.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:limit]
        
        return [
            {'user_id': uid, 'invites': len(invited)}
            for uid, invited in sorted_refs
        ]
    
    def get_user_referral_count(self, user_id: str) -> int:
        """Get number of referrals for a user"""
        return len(self._referrals.get(user_id, []))
    
    def get_next_reward(self, user_id: str) -> Optional[Dict]:
        """Get next reward milestone for a user"""
        current = self.get_user_referral_count(user_id)
        
        for milestone, reward in sorted(self._rewards.items()):
            if milestone > current:
                return {
                    'current': current,
                    'next_milestone': milestone,
                    'reward': reward,
                    'needed': milestone - current
                }
        
        return None
