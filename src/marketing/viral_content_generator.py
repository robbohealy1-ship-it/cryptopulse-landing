"""
Viral Content Generator
Creates shareable images for social media marketing
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from PIL import Image, ImageDraw, ImageFont
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ViralContentGenerator:
    """Generate viral-style images for social media sharing"""
    
    def __init__(self, output_dir: str = "generated_content"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Brand colors
        self.colors = {
            'bg_dark': (10, 14, 26),
            'bg_card': (20, 24, 40),
            'accent_green': (0, 255, 128),
            'accent_red': (255, 70, 70),
            'accent_gold': (255, 200, 0),
            'text_white': (255, 255, 255),
            'text_gray': (180, 180, 180),
        }
        
        # Try to load fonts, fallback to default
        self._load_fonts()
    
    def _load_fonts(self):
        """Load fonts with fallbacks"""
        try:
            # Try common font paths
            font_paths = [
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
            
            font_path = None
            for fp in font_paths:
                if os.path.exists(fp):
                    font_path = fp
                    break
            
            if font_path:
                self.font_title = ImageFont.truetype(font_path, 36)
                self.font_large = ImageFont.truetype(font_path, 28)
                self.font_medium = ImageFont.truetype(font_path, 22)
                self.font_small = ImageFont.truetype(font_path, 18)
                self.font_tiny = ImageFont.truetype(font_path, 14)
            else:
                self.font_title = ImageFont.load_default()
                self.font_large = self.font_title
                self.font_medium = self.font_title
                self.font_small = self.font_title
                self.font_tiny = self.font_title
        except Exception as e:
            logger.warning(f"Font loading failed: {e}, using default")
            self.font_title = ImageFont.load_default()
            self.font_large = self.font_title
            self.font_medium = self.font_title
            self.font_small = self.font_title
            self.font_tiny = self.font_title
    
    def _draw_rounded_rect(self, draw, xy, radius, fill):
        """Draw rounded rectangle"""
        x1, y1, x2, y2 = xy
        draw.rounded_rectangle(xy, radius=radius, fill=fill)
    
    def create_signal_card(self, signal) -> str:
        """Generate a viral-style signal card image"""
        width, height = 1080, 1080  # Instagram square format
        
        img = Image.new('RGB', (width, height), self.colors['bg_dark'])
        draw = ImageDraw.Draw(img)
        
        ticker = signal.symbol.replace('/', '')
        direction = signal.direction.value
        color = self.colors['accent_green'] if direction == "LONG" else self.colors['accent_red']
        
        # Background gradient effect (simulated with rectangles)
        for i in range(0, height, 4):
            alpha = int(20 * (1 - i / height))
            draw.rectangle([(0, i), (width, i+4)], fill=(10 + alpha, 14 + alpha, 26 + alpha))
        
        # Header banner
        draw.rectangle([(0, 0), (width, 120)], fill=self.colors['bg_card'])
        
        # Brand
        draw.text((40, 40), "CryptoPulse", font=self.font_title, fill=self.colors['text_white'])
        draw.text((280, 50), "SIGNALS", font=self.font_medium, fill=self.colors['accent_gold'])
        
        # VIP badge
        draw.rounded_rectangle([(width-200, 30), (width-40, 80)], radius=10, fill=self.colors['accent_gold'])
        draw.text((width-180, 42), "VIP ONLY", font=self.font_small, fill=self.colors['bg_dark'])
        
        # Main content card
        card_margin = 60
        card_top = 160
        card_bottom = height - 200
        draw.rounded_rectangle(
            [(card_margin, card_top), (width-card_margin, card_bottom)],
            radius=20,
            fill=self.colors['bg_card']
        )
        
        # Direction banner inside card
        banner_height = 80
        draw.rounded_rectangle(
            [(card_margin, card_top), (width-card_margin, card_top + banner_height)],
            radius=20,
            fill=color
        )
        
        # Direction text
        dir_text = f"🚀 {direction} ALERT"
        draw.text((width//2 - 150, card_top + 20), dir_text, font=self.font_large, fill=self.colors['text_white'])
        
        # Ticker (large)
        draw.text((width//2 - 100, card_top + 100), f"#{ticker}", font=self.font_title, fill=self.colors['text_white'])
        
        # Confidence
        draw.text((width//2 - 80, card_top + 160), f"Confidence: {signal.confidence:.0f}%", 
                 font=self.font_medium, fill=self.colors['accent_gold'])
        
        # Stats grid
        stats_y = card_top + 220
        stats = [
            ("ENTRY", f"${signal.entry_price:.6f}"),
            ("STOP LOSS", f"${signal.stop_loss:.6f}"),
            ("TARGET 1", f"${signal.take_profit_1:.6f}"),
            ("TARGET 2", f"${signal.take_profit_2:.6f}"),
            ("TARGET 3", f"${signal.take_profit_3:.6f}"),
            ("R/R", f"1:{signal.risk_reward:.1f}"),
        ]
        
        col_width = (width - 2*card_margin) // 2
        for i, (label, value) in enumerate(stats):
            x = card_margin + (i % 2) * col_width + 20
            y = stats_y + (i // 2) * 70
            
            draw.text((x, y), label, font=self.font_small, fill=self.colors['text_gray'])
            draw.text((x, y + 25), value, font=self.font_medium, fill=self.colors['text_white'])
        
        # CTA section
        cta_y = card_bottom - 120
        draw.rounded_rectangle(
            [(card_margin + 20, cta_y), (width - card_margin - 20, cta_y + 80)],
            radius=15,
            fill=self.colors['accent_gold']
        )
        draw.text((width//2 - 200, cta_y + 25), "Join FREE Channel", font=self.font_medium, fill=self.colors['bg_dark'])
        draw.text((width//2 - 200, cta_y + 55), "t.me/cryptopulse_signals_free1", font=self.font_tiny, fill=self.colors['bg_dark'])
        
        # Footer
        draw.text((40, height - 60), "CryptoPulse Signals | Premium Trading Alerts", 
                 font=self.font_small, fill=self.colors['text_gray'])
        
        # Save
        filename = f"signal_card_{ticker}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = self.output_dir / filename
        img.save(filepath, quality=95)
        
        logger.info(f"Generated signal card: {filepath}")
        return str(filepath)
    
    def create_performance_card(self, stats: dict) -> str:
        """Generate a performance highlight card"""
        width, height = 1080, 1080
        
        img = Image.new('RGB', (width, height), self.colors['bg_dark'])
        draw = ImageDraw.Draw(img)
        
        # Header
        draw.rectangle([(0, 0), (width, 140)], fill=self.colors['bg_card'])
        draw.text((40, 40), "WEEKLY", font=self.font_title, fill=self.colors['text_white'])
        draw.text((240, 50), "RESULTS", font=self.font_medium, fill=self.colors['accent_gold'])
        
        # Stats boxes
        stats_data = [
            ("📊 SIGNALS", str(stats.get('total_signals', 0)), self.colors['accent_gold']),
            ("✅ WINS", str(stats.get('wins', 0)), self.colors['accent_green']),
            ("📈 WIN RATE", f"{stats.get('win_rate', 0):.1f}%", self.colors['accent_green']),
            ("💰 P&L", f"{stats.get('total_pnl', 0):.1f}%", self.colors['accent_green']),
        ]
        
        box_size = 400
        margin = 60
        for i, (label, value, color) in enumerate(stats_data):
            row = i // 2
            col = i % 2
            x = margin + col * (box_size + margin)
            y = 200 + row * (box_size + margin)
            
            # Box
            draw.rounded_rectangle([(x, y), (x + box_size, y + box_size)], radius=20, fill=self.colors['bg_card'])
            
            # Label
            draw.text((x + 30, y + 30), label, font=self.font_medium, fill=self.colors['text_gray'])
            
            # Value (large)
            draw.text((x + 30, y + 80), value, font=self.font_title, fill=color)
        
        # CTA
        cta_y = height - 180
        draw.rounded_rectangle([(margin, cta_y), (width - margin, cta_y + 100)], radius=15, fill=self.colors['accent_gold'])
        draw.text((width//2 - 180, cta_y + 30), "Get VIP Signals", font=self.font_large, fill=self.colors['bg_dark'])
        draw.text((width//2 - 180, cta_y + 70), "t.me/CryptoPulseVIPAccessBot", font=self.font_small, fill=self.colors['bg_dark'])
        
        # Footer
        draw.text((40, height - 50), "CryptoPulse Signals", font=self.font_small, fill=self.colors['text_gray'])
        
        filename = f"performance_{datetime.utcnow().strftime('%Y%m%d')}.png"
        filepath = self.output_dir / filename
        img.save(filepath, quality=95)
        
        logger.info(f"Generated performance card: {filepath}")
        return str(filepath)
    
    def create_fomo_card(self, recent_signals: list) -> str:
        """Create FOMO-inducing 'missed signals' card"""
        width, height = 1080, 1080
        
        img = Image.new('RGB', (width, height), self.colors['bg_dark'])
        draw = ImageDraw.Draw(img)
        
        # Header
        draw.text((width//2 - 250, 60), "⚡ MISSED OPPORTUNITIES", font=self.font_large, fill=self.colors['accent_gold'])
        
        # Signal list
        y = 160
        for signal in recent_signals[:5]:
            ticker = signal.symbol.replace('/', '')
            color = self.colors['accent_green'] if signal.direction.value == "LONG" else self.colors['accent_red']
            
            draw.rounded_rectangle([(60, y), (width-60, y+80)], radius=15, fill=self.colors['bg_card'])
            draw.text((80, y+15), f"#{ticker}", font=self.font_medium, fill=self.colors['text_white'])
            draw.text((300, y+15), signal.direction.value, font=self.font_medium, fill=color)
            draw.text((500, y+15), f"{signal.confidence:.0f}%", font=self.font_medium, fill=self.colors['accent_gold'])
            
            y += 100
        
        # FOMO text
        fomo_y = y + 40
        draw.text((80, fomo_y), "Don't miss the next one...", font=self.font_large, fill=self.colors['text_white'])
        draw.text((80, fomo_y + 50), "Join VIP for instant alerts", font=self.font_medium, fill=self.colors['text_gray'])
        
        # CTA
        draw.rounded_rectangle([(60, height-160), (width-60, height-60)], radius=15, fill=self.colors['accent_gold'])
        draw.text((width//2 - 200, height-130), "DM @CryptoPulseVIPAccessBot", font=self.font_medium, fill=self.colors['bg_dark'])
        
        filename = f"fomo_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = self.output_dir / filename
        img.save(filepath, quality=95)
        
        logger.info(f"Generated FOMO card: {filepath}")
        return str(filepath)
