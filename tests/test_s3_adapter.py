"""
Unit tests for S3StorageAdapter

Tests verify S3 adapter functionality including upload, download, list, delete,
and connection testing for both AWS S3 and S3-compatible storage.

Requirements: 1.5, 4.3, 4.4, 4.5, 5.4, 15.5
"""

import unittest
from unittest.mock import Mock, patch, mock_open, MagicMock
from botocore.exceptions import ClientError, BotoCoreError
from services.storage.s3_adapter import S3StorageAdapter
from services.storage.base import StorageAdapter


class TestS3StorageAdapterInitialization(unittest.TestCase):
    """Test S3StorageAdapter initialization"""
    
    def test_s3_adapter_inherits_from_storage_adapter(self):
        """测试S3StorageAdapter继承自StorageAdapter"""
        self.assertTrue(issubclass(S3StorageAdapter, StorageAdapter))
    
    def test_s3_adapter_initialization_with_endpoint(self):
        """测试S3StorageAdapter初始化（带自定义端点）"""
        adapter = S3StorageAdapter(
            endpoint='https://s3.example.com',
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-west-2'
        )
        
        self.assertEqual(adapter.endpoint, 'https://s3.example.com')
        self.assertEqual(adapter.bucket, 'my-bucket')
        self.assertEqual(adapter.access_key, 'access123')
        self.assertEqual(adapter.secret_key, 'secret456')
        self.assertEqual(adapter.path_prefix, 'backups/')
        self.assertEqual(adapter.region, 'us-west-2')
    
    def test_s3_adapter_initialization_without_endpoint(self):
        """测试S3StorageAdapter初始化（AWS S3）"""
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups',
            region='us-east-1'
        )
        
        self.assertIsNone(adapter.endpoint)
        self.assertEqual(adapter.region, 'us-east-1')
    
    def test_s3_adapter_adds_trailing_slash_to_path_prefix(self):
        """测试S3StorageAdapter为path_prefix添加末尾斜杠"""
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups',
            region=None
        )
        
        self.assertEqual(adapter.path_prefix, 'backups/')
    
    def test_s3_adapter_handles_empty_path_prefix(self):
        """测试S3StorageAdapter处理空path_prefix"""
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='',
            region=None
        )
        
        self.assertEqual(adapter.path_prefix, '')
    
    def test_s3_adapter_defaults_region_to_us_east_1(self):
        """测试S3StorageAdapter默认region为us-east-1"""
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups',
            region=None
        )
        
        self.assertEqual(adapter.region, 'us-east-1')


