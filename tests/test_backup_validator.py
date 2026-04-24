"""
Unit tests for BackupValidator service

Tests cover:
- SHA256 hash calculation
- Archive integrity verification
- Remote backup accessibility testing
- Metadata validation

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

import pytest
import tempfile
import tarfile
import os
import json
from services.backup_validator import BackupValidator
from services.storage.base import StorageAdapter
from typing import Tuple, List, Dict


class MockStorageAdapter(StorageAdapter):
    """Mock storage adapter for testing"""
    
    def __init__(self, should_succeed=True, download_size=1024):
        self.should_succeed = should_succeed
        self.download_size = download_size
        self.uploaded_files = []
        self.downloaded_files = []
    
    def upload(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        if self.should_succeed:
            self.uploaded_files.append((local_path, remote_path))
            return True, f"Uploaded to {remote_path}"
        return False, "Upload failed"
    
    def download(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        self.downloaded_files.append((remote_path, local_path))
        if self.should_succeed:
            # Create a test file with specified size
            with open(local_path, 'wb') as f:
                f.write(b'x' * self.download_size)
            return True, f"Downloaded from {remote_path}"
        return False, "Download failed"
    
    def list_files(self, remote_dir: str) -> List[Dict]:
        return []
    
    def delete(self, remote_path: str) -> Tuple[bool, str]:
        return True, "Deleted"
    
    def test_connection(self) -> Tuple[bool, str]:
        return self.should_succeed, "Connection OK" if self.should_succeed else "Connection failed"


class TestCalculateHash:
    """Tests for calculate_hash method"""
    
    def test_calculate_hash_small_file(self):
        """Test hash calculation for a small file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Hello, World!")
            temp_path = f.name
        
        try:
            hash_value = BackupValidator.calculate_hash(temp_path)
            
            # Verify it's a valid SHA256 hash (64 hex characters)
            assert len(hash_value) == 64
            assert all(c in '0123456789abcdef' for c in hash_value)
            
            # Verify consistency - same file should produce same hash
            hash_value2 = BackupValidator.calculate_hash(temp_path)
            assert hash_value == hash_value2
        finally:
            os.remove(temp_path)
    
    def test_calculate_hash_empty_file(self):
        """Test hash calculation for an empty file"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
        
        try:
            hash_value = BackupValidator.calculate_hash(temp_path)
            
            # SHA256 of empty file is a known value
            expected_hash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
            assert hash_value == expected_hash
        finally:
            os.remove(temp_path)
    
    def test_calculate_hash_large_file(self):
        """Test hash calculation for a large file (tests chunked reading)"""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            # Write 1MB of data
            f.write(b'A' * (1024 * 1024))
            temp_path = f.name
        
        try:
            hash_value = BackupValidator.calculate_hash(temp_path)
            
            # Verify it's a valid SHA256 hash
            assert len(hash_value) == 64
            assert all(c in '0123456789abcdef' for c in hash_value)
        finally:
            os.remove(temp_path)
    
    def test_calculate_hash_nonexistent_file(self):
        """Test hash calculation fails for nonexistent file"""
        with pytest.raises(FileNotFoundError):
            BackupValidator.calculate_hash('/nonexistent/file.txt')
    
    def test_calculate_hash_different_content(self):
        """Test that different content produces different hashes"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f1:
            f1.write("Content A")
            path1 = f1.name
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f2:
            f2.write("Content B")
            path2 = f2.name
        
        try:
            hash1 = BackupValidator.calculate_hash(path1)
            hash2 = BackupValidator.calculate_hash(path2)
            
            assert hash1 != hash2
        finally:
            os.remove(path1)
            os.remove(path2)


