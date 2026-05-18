import os
from pathlib import Path
from datetime import datetime, timedelta
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CleanupManager:
    """Manages cleanup of old files to prevent disk space issues"""
    
    def __init__(self):
        self.charts_dir = Path("charts")
        self.logs_dir = Path("logs")
        self.data_dir = Path("data")
        
    def cleanup_old_charts(self, days_to_keep=7):
        """Remove chart images older than specified days"""
        try:
            if not self.charts_dir.exists():
                return
            
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            removed_count = 0
            
            for chart_file in self.charts_dir.glob("*.png"):
                file_time = datetime.fromtimestamp(chart_file.stat().st_mtime)
                if file_time < cutoff_date:
                    chart_file.unlink()
                    removed_count += 1
            
            if removed_count > 0:
                logger.info(f"🗑️  Cleaned up {removed_count} old chart files")
                
        except Exception as e:
            logger.error(f"Error cleaning up charts: {e}")
    
    def cleanup_old_logs(self, days_to_keep=30):
        """Remove log files older than specified days"""
        try:
            if not self.logs_dir.exists():
                return
            
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            removed_count = 0
            
            for log_file in self.logs_dir.glob("*.log*"):
                if log_file.name.startswith('.'):
                    continue
                    
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff_date:
                    log_file.unlink()
                    removed_count += 1
            
            if removed_count > 0:
                logger.info(f"🗑️  Cleaned up {removed_count} old log files")
                
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}")
    
    def get_directory_size(self, directory):
        """Get total size of directory in MB"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            return total_size / (1024 * 1024)  # Convert to MB
        except Exception as e:
            logger.error(f"Error calculating directory size: {e}")
            return 0
    
    def check_disk_usage(self):
        """Check and log disk usage for key directories"""
        try:
            charts_size = self.get_directory_size(self.charts_dir)
            logs_size = self.get_directory_size(self.logs_dir)
            data_size = self.get_directory_size(self.data_dir)
            
            logger.info(f"📊 Disk usage - Charts: {charts_size:.2f}MB, Logs: {logs_size:.2f}MB, Data: {data_size:.2f}MB")
            
            if charts_size > 500:
                logger.warning(f"⚠️  Charts directory is large ({charts_size:.2f}MB). Consider cleanup.")
            if logs_size > 1000:
                logger.warning(f"⚠️  Logs directory is large ({logs_size:.2f}MB). Consider cleanup.")
                
        except Exception as e:
            logger.error(f"Error checking disk usage: {e}")
    
    def run_daily_cleanup(self):
        """Run all cleanup tasks"""
        logger.info("🧹 Running daily cleanup...")
        self.cleanup_old_charts(days_to_keep=7)
        self.cleanup_old_logs(days_to_keep=30)
        self.check_disk_usage()
        logger.info("✅ Daily cleanup complete")
