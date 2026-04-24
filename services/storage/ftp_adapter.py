"""
FTP Storage Adapter

This module implements the FTP storage adapter for the backup system.
It provides functionality to upload, download, list, and delete backup files
on FTP servers with retry logic for reliability.

Requirements: 1.3, 4.1, 4.5, 5.3, 15.3
"""

import ftplib
import os
import time
from typing import Tuple, List, Dict
from .base import StorageAdapter


class FTPStorageAdapter(StorageAdapter):
    """
    FTP storage adapter implementation.
    
    Handles backup file operations on FTP servers with automatic retry logic
    for upload operations to ensure reliability.
    """
    
    def __init__(self, host: str, port: int, username: str, password: str, base_path: str):
        """
        Initialize FTP storage adapter.
        
        Args:
            host: FTP server hostname or IP address
            port: FTP server port (typically 21)
            username: FTP login username
            password: FTP login password
            base_path: Base directory path on FTP server for backups
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.base_path = base_path.rstrip('/')
    
    def _connect(self) -> Tuple[ftplib.FTP, str]:
        """
        Establish FTP connection.
        
        Returns:
            Tuple of (FTP connection object, error message if failed)
        """
        ftp = None
        try:
            ftp = ftplib.FTP()
            ftp.connect(self.host, self.port, timeout=30)
            ftp.login(self.username, self.password)
            
            # Change to base path, create if doesn't exist
            try:
                ftp.cwd(self.base_path)
            except ftplib.error_perm:
                # Try to create the directory
                try:
                    self._create_directory_recursive(ftp, self.base_path)
                    ftp.cwd(self.base_path)
                except Exception as dir_error:
                    if ftp:
                        try:
                            ftp.quit()
                        except:
                            pass
                    return None, f"FTP connection failed: Cannot create or access directory {self.base_path}: {str(dir_error)}"
            
            return ftp, ""
        except TimeoutError as e:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
            return None, (
                f"FTP 连接超时: 无法连接到 {self.host}:{self.port}\n\n"
                f"可能的原因：\n"
                f"1. FTP 服务器地址或端口错误\n"
                f"2. FTP 服务未启动\n"
                f"3. 防火墙阻止了连接\n"
                f"4. 服务器不在线或网络不通\n\n"
                f"建议：\n"
                f"- 检查服务器 IP 地址和端口是否正确\n"
                f"- 确认 FTP 服务已启动\n"
                f"- 检查防火墙设置（服务器和本地）\n"
                f"- 尝试使用 FTP 客户端工具（如 FileZilla）测试连接"
            )
        except ftplib.error_perm as e:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
            return None, (
                f"FTP 认证失败: {str(e)}\n\n"
                f"可能的原因：\n"
                f"1. 用户名或密码错误\n"
                f"2. 用户没有访问权限\n\n"
                f"建议：\n"
                f"- 检查用户名和密码是否正确\n"
                f"- 确认用户有访问 FTP 服务器的权限"
            )
        except Exception as e:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
            
            # 检查是否是 Windows 连接超时错误
            error_str = str(e)
            if 'WinError 10060' in error_str or '10060' in error_str:
                return None, (
                    f"FTP 连接超时: 无法连接到 {self.host}:{self.port}\n\n"
                    f"错误详情: {error_str}\n\n"
                    f"可能的原因：\n"
                    f"1. FTP 服务器地址或端口错误\n"
                    f"2. FTP 服务未启动\n"
                    f"3. 防火墙阻止了连接（Windows 防火墙或服务器防火墙）\n"
                    f"4. 服务器不在线或网络不通\n\n"
                    f"建议：\n"
                    f"- 检查服务器 IP 地址: {self.host}\n"
                    f"- 检查端口号: {self.port}\n"
                    f"- 确认 FTP 服务已启动\n"
                    f"- 检查 Windows 防火墙设置\n"
                    f"- 检查服务器防火墙设置\n"
                    f"- 尝试使用 FTP 客户端工具（如 FileZilla）测试连接"
                )
            
            return None, f"FTP connection failed: {error_str}"
    
    def _create_directory_recursive(self, ftp: ftplib.FTP, path: str):
        """
        Create directory recursively on FTP server.
        
        Args:
            ftp: Active FTP connection
            path: Directory path to create
        """
        parts = path.strip('/').split('/')
        current = ''
        
        for part in parts:
            current += '/' + part
            try:
                ftp.cwd(current)
            except ftplib.error_perm:
                try:
                    ftp.mkd(current)
                    ftp.cwd(current)
                except ftplib.error_perm:
                    pass  # Directory might already exist
    
    def upload(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """
        Upload a file to FTP server with retry logic.
        
        Implements retry mechanism: max 3 attempts with 30 second intervals.
        
        Args:
            local_path: Path to the local file to upload
            remote_path: Destination filename on FTP server (relative to base_path)
            
        Returns:
            Tuple of (success: bool, remote_path or error_message: str)
        """
        max_retries = 3
        retry_interval = 30
        
        for attempt in range(1, max_retries + 1):
            try:
                # Connect to FTP server
                ftp, error = self._connect()
                if not ftp:
                    if attempt < max_retries:
                        time.sleep(retry_interval)
                        continue
                    return False, error
                
                # Upload file
                with open(local_path, 'rb') as f:
                    ftp.storbinary(f'STOR {remote_path}', f)
                
                ftp.quit()
                # Return the remote path (relative to base_path) for storage_path
                return True, remote_path
                
            except Exception as e:
                error_msg = f"Upload attempt {attempt}/{max_retries} failed: {str(e)}"
                
                if attempt < max_retries:
                    # Wait before retry
                    time.sleep(retry_interval)
                else:
                    # Final attempt failed
                    return False, error_msg
        
        return False, "Upload failed after all retry attempts"
    
    def download(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """
        Download a file from FTP server.
        
        Args:
            remote_path: Path to the file on FTP server (relative to base_path)
            local_path: Destination path for the downloaded file
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Connect to FTP server
            ftp, error = self._connect()
            if not ftp:
                return False, error
            
            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download file
            with open(local_path, 'wb') as f:
                ftp.retrbinary(f'RETR {remote_path}', f.write)
            
            ftp.quit()
            return True, f"Successfully downloaded to {local_path}"
            
        except Exception as e:
            return False, f"Download failed: {str(e)}"
    
    def list_files(self, remote_dir: str = '') -> List[Dict]:
        """
        List files in a remote directory on FTP server.
        
        Args:
            remote_dir: Directory path relative to base_path (empty string for base_path)
            
        Returns:
            List of dictionaries containing file information
        """
        try:
            # Connect to FTP server
            ftp, error = self._connect()
            if not ftp:
                return []
            
            # Change to target directory if specified
            if remote_dir:
                target_path = f"{self.base_path}/{remote_dir}".replace('//', '/')
                try:
                    ftp.cwd(target_path)
                except ftplib.error_perm:
                    ftp.quit()
                    return []
            
            # List files
            files = []
            file_list = []
            
            try:
                # Try MLSD first (more detailed)
                file_list = list(ftp.mlsd())
                for name, facts in file_list:
                    if name in ['.', '..']:
                        continue
                    
                    file_info = {
                        'name': name,
                        'path': f"{remote_dir}/{name}".lstrip('/') if remote_dir else name,
                        'size': int(facts.get('size', 0)),
                        'modified': facts.get('modify', '')
                    }
                    
                    # Only include files, not directories
                    if facts.get('type') == 'file':
                        files.append(file_info)
                        
            except (ftplib.error_perm, AttributeError):
                # MLSD not supported, fall back to NLST
                file_list = ftp.nlst()
                for name in file_list:
                    if name in ['.', '..']:
                        continue
                    
                    try:
                        # Try to get file size
                        size = ftp.size(name)
                    except:
                        size = 0
                    
                    file_info = {
                        'name': name,
                        'path': f"{remote_dir}/{name}".lstrip('/') if remote_dir else name,
                        'size': size if size else 0,
                        'modified': ''
                    }
                    files.append(file_info)
            
            ftp.quit()
            return files
            
        except Exception as e:
            return []
    
    def delete(self, remote_path: str) -> Tuple[bool, str]:
        """
        Delete a file from FTP server.
        
        Args:
            remote_path: Path to the file on FTP server (relative to base_path)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Connect to FTP server
            ftp, error = self._connect()
            if not ftp:
                return False, error
            
            # Delete file
            ftp.delete(remote_path)
            
            ftp.quit()
            return True, f"Successfully deleted {remote_path}"
            
        except Exception as e:
            return False, f"Delete failed: {str(e)}"
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test FTP connection and verify credentials.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Connect to FTP server
            ftp, error = self._connect()
            if not ftp:
                return False, error
            
            # Get welcome message
            welcome = ftp.getwelcome()
            
            # Try to list current directory to verify permissions
            try:
                ftp.nlst()
            except ftplib.error_perm as e:
                ftp.quit()
                return False, f"Connected but no permission to list directory: {str(e)}"
            
            ftp.quit()
            return True, f"FTP connection successful. Server: {welcome}"
            
        except Exception as e:
            return False, f"FTP connection test failed: {str(e)}"
