# -*- coding: utf-8 -*-
"""
备份调度器服务
Backup Scheduler Service
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from models import BackupConfig
from services.backup_config import BackupConfigManager
from services.backup_engine import BackupEngine


class BackupScheduler:
    """备份调度器"""
    
    def __init__(self, app):
        """
        初始化备份调度器
        Initialize backup scheduler
        
        Args:
            app: Flask应用实例
        """
        self.app = app
        self.scheduler = BackgroundScheduler()
        self._job_running = False
        self.engine = BackupEngine(app)
    
    def start(self):
        """
        启动调度器
        Start the scheduler
        
        初始化并启动APScheduler后台调度器。
        如果备份配置已启用，则根据配置添加调度任务。
        """
        if self.scheduler.running:
            print("[BackupScheduler] 调度器已在运行中")
            return
        
        # 启动调度器
        self.scheduler.start()
        print("[BackupScheduler] 调度器已启动")
        
        # 加载并应用当前配置
        with self.app.app_context():
            config = BackupConfigManager.get_config()
            if config and config.enabled:
                self.update_schedule(config)
                print(f"[BackupScheduler] 已加载备份配置: {config.schedule_type}")
    
    def stop(self):
        """
        停止调度器
        Stop the scheduler
        
        关闭APScheduler后台调度器，停止所有调度任务。
        """
        if not self.scheduler.running:
            print("[BackupScheduler] 调度器未运行")
            return
        
        self.scheduler.shutdown(wait=True)
        print("[BackupScheduler] 调度器已停止")
    
    def update_schedule(self, config: BackupConfig):
        """
        更新调度配置
        Update schedule configuration
        
        根据备份配置更新调度任务。如果备份已启用，则添加或更新调度任务；
        如果备份已禁用，则移除所有调度任务。
        
        Args:
            config: 备份配置对象
        """
        # 移除现有的调度任务
        job_id = 'backup_job'
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            print(f"[BackupScheduler] 已移除现有调度任务: {job_id}")
        
        # 如果备份未启用，不添加新任务
        if not config.enabled:
            print("[BackupScheduler] 备份已禁用，不添加调度任务")
            return
        
        # 根据调度类型创建触发器
        trigger = self._create_trigger(config.schedule_type, config.schedule_value)
        
        if trigger is None:
            print(f"[BackupScheduler] 无法创建触发器: {config.schedule_type}")
            return
        
        # 添加调度任务
        self.scheduler.add_job(
            func=self._execute_backup_job,
            trigger=trigger,
            id=job_id,
            name='自动备份任务',
            replace_existing=True
        )
        
        print(f"[BackupScheduler] 已添加调度任务: {config.schedule_type}")
    
    def trigger_manual_backup(self) -> tuple:
        """
        手动触发备份
        Manually trigger backup
        
        立即执行一次备份任务。如果已有备份任务正在执行，则拒绝新的请求。
        
        Returns:
            tuple: (是否成功, 消息)
        """
        # 检查是否有备份任务正在执行
        if self._job_running:
            return False, "备份任务正在执行中，请稍后再试"
        
        try:
            # 标记任务正在执行
            self._job_running = True
            
            # 在应用上下文中执行备份
            with self.app.app_context():
                backup_job = self.engine.execute_backup(trigger_type='manual')
                
                if backup_job.status == 'success':
                    return True, f"手动备份成功: {backup_job.filename}"
                else:
                    return False, f"手动备份失败: {backup_job.error_message}"
        
        except Exception as e:
            return False, f"手动备份失败: {str(e)}"
        
        finally:
            # 清除执行标志
            self._job_running = False
    
    def _execute_backup_job(self):
        """
        执行备份任务（内部方法）
        Execute backup job (internal method)
        
        由调度器自动调用的备份任务执行方法。
        使用标志位防止并发执行。
        """
        # 检查是否有备份任务正在执行
        if self._job_running:
            print("[BackupScheduler] 备份任务正在执行中，跳过本次调度")
            return
        
        try:
            # 标记任务正在执行
            self._job_running = True
            print("[BackupScheduler] 开始执行自动备份任务")
            
            # 在应用上下文中执行备份
            with self.app.app_context():
                backup_job = self.engine.execute_backup(trigger_type='auto')
                
                if backup_job.status == 'success':
                    print(f"[BackupScheduler] 自动备份成功: {backup_job.filename}")
                else:
                    print(f"[BackupScheduler] 自动备份失败: {backup_job.error_message}")
        
        except Exception as e:
            print(f"[BackupScheduler] 自动备份异常: {str(e)}")
        
        finally:
            # 清除执行标志
            self._job_running = False
    
    def _create_trigger(self, schedule_type: str, schedule_value: str = None):
        """
        创建调度触发器
        Create schedule trigger
        
        根据调度类型和值创建APScheduler触发器。
        
        Args:
            schedule_type: 调度类型（hourly, daily, weekly, cron等）
            schedule_value: 调度值（cron表达式）
            
        Returns:
            触发器对象，如果创建失败则返回None
        """
        try:
            # 如果提供了 schedule_value（cron表达式），优先使用
            if schedule_value:
                # 解析cron表达式
                # APScheduler的CronTrigger支持标准cron格式
                # 格式：分 时 日 月 周 或 秒 分 时 日 月 周
                parts = schedule_value.strip().split()
                
                if len(parts) == 5:
                    # 5部分格式：分 时 日 月 周
                    print(f"[BackupScheduler] 使用cron表达式: {schedule_value}")
                    return CronTrigger(
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4]
                    )
                elif len(parts) == 6:
                    # 6部分格式：秒 分 时 日 月 周
                    print(f"[BackupScheduler] 使用cron表达式（含秒）: {schedule_value}")
                    return CronTrigger(
                        second=parts[0],
                        minute=parts[1],
                        hour=parts[2],
                        day=parts[3],
                        month=parts[4],
                        day_of_week=parts[5]
                    )
                else:
                    print(f"[BackupScheduler] 无效的cron表达式格式: {schedule_value}，部分数量: {len(parts)}")
                    # 如果是cron类型但格式无效，返回None
                    if schedule_type == 'cron':
                        return None
            
            # 如果没有 schedule_value 或解析失败，使用默认规则
            if schedule_type == 'hourly':
                # 每小时执行一次（在每小时的第0分钟）
                print("[BackupScheduler] 使用默认hourly触发器")
                return CronTrigger(minute=0)
            
            elif schedule_type == 'daily':
                # 每天执行一次（默认凌晨2点，但应该从schedule_value读取）
                # 如果没有schedule_value，使用默认值
                print("[BackupScheduler] 使用默认daily触发器")
                return CronTrigger(hour=2, minute=0)
            
            elif schedule_type == 'weekly':
                # 每周执行一次（默认周日凌晨2点）
                print("[BackupScheduler] 使用默认weekly触发器")
                return CronTrigger(day_of_week='sun', hour=2, minute=0)
            
            elif schedule_type == 'cron':
                # 自定义cron表达式（已在上面处理）
                print("[BackupScheduler] cron调度类型需要提供有效的cron表达式")
                return None
            
            else:
                print(f"[BackupScheduler] 不支持的调度类型: {schedule_type}")
                return None
        
        except Exception as e:
            print(f"[BackupScheduler] 创建触发器失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
