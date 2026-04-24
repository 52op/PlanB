"""
Unit tests for StorageAdapter abstract base class

Tests verify that the abstract interface is properly defined and that
concrete implementations must implement all required methods.
"""

import unittest
from abc import ABC
from services.storage.base import StorageAdapter


class TestStorageAdapterInterface(unittest.TestCase):
    """Test the StorageAdapter abstract base class interface"""
    
    def test_storage_adapter_is_abstract(self):
        """测试StorageAdapter是抽象类"""
        self.assertTrue(issubclass(StorageAdapter, ABC))
        
    def test_cannot_instantiate_storage_adapter_directly(self):
        """测试不能直接实例化StorageAdapter"""
        with self.assertRaises(TypeError) as context:
            StorageAdapter()
        self.assertIn("abstract", str(context.exception).lower())
    
    def test_storage_adapter_has_upload_method(self):
        """测试StorageAdapter定义了upload抽象方法"""
        self.assertTrue(hasattr(StorageAdapter, 'upload'))
        self.assertTrue(callable(getattr(StorageAdapter, 'upload')))
    
    def test_storage_adapter_has_download_method(self):
        """测试StorageAdapter定义了download抽象方法"""
        self.assertTrue(hasattr(StorageAdapter, 'download'))
        self.assertTrue(callable(getattr(StorageAdapter, 'download')))
    
    def test_storage_adapter_has_list_files_method(self):
        """测试StorageAdapter定义了list_files抽象方法"""
        self.assertTrue(hasattr(StorageAdapter, 'list_files'))
        self.assertTrue(callable(getattr(StorageAdapter, 'list_files')))
    
    def test_storage_adapter_has_delete_method(self):
        """测试StorageAdapter定义了delete抽象方法"""
        self.assertTrue(hasattr(StorageAdapter, 'delete'))
        self.assertTrue(callable(getattr(StorageAdapter, 'delete')))
    
    def test_storage_adapter_has_test_connection_method(self):
        """测试StorageAdapter定义了test_connection抽象方法"""
        self.assertTrue(hasattr(StorageAdapter, 'test_connection'))
        self.assertTrue(callable(getattr(StorageAdapter, 'test_connection')))


class ConcreteStorageAdapter(StorageAdapter):
    """Concrete implementation for testing"""
    
    def upload(self, local_path: str, remote_path: str):
        return True, "Upload successful"
    
    def download(self, remote_path: str, local_path: str):
        return True, "Download successful"
    
    def list_files(self, remote_dir: str):
        return []
    
    def delete(self, remote_path: str):
        return True, "Delete successful"
    
    def test_connection(self):
        return True, "Connection successful"


class TestConcreteImplementation(unittest.TestCase):
    """Test that concrete implementations work correctly"""
    
    def test_can_instantiate_concrete_implementation(self):
        """测试可以实例化具体实现"""
        adapter = ConcreteStorageAdapter()
        self.assertIsInstance(adapter, StorageAdapter)
    
    def test_concrete_upload_returns_tuple(self):
        """测试具体实现的upload返回元组"""
        adapter = ConcreteStorageAdapter()
        result = adapter.upload("/local/file", "/remote/file")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)
    
    def test_concrete_download_returns_tuple(self):
        """测试具体实现的download返回元组"""
        adapter = ConcreteStorageAdapter()
        result = adapter.download("/remote/file", "/local/file")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)
    
    def test_concrete_list_files_returns_list(self):
        """测试具体实现的list_files返回列表"""
        adapter = ConcreteStorageAdapter()
        result = adapter.list_files("/remote/dir")
        self.assertIsInstance(result, list)
    
    def test_concrete_delete_returns_tuple(self):
        """测试具体实现的delete返回元组"""
        adapter = ConcreteStorageAdapter()
        result = adapter.delete("/remote/file")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)
    
    def test_concrete_test_connection_returns_tuple(self):
        """测试具体实现的test_connection返回元组"""
        adapter = ConcreteStorageAdapter()
        result = adapter.test_connection()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)


class IncompleteStorageAdapter(StorageAdapter):
    """Incomplete implementation missing some methods"""
    
    def upload(self, local_path: str, remote_path: str):
        return True, "Upload successful"
    
    # Missing other required methods


class TestIncompleteImplementation(unittest.TestCase):
    """Test that incomplete implementations cannot be instantiated"""
    
    def test_cannot_instantiate_incomplete_implementation(self):
        """测试不能实例化不完整的实现"""
        with self.assertRaises(TypeError) as context:
            IncompleteStorageAdapter()
        self.assertIn("abstract", str(context.exception).lower())


if __name__ == '__main__':
    unittest.main()
