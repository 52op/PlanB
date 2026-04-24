"""
Unit tests for FTPStorageAdapter

Tests verify FTP adapter functionality including upload with retry logic,
download, list, delete, and connection testing.

Requirements: 1.3, 4.1, 4.5, 5.3, 15.3
"""

import unittest
from unittest.mock import Mock, patch, mock_open, MagicMock, call
import ftplib
import time
from services.storage.ftp_adapter import FTPStorageAdapter
from services.storage.base import StorageAdapter


class TestFTPStorageAdapterInitialization(unittest.TestCase):
    """Test FTPStorageAdapter initialization"""
    
    def test_ftp_adapter_inherits_from_storage_adapter(self):
        """测试FTPStorageAdapter继承自StorageAdapter"""
        self.assertTrue(issubclass(FTPStorageAdapter, StorageAdapter))
    
    def test_ftp_adapter_initialization(self):
        """测试FTPStorageAdapter初始化"""
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        self.assertEqual(adapter.host, 'ftp.example.com')
        self.assertEqual(adapter.port, 21)
        self.assertEqual(adapter.username, 'user')
        self.assertEqual(adapter.password, 'pass')
        self.assertEqual(adapter.base_path, '/backups')
    
    def test_ftp_adapter_strips_trailing_slash_from_base_path(self):
        """测试FTPStorageAdapter去除base_path末尾的斜杠"""
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups/'
        )
        
        self.assertEqual(adapter.base_path, '/backups')


class TestFTPStorageAdapterConnection(unittest.TestCase):
    """Test FTP connection functionality"""
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_connect_success(self, mock_ftp_class):
        """测试成功连接FTP服务器"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        ftp, error = adapter._connect()
        
        self.assertIsNotNone(ftp)
        self.assertEqual(error, "")
        mock_ftp.connect.assert_called_once_with('ftp.example.com', 21, timeout=30)
        mock_ftp.login.assert_called_once_with('user', 'pass')
        mock_ftp.cwd.assert_called_once_with('/backups')
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_connect_creates_base_path_if_not_exists(self, mock_ftp_class):
        """测试连接时如果base_path不存在则创建"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        # First cwd fails, after creating directory it succeeds
        mock_ftp.cwd.side_effect = [ftplib.error_perm("550 No such directory"), None]
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        # Mock the _create_directory_recursive method to avoid actual directory creation
        with patch.object(adapter, '_create_directory_recursive'):
            ftp, error = adapter._connect()
        
        self.assertIsNotNone(ftp)
        self.assertEqual(error, "")
        self.assertEqual(mock_ftp.cwd.call_count, 2)
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_connect_failure(self, mock_ftp_class):
        """测试FTP连接失败"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.connect.side_effect = Exception("Connection refused")
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        ftp, error = adapter._connect()
        
        self.assertIsNone(ftp)
        self.assertIn("FTP connection failed", error)
        self.assertIn("Connection refused", error)


class TestFTPStorageAdapterUpload(unittest.TestCase):
    """Test FTP upload functionality with retry logic"""
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test data')
    def test_upload_success_first_attempt(self, mock_file, mock_ftp_class):
        """测试首次上传成功"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.upload('/local/backup.tar.gz', 'backup.tar.gz')
        
        self.assertTrue(success)
        self.assertIn("Successfully uploaded", message)
        self.assertIn("backup.tar.gz", message)
        mock_ftp.storbinary.assert_called_once()
        mock_ftp.quit.assert_called_once()
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    @patch('services.storage.ftp_adapter.time.sleep')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test data')
    def test_upload_success_after_retry(self, mock_file, mock_sleep, mock_ftp_class):
        """测试重试后上传成功"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        # First attempt fails, second succeeds
        mock_ftp.storbinary.side_effect = [
            Exception("Network error"),
            None
        ]
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.upload('/local/backup.tar.gz', 'backup.tar.gz')
        
        self.assertTrue(success)
        self.assertIn("Successfully uploaded", message)
        self.assertEqual(mock_ftp.storbinary.call_count, 2)
        mock_sleep.assert_called_once_with(30)  # 30 second retry interval
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    @patch('services.storage.ftp_adapter.time.sleep')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test data')
    def test_upload_fails_after_max_retries(self, mock_file, mock_sleep, mock_ftp_class):
        """测试达到最大重试次数后上传失败"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        # All attempts fail
        mock_ftp.storbinary.side_effect = Exception("Network error")
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.upload('/local/backup.tar.gz', 'backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("attempt 3/3 failed", message)
        self.assertEqual(mock_ftp.storbinary.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)  # Sleep between retries
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    @patch('services.storage.ftp_adapter.time.sleep')
    def test_upload_retries_with_30_second_interval(self, mock_sleep, mock_ftp_class):
        """测试上传重试间隔为30秒"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.connect.side_effect = Exception("Connection failed")
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.upload('/local/backup.tar.gz', 'backup.tar.gz')
        
        self.assertFalse(success)
        # Verify 30 second sleep interval
        for call_args in mock_sleep.call_args_list:
            self.assertEqual(call_args[0][0], 30)


class TestFTPStorageAdapterDownload(unittest.TestCase):
    """Test FTP download functionality"""
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    @patch('services.storage.ftp_adapter.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_success(self, mock_file, mock_makedirs, mock_ftp_class):
        """测试成功下载文件"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.download('backup.tar.gz', '/local/backup.tar.gz')
        
        self.assertTrue(success)
        self.assertIn("Successfully downloaded", message)
        mock_ftp.retrbinary.assert_called_once()
        mock_ftp.quit.assert_called_once()
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_download_failure(self, mock_ftp_class):
        """测试下载失败"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.retrbinary.side_effect = Exception("File not found")
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.download('backup.tar.gz', '/local/backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("Download failed", message)


class TestFTPStorageAdapterListFiles(unittest.TestCase):
    """Test FTP list files functionality"""
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_list_files_with_mlsd(self, mock_ftp_class):
        """测试使用MLSD命令列出文件"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        mock_ftp.mlsd.return_value = [
            ('backup1.tar.gz', {'type': 'file', 'size': '1024', 'modify': '20240115143022'}),
            ('backup2.tar.gz', {'type': 'file', 'size': '2048', 'modify': '20240116143022'}),
            ('.', {'type': 'dir'}),
            ('..', {'type': 'dir'})
        ]
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        files = adapter.list_files()
        
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]['name'], 'backup1.tar.gz')
        self.assertEqual(files[0]['size'], 1024)
        self.assertEqual(files[1]['name'], 'backup2.tar.gz')
        self.assertEqual(files[1]['size'], 2048)
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_list_files_fallback_to_nlst(self, mock_ftp_class):
        """测试MLSD不支持时回退到NLST"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        mock_ftp.mlsd.side_effect = ftplib.error_perm("MLSD not supported")
        mock_ftp.nlst.return_value = ['backup1.tar.gz', 'backup2.tar.gz']
        mock_ftp.size.side_effect = [1024, 2048]
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        files = adapter.list_files()
        
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]['name'], 'backup1.tar.gz')
        self.assertEqual(files[0]['size'], 1024)
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_list_files_returns_empty_on_error(self, mock_ftp_class):
        """测试列出文件失败时返回空列表"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.mlsd.side_effect = Exception("Connection error")
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        files = adapter.list_files()
        
        self.assertEqual(files, [])