class TestVerifyArchive:
    """Tests for verify_archive method"""
    
    def test_verify_valid_archive(self):
        """Test verification of a valid tar.gz archive"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_file = os.path.join(temp_dir, 'test.txt')
            with open(test_file, 'w') as f:
                f.write("Test content")
            
            # Create archive
            archive_path = os.path.join(temp_dir, 'test.tar.gz')
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(test_file, arcname='test.txt')
            
            # Verify archive
            is_valid, message = BackupValidator.verify_archive(archive_path)
            
            assert is_valid is True
            assert 'valid' in message.lower()
            assert '1' in message  # Should mention 1 file
    
    def test_verify_archive_with_multiple_files(self):
        """Test verification of archive with multiple files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple test files
            files = []
            for i in range(5):
                file_path = os.path.join(temp_dir, f'file{i}.txt')
                with open(file_path, 'w') as f:
                    f.write(f"Content {i}")
                files.append(file_path)
            
            # Create archive
            archive_path = os.path.join(temp_dir, 'multi.tar.gz')
            with tarfile.open(archive_path, 'w:gz') as tar:
                for file_path in files:
                    tar.add(file_path, arcname=os.path.basename(file_path))
            
            # Verify archive
            is_valid, message = BackupValidator.verify_archive(archive_path)
            
            assert is_valid is True
            assert '5' in message  # Should mention 5 files
    
    def test_verify_empty_archive(self):
        """Test verification of an empty archive"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty archive
            archive_path = os.path.join(temp_dir, 'empty.tar.gz')
            with tarfile.open(archive_path, 'w:gz') as tar:
                pass  # Don't add any files
            
            # Verify archive
            is_valid, message = BackupValidator.verify_archive(archive_path)
            
            assert is_valid is False
            assert 'empty' in message.lower()
    
    def test_verify_corrupted_archive(self):
        """Test verification of a corrupted archive"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file that's not a valid tar.gz
            archive_path = os.path.join(temp_dir, 'corrupted.tar.gz')
            with open(archive_path, 'wb') as f:
                f.write(b'This is not a valid tar.gz file')
            
            # Verify archive
            is_valid, message = BackupValidator.verify_archive(archive_path)
            
            assert is_valid is False
            assert 'failed' in message.lower() or 'error' in message.lower()
    
    def test_verify_nonexistent_archive(self):
        """Test verification of nonexistent archive"""
        is_valid, message = BackupValidator.verify_archive('/nonexistent/archive.tar.gz')
        
        assert is_valid is False
        assert 'error' in message.lower()


class TestVerifyRemoteBackup:
    """Tests for verify_remote_backup method"""
    
    def test_verify_accessible_remote_backup(self):
        """Test verification of accessible remote backup"""
        adapter = MockStorageAdapter(should_succeed=True, download_size=2048)
        
        is_accessible, message = BackupValidator.verify_remote_backup(
            adapter, 
            '/backups/test.tar.gz'
        )
        
        assert is_accessible is True
        assert 'accessible' in message.lower()
        assert '2048' in message  # Should mention file size
        assert len(adapter.downloaded_files) == 1
    
    def test_verify_inaccessible_remote_backup(self):
        """Test verification of inaccessible remote backup"""
        adapter = MockStorageAdapter(should_succeed=False)
        
        is_accessible, message = BackupValidator.verify_remote_backup(
            adapter,
            '/backups/missing.tar.gz'
        )
        
        assert is_accessible is False
        assert 'not accessible' in message.lower()
    
    def test_verify_empty_remote_backup(self):
        """Test verification of empty remote backup file"""
        adapter = MockStorageAdapter(should_succeed=True, download_size=0)
        
        is_accessible, message = BackupValidator.verify_remote_backup(
            adapter,
            '/backups/empty.tar.gz'
        )
        
        assert is_accessible is False
        assert 'empty' in message.lower()
    
    def test_verify_remote_backup_cleanup(self):
        """Test that temporary files are cleaned up after verification"""
        adapter = MockStorageAdapter(should_succeed=True, download_size=1024)
        
        # Get the temp file path that will be created
        import tempfile
        temp_dir = tempfile.gettempdir()
        
        # Count files before
        files_before = set(os.listdir(temp_dir))
        
        BackupValidator.verify_remote_backup(adapter, '/backups/test.tar.gz')
        
        # Count files after
        files_after = set(os.listdir(temp_dir))
        
        # Should not have created any persistent files
        new_files = files_after - files_before
        # Filter out any system files that might have been created
        new_files = {f for f in new_files if not f.startswith('.')}
        
        assert len(new_files) == 0, f"Temporary files not cleaned up: {new_files}"


