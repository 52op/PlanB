"""
Unit tests for EmailStorageAdapter

Tests verify email adapter functionality including sending backup files as
email attachments, test email sending, and proper handling of unsupported
operations (download, list, delete).

Requirements: 1.4, 4.2, 4.5, 15.4
"""

import unittest
from unittest.mock import Mock, patch, mock_open, MagicMock
import os
from services.storage.email_adapter import EmailStorageAdapter
from services.storage.base import StorageAdapter


class TestEmailStorageAdapterInitialization(unittest.TestCase):
    """Test EmailStorageAdapter initialization"""
    
    def test_email_adapter_inherits_from_storage_adapter(self):
        """测试EmailStorageAdapter继承自StorageAdapter"""
        self.assertTrue(issubclass(EmailStorageAdapter, StorageAdapter))
    
    def test_email_adapter_initialization(self):
        """测试EmailStorageAdapter初始化"""
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        
        self.assertEqual(adapter.recipient, 'backup@example.com')


class TestEmailStorageAdapterUpload(unittest.TestCase):
    """Test email upload (send) functionality"""
    
    @patch('services.storage.email_adapter.SystemSetting')
    @patch('services.storage.email_adapter.smtplib.SMTP_SSL')
    @patch('services.storage.email_adapter.os.path.exists')
    @patch('services.storage.email_adapter.os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test backup data')
    def test_upload_success_with_ssl(self, mock_file, mock_getsize, mock_exists, 
                                      mock_smtp_ssl, mock_setting):
        """测试使用SSL成功发送备份邮件"""
        # Setup mocks
        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024  # 1MB
        
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': 'smtp.example.com',
            'smtp_sender': 'noreply@example.com',
            'smtp_port': '465',
            'smtp_username': 'user',
            'smtp_password': 'pass',
            'smtp_use_ssl': 'true',
            'site_name': 'Test Site'
        }.get(key, default)
        
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.upload('/local/backup.tar.gz', 'backup_20240115.tar.gz')
        
        self.assertTrue(success)
        self.assertIn("sent to backup@example.com", message)
        mock_server.login.assert_called_once_with('user', 'pass')
        mock_server.send_message.assert_called_once()
    
    @patch('services.storage.email_adapter.SystemSetting')
    @patch('services.storage.email_adapter.smtplib.SMTP')
    @patch('services.storage.email_adapter.os.path.exists')
    @patch('services.storage.email_adapter.os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test backup data')
    def test_upload_success_without_ssl(self, mock_file, mock_getsize, mock_exists,
                                         mock_smtp, mock_setting):
        """测试不使用SSL成功发送备份邮件"""
        # Setup mocks
        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024  # 1MB
        
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': 'smtp.example.com',
            'smtp_sender': 'noreply@example.com',
            'smtp_port': '587',
            'smtp_username': 'user',
            'smtp_password': 'pass',
            'smtp_use_ssl': 'false',
            'site_name': 'Test Site'
        }.get(key, default)
        
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.upload('/local/backup.tar.gz', 'backup_20240115.tar.gz')
        
        self.assertTrue(success)
        self.assertIn("sent to backup@example.com", message)
        mock_server.ehlo.assert_called()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('user', 'pass')
        mock_server.send_message.assert_called_once()
    
    @patch('services.storage.email_adapter.os.path.exists')
    def test_upload_file_not_found(self, mock_exists):
        """测试文件不存在时上传失败"""
        mock_exists.return_value = False
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.upload('/local/backup.tar.gz', 'backup_20240115.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("File not found", message)
    
    @patch('services.storage.email_adapter.os.path.exists')
    @patch('services.storage.email_adapter.os.path.getsize')
    def test_upload_file_too_large(self, mock_getsize, mock_exists):
        """测试文件过大时上传失败"""
        mock_exists.return_value = True
        mock_getsize.return_value = 30 * 1024 * 1024  # 30MB (exceeds 25MB limit)
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.upload('/local/backup.tar.gz', 'backup_20240115.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("too large for email", message)
        self.assertIn("30.0MB", message)
    
    @patch('services.storage.email_adapter.SystemSetting')
    @patch('services.storage.email_adapter.os.path.exists')
    @patch('services.storage.email_adapter.os.path.getsize')
    def test_upload_smtp_not_configured(self, mock_getsize, mock_exists, mock_setting):
        """测试SMTP未配置时上传失败"""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024  # 1MB
        
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': '',
            'smtp_sender': '',
        }.get(key, default)
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.upload('/local/backup.tar.gz', 'backup_20240115.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("SMTP server not configured", message)
    
    @patch('services.storage.email_adapter.SystemSetting')
    @patch('services.storage.email_adapter.smtplib.SMTP_SSL')
    @patch('services.storage.email_adapter.os.path.exists')
    @patch('services.storage.email_adapter.os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test backup data')
    def test_upload_smtp_error(self, mock_file, mock_getsize, mock_exists,
                                mock_smtp_ssl, mock_setting):
        """测试SMTP发送失败"""
        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024  # 1MB
        
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': 'smtp.example.com',
            'smtp_sender': 'noreply@example.com',
            'smtp_port': '465',
            'smtp_username': 'user',
            'smtp_password': 'pass',
            'smtp_use_ssl': 'true',
            'site_name': 'Test Site'
        }.get(key, default)
        
        mock_server = MagicMock()
        mock_server.send_message.side_effect = Exception("SMTP error")
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.upload('/local/backup.tar.gz', 'backup_20240115.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("Failed to send backup email", message)
        self.assertIn("SMTP error", message)
    
    @patch('services.storage.email_adapter.SystemSetting')
    @patch('services.storage.email_adapter.smtplib.SMTP_SSL')
    @patch('services.storage.email_adapter.os.path.exists')
    @patch('services.storage.email_adapter.os.path.getsize')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test backup data')
    def test_upload_email_contains_backup_info(self, mock_file, mock_getsize, mock_exists,
                                                 mock_smtp_ssl, mock_setting):
        """测试邮件包含备份信息"""
        mock_exists.return_value = True
        mock_getsize.return_value = 2 * 1024 * 1024  # 2MB
        
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': 'smtp.example.com',
            'smtp_sender': 'noreply@example.com',
            'smtp_port': '465',
            'smtp_username': 'user',
            'smtp_password': 'pass',
            'smtp_use_ssl': 'true',
            'site_name': 'Test Site'
        }.get(key, default)
        
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.upload('/local/backup.tar.gz', 'backup_20240115.tar.gz')
        
        self.assertTrue(success)
        
        # Verify send_message was called with an EmailMessage
        call_args = mock_server.send_message.call_args
        email_message = call_args[0][0]
        
        # Check email headers
        self.assertEqual(email_message['To'], 'backup@example.com')
        self.assertEqual(email_message['From'], 'noreply@example.com')
        self.assertIn('Test Site', email_message['Subject'])
        self.assertIn('backup_20240115.tar.gz', email_message['Subject'])


class TestEmailStorageAdapterDownload(unittest.TestCase):
    """Test email download (not supported)"""
    
    def test_download_not_supported(self):
        """测试下载操作不支持"""
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.download('backup.tar.gz', '/local/backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("Download not supported", message)
        self.assertIn("email inbox", message)


class TestEmailStorageAdapterListFiles(unittest.TestCase):
    """Test email list files (not supported)"""
    
    def test_list_files_not_supported(self):
        """测试列出文件操作不支持"""
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        files = adapter.list_files()
        
        self.assertEqual(files, [])
    
    def test_list_files_with_directory_not_supported(self):
        """测试指定目录列出文件操作不支持"""
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        files = adapter.list_files('/some/dir')
        
        self.assertEqual(files, [])


class TestEmailStorageAdapterDelete(unittest.TestCase):
    """Test email delete (not supported)"""
    
    def test_delete_not_supported(self):
        """测试删除操作不支持"""
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.delete('backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("Delete not supported", message)
        self.assertIn("inbox", message)


class TestEmailStorageAdapterTestConnection(unittest.TestCase):
    """Test email connection testing"""
    
    @patch('services.storage.email_adapter.SystemSetting')
    @patch('services.storage.email_adapter.smtplib.SMTP_SSL')
    def test_connection_test_success_with_ssl(self, mock_smtp_ssl, mock_setting):
        """测试使用SSL成功发送测试邮件"""
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': 'smtp.example.com',
            'smtp_sender': 'noreply@example.com',
            'smtp_port': '465',
            'smtp_username': 'user',
            'smtp_password': 'pass',
            'smtp_use_ssl': 'true',
            'site_name': 'Test Site'
        }.get(key, default)
        
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.test_connection()
        
        self.assertTrue(success)
        self.assertIn("Test email sent successfully", message)
        self.assertIn("backup@example.com", message)
        mock_server.login.assert_called_once_with('user', 'pass')
        mock_server.send_message.assert_called_once()
    
    @patch('services.storage.email_adapter.SystemSetting')
    @patch('services.storage.email_adapter.smtplib.SMTP')
    def test_connection_test_success_without_ssl(self, mock_smtp, mock_setting):
        """测试不使用SSL成功发送测试邮件"""
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': 'smtp.example.com',
            'smtp_sender': 'noreply@example.com',
            'smtp_port': '587',
            'smtp_username': 'user',
            'smtp_password': 'pass',
            'smtp_use_ssl': 'false',
            'site_name': 'Test Site'
        }.get(key, default)
        
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.test_connection()
        
        self.assertTrue(success)
        self.assertIn("Test email sent successfully", message)
        mock_server.ehlo.assert_called()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('user', 'pass')
        mock_server.send_message.assert_called_once()
    
    @patch('services.storage.email_adapter.SystemSetting')
    def test_connection_test_smtp_not_configured(self, mock_setting):
        """测试SMTP未配置时连接测试失败"""
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': '',
            'smtp_sender': '',
        }.get(key, default)
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.test_connection()
        
        self.assertFalse(success)
        self.assertIn("SMTP server not configured", message)
    
    @patch('services.storage.email_adapter.SystemSetting')
    @patch('services.storage.email_adapter.smtplib.SMTP_SSL')
    def test_connection_test_smtp_error(self, mock_smtp_ssl, mock_setting):
        """测试SMTP连接失败"""
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': 'smtp.example.com',
            'smtp_sender': 'noreply@example.com',
            'smtp_port': '465',
            'smtp_username': 'user',
            'smtp_password': 'pass',
            'smtp_use_ssl': 'true',
            'site_name': 'Test Site'
        }.get(key, default)
        
        mock_server = MagicMock()
        mock_server.send_message.side_effect = Exception("Authentication failed")
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.test_connection()
        
        self.assertFalse(success)
        self.assertIn("Failed to send test email", message)
        self.assertIn("Authentication failed", message)
    
    @patch('services.storage.email_adapter.SystemSetting')
    @patch('services.storage.email_adapter.smtplib.SMTP_SSL')
    def test_connection_test_email_contains_test_info(self, mock_smtp_ssl, mock_setting):
        """测试邮件包含测试信息"""
        mock_setting.get.side_effect = lambda key, default=None: {
            'smtp_host': 'smtp.example.com',
            'smtp_sender': 'noreply@example.com',
            'smtp_port': '465',
            'smtp_username': 'user',
            'smtp_password': 'pass',
            'smtp_use_ssl': 'true',
            'site_name': 'Test Site'
        }.get(key, default)
        
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        adapter = EmailStorageAdapter(recipient='backup@example.com')
        success, message = adapter.test_connection()
        
        self.assertTrue(success)
        
        # Verify send_message was called with an EmailMessage
        call_args = mock_server.send_message.call_args
        email_message = call_args[0][0]
        
        # Check email headers
        self.assertEqual(email_message['To'], 'backup@example.com')
        self.assertEqual(email_message['From'], 'noreply@example.com')
        self.assertIn('Test Site', email_message['Subject'])
        self.assertIn('测试', email_message['Subject'])


if __name__ == '__main__':
    unittest.main()