class TestFTPStorageAdapterDelete(unittest.TestCase):
    """Test FTP delete functionality"""
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_delete_success(self, mock_ftp_class):
        """测试成功删除文件"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.delete('backup.tar.gz')
        
        self.assertTrue(success)
        self.assertIn("Successfully deleted", message)
        mock_ftp.delete.assert_called_once_with('backup.tar.gz')
        mock_ftp.quit.assert_called_once()
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_delete_failure(self, mock_ftp_class):
        """测试删除失败"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.delete.side_effect = Exception("File not found")
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.delete('backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("Delete failed", message)


class TestFTPStorageAdapterTestConnection(unittest.TestCase):
    """Test FTP connection testing functionality"""
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_connection_test_success(self, mock_ftp_class):
        """测试连接测试成功"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.getwelcome.return_value = "220 Welcome to FTP Server"
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.test_connection()
        
        self.assertTrue(success)
        self.assertIn("FTP connection successful", message)
        self.assertIn("220 Welcome to FTP Server", message)
        mock_ftp.nlst.assert_called_once()
        mock_ftp.quit.assert_called_once()
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_connection_test_no_permission(self, mock_ftp_class):
        """测试连接成功但无权限"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.nlst.side_effect = ftplib.error_perm("550 Permission denied")
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.test_connection()
        
        self.assertFalse(success)
        self.assertIn("no permission", message)
    
    @patch('services.storage.ftp_adapter.ftplib.FTP')
    def test_connection_test_failure(self, mock_ftp_class):
        """测试连接测试失败"""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        mock_ftp.connect.side_effect = Exception("Connection refused")
        
        adapter = FTPStorageAdapter(
            host='ftp.example.com',
            port=21,
            username='user',
            password='pass',
            base_path='/backups'
        )
        
        success, message = adapter.test_connection()
        
        self.assertFalse(success)
        self.assertIn("FTP connection failed", message)
        self.assertIn("Connection refused", message)


if __name__ == '__main__':
    unittest.main()
