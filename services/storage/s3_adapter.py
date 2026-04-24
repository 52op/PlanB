"""
S3 Storage Adapter

This module implements the S3 storage adapter for the backup system.
It provides functionality to upload, download, list, and delete backup files
on AWS S3 and S3-compatible storage services (MinIO, DigitalOcean Spaces, etc.).

Requirements: 1.5, 4.3, 4.4, 4.5, 5.4, 15.5
"""

import os
from typing import Tuple, List, Dict, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from .base import StorageAdapter


class S3StorageAdapter(StorageAdapter):
    """
    S3 storage adapter implementation.
    
    Supports both AWS S3 and S3-compatible storage services (MinIO, DigitalOcean Spaces,
    Wasabi, etc.) through custom endpoint configuration.
    """
    
    def __init__(self, endpoint: Optional[str], bucket: str, access_key: str, 
                 secret_key: str, path_prefix: str, region: Optional[str] = None):
        """
        Initialize S3 storage adapter.
        
        Args:
            endpoint: S3 endpoint URL (None for AWS S3, custom URL for S3-compatible storage)
            bucket: S3 bucket name
            access_key: AWS access key ID or S3-compatible access key
            secret_key: AWS secret access key or S3-compatible secret key
            path_prefix: Prefix path for backup files in the bucket (e.g., 'backups/')
            region: AWS region (optional, defaults to 'us-east-1' if not specified)
        """
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.path_prefix = path_prefix.rstrip('/') + '/' if path_prefix else ''
        self.region = region or 'us-east-1'
        self._client = None
    
    def _get_client(self):
        """
        Get or create boto3 S3 client.
        
        Returns:
            boto3 S3 client instance
        """
        if self._client is None:
            # Configure boto3 client
            config = Config(
                signature_version='s3v4',
                retries={'max_attempts': 3, 'mode': 'standard'}
            )
            
            # Create client with custom endpoint if specified
            if self.endpoint:
                self._client = boto3.client(
                    's3',
                    endpoint_url=self.endpoint,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                    config=config
                )
            else:
                # Use AWS S3
                self._client = boto3.client(
                    's3',
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                    config=config
                )
        
        return self._client
    
    def upload(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """
        Upload a file to S3 storage.
        
        Args:
            local_path: Path to the local file to upload
            remote_path: Destination key in S3 bucket (relative to path_prefix)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Verify file exists
            if not os.path.exists(local_path):
                return False, f"File not found: {local_path}"
            
            # Get S3 client
            client = self._get_client()
            
            # Construct full S3 key
            s3_key = f"{self.path_prefix}{remote_path}"
            
            # Upload file
            client.upload_file(local_path, self.bucket, s3_key)
            
            return True, f"Successfully uploaded to s3://{self.bucket}/{s3_key}"
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            return False, f"S3 upload failed ({error_code}): {error_msg}"
        except BotoCoreError as e:
            return False, f"S3 upload failed: {str(e)}"
        except Exception as e:
            return False, f"Upload failed: {str(e)}"
    
    def download(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """
        Download a file from S3 storage.
        
        Args:
            remote_path: S3 object key (relative to path_prefix)
            local_path: Destination path for the downloaded file
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get S3 client
            client = self._get_client()
            
            # Construct full S3 key
            s3_key = f"{self.path_prefix}{remote_path}"
            
            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download file
            client.download_file(self.bucket, s3_key, local_path)
            
            return True, f"Successfully downloaded to {local_path}"
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == 'NoSuchKey':
                return False, f"File not found: s3://{self.bucket}/{self.path_prefix}{remote_path}"
            
            return False, f"S3 download failed ({error_code}): {error_msg}"
        except BotoCoreError as e:
            return False, f"S3 download failed: {str(e)}"
        except Exception as e:
            return False, f"Download failed: {str(e)}"
    
    def list_files(self, remote_dir: str = '') -> List[Dict]:
        """
        List files in S3 bucket with specified prefix.
        
        Args:
            remote_dir: Directory path relative to path_prefix (empty string for path_prefix root)
            
        Returns:
            List of dictionaries containing file information
        """
        try:
            # Get S3 client
            client = self._get_client()
            
            # Construct full prefix
            if remote_dir:
                prefix = f"{self.path_prefix}{remote_dir}".rstrip('/') + '/'
            else:
                prefix = self.path_prefix
            
            # List objects
            files = []
            paginator = client.get_paginator('list_objects_v2')
            
            page_count = 0
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                page_count += 1
                
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    key = obj['Key']
                    
                    # Skip if it's a directory marker
                    if key.endswith('/'):
                        continue
                    
                    # Get relative path (remove path_prefix)
                    relative_path = key[len(self.path_prefix):] if key.startswith(self.path_prefix) else key
                    
                    # Get filename
                    filename = os.path.basename(key)
                    
                    file_info = {
                        'name': filename,
                        'path': relative_path,
                        'size': obj.get('Size', 0),
                        'modified': obj.get('LastModified', '').isoformat() if obj.get('LastModified') else ''
                    }
                    files.append(file_info)
            
            return files
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchBucket':
                return []
            return []
        except Exception as e:
            import traceback
            traceback.print_exc()
            return []
    
    def delete(self, remote_path: str) -> Tuple[bool, str]:
        """
        Delete a file from S3 storage.
        
        Args:
            remote_path: S3 object key (relative to path_prefix)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get S3 client
            client = self._get_client()
            
            # Construct full S3 key
            s3_key = f"{self.path_prefix}{remote_path}"
            
            # Delete object
            client.delete_object(Bucket=self.bucket, Key=s3_key)
            
            return True, f"Successfully deleted s3://{self.bucket}/{s3_key}"
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            return False, f"S3 delete failed ({error_code}): {error_msg}"
        except BotoCoreError as e:
            return False, f"S3 delete failed: {str(e)}"
        except Exception as e:
            return False, f"Delete failed: {str(e)}"
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test S3 connection and verify credentials.
        
        Tests connection by attempting to list objects in the bucket.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get S3 client
            client = self._get_client()
            
            # Try to head bucket (check if bucket exists and we have access)
            try:
                client.head_bucket(Bucket=self.bucket)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                
                if error_code == '404':
                    return False, f"Bucket '{self.bucket}' does not exist"
                elif error_code == '403':
                    return False, f"Access denied to bucket '{self.bucket}'. Check credentials and permissions."
                else:
                    error_msg = e.response.get('Error', {}).get('Message', str(e))
                    return False, f"Cannot access bucket ({error_code}): {error_msg}"
            
            # Try to list objects with the configured prefix
            try:
                response = client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=self.path_prefix,
                    MaxKeys=1
                )
                
                # Check if we have permission to list
                object_count = response.get('KeyCount', 0)
                
                # Build success message
                endpoint_info = f" (Endpoint: {self.endpoint})" if self.endpoint else " (AWS S3)"
                prefix_info = f" with prefix '{self.path_prefix}'" if self.path_prefix else ""
                
                return True, f"S3 connection successful{endpoint_info}. Bucket '{self.bucket}' is accessible{prefix_info}."
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_msg = e.response.get('Error', {}).get('Message', str(e))
                return False, f"Cannot list objects in bucket ({error_code}): {error_msg}"
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            return False, f"S3 connection test failed ({error_code}): {error_msg}"
        except BotoCoreError as e:
            return False, f"S3 connection test failed: {str(e)}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
