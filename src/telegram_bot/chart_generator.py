import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from datetime import datetime
from pathlib import Path
from typing import Optional
import asyncio
from src.models.signal import TradingSignal, SignalDirection
from src.scanner.market_scanner import MarketScanner
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ChartGenerator:
    def __init__(self):
        self.charts_dir = Path("charts")
        self.charts_dir.mkdir(exist_ok=True)
        self.scanner = MarketScanner()
        
        # Load logo for watermark
        self.logo_path = Path("assets/logo.png")
        self.logo_img = None
        if self.logo_path.exists():
            try:
                self.logo_img = plt.imread(str(self.logo_path))
            except Exception as e:
                logger.warning(f"Could not load logo for chart watermark: {e}")
        else:
            logger.debug("Logo not found at assets/logo.png — charts will have no watermark")
    
    async def generate_chart(self, signal: TradingSignal) -> Optional[str]:
        try:
            df = await self.scanner.fetch_ohlcv(signal.symbol, signal.timeframe, limit=100)
            
            if df.empty:
                logger.warning(f"No data available for chart: {signal.symbol}")
                return None
            
            # Use last 50 candles for clarity
            df_plot = df.tail(50).reset_index(drop=True)
            n = len(df_plot)
            
            # Numeric x positions (0, 1, 2... not datetimes)
            x = range(n)
            candle_width = 0.65  # 65% of slot width
            
            fig, ax = plt.subplots(figsize=(14, 8))
            fig.patch.set_facecolor('#0d1117')
            ax.set_facecolor('#0d1117')
            
            # --- Plot proper candlesticks ---
            for i in range(n):
                o = df_plot['open'].iloc[i]
                c = df_plot['close'].iloc[i]
                h = df_plot['high'].iloc[i]
                l = df_plot['low'].iloc[i]
                
                is_green = c >= o
                color = '#26a69a' if is_green else '#ef5350'
                
                # Wick (thin vertical line)
                ax.plot([i, i], [l, h], color=color, linewidth=0.7, alpha=0.9, solid_capstyle='round')
                
                # Body (filled rectangle)
                body_bottom = min(o, c)
                body_height = abs(c - o)
                if body_height == 0:
                    body_height = 0.000001  # Avoid zero-height bars
                ax.bar(i, body_height, bottom=body_bottom, width=candle_width,
                       color=color, edgecolor=color, linewidth=0.3, alpha=0.95)
            
            # --- Trade Zone shading (entry to SL) ---
            if signal.direction == SignalDirection.SHORT:
                zone_low = signal.stop_loss
                zone_high = signal.entry_price
                zone_color = '#ef5350'
                zone_label = 'RISK ZONE'
            else:
                zone_low = signal.entry_price
                zone_high = signal.stop_loss
                zone_color = '#26a69a'
                zone_label = 'RISK ZONE'
            
            ax.axhspan(zone_low, zone_high, alpha=0.12, color=zone_color, zorder=0)
            ax.text(n - 1, (zone_low + zone_high) / 2, f'  {zone_label}',
                   color=zone_color, fontsize=8, fontweight='bold',
                   va='center', ha='right', alpha=0.7)
            
            # --- Entry line ---
            ax.axhline(y=signal.entry_price, color='#00bcd4', linestyle='-', 
                      linewidth=2.5, alpha=1.0, zorder=5)
            ax.text(-0.5, signal.entry_price, 'ENTRY  ', 
                   color='#00bcd4', fontsize=10, fontweight='bold',
                   va='center', ha='right')
            ax.text(n - 0.5, signal.entry_price, 
                   f'  ${signal.entry_price:.6f}',
                   color='#00bcd4', fontsize=9, fontweight='bold',
                   va='center', ha='left')
            
            # --- Stop Loss line ---
            ax.axhline(y=signal.stop_loss, color='#ff1744', linestyle='--', 
                      linewidth=2.5, alpha=1.0, zorder=5)
            ax.text(-0.5, signal.stop_loss, 'SL  ', 
                   color='#ff1744', fontsize=10, fontweight='bold',
                   va='center', ha='right')
            ax.text(n - 0.5, signal.stop_loss, 
                   f'  ${signal.stop_loss:.6f}',
                   color='#ff1744', fontsize=9, fontweight='bold',
                   va='center', ha='left')
            
            # --- Take Profit 1 ---
            ax.axhline(y=signal.take_profit_1, color='#00e676', linestyle='--', 
                      linewidth=2.0, alpha=1.0, zorder=5)
            ax.text(-0.5, signal.take_profit_1, 'TP1  ', 
                   color='#00e676', fontsize=10, fontweight='bold',
                   va='center', ha='right')
            ax.text(n - 0.5, signal.take_profit_1, 
                   f'  ${signal.take_profit_1:.6f}',
                   color='#00e676', fontsize=9, fontweight='bold',
                   va='center', ha='left')
            
            # --- Take Profit 2 ---
            if signal.take_profit_2:
                ax.axhline(y=signal.take_profit_2, color='#69f0ae', linestyle=':', 
                          linewidth=2.0, alpha=0.9, zorder=5)
                ax.text(-0.5, signal.take_profit_2, 'TP2  ', 
                       color='#69f0ae', fontsize=9, fontweight='bold',
                       va='center', ha='right')
                ax.text(n - 0.5, signal.take_profit_2, 
                       f'  ${signal.take_profit_2:.6f}',
                       color='#69f0ae', fontsize=8, va='center', ha='left')
            
            # --- Take Profit 3 ---
            if signal.take_profit_3:
                ax.axhline(y=signal.take_profit_3, color='#b9f6ca', linestyle=':', 
                          linewidth=1.5, alpha=0.8, zorder=5)
                ax.text(-0.5, signal.take_profit_3, 'TP3  ', 
                       color='#b9f6ca', fontsize=9, fontweight='bold',
                       va='center', ha='right')
                ax.text(n - 0.5, signal.take_profit_3, 
                       f'  ${signal.take_profit_3:.6f}',
                       color='#b9f6ca', fontsize=8, va='center', ha='left')
            
            # --- Setup annotation box ---
            setup_label = signal.setup_type.value.replace('_', ' ').upper()
            direction_label = signal.direction.value
            dir_color = '#00e676' if signal.direction == SignalDirection.LONG else '#ff5252'
            ax.text(0.015, 0.98, f'{setup_label}\n{direction_label}', 
                   transform=ax.transAxes, fontsize=10, fontweight='bold',
                   color='#ffffff',
                   verticalalignment='top',
                   bbox=dict(boxstyle='round,pad=0.6', facecolor='#1a1f2e', 
                            edgecolor=dir_color, linewidth=2, alpha=0.95))
            
            # --- Title ---
            ax.set_title(
                f'{signal.symbol}  |  {signal.timeframe}  |  {signal.direction.value}\n'
                f'Confidence: {signal.confidence:.1f}%  |  Risk:Reward 1:{signal.risk_reward:.2f}',
                fontsize=14, fontweight='bold', color='#e2e8f0',
                pad=18
            )
            
            # --- X-axis labels (time) ---
            tick_positions = list(range(0, n, max(1, n // 8)))
            tick_labels = []
            for pos in tick_positions:
                ts = df_plot.index[pos]
                if hasattr(ts, 'strftime'):
                    tick_labels.append(ts.strftime('%H:%M'))
                else:
                    tick_labels.append(str(ts))
            
            ax.set_xticks(tick_positions)
            ax.set_xticklabels(tick_labels, rotation=0, ha='center')
            
            # --- Y-axis formatting ---
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:.6f}'))
            
            # --- Styling ---
            ax.tick_params(colors='#94a3b8', labelsize=8, length=3)
            ax.set_ylabel('Price (USDT)', fontsize=10, color='#94a3b8', fontweight='bold')
            ax.set_xlabel('Time', fontsize=10, color='#94a3b8', fontweight='bold')
            
            ax.grid(True, alpha=0.12, color='#475569', linestyle='-', linewidth=0.5)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#334155')
            ax.spines['bottom'].set_color('#334155')
            ax.spines['left'].set_linewidth(0.5)
            ax.spines['bottom'].set_linewidth(0.5)
            
            # Padding for labels
            ax.set_xlim(-2, n + 1)
            
            # --- CryptoPulse Logo Watermark (subtle background, bottom-right) ---
            if self.logo_img is not None:
                try:
                    logo_box = OffsetImage(self.logo_img, zoom=0.10, alpha=0.30)
                    ab = AnnotationBbox(
                        logo_box,
                        (n - 1.5, ax.get_ylim()[0]),
                        xybox=(n - 1.5, ax.get_ylim()[0]),
                        frameon=False,
                        pad=0,
                        xycoords='data',
                        boxcoords='data'
                    )
                    ax.add_artist(ab)
                except Exception as e:
                    logger.debug(f"Logo watermark skipped: {e}")
            
            plt.tight_layout()
            plt.subplots_adjust(left=0.08, right=0.92)
            
            chart_filename = f"{signal.symbol.replace('/', '_')}_{signal.id[:8]}.png"
            chart_path = self.charts_dir / chart_filename
            
            await asyncio.to_thread(plt.savefig, chart_path, dpi=180, bbox_inches='tight',
                                   facecolor='#0d1117', edgecolor='none')
            plt.close(fig)
            
            logger.info(f"Chart generated: {chart_path}")
            return str(chart_path)
            
        except Exception as e:
            logger.error(f"Error generating chart: {e}")
            return None