class TestValidateBackupMetadata:
    """Tests for validate_backup_metadata method"""
    
    def get_valid_metadata(self):
        """Helper to create valid metadata"""
        return {
            'version': '1.0',
            'backup_id': 123,
            'backup_mode': 'full',
            'trigger_type': 'auto',
            'created_at': '2024-01-15T14:30:22Z',
            'is_encrypted': False,
            'base_backup_id': None,
            'files': {
                'database': {
                    'path': 'database/app.db',
                    'size_bytes': 1048576,
                    'hash': 'abc123'
                }
            },
            'statistics': {
                'total_files': 150,
                'total_size_bytes': 10485760,
                'db_size_bytes': 1048576,
                'uploads_count': 50,
                'uploads_size_bytes': 5242880,
                'docs_count': 100,
                'docs_size_bytes': 4194304
            },
            'archive_hash': 'a' * 64  # Valid 64-char hash
        }
    
    def test_validate_valid_metadata(self):
        """Test validation of valid metadata"""
        metadata = self.get_valid_metadata()
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is True
        assert 'valid' in message.lower()
    
    def test_validate_missing_required_field(self):
        """Test validation fails when required field is missing"""
        metadata = self.get_valid_metadata()
        del metadata['backup_id']
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'backup_id' in message.lower()
    
    def test_validate_invalid_version_type(self):
        """Test validation fails for invalid version type"""
        metadata = self.get_valid_metadata()
        metadata['version'] = 1.0  # Should be string
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'version' in message.lower()
    
    def test_validate_invalid_backup_id(self):
        """Test validation fails for invalid backup_id"""
        metadata = self.get_valid_metadata()
        metadata['backup_id'] = -1
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'backup_id' in message.lower()
    
    def test_validate_invalid_backup_mode(self):
        """Test validation fails for invalid backup_mode"""
        metadata = self.get_valid_metadata()
        metadata['backup_mode'] = 'invalid_mode'
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'backup_mode' in message.lower()
    
    def test_validate_invalid_trigger_type(self):
        """Test validation fails for invalid trigger_type"""
        metadata = self.get_valid_metadata()
        metadata['trigger_type'] = 'invalid_trigger'
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'trigger_type' in message.lower()
    
    def test_validate_invalid_is_encrypted_type(self):
        """Test validation fails for invalid is_encrypted type"""
        metadata = self.get_valid_metadata()
        metadata['is_encrypted'] = 'yes'  # Should be boolean
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'is_encrypted' in message.lower()
    
    def test_validate_invalid_files_type(self):
        """Test validation fails for invalid files type"""
        metadata = self.get_valid_metadata()
        metadata['files'] = []  # Should be dict
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'files' in message.lower()
    
    def test_validate_invalid_statistics_type(self):
        """Test validation fails for invalid statistics type"""
        metadata = self.get_valid_metadata()
        metadata['statistics'] = []  # Should be dict
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'statistics' in message.lower()
    
    def test_validate_missing_statistic(self):
        """Test validation fails when required statistic is missing"""
        metadata = self.get_valid_metadata()
        del metadata['statistics']['total_files']
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'total_files' in message.lower()
    
    def test_validate_negative_statistic(self):
        """Test validation fails for negative statistic value"""
        metadata = self.get_valid_metadata()
        metadata['statistics']['total_files'] = -1
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'total_files' in message.lower()
    
    def test_validate_invalid_archive_hash(self):
        """Test validation fails for invalid archive hash"""
        metadata = self.get_valid_metadata()
        metadata['archive_hash'] = 'short_hash'  # Should be 64 chars
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is False
        assert 'archive_hash' in message.lower()
    
    def test_validate_incremental_backup_metadata(self):
        """Test validation of incremental backup metadata"""
        metadata = self.get_valid_metadata()
        metadata['backup_mode'] = 'incremental'
        metadata['base_backup_id'] = 100
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is True
    
    def test_validate_encrypted_backup_metadata(self):
        """Test validation of encrypted backup metadata"""
        metadata = self.get_valid_metadata()
        metadata['is_encrypted'] = True
        
        is_valid, message = BackupValidator.validate_backup_metadata(metadata)
        
        assert is_valid is True
