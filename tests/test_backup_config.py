# -*- coding: utf-8 -*-
"""
备份配置管理器测试
Backup Configuration Manager Tests
"""

import unittest
from tests.support import PlanningTestCase
from models import BackupConfig, db
from services.backup_config import BackupConfigManager


class TestBackupConfigManager(PlanningTestCase):
    """测试BackupConfigManager服务类"""
    
    def test_get_config_returns_none_when_no_config_exists(self):
        """测试当配置不存在时返回None"""
        with self.app.app_context():
            config = BackupConfigManager.get_config()
            self.assertIsNone(config)
    
    def test_get_config_returns_existing_config(self):
        """测试获取已存在的配置"""
        with self.app.app_context():
            # 创建配置
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_username='user',
                ftp_password='pass'
            )
            db.session.add(config)
            db.session.commit()
            
            # 获取配置
            retrieved_config = BackupConfigManager.get_config()
            self.assertIsNotNone(retrieved_config)
            self.assertEqual(retrieved_config.storage_type, 'ftp')
            self.assertEqual(retrieved_config.ftp_host, 'ftp.example.com')
    
    def test_update_config_creates_new_config_when_none_exists(self):
        """测试当配置不存在时创建新配置"""
        with self.app.app_context():
            config_data = {
                'storage_type': 'ftp',
                'schedule_type': 'daily',
                'ftp_host': 'ftp.example.com',
                'ftp_port': 21,
                'ftp_username': 'testuser',
                'ftp_password': 'testpass',
                'retention_count': 5
            }
            
            config = BackupConfigManager.update_config(config_data)
            
            self.assertIsNotNone(config)
            self.assertEqual(config.storage_type, 'ftp')
            self.assertEqual(config.ftp_host, 'ftp.example.com')
            self.assertEqual(config.retention_count, 5)
    
    def test_update_config_updates_existing_config(self):
        """测试更新已存在的配置"""
        with self.app.app_context():
            # 创建初始配置
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='old.example.com',
                ftp_username='user',
                ftp_password='pass'
            )
            db.session.add(config)
            db.session.commit()
            
            # 更新配置
            config_data = {
                'ftp_host': 'new.example.com',
                'retention_count': 15
            }
            
            updated_config = BackupConfigManager.update_config(config_data)
            
            self.assertEqual(updated_config.ftp_host, 'new.example.com')
            self.assertEqual(updated_config.retention_count, 15)
            # 验证其他字段未改变
            self.assertEqual(updated_config.storage_type, 'ftp')
    
    def test_validate_config_rejects_invalid_storage_type(self):
        """测试验证拒绝无效的存储类型"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='invalid',
                schedule_type='daily'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertFalse(is_valid)
            self.assertIn('存储类型', error_msg)
    
    def test_validate_config_rejects_invalid_schedule_type(self):
        """测试验证拒绝无效的调度类型"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='invalid',
                ftp_host='ftp.example.com',
                ftp_username='user',
                ftp_password='pass'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertFalse(is_valid)
            self.assertIn('调度类型', error_msg)
    
    def test_validate_config_requires_cron_expression_for_cron_schedule(self):
        """测试cron调度类型需要cron表达式"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='cron',
                schedule_value=None,
                ftp_host='ftp.example.com',
                ftp_username='user',
                ftp_password='pass'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertFalse(is_valid)
            self.assertIn('cron表达式', error_msg)
    
    def test_validate_config_accepts_valid_cron_expression(self):
        """测试验证接受有效的cron表达式"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='cron',
                schedule_value='0 2 * * *',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='user',
                ftp_password='pass'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertTrue(is_valid)
            self.assertEqual(error_msg, '')
    
    def test_validate_config_rejects_invalid_retention_count(self):
        """测试验证拒绝无效的保留数量"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                retention_count=0,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='user',
                ftp_password='pass'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertFalse(is_valid)
            self.assertIn('保留数量', error_msg)
    
    def test_validate_config_requires_ftp_fields_for_ftp_storage(self):
        """测试FTP存储需要FTP字段"""
        with self.app.app_context():
            # 缺少主机
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_username='user',
                ftp_password='pass'
            )
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            self.assertFalse(is_valid)
            self.assertIn('FTP主机', error_msg)
            
            # 缺少用户名
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_password='pass'
            )
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            self.assertFalse(is_valid)
            self.assertIn('用户名', error_msg)
            
            # 缺少密码
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_username='user'
            )
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            self.assertFalse(is_valid)
            self.assertIn('密码', error_msg)
    
    def test_validate_config_requires_email_for_email_storage(self):
        """测试邮件存储需要邮箱地址"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='email',
                schedule_type='daily'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertFalse(is_valid)
            self.assertIn('邮箱', error_msg)
    
    def test_validate_config_validates_email_format(self):
        """测试验证邮箱格式"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='email',
                schedule_type='daily',
                email_recipient='invalid-email'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertFalse(is_valid)
            self.assertIn('邮箱地址格式', error_msg)
    
    def test_validate_config_requires_s3_fields_for_s3_storage(self):
        """测试S3存储需要S3字段"""
        with self.app.app_context():
            # 缺少存储桶
            config = BackupConfig(
                storage_type='s3',
                schedule_type='daily',
                s3_access_key='key',
                s3_secret_key='secret'
            )
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            self.assertFalse(is_valid)
            self.assertIn('存储桶', error_msg)
            
            # 缺少访问密钥
            config = BackupConfig(
                storage_type='s3',
                schedule_type='daily',
                s3_bucket='my-bucket',
                s3_secret_key='secret'
            )
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            self.assertFalse(is_valid)
            self.assertIn('访问密钥', error_msg)
            
            # 缺少密钥
            config = BackupConfig(
                storage_type='s3',
                schedule_type='daily',
                s3_bucket='my-bucket',
                s3_access_key='key'
            )
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            self.assertFalse(is_valid)
            self.assertIn('密钥', error_msg)
    
    def test_validate_config_accepts_valid_ftp_config(self):
        """测试验证接受有效的FTP配置"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='user',
                ftp_password='pass',
                retention_count=10,
                backup_mode='full'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertTrue(is_valid)
            self.assertEqual(error_msg, '')
    
    def test_validate_config_accepts_valid_email_config(self):
        """测试验证接受有效的邮件配置"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='email',
                schedule_type='weekly',
                email_recipient='admin@example.com',
                retention_count=5,
                backup_mode='full'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertTrue(is_valid)
            self.assertEqual(error_msg, '')
    
    def test_validate_config_accepts_valid_s3_config(self):
        """测试验证接受有效的S3配置"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='s3',
                schedule_type='hourly',
                s3_bucket='my-backup-bucket',
                s3_access_key='AKIAIOSFODNN7EXAMPLE',
                s3_secret_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                retention_count=20,
                backup_mode='incremental'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertTrue(is_valid)
            self.assertEqual(error_msg, '')
    
    def test_update_config_raises_error_on_invalid_config(self):
        """测试更新无效配置时抛出异常"""
        with self.app.app_context():
            config_data = {
                'storage_type': 'ftp',
                'schedule_type': 'daily',
                'ftp_host': 'ftp.example.com',
                # 缺少必需的用户名和密码
            }
            
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.update_config(config_data)
            
            self.assertIn('用户名', str(context.exception))
    
    def test_validate_email_accepts_valid_emails(self):
        """测试邮箱验证接受有效邮箱"""
        valid_emails = [
            'user@example.com',
            'test.user@example.co.uk',
            'admin+backup@company.org',
            'user123@test-domain.com'
        ]
        
        for email in valid_emails:
            self.assertTrue(
                BackupConfigManager._validate_email(email),
                f"应该接受有效邮箱: {email}"
            )
    
    def test_validate_email_rejects_invalid_emails(self):
        """测试邮箱验证拒绝无效邮箱"""
        invalid_emails = [
            'invalid',
            '@example.com',
            'user@',
            'user@.com',
            'user space@example.com',
            ''
        ]
        
        for email in invalid_emails:
            self.assertFalse(
                BackupConfigManager._validate_email(email),
                f"应该拒绝无效邮箱: {email}"
            )
    
    def test_validate_cron_expression_accepts_valid_expressions(self):
        """测试cron表达式验证接受有效表达式"""
        valid_crons = [
            '0 2 * * *',           # 每天凌晨2点
            '*/15 * * * *',        # 每15分钟
            '0 0 1 * *',           # 每月1号
            '0 0 * * 0',           # 每周日
            '0 */2 * * *',         # 每2小时
            '0 0 2 * * *'          # 6部分格式（带秒）
        ]
        
        for cron in valid_crons:
            self.assertTrue(
                BackupConfigManager._validate_cron_expression(cron),
                f"应该接受有效cron表达式: {cron}"
            )
    
    def test_validate_cron_expression_rejects_invalid_expressions(self):
        """测试cron表达式验证拒绝无效表达式"""
        invalid_crons = [
            '',
            '* * * *',             # 只有4部分
            '* * * * * * *',       # 7部分
            'invalid cron',
            '0 2 * * * extra'
        ]
        
        for cron in invalid_crons:
            self.assertFalse(
                BackupConfigManager._validate_cron_expression(cron),
                f"应该拒绝无效cron表达式: {cron}"
            )
    
    def test_validate_config_rejects_invalid_ftp_port(self):
        """测试验证拒绝无效的FTP端口"""
        with self.app.app_context():
            # 端口为0
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_port=0,
                ftp_username='user',
                ftp_password='pass'
            )
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            self.assertFalse(is_valid)
            self.assertIn('端口', error_msg)
            
            # 端口超过65535
            config.ftp_port = 70000
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            self.assertFalse(is_valid)
            self.assertIn('端口', error_msg)
    
    def test_validate_config_validates_notification_email_format(self):
        """测试验证通知邮箱格式"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='user',
                ftp_password='pass',
                notification_enabled=True,
                notification_email='invalid-email'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertFalse(is_valid)
            self.assertIn('通知邮箱', error_msg)
    
    def test_validate_config_rejects_invalid_backup_mode(self):
        """测试验证拒绝无效的备份模式"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='user',
                ftp_password='pass',
                backup_mode='invalid'
            )
            
            is_valid, error_msg = BackupConfigManager.validate_config(config)
            
            self.assertFalse(is_valid)
            self.assertIn('备份模式', error_msg)
    
    # Task 2.2: 测试 test_connection() 方法
    
    def test_test_connection_returns_error_when_no_config_exists(self):
        """测试当配置不存在时返回错误"""
        with self.app.app_context():
            success, message = BackupConfigManager.test_connection()
            
            self.assertFalse(success)
            self.assertIn('配置不存在', message)
    
    def test_test_connection_validates_config_before_testing(self):
        """测试连接前验证配置有效性"""
        with self.app.app_context():
            # 创建无效配置
            config = BackupConfig(
                storage_type='invalid',
                schedule_type='daily'
            )
            
            success, message = BackupConfigManager.test_connection(config)
            
            self.assertFalse(success)
            self.assertIn('配置验证失败', message)
    
    def test_test_connection_returns_success_for_ftp_config(self):
        """测试FTP配置连接测试"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='user',
                ftp_password='pass'
            )
            
            success, message = BackupConfigManager.test_connection(config)
            
            # 由于适配器尚未实现，应返回成功和提示信息
            self.assertTrue(success)
            self.assertIn('FTP', message)
    
    def test_test_connection_returns_success_for_email_config(self):
        """测试邮件配置连接测试"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='email',
                schedule_type='daily',
                email_recipient='admin@example.com'
            )
            
            success, message = BackupConfigManager.test_connection(config)
            
            # 由于适配器尚未实现，应返回成功和提示信息
            self.assertTrue(success)
            self.assertIn('邮件', message)
    
    def test_test_connection_returns_success_for_s3_config(self):
        """测试S3配置连接测试"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='s3',
                schedule_type='daily',
                s3_bucket='my-bucket',
                s3_access_key='key',
                s3_secret_key='secret'
            )
            
            success, message = BackupConfigManager.test_connection(config)
            
            # 由于适配器尚未实现，应返回成功和提示信息
            self.assertTrue(success)
            self.assertIn('S3', message)
    
    def test_test_connection_uses_current_config_when_none_provided(self):
        """测试未提供配置时使用当前配置"""
        with self.app.app_context():
            # 创建并保存配置
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='user',
                ftp_password='pass'
            )
            db.session.add(config)
            db.session.commit()
            
            # 不传入配置参数
            success, message = BackupConfigManager.test_connection()
            
            self.assertTrue(success)
    
    # Task 2.2: 测试 export_config() 方法
    
    def test_export_config_returns_empty_dict_when_no_config_exists(self):
        """测试当配置不存在时返回空字典"""
        with self.app.app_context():
            exported = BackupConfigManager.export_config()
            
            self.assertEqual(exported, {})
    
    def test_export_config_excludes_sensitive_ftp_fields(self):
        """测试导出FTP配置时排除敏感字段"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='user',
                ftp_password='secret_password',
                ftp_path='/backups'
            )
            db.session.add(config)
            db.session.commit()
            
            exported = BackupConfigManager.export_config()
            
            # 应包含非敏感字段
            self.assertEqual(exported['storage_type'], 'ftp')
            self.assertEqual(exported['ftp_host'], 'ftp.example.com')
            self.assertEqual(exported['ftp_port'], 21)
            self.assertEqual(exported['ftp_username'], 'user')
            self.assertEqual(exported['ftp_path'], '/backups')
            
            # 不应包含敏感字段
            self.assertNotIn('ftp_password', exported)
    
    def test_export_config_excludes_sensitive_s3_fields(self):
        """测试导出S3配置时排除敏感字段"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='s3',
                schedule_type='daily',
                s3_endpoint='https://s3.example.com',
                s3_bucket='my-bucket',
                s3_access_key='AKIAIOSFODNN7EXAMPLE',
                s3_secret_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                s3_path_prefix='backups/',
                s3_region='us-east-1'
            )
            db.session.add(config)
            db.session.commit()
            
            exported = BackupConfigManager.export_config()
            
            # 应包含非敏感字段
            self.assertEqual(exported['storage_type'], 's3')
            self.assertEqual(exported['s3_endpoint'], 'https://s3.example.com')
            self.assertEqual(exported['s3_bucket'], 'my-bucket')
            self.assertEqual(exported['s3_path_prefix'], 'backups/')
            self.assertEqual(exported['s3_region'], 'us-east-1')
            
            # 不应包含敏感字段
            self.assertNotIn('s3_access_key', exported)
            self.assertNotIn('s3_secret_key', exported)
    
    def test_export_config_includes_common_fields(self):
        """测试导出配置包含通用字段"""
        with self.app.app_context():
            config = BackupConfig(
                enabled=True,
                storage_type='email',
                schedule_type='weekly',
                schedule_value='0 0 * * 0',
                retention_count=15,
                backup_mode='incremental',
                encryption_enabled=True,
                email_recipient='admin@example.com',
                notification_enabled=True,
                notification_email='notify@example.com',
                storage_warning_threshold_mb=2048
            )
            db.session.add(config)
            db.session.commit()
            
            exported = BackupConfigManager.export_config()
            
            self.assertEqual(exported['enabled'], True)
            self.assertEqual(exported['storage_type'], 'email')
            self.assertEqual(exported['schedule_type'], 'weekly')
            self.assertEqual(exported['schedule_value'], '0 0 * * 0')
            self.assertEqual(exported['retention_count'], 15)
            self.assertEqual(exported['backup_mode'], 'incremental')
            self.assertEqual(exported['encryption_enabled'], True)
            self.assertEqual(exported['notification_enabled'], True)
            self.assertEqual(exported['notification_email'], 'notify@example.com')
            self.assertEqual(exported['storage_warning_threshold_mb'], 2048)
            self.assertEqual(exported['email_recipient'], 'admin@example.com')
    
    def test_export_config_excludes_encryption_key_hash(self):
        """测试导出配置不包含加密密钥哈希"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='user',
                ftp_password='pass',
                encryption_enabled=True,
                encryption_key_hash='hashed_key_value'
            )
            db.session.add(config)
            db.session.commit()
            
            exported = BackupConfigManager.export_config()
            
            self.assertEqual(exported['encryption_enabled'], True)
            self.assertNotIn('encryption_key_hash', exported)
    
    # Task 2.2: 测试 import_config() 方法
    
    def test_import_config_raises_error_on_empty_data(self):
        """测试导入空数据时抛出异常"""
        with self.app.app_context():
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config({})
            
            self.assertIn('不能为空', str(context.exception))
    
    def test_import_config_raises_error_on_missing_required_fields(self):
        """测试导入缺少必需字段时抛出异常"""
        with self.app.app_context():
            # 缺少 storage_type
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config({'schedule_type': 'daily'})
            self.assertIn('storage_type', str(context.exception))
            
            # 缺少 schedule_type
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config({'storage_type': 'ftp'})
            self.assertIn('schedule_type', str(context.exception))
    
    def test_import_config_raises_error_on_invalid_storage_type(self):
        """测试导入无效存储类型时抛出异常"""
        with self.app.app_context():
            config_data = {
                'storage_type': 'invalid',
                'schedule_type': 'daily'
            }
            
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config(config_data)
            
            self.assertIn('无效的存储类型', str(context.exception))
    
    def test_import_config_raises_error_on_invalid_schedule_type(self):
        """测试导入无效调度类型时抛出异常"""
        with self.app.app_context():
            config_data = {
                'storage_type': 'ftp',
                'schedule_type': 'invalid'
            }
            
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config(config_data)
            
            self.assertIn('无效的调度类型', str(context.exception))
    
    def test_import_config_raises_error_on_missing_ftp_fields(self):
        """测试导入FTP配置缺少必需字段时抛出异常"""
        with self.app.app_context():
            # 缺少 ftp_host
            config_data = {
                'storage_type': 'ftp',
                'schedule_type': 'daily',
                'ftp_username': 'user'
            }
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config(config_data)
            self.assertIn('主机地址', str(context.exception))
            
            # 缺少 ftp_username
            config_data = {
                'storage_type': 'ftp',
                'schedule_type': 'daily',
                'ftp_host': 'ftp.example.com'
            }
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config(config_data)
            self.assertIn('用户名', str(context.exception))
    
    def test_import_config_raises_error_on_missing_email_fields(self):
        """测试导入邮件配置缺少必需字段时抛出异常"""
        with self.app.app_context():
            config_data = {
                'storage_type': 'email',
                'schedule_type': 'daily'
            }
            
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config(config_data)
            
            self.assertIn('收件人地址', str(context.exception))
    
    def test_import_config_raises_error_on_missing_s3_fields(self):
        """测试导入S3配置缺少必需字段时抛出异常"""
        with self.app.app_context():
            config_data = {
                'storage_type': 's3',
                'schedule_type': 'daily'
            }
            
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config(config_data)
            
            self.assertIn('存储桶名称', str(context.exception))
    
    def test_import_config_raises_error_when_missing_sensitive_info(self):
        """测试导入配置缺少敏感信息时提示用户补充"""
        with self.app.app_context():
            # FTP配置缺少密码
            config_data = {
                'storage_type': 'ftp',
                'schedule_type': 'daily',
                'ftp_host': 'ftp.example.com',
                'ftp_port': 21,
                'ftp_username': 'user',
                'ftp_path': '/backups'
            }
            
            with self.assertRaises(ValueError) as context:
                BackupConfigManager.import_config(config_data)
            
            # 应提示补充敏感信息
            self.assertIn('敏感信息', str(context.exception))
    
    def test_import_config_succeeds_with_complete_ftp_data(self):
        """测试导入完整FTP配置成功"""
        with self.app.app_context():
            config_data = {
                'storage_type': 'ftp',
                'schedule_type': 'daily',
                'ftp_host': 'ftp.example.com',
                'ftp_port': 21,
                'ftp_username': 'user',
                'ftp_password': 'password',
                'ftp_path': '/backups',
                'retention_count': 10
            }
            
            config = BackupConfigManager.import_config(config_data)
            
            self.assertIsNotNone(config)
            self.assertEqual(config.storage_type, 'ftp')
            self.assertEqual(config.ftp_host, 'ftp.example.com')
            self.assertEqual(config.ftp_username, 'user')
            self.assertEqual(config.retention_count, 10)
    
    def test_import_config_succeeds_with_complete_email_data(self):
        """测试导入完整邮件配置成功"""
        with self.app.app_context():
            config_data = {
                'storage_type': 'email',
                'schedule_type': 'weekly',
                'email_recipient': 'admin@example.com',
                'retention_count': 5
            }
            
            config = BackupConfigManager.import_config(config_data)
            
            self.assertIsNotNone(config)
            self.assertEqual(config.storage_type, 'email')
            self.assertEqual(config.email_recipient, 'admin@example.com')
            self.assertEqual(config.retention_count, 5)
    
    def test_import_config_succeeds_with_complete_s3_data(self):
        """测试导入完整S3配置成功"""
        with self.app.app_context():
            config_data = {
                'storage_type': 's3',
                'schedule_type': 'hourly',
                's3_endpoint': 'https://s3.example.com',
                's3_bucket': 'my-bucket',
                's3_access_key': 'AKIAIOSFODNN7EXAMPLE',
                's3_secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                's3_path_prefix': 'backups/',
                's3_region': 'us-east-1',
                'retention_count': 20
            }
            
            config = BackupConfigManager.import_config(config_data)
            
            self.assertIsNotNone(config)
            self.assertEqual(config.storage_type, 's3')
            self.assertEqual(config.s3_bucket, 'my-bucket')
            self.assertEqual(config.s3_region, 'us-east-1')
            self.assertEqual(config.retention_count, 20)
    
    def test_import_config_updates_existing_config(self):
        """测试导入配置更新已存在的配置"""
        with self.app.app_context():
            # 创建初始配置
            initial_config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='old.example.com',
                ftp_username='olduser',
                ftp_password='oldpass'
            )
            db.session.add(initial_config)
            db.session.commit()
            
            # 导入新配置
            config_data = {
                'storage_type': 'ftp',
                'schedule_type': 'weekly',
                'ftp_host': 'new.example.com',
                'ftp_port': 2121,
                'ftp_username': 'newuser',
                'ftp_password': 'newpass',
                'retention_count': 15
            }
            
            imported_config = BackupConfigManager.import_config(config_data)
            
            # 验证配置已更新
            self.assertEqual(imported_config.ftp_host, 'new.example.com')
            self.assertEqual(imported_config.ftp_port, 2121)
            self.assertEqual(imported_config.schedule_type, 'weekly')
            self.assertEqual(imported_config.retention_count, 15)
            
            # 验证只有一个配置记录
            all_configs = BackupConfig.query.all()
            self.assertEqual(len(all_configs), 1)


if __name__ == '__main__':
    unittest.main()
