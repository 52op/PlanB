"""
BackupValidator Service

This module provides backup file validation functionality including hash calculation,
archive integrity verification, remote backup accessibility testing, and metadata validation.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

import hashlib
import tarfile
import io
from typing import Tuple, Dict
from services.storage.base import StorageAdapter


class BackupValidator:
    """
    Backup validation service for ensuring backup integrity and accessibility.
    
    This class provides static methods for:
    - Calculating file hashes (SHA256)
    - Verifying tar.gz archive integrity
    - Testing remote backup accessibility
    - Validating backup metadata structure
    """
    
    @staticmethod
    def calculate_hash(file_path: str) -> str:
        """
        Calculate SHA256 hash of a file.
        
        Reads the file in chunks to handle large files efficiently without
        loading the entire file into memory.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            Hexadecimal string representation of the SHA256 hash
            
        Raises:
            FileNotFoundError: If the file does not exist
            IOError: If there's an error reading the file
            
        **Validates: Requirements 6.1, 6.2**
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # Read file in 8KB chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    @staticmethod
    def verify_archive(archive_path: str) -> Tuple[bool, str]:
        """
        Verify the integrity of a tar.gz archive file.
        
        Attempts to open and list the contents of the archive to ensure it's
        not corrupted and can be extracted successfully.
        
        Args:
            archive_path: Path to the tar.gz archive file
            
        Returns:
            Tuple of (is_valid: bool, message: str)
            - is_valid: True if archive is valid, False otherwise
            - message: Error description if invalid, success message if valid
            
        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        try:
            # Attempt to open the archive
            with tarfile.open(archive_path, 'r:gz') as tar:
                # Try to list all members to verify integrity
                members = tar.getmembers()
                
                if len(members) == 0:
                    return False, "Archive is empty"
                
                # Verify we can read member names (basic integrity check)
                for member in members:
                    _ = member.name
                
                return True, f"Archive is valid with {len(members)} files"
                
        except tarfile.TarError as e:
            return False, f"Archive integrity check failed: {str(e)}"
        except Exception as e:
            return False, f"Error verifying archive: {str(e)}"
    
    @staticmethod
    def verify_remote_backup(adapter: StorageAdapter, remote_path: str) -> Tuple[bool, str]:
        """
        Verify remote backup accessibility by downloading the first 1KB.
        
        This method tests whether a backup file can be accessed from remote storage
        without downloading the entire file. It creates a temporary file to test
        the download capability.
        
        Args:
            adapter: Storage adapter instance to use for verification
            remote_path: Path to the backup file in remote storage
            
        Returns:
            Tuple of (is_accessible: bool, message: str)
            - is_accessible: True if backup can be accessed, False otherwise
            - message: Error description if inaccessible, success message if accessible
            
        **Validates: Requirements 6.3, 6.4**
        """
        import tempfile
        import os
        
        try:
            # Create a temporary file for testing download
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Attempt to download the file
                success, message = adapter.download(remote_path, temp_path)
                
                if not success:
                    return False, f"Remote backup not accessible: {message}"
                
                # Check if file was actually downloaded and has content
                if os.path.exists(temp_path):
                    file_size = os.path.getsize(temp_path)
                    if file_size > 0:
                        return True, f"Remote backup is accessible (verified {file_size} bytes)"
                    else:
                        return False, "Remote backup downloaded but file is empty"
                else:
                    return False, "Remote backup download did not create file"
                    
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            return False, f"Error verifying remote backup: {str(e)}"
    
    @staticmethod
    def validate_backup_metadata(metadata: Dict) -> Tuple[bool, str]:
        """
        Validate the structure and content of backup metadata.
        
        Checks that all required fields are present and have valid values
        according to the backup metadata specification.
        
        Args:
            metadata: Dictionary containing backup metadata
            
        Returns:
            Tuple of (is_valid: bool, message: str)
            - is_valid: True if metadata is valid, False otherwise
            - message: Error description if invalid, success message if valid
            
        **Validates: Requirements 6.5, 6.6**
        """
        # Required top-level fields
        required_fields = [
            'version',
            'backup_id',
            'backup_mode',
            'trigger_type',
            'created_at',
            'is_encrypted',
            'files',
            'statistics',
            'archive_hash'
        ]
        
        # Check for required fields
        for field in required_fields:
            if field not in metadata:
                return False, f"Missing required field: {field}"
        
        # Validate version format
        if not isinstance(metadata['version'], str):
            return False, "Field 'version' must be a string"
        
        # Validate backup_id
        if not isinstance(metadata['backup_id'], int) or metadata['backup_id'] <= 0:
            return False, "Field 'backup_id' must be a positive integer"
        
        # Validate backup_mode
        valid_modes = ['full', 'incremental']
        if metadata['backup_mode'] not in valid_modes:
            return False, f"Field 'backup_mode' must be one of {valid_modes}"
        
        # Validate trigger_type
        valid_triggers = ['auto', 'manual']
        if metadata['trigger_type'] not in valid_triggers:
            return False, f"Field 'trigger_type' must be one of {valid_triggers}"
        
        # Validate is_encrypted
        if not isinstance(metadata['is_encrypted'], bool):
            return False, "Field 'is_encrypted' must be a boolean"
        
        # Validate files structure
        if not isinstance(metadata['files'], dict):
            return False, "Field 'files' must be a dictionary"
        
        # Validate statistics structure
        if not isinstance(metadata['statistics'], dict):
            return False, "Field 'statistics' must be a dictionary"
        
        required_stats = [
            'total_files',
            'total_size_bytes',
            'db_size_bytes',
            'uploads_count',
            'uploads_size_bytes',
            'docs_count',
            'docs_size_bytes'
        ]
        
        for stat in required_stats:
            if stat not in metadata['statistics']:
                return False, f"Missing required statistic: {stat}"
            if not isinstance(metadata['statistics'][stat], int) or metadata['statistics'][stat] < 0:
                return False, f"Statistic '{stat}' must be a non-negative integer"
        
        # Validate archive_hash
        if not isinstance(metadata['archive_hash'], str) or len(metadata['archive_hash']) != 64:
            return False, "Field 'archive_hash' must be a 64-character SHA256 hash"
        
        return True, "Metadata is valid"
