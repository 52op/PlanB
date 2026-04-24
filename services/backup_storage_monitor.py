"""
备份存储空间监控服务

提供存储空间使用统计、趋势分析和警告检查功能。
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from models import db, BackupJob, BackupConfig
from sqlalchemy import func


class BackupStorageMonitor:
    """备份存储空间监控服务"""
    
    @staticmethod
    def get_storage_stats() -> Dict:
        """
        获取存储空间使用统计
        
        Returns:
            包含存储统计信息的字典
        """
        # 获取所有成功的备份任务
        successful_jobs = BackupJob.query.filter_by(status='success').all()
        
        # 计算总空间使用
        total_size_bytes = sum(job.file_size_bytes or 0 for job in successful_jobs)
        backup_count = len(successful_jobs)
        
        # 获取最新备份信息
        latest_backup = BackupJob.query.filter_by(status='success').order_by(
            BackupJob.completed_at.desc()
        ).first()
        
        # 获取配置的保留数量
        config = BackupConfig.query.first()
        retention_count = config.retention_count if config else 10
        
        # 计算平均备份大小
        avg_size_bytes = total_size_bytes / backup_count if backup_count > 0 else 0
        
        # 估算可用空间（基于保留策略）
        estimated_max_size = avg_size_bytes * retention_count
        available_bytes = max(0, estimated_max_size - total_size_bytes)
        
        return {
            'total_size_bytes': total_size_bytes,
            'total_size_mb': round(total_size_bytes / (1024 * 1024), 2),
            'total_size_gb': round(total_size_bytes / (1024 * 1024 * 1024), 2),
            'backup_count': backup_count,
            'avg_size_bytes': avg_size_bytes,
            'avg_size_mb': round(avg_size_bytes / (1024 * 1024), 2),
            'retention_count': retention_count,
            'estimated_max_size_bytes': estimated_max_size,
            'estimated_max_size_gb': round(estimated_max_size / (1024 * 1024 * 1024), 2),
            'available_bytes': available_bytes,
            'available_gb': round(available_bytes / (1024 * 1024 * 1024), 2),
            'usage_percent': round((total_size_bytes / estimated_max_size * 100), 2) if estimated_max_size > 0 else 0,
            'latest_backup_date': latest_backup.completed_at.isoformat() if latest_backup and latest_backup.completed_at else None,
            'latest_backup_size_mb': round((latest_backup.file_size_bytes or 0) / (1024 * 1024), 2) if latest_backup else 0
        }
    
    @staticmethod
    def get_storage_trend(days: int = 30) -> List[Dict]:
        """
        获取存储空间使用趋势
        
        Args:
            days: 统计天数，默认30天
            
        Returns:
            趋势数据列表，每个元素包含日期和累计大小
        """
        start_date = datetime.now() - timedelta(days=days)
        
        # 获取时间范围内的所有成功备份
        jobs = BackupJob.query.filter(
            BackupJob.status == 'success',
            BackupJob.completed_at >= start_date
        ).order_by(BackupJob.completed_at.asc()).all()
        
        # 按日期分组统计
        daily_stats = {}
        cumulative_size = 0
        
        for job in jobs:
            if job.completed_at:
                date_key = job.completed_at.strftime('%Y-%m-%d')
                if date_key not in daily_stats:
                    daily_stats[date_key] = {
                        'date': date_key,
                        'count': 0,
                        'size_bytes': 0,
                        'cumulative_size_bytes': 0
                    }
                
                daily_stats[date_key]['count'] += 1
                daily_stats[date_key]['size_bytes'] += job.file_size_bytes or 0
                cumulative_size += job.file_size_bytes or 0
                daily_stats[date_key]['cumulative_size_bytes'] = cumulative_size
        
        # 填充没有备份的日期（保持连续性）
        result = []
        current_date = start_date.date()
        end_date = datetime.now().date()
        last_cumulative = 0
        
        while current_date <= end_date:
            date_key = current_date.strftime('%Y-%m-%d')
            if date_key in daily_stats:
                last_cumulative = daily_stats[date_key]['cumulative_size_bytes']
                result.append({
                    'date': date_key,
                    'count': daily_stats[date_key]['count'],
                    'size_mb': round(daily_stats[date_key]['size_bytes'] / (1024 * 1024), 2),
                    'cumulative_size_mb': round(last_cumulative / (1024 * 1024), 2),
                    'cumulative_size_gb': round(last_cumulative / (1024 * 1024 * 1024), 2)
                })
            else:
                # 没有备份的日期，使用上一个累计值
                result.append({
                    'date': date_key,
                    'count': 0,
                    'size_mb': 0,
                    'cumulative_size_mb': round(last_cumulative / (1024 * 1024), 2),
                    'cumulative_size_gb': round(last_cumulative / (1024 * 1024 * 1024), 2)
                })
            
            current_date += timedelta(days=1)
        
        return result
    
    @staticmethod
    def check_storage_warning() -> Tuple[bool, Optional[str]]:
        """
        检查存储空间是否低于警告阈值
        
        Returns:
            (是否需要警告, 警告消息)
        """
        config = BackupConfig.query.first()
        if not config:
            return False, None
        
        threshold_mb = config.storage_warning_threshold_mb or 1024
        stats = BackupStorageMonitor.get_storage_stats()
        
        available_mb = stats['available_gb'] * 1024
        
        if available_mb < threshold_mb:
            message = f"备份存储空间不足！可用空间仅剩 {stats['available_gb']:.2f} GB，低于警告阈值 {threshold_mb / 1024:.2f} GB"
            return True, message
        
        return False, None
    
    @staticmethod
    def get_storage_by_type() -> Dict:
        """
        按备份类型统计存储使用情况
        
        Returns:
            按类型分组的存储统计
        """
        # 按备份模式分组统计
        full_backups = BackupJob.query.filter_by(
            status='success',
            backup_mode='full'
        ).all()
        
        incremental_backups = BackupJob.query.filter_by(
            status='success',
            backup_mode='incremental'
        ).all()
        
        full_size = sum(job.file_size_bytes or 0 for job in full_backups)
        incremental_size = sum(job.file_size_bytes or 0 for job in incremental_backups)
        
        return {
            'full': {
                'count': len(full_backups),
                'size_bytes': full_size,
                'size_mb': round(full_size / (1024 * 1024), 2),
                'size_gb': round(full_size / (1024 * 1024 * 1024), 2)
            },
            'incremental': {
                'count': len(incremental_backups),
                'size_bytes': incremental_size,
                'size_mb': round(incremental_size / (1024 * 1024), 2),
                'size_gb': round(incremental_size / (1024 * 1024 * 1024), 2)
            }
        }
