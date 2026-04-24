"""
测试备份通知服务
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from services.backup_notification import NotificationService


class TestNotificationService:
    """测试NotificationService类"""
    
    def test_send_backup_success_notification_disabled(self):
        """测试通知禁用时跳过发送"""
        # 创建测试数据
        config = Mock()
        config.notification_enabled = False
        config.notification_email = "admin@example.com"
        
        backup_job = Mock()
        backup_job.id = 1
        
        # 执行测试
        result = NotificationService.send_backup_success_notification(backup_job, config)
        
        # 验证结果
        assert result is False
    
    def test_send_backup_success_notification_no_email(self):
        """测试未配置邮箱时跳过发送"""
        # 创建测试数据
        config = Mock()
        config.notification_enabled = True
        config.notification_email = None
        
        backup_job = Mock()
        backup_job.id = 1
        
        # 执行测试
        result = NotificationService.send_backup_success_notification(backup_job, config)
        
        # 验证结果
        assert result is False
    
    @patch('services.backup_notification.mailer_is_configured')
    def test_send_backup_success_notification_smtp_not_configured(self, mock_mailer_configured):
        """测试SMTP未配置时跳过发送"""
        # 模拟SMTP未配置
        mock_mailer_configured.return_value = False
        
        # 创建测试数据
        config = Mock()
        config.notification_enabled = True
        config.notification_email = "admin@example.com"
        
        backup_job = Mock()
        backup_job.id = 1
        
        # 执行测试
        result = NotificationService.send_backup_success_notification(backup_job, config)
        
        # 验证结果
        assert result is False
    
    @patch('services.backup_notification.send_logged_mail')
    @patch('services.backup_notification.mailer_is_configured')
    def test_send_backup_success_notification_success(self, mock_mailer_configured, mock_send_mail):
        """测试成功发送备份成功通知"""
        # 模拟配置
        mock_mailer_configured.return_value = True
        mock_send_mail.return_value = True
        
        # 创建测试数据
        config = Mock()
        config.notification_enabled = True
        config.notification_email = "admin@example.com"
        
        backup_job = Mock()
        backup_job.id = 1
        backup_job.trigger_type = "manual"
        backup_job.backup_mode = "full"
        backup_job.started_at = datetime(2024, 1, 15, 14, 30, 0)
        backup_job.completed_at = datetime(2024, 1, 15, 14, 35, 0)
        backup_job.duration_seconds = 300
        backup_job.filename = "backup_20240115_143000.tar.gz"
        backup_job.file_size_bytes = 10485760  # 10 MB
        backup_job.storage_type = "ftp"
        backup_job.is_encrypted = False
        
        # 执行测试
        result = NotificationService.send_backup_success_notification(backup_job, config)
        
        # 验证结果
        assert result is True
        mock_send_mail.assert_called_once()
        
        # 验证邮件参数
        call_args = mock_send_mail.call_args
        assert call_args[1]['event_type'] == 'backup_success'
        assert call_args[1]['recipient'] == 'admin@example.com'
        assert '成功' in call_args[1]['subject']
    
    @patch('services.backup_notification.send_logged_mail')
    @patch('services.backup_notification.mailer_is_configured')
    def test_send_backup_failure_notification_success(self, mock_mailer_configured, mock_send_mail):
        """测试成功发送备份失败通知"""
        # 模拟配置
        mock_mailer_configured.return_value = True
        mock_send_mail.return_value = True
        
        # 创建测试数据
        config = Mock()
        config.notification_enabled = True
        config.notification_email = "admin@example.com"
        
        backup_job = Mock()
        backup_job.id = 2
        backup_job.trigger_type = "auto"
        backup_job.backup_mode = "full"
        backup_job.started_at = datetime(2024, 1, 15, 14, 30, 0)
        backup_job.completed_at = datetime(2024, 1, 15, 14, 31, 0)
        backup_job.duration_seconds = None
        backup_job.filename = None
        backup_job.file_size_bytes = None
        backup_job.storage_type = "ftp"
        backup_job.is_encrypted = False
        backup_job.error_message = "FTP连接失败: Connection timeout"
        
        # 执行测试
        result = NotificationService.send_backup_failure_notification(backup_job, config)
        
        # 验证结果
        assert result is True
        mock_send_mail.assert_called_once()
        
        # 验证邮件参数
        call_args = mock_send_mail.call_args
        assert call_args[1]['event_type'] == 'backup_failure'
        assert call_args[1]['recipient'] == 'admin@example.com'
        assert '失败' in call_args[1]['subject']
    
    @patch('services.backup_notification.send_logged_mail')
    @patch('services.backup_notification.mailer_is_configured')
    def test_send_storage_warning_notification_success(self, mock_mailer_configured, mock_send_mail):
        """测试成功发送存储空间警告通知"""
        # 模拟配置
        mock_mailer_configured.return_value = True
        mock_send_mail.return_value = True
        
        # 创建测试数据
        config = Mock()
        config.notification_enabled = True
        config.notification_email = "admin@example.com"
        config.storage_warning_threshold_mb = 1024
        
        usage_info = {
            'total_size_mb': 1200.5,
            'backup_count': 15,
            'available_space_mb': 500.0,
            'threshold_mb': 1024
        }
        
        # 执行测试
        result = NotificationService.send_storage_warning_notification(config, usage_info)
        
        # 验证结果
        assert result is True
        mock_send_mail.assert_called_once()
        
        # 验证邮件参数
        call_args = mock_send_mail.call_args
        assert call_args[1]['event_type'] == 'backup_storage_warning'
        assert call_args[1]['recipient'] == 'admin@example.com'
        assert '警告' in call_args[1]['subject']
        assert call_args[1]['cooldown_seconds'] == 3600
    
    def test_format_backup_notification_email_success(self):
        """测试格式化成功通知邮件内容"""
        # 创建测试数据
        backup_job = Mock()
        backup_job.id = 1
        backup_job.trigger_type = "manual"
        backup_job.backup_mode = "full"
        backup_job.started_at = datetime(2024, 1, 15, 14, 30, 0)
        backup_job.completed_at = datetime(2024, 1, 15, 14, 35, 0)
        backup_job.duration_seconds = 300
        backup_job.filename = "backup_20240115_143000.tar.gz"
        backup_job.file_size_bytes = 10485760  # 10 MB
        backup_job.storage_type = "ftp"
        backup_job.is_encrypted = True
        
        # 执行测试
        result = NotificationService._format_backup_notification_email(backup_job, is_success=True)
        
        # 验证结果
        assert '成功' in result['subject']
        assert '成功' in result['title']
        assert 'backup_20240115_143000.tar.gz' in result['body_html']
        assert '10.00 MB' in result['body_html']
        assert '已加密' in result['body_html']
        assert '手动' in result['plain_text']
    
    def test_format_backup_notification_email_failure(self):
        """测试格式化失败通知邮件内容"""
        # 创建测试数据
        backup_job = Mock()
        backup_job.id = 2
        backup_job.trigger_type = "auto"
        backup_job.backup_mode = "incremental"
        backup_job.started_at = datetime(2024, 1, 15, 14, 30, 0)
        backup_job.completed_at = datetime(2024, 1, 15, 14, 31, 0)
        backup_job.duration_seconds = None
        backup_job.filename = None
        backup_job.file_size_bytes = None
        backup_job.storage_type = "s3"
        backup_job.is_encrypted = False
        backup_job.error_message = "S3上传失败: Access denied"
        
        # 执行测试
        result = NotificationService._format_backup_notification_email(backup_job, is_success=False)
        
        # 验证结果
        assert '失败' in result['subject']
        assert '失败' in result['title']
        assert 'S3上传失败: Access denied' in result['body_html']
        assert '自动' in result['plain_text']
        assert '增量备份' in result['plain_text']
