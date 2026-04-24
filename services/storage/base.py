"""
StorageAdapter Abstract Base Class

This module defines the abstract interface that all storage adapters must implement.
Storage adapters handle uploading, downloading, listing, and deleting backup files
from various storage backends (FTP, Email, S3, etc.).

Requirements: 4.1, 4.2, 4.3, 4.4
"""

from abc import ABC, abstractmethod
from typing import Tuple, List, Dict


class StorageAdapter(ABC):
    """
    Abstract base class for storage adapters.
    
    All storage adapter implementations (FTP, Email, S3) must inherit from this class
    and implement all abstract methods.
    """
    
    @abstractmethod
    def upload(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """
        Upload a file to remote storage.
        
        Args:
            local_path: Path to the local file to upload
            remote_path: Destination path in remote storage
            
        Returns:
            Tuple of (success: bool, message: str)
            - success: True if upload succeeded, False otherwise
            - message: Error message if failed, or success message/remote path if succeeded
        """
        pass
    
    @abstractmethod
    def download(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """
        Download a file from remote storage.
        
        Args:
            remote_path: Path to the file in remote storage
            local_path: Destination path for the downloaded file
            
        Returns:
            Tuple of (success: bool, message: str)
            - success: True if download succeeded, False otherwise
            - message: Error message if failed, or success message if succeeded
        """
        pass
    
    @abstractmethod
    def list_files(self, remote_dir: str) -> List[Dict]:
        """
        List files in a remote directory.
        
        Args:
            remote_dir: Path to the remote directory
            
        Returns:
            List of dictionaries containing file information. Each dict should include:
            - 'name': filename
            - 'path': full path to the file
            - 'size': file size in bytes (optional)
            - 'modified': last modified timestamp (optional)
        """
        pass
    
    @abstractmethod
    def delete(self, remote_path: str) -> Tuple[bool, str]:
        """
        Delete a file from remote storage.
        
        Args:
            remote_path: Path to the file in remote storage
            
        Returns:
            Tuple of (success: bool, message: str)
            - success: True if deletion succeeded, False otherwise
            - message: Error message if failed, or success message if succeeded
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test the connection to remote storage.
        
        This method should verify that the storage adapter can connect to the remote
        storage using the configured credentials and settings.
        
        Returns:
            Tuple of (success: bool, message: str)
            - success: True if connection test succeeded, False otherwise
            - message: Detailed message about the connection test result
        """
        pass
