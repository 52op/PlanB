# -*- coding: utf-8 -*-
"""
备份调度器单元测试
Backup Scheduler Unit Tests
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from services.backup_scheduler import BackupScheduler
from models import BackupConfig, BackupJob


class TestBackupScheduler:
    """备份调度器测试类"""
    
    @pytest.fixture
    def app(self):
        """创建测试应用"""
        from flask import Flask
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        return app
    
    @pytest.fixture
    def scheduler(self, app):
        """创建调度器实例"""
        return BackupScheduler(app)
    
    @pytest.fixture
    def mock_config(self):
        """创建模拟配置"""
        config = Mock()
        config.enabled = True
        config.storage_type = 'ftp'
        config.schedule_type = 'daily'
        config.schedule_value = None
        config.retention_count = 10
        config.backup_mode = 'full'
        return config
    
    def test_init(self, app):
        """测试调度器初始化"""
        scheduler = BackupScheduler(app)
        
        assert scheduler.app == app
        assert scheduler.scheduler is not None
        assert scheduler._job_running is False
        assert scheduler.engine is not None
    
    def test_start_scheduler(self, scheduler):
        """测试启动调度器"""
        with patch.object(scheduler.scheduler, 'start') as mock_start, \
             patch('services.backup_scheduler.BackupConfigManager.get_config', return_value=None):
            scheduler.start()
            mock_start.assert_called_once()
    
    def test_start_scheduler_already_running(self, scheduler):
        """测试启动已运行的调度器"""
        # 先启动调度器使其处于运行状态
        scheduler.scheduler.start()
        
        with patch.object(scheduler.scheduler, 'start') as mock_start, \
             patch('services.backup_scheduler.BackupConfigManager.get_config', return_value=None):
            scheduler.start()
            # 验证start未被调用（因为已经在运行）
            mock_start.assert_not_called()
    
    def test_stop_scheduler(self, scheduler):
        """测试停止调度器"""
        # 先启动调度器
        scheduler.scheduler.start()
        
        with patch.object(scheduler.scheduler, 'shutdown') as mock_shutdown:
            scheduler.stop()
            mock_shutdown.assert_called_once_with(wait=True)
    
    def test_stop_scheduler_not_running(self, scheduler):
        """测试停止未运行的调度器"""
        # 确保调度器未运行
        if scheduler.scheduler.running:
            scheduler.scheduler.shutdown()
        
        with patch.object(scheduler.scheduler, 'shutdown') as mock_shutdown:
            scheduler.stop()
            mock_shutdown.assert_not_called()
    
    def test_update_schedule_enabled(self, scheduler, mock_config):
        """测试更新调度配置（启用）"""
        with patch.object(scheduler.scheduler, 'add_job') as mock_add_job, \
             patch.object(scheduler.scheduler, 'get_job', return_value=None):
            
            scheduler.update_schedule(mock_config)
            
            # 验证添加了调度任务
            mock_add_job.assert_called_once()
            call_kwargs = mock_add_job.call_args[1]
            assert call_kwargs['id'] == 'backup_job'
            assert call_kwargs['func'] == scheduler._execute_backup_job
    
    def test_update_schedule_disabled(self, scheduler, mock_config):
        """测试更新调度配置（禁用）"""
        mock_config.enabled = False
        
        with patch.object(scheduler.scheduler, 'add_job') as mock_add_job, \
             patch.object(scheduler.scheduler, 'get_job', return_value=None):
            
            scheduler.update_schedule(mock_config)
            
            # 验证未添加调度任务
            mock_add_job.assert_not_called()
    
    def test_update_schedule_remove_existing(self, scheduler, mock_config):
        """测试更新调度配置（移除现有任务）"""
        mock_job = Mock()
        
        with patch.object(scheduler.scheduler, 'get_job', return_value=mock_job), \
             patch.object(scheduler.scheduler, 'remove_job') as mock_remove_job, \
             patch.object(scheduler.scheduler, 'add_job'):
            
            scheduler.update_schedule(mock_config)
            
            # 验证移除了现有任务
            mock_remove_job.assert_called_once_with('backup_job')
    
    def test_trigger_manual_backup_success(self, scheduler, app):
        """测试手动触发备份（成功）"""
        mock_backup_job = Mock()
        mock_backup_job.status = 'success'
        mock_backup_job.filename = 'backup_20240115_143022.tar.gz'
        
        with patch.object(scheduler.engine, 'execute_backup', return_value=mock_backup_job):
            success, message = scheduler.trigger_manual_backup()
            
            assert success is True
            assert 'backup_20240115_143022.tar.gz' in message
            assert scheduler._job_running is False
    
    def test_trigger_manual_backup_failure(self, scheduler, app):
        """测试手动触发备份（失败）"""
        mock_backup_job = Mock()
        mock_backup_job.status = 'failed'
        mock_backup_job.error_message = '上传失败'
        
        with patch.object(scheduler.engine, 'execute_backup', return_value=mock_backup_job):
            success, message = scheduler.trigger_manual_backup()
            
            assert success is False
            assert '上传失败' in message
            assert scheduler._job_running is False
    
    def test_trigger_manual_backup_already_running(self, scheduler):
        """测试手动触发备份（已有任务运行）"""
        scheduler._job_running = True
        
        success, message = scheduler.trigger_manual_backup()
        
        assert success is False
        assert '正在执行中' in message
    
    def test_trigger_manual_backup_exception(self, scheduler, app):
        """测试手动触发备份（异常）"""
        with patch.object(scheduler.engine, 'execute_backup', side_effect=Exception('测试异常')):
            success, message = scheduler.trigger_manual_backup()
            
            assert success is False
            assert '测试异常' in message
            assert scheduler._job_running is False
    
    def test_execute_backup_job_success(self, scheduler, app):
        """测试执行备份任务（成功）"""
        mock_backup_job = Mock()
        mock_backup_job.status = 'success'
        mock_backup_job.filename = 'backup_20240115_143022.tar.gz'
        
        with patch.object(scheduler.engine, 'execute_backup', return_value=mock_backup_job):
            scheduler._execute_backup_job()
            
            assert scheduler._job_running is False
    
    def test_execute_backup_job_failure(self, scheduler, app):
        """测试执行备份任务（失败）"""
        mock_backup_job = Mock()
        mock_backup_job.status = 'failed'
        mock_backup_job.error_message = '上传失败'
        
        with patch.object(scheduler.engine, 'execute_backup', return_value=mock_backup_job):
            scheduler._execute_backup_job()
            
            assert scheduler._job_running is False
    
    def test_execute_backup_job_already_running(self, scheduler):
        """测试执行备份任务（已有任务运行）"""
        scheduler._job_running = True
        
        with patch.object(scheduler.engine, 'execute_backup') as mock_execute:
            scheduler._execute_backup_job()
            
            # 验证未执行备份
            mock_execute.assert_not_called()
    
    def test_execute_backup_job_exception(self, scheduler, app):
        """测试执行备份任务（异常）"""
        with patch.object(scheduler.engine, 'execute_backup', side_effect=Exception('测试异常')):
            scheduler._execute_backup_job()
            
            assert scheduler._job_running is False
    
    def test_create_trigger_hourly(self, scheduler):
        """测试创建每小时触发器"""
        trigger = scheduler._create_trigger('hourly')
        
        assert trigger is not None
        # 验证触发器配置
        assert hasattr(trigger, 'fields')
    
    def test_create_trigger_daily(self, scheduler):
        """测试创建每天触发器"""
        trigger = scheduler._create_trigger('daily')
        
        assert trigger is not None
        assert hasattr(trigger, 'fields')
    
    def test_create_trigger_weekly(self, scheduler):
        """测试创建每周触发器"""
        trigger = scheduler._create_trigger('weekly')
        
        assert trigger is not None
        assert hasattr(trigger, 'fields')
    
    def test_create_trigger_cron_5_parts(self, scheduler):
        """测试创建cron触发器（5部分）"""
        trigger = scheduler._create_trigger('cron', '0 2 * * *')
        
        assert trigger is not None
        assert hasattr(trigger, 'fields')
    
    def test_create_trigger_cron_6_parts(self, scheduler):
        """测试创建cron触发器（6部分）"""
        trigger = scheduler._create_trigger('cron', '0 0 2 * * *')
        
        assert trigger is not None
        assert hasattr(trigger, 'fields')
    
    def test_create_trigger_cron_no_value(self, scheduler):
        """测试创建cron触发器（无表达式）"""
        trigger = scheduler._create_trigger('cron', None)
        
        assert trigger is None
    
    def test_create_trigger_cron_invalid_format(self, scheduler):
        """测试创建cron触发器（无效格式）"""
        trigger = scheduler._create_trigger('cron', '0 2 *')
        
        assert trigger is None
    
    def test_create_trigger_invalid_type(self, scheduler):
        """测试创建触发器（无效类型）"""
        trigger = scheduler._create_trigger('invalid_type')
        
        assert trigger is None
    
    def test_concurrent_execution_protection(self, scheduler, app):
        """测试并发执行保护"""
        mock_backup_job = Mock()
        mock_backup_job.status = 'success'
        mock_backup_job.filename = 'backup_20240115_143022.tar.gz'
        
        # 模拟长时间运行的备份任务
        def slow_backup(*args, **kwargs):
            time.sleep(0.1)
            return mock_backup_job
        
        with patch.object(scheduler.engine, 'execute_backup', side_effect=slow_backup):
            # 启动第一个备份任务
            import threading
            thread1 = threading.Thread(target=scheduler._execute_backup_job)
            thread1.start()
            
            # 等待第一个任务开始
            time.sleep(0.01)
            
            # 尝试启动第二个备份任务（应该被拒绝）
            with patch.object(scheduler.engine, 'execute_backup') as mock_execute:
                scheduler._execute_backup_job()
                # 验证第二个任务未执行
                mock_execute.assert_not_called()
            
            # 等待第一个任务完成
            thread1.join()
            
            assert scheduler._job_running is False
