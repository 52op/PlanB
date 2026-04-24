# Storage adapters for backup system
from .base import StorageAdapter
from .ftp_adapter import FTPStorageAdapter
from .email_adapter import EmailStorageAdapter
from .s3_adapter import S3StorageAdapter

__all__ = ['StorageAdapter', 'FTPStorageAdapter', 'EmailStorageAdapter', 'S3StorageAdapter']