class TestS3StorageAdapterClient(unittest.TestCase):
    """Test S3 client creation"""
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_get_client_with_custom_endpoint(self, mock_boto_client):
        """测试创建带自定义端点的S3客户端"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        adapter = S3StorageAdapter(
            endpoint='https://s3.example.com',
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-west-2'
        )
        
        client = adapter._get_client()
        
        self.assertIsNotNone(client)
        mock_boto_client.assert_called_once()
        call_kwargs = mock_boto_client.call_args[1]
        self.assertEqual(call_kwargs['endpoint_url'], 'https://s3.example.com')
        self.assertEqual(call_kwargs['aws_access_key_id'], 'access123')
        self.assertEqual(call_kwargs['aws_secret_access_key'], 'secret456')
        self.assertEqual(call_kwargs['region_name'], 'us-west-2')
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_get_client_without_custom_endpoint(self, mock_boto_client):
        """测试创建AWS S3客户端"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        client = adapter._get_client()
        
        self.assertIsNotNone(client)
        mock_boto_client.assert_called_once()
        call_kwargs = mock_boto_client.call_args[1]
        self.assertNotIn('endpoint_url', call_kwargs)
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_get_client_caches_client_instance(self, mock_boto_client):
        """测试S3客户端实例被缓存"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        client1 = adapter._get_client()
        client2 = adapter._get_client()
        
        self.assertIs(client1, client2)
        mock_boto_client.assert_called_once()


class TestS3StorageAdapterUpload(unittest.TestCase):
    """Test S3 upload functionality"""
    
    @patch('services.storage.s3_adapter.os.path.exists')
    @patch('services.storage.s3_adapter.boto3.client')
    def test_upload_success(self, mock_boto_client, mock_exists):
        """测试成功上传文件到S3"""
        mock_exists.return_value = True
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.upload('/local/backup.tar.gz', 'backup.tar.gz')
        
        self.assertTrue(success)
        self.assertIn("Successfully uploaded", message)
        self.assertIn("s3://my-bucket/backups/backup.tar.gz", message)
        mock_client.upload_file.assert_called_once_with(
            '/local/backup.tar.gz',
            'my-bucket',
            'backups/backup.tar.gz'
        )
    
    @patch('services.storage.s3_adapter.os.path.exists')
    def test_upload_file_not_found(self, mock_exists):
        """测试上传不存在的文件"""
        mock_exists.return_value = False
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.upload('/local/backup.tar.gz', 'backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("File not found", message)
    
    @patch('services.storage.s3_adapter.os.path.exists')
    @patch('services.storage.s3_adapter.boto3.client')
    def test_upload_client_error(self, mock_boto_client, mock_exists):
        """测试上传时S3客户端错误"""
        mock_exists.return_value = True
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_client.upload_file.side_effect = ClientError(error_response, 'upload_file')
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.upload('/local/backup.tar.gz', 'backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("S3 upload failed", message)
        self.assertIn("NoSuchBucket", message)
    
    @patch('services.storage.s3_adapter.os.path.exists')
    @patch('services.storage.s3_adapter.boto3.client')
    def test_upload_botocore_error(self, mock_boto_client, mock_exists):
        """测试上传时BotoCore错误"""
        mock_exists.return_value = True
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.upload_file.side_effect = BotoCoreError()
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.upload('/local/backup.tar.gz', 'backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("S3 upload failed", message)


class TestS3StorageAdapterDownload(unittest.TestCase):
    """Test S3 download functionality"""
    
    @patch('services.storage.s3_adapter.os.makedirs')
    @patch('services.storage.s3_adapter.boto3.client')
    def test_download_success(self, mock_boto_client, mock_makedirs):
        """测试成功从S3下载文件"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.download('backup.tar.gz', '/local/backup.tar.gz')
        
        self.assertTrue(success)
        self.assertIn("Successfully downloaded", message)
        mock_client.download_file.assert_called_once_with(
            'my-bucket',
            'backups/backup.tar.gz',
            '/local/backup.tar.gz'
        )
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_download_file_not_found(self, mock_boto_client):
        """测试下载不存在的文件"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        error_response = {
            'Error': {
                'Code': 'NoSuchKey',
                'Message': 'The specified key does not exist'
            }
        }
        mock_client.download_file.side_effect = ClientError(error_response, 'download_file')
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.download('backup.tar.gz', '/local/backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("File not found", message)
        self.assertIn("s3://my-bucket/backups/backup.tar.gz", message)
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_download_client_error(self, mock_boto_client):
        """测试下载时S3客户端错误"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access Denied'
            }
        }
        mock_client.download_file.side_effect = ClientError(error_response, 'download_file')
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.download('backup.tar.gz', '/local/backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("S3 download failed", message)
        self.assertIn("AccessDenied", message)


class TestS3StorageAdapterListFiles(unittest.TestCase):
    """Test S3 list files functionality"""
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_list_files_success(self, mock_boto_client):
        """测试成功列出S3文件"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        # Mock paginator
        mock_paginator = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        
        from datetime import datetime
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {
                        'Key': 'backups/backup1.tar.gz',
                        'Size': 1024,
                        'LastModified': datetime(2024, 1, 15, 14, 30, 22)
                    },
                    {
                        'Key': 'backups/backup2.tar.gz',
                        'Size': 2048,
                        'LastModified': datetime(2024, 1, 16, 14, 30, 22)
                    }
                ]
            }
        ]
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        files = adapter.list_files()
        
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]['name'], 'backup1.tar.gz')
        self.assertEqual(files[0]['path'], 'backup1.tar.gz')
        self.assertEqual(files[0]['size'], 1024)
        self.assertEqual(files[1]['name'], 'backup2.tar.gz')
        self.assertEqual(files[1]['size'], 2048)
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_list_files_with_subdirectory(self, mock_boto_client):
        """测试列出S3子目录中的文件"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        mock_paginator = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        
        from datetime import datetime
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {
                        'Key': 'backups/2024/backup1.tar.gz',
                        'Size': 1024,
                        'LastModified': datetime(2024, 1, 15, 14, 30, 22)
                    }
                ]
            }
        ]
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        files = adapter.list_files('2024')
        
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['path'], '2024/backup1.tar.gz')
        
        # Verify paginate was called with correct prefix
        mock_paginator.paginate.assert_called_once()
        call_kwargs = mock_paginator.paginate.call_args[1]
        self.assertEqual(call_kwargs['Prefix'], 'backups/2024/')
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_list_files_skips_directory_markers(self, mock_boto_client):
        """测试列出文件时跳过目录标记"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        mock_paginator = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        
        from datetime import datetime
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {
                        'Key': 'backups/',
                        'Size': 0,
                        'LastModified': datetime(2024, 1, 15, 14, 30, 22)
                    },
                    {
                        'Key': 'backups/backup1.tar.gz',
                        'Size': 1024,
                        'LastModified': datetime(2024, 1, 15, 14, 30, 22)
                    }
                ]
            }
        ]
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        files = adapter.list_files()
        
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['name'], 'backup1.tar.gz')
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_list_files_empty_bucket(self, mock_boto_client):
        """测试列出空存储桶"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        mock_paginator = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        files = adapter.list_files()
        
        self.assertEqual(files, [])
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_list_files_bucket_not_found(self, mock_boto_client):
        """测试列出不存在的存储桶"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        mock_paginator = Mock()
        mock_client.get_paginator.return_value = mock_paginator
        
        error_response = {
            'Error': {
                'Code': 'NoSuchBucket',
                'Message': 'The specified bucket does not exist'
            }
        }
        mock_paginator.paginate.side_effect = ClientError(error_response, 'list_objects_v2')
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        files = adapter.list_files()
        
        self.assertEqual(files, [])


class TestS3StorageAdapterDelete(unittest.TestCase):
    """Test S3 delete functionality"""
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_delete_success(self, mock_boto_client):
        """测试成功删除S3文件"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.delete('backup.tar.gz')
        
        self.assertTrue(success)
        self.assertIn("Successfully deleted", message)
        self.assertIn("s3://my-bucket/backups/backup.tar.gz", message)
        mock_client.delete_object.assert_called_once_with(
            Bucket='my-bucket',
            Key='backups/backup.tar.gz'
        )
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_delete_client_error(self, mock_boto_client):
        """测试删除时S3客户端错误"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access Denied'
            }
        }
        mock_client.delete_object.side_effect = ClientError(error_response, 'delete_object')
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.delete('backup.tar.gz')
        
        self.assertFalse(success)
        self.assertIn("S3 delete failed", message)
        self.assertIn("AccessDenied", message)


class TestS3StorageAdapterTestConnection(unittest.TestCase):
    """Test S3 connection testing functionality"""
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_connection_test_success(self, mock_boto_client):
        """测试S3连接测试成功"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.list_objects_v2.return_value = {'KeyCount': 0}
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.test_connection()
        
        self.assertTrue(success)
        self.assertIn("S3 connection successful", message)
        self.assertIn("AWS S3", message)
        self.assertIn("my-bucket", message)
        mock_client.head_bucket.assert_called_once_with(Bucket='my-bucket')
        mock_client.list_objects_v2.assert_called_once()
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_connection_test_success_with_custom_endpoint(self, mock_boto_client):
        """测试S3兼容存储连接测试成功"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.list_objects_v2.return_value = {'KeyCount': 2}
        
        adapter = S3StorageAdapter(
            endpoint='https://s3.example.com',
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-west-2'
        )
        
        success, message = adapter.test_connection()
        
        self.assertTrue(success)
        self.assertIn("S3 connection successful", message)
        self.assertIn("https://s3.example.com", message)
        self.assertIn("my-bucket", message)
        self.assertIn("backups/", message)
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_connection_test_bucket_not_found(self, mock_boto_client):
        """测试连接测试时存储桶不存在"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        error_response = {
            'Error': {
                'Code': '404',
                'Message': 'Not Found'
            }
        }
        mock_client.head_bucket.side_effect = ClientError(error_response, 'head_bucket')
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.test_connection()
        
        self.assertFalse(success)
        self.assertIn("does not exist", message)
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_connection_test_access_denied(self, mock_boto_client):
        """测试连接测试时访问被拒绝"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        error_response = {
            'Error': {
                'Code': '403',
                'Message': 'Forbidden'
            }
        }
        mock_client.head_bucket.side_effect = ClientError(error_response, 'head_bucket')
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.test_connection()
        
        self.assertFalse(success)
        self.assertIn("Access denied", message)
        self.assertIn("credentials", message)
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_connection_test_cannot_list_objects(self, mock_boto_client):
        """测试连接测试时无法列出对象"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'Access Denied'
            }
        }
        mock_client.list_objects_v2.side_effect = ClientError(error_response, 'list_objects_v2')
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.test_connection()
        
        self.assertFalse(success)
        self.assertIn("Cannot list objects", message)
    
    @patch('services.storage.s3_adapter.boto3.client')
    def test_connection_test_botocore_error(self, mock_boto_client):
        """测试连接测试时BotoCore错误"""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.head_bucket.side_effect = BotoCoreError()
        
        adapter = S3StorageAdapter(
            endpoint=None,
            bucket='my-bucket',
            access_key='access123',
            secret_key='secret456',
            path_prefix='backups/',
            region='us-east-1'
        )
        
        success, message = adapter.test_connection()
        
        self.assertFalse(success)
        self.assertIn("S3 connection test failed", message)


if __name__ == '__main__':
    unittest.main()
