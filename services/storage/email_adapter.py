"""
Email Storage Adapter

This module implements the email storage adapter for the backup system.
It provides functionality to send backup files as email attachments using
the existing SMTP service.

Note: Email storage is one-way only - it supports upload (sending) but not
download, list, or delete operations.

Requirements: 1.4, 4.2, 4.5, 15.4
"""

import os
from typing import Tuple, List, Dict
from email.message import EmailMessage
import smtplib

from models import SystemSetting
from .base import StorageAdapter


class EmailStorageAdapter(StorageAdapter):
    """
    Email storage adapter implementation.
    
    Sends backup files as email attachments. This is a one-way storage method
    suitable for small to medium-sized backups. Email storage does not support
    download, list, or delete operations.
    """
    
    def __init__(self, recipient: str):
        """
        Initialize email storage adapter.
        
        Args:
            recipient: Email address to send backup files to
        """
        self.recipient = recipient
    
    def upload(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """
        Send backup file as email attachment.
        
        Args:
            local_path: Path to the local backup file
            remote_path: Filename to use for the attachment (not used for path, just filename)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Verify file exists
            if not os.path.exists(local_path):
                return False, f"File not found: {local_path}"
            
            # Get file size for validation
            file_size = os.path.getsize(local_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Warn if file is large (most email servers have 25MB limit)
            if file_size_mb > 25:
                return False, f"Backup file too large for email ({file_size_mb:.1f}MB). Email servers typically limit attachments to 25MB."
            
            # Get SMTP configuration
            host = (SystemSetting.get('smtp_host') or '').strip()
            sender = (SystemSetting.get('smtp_sender') or '').strip()
            port = int(SystemSetting.get('smtp_port', '465') or '465')
            username = (SystemSetting.get('smtp_username') or '').strip()
            password = SystemSetting.get('smtp_password') or ''
            use_ssl = (SystemSetting.get('smtp_use_ssl', 'true') or 'true').lower() == 'true'
            
            if not host or not sender:
                return False, "SMTP server not configured. Please configure email settings first."
            
            # Get site name for email subject
            site_name = SystemSetting.get('site_name', 'Planning') or 'Planning'
            
            # Create email message
            message = EmailMessage()
            message['Subject'] = f"[{site_name}] 自动备份 - {remote_path}"
            message['From'] = sender
            message['To'] = self.recipient
            
            # Email body
            body_text = f"""系统自动备份

备份文件: {remote_path}
文件大小: {file_size_mb:.2f} MB

此邮件由 {site_name} 自动备份系统发送。
备份文件已作为附件发送，请妥善保存。
"""
            message.set_content(body_text)
            
            # Add HTML version
            body_html = f"""
<div style="font-family:Segoe UI,PingFang SC,sans-serif;background:#f8f5ef;padding:24px;">
    <div style="max-width:620px;margin:0 auto;background:#fffdf9;border:1px solid #eadfce;border-radius:18px;padding:28px;">
        <h2 style="margin:0 0 12px;color:#b85c38;">系统自动备份</h2>
        <p style="color:#64748b;line-height:1.8;">备份文件已生成并作为附件发送。</p>
        <div style="background:#f8f5ef;border-radius:8px;padding:16px;margin:16px 0;">
            <p style="margin:4px 0;color:#64748b;"><strong>备份文件:</strong> {remote_path}</p>
            <p style="margin:4px 0;color:#64748b;"><strong>文件大小:</strong> {file_size_mb:.2f} MB</p>
        </div>
        <p style="color:#94a3b8;font-size:14px;margin-top:20px;">请妥善保存此备份文件，以便在需要时恢复数据。</p>
        <div style="margin-top:32px;padding-top:20px;border-top:1px solid #eadfce;">
            <p style="margin:0;color:#94a3b8;font-size:13px;line-height:1.6;">
                此邮件由 <strong style="color:#64748b;">{site_name}</strong> 自动备份系统发送
            </p>
        </div>
    </div>
</div>
"""
            message.add_alternative(body_html, subtype='html')
            
            # Attach backup file
            with open(local_path, 'rb') as f:
                file_data = f.read()
                message.add_attachment(
                    file_data,
                    maintype='application',
                    subtype='gzip',
                    filename=remote_path
                )
            
            # Send email
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=60) as server:
                    if username:
                        server.login(username, password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(host, port, timeout=60) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    if username:
                        server.login(username, password)
                    server.send_message(message)
            
            return True, f"Backup file sent to {self.recipient}"
            
        except Exception as e:
            return False, f"Failed to send backup email: {str(e)}"
    
    def download(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """
        Download is not supported for email storage.
        
        Email storage is one-way only. Backup files must be manually retrieved
        from the recipient's email inbox.
        
        Returns:
            Tuple of (False, error message)
        """
        return False, "Download not supported for email storage. Please retrieve backup files from your email inbox manually."
    
    def list_files(self, remote_dir: str = '') -> List[Dict]:
        """
        List files is not supported for email storage.
        
        Email storage does not maintain a file listing. Backup files are stored
        in the recipient's email inbox.
        
        Returns:
            Empty list
        """
        return []
    
    def delete(self, remote_path: str) -> Tuple[bool, str]:
        """
        Delete is not supported for email storage.
        
        Email storage does not support remote deletion. Backup files must be
        manually deleted from the recipient's email inbox.
        
        Returns:
            Tuple of (False, error message)
        """
        return False, "Delete not supported for email storage. Please manage backup emails in your inbox manually."
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test email configuration by sending a test email with a small backup attachment.
        
        Sends a test email with a small backup file to verify SMTP settings, 
        recipient address, and attachment handling.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        import tempfile
        import tarfile
        import json
        from datetime import datetime
        
        try:
            # Get SMTP configuration
            host = (SystemSetting.get('smtp_host') or '').strip()
            sender = (SystemSetting.get('smtp_sender') or '').strip()
            port = int(SystemSetting.get('smtp_port', '465') or '465')
            username = (SystemSetting.get('smtp_username') or '').strip()
            password = SystemSetting.get('smtp_password') or ''
            use_ssl = (SystemSetting.get('smtp_use_ssl', 'true') or 'true').lower() == 'true'
            
            if not host or not sender:
                return False, "SMTP server not configured. Please configure email settings first."
            
            # Get site name
            site_name = SystemSetting.get('site_name', 'Planning') or 'Planning'
            
            # Create a small test backup file
            test_backup_path = None
            try:
                # Create temporary directory for test backup
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Create test metadata
                    metadata = {
                        'test': True,
                        'timestamp': datetime.now().isoformat(),
                        'purpose': 'Email backup configuration test',
                        'site_name': site_name
                    }
                    
                    metadata_path = os.path.join(temp_dir, 'test_metadata.json')
                    with open(metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    
                    # Create test backup archive
                    test_backup_path = os.path.join(temp_dir, f'test_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tar.gz')
                    with tarfile.open(test_backup_path, 'w:gz') as tar:
                        tar.add(metadata_path, arcname='test_metadata.json')
                    
                    # Get file size
                    file_size = os.path.getsize(test_backup_path)
                    file_size_kb = file_size / 1024
                    
                    # Create test email
                    message = EmailMessage()
                    message['Subject'] = f"[{site_name}] 备份邮件测试（含附件）"
                    message['From'] = sender
                    message['To'] = self.recipient
                    
                    # Test email body
                    body_text = f"""备份邮件配置测试

这是一封测试邮件，用于验证备份系统的邮件发送功能。

✓ 此邮件包含一个测试备份文件作为附件（{file_size_kb:.1f} KB）
✓ 如果您收到此邮件和附件，说明邮件配置正确
✓ 备份系统可以正常发送备份文件

收件人: {self.recipient}

此邮件由 {site_name} 自动备份系统发送。
"""
                    message.set_content(body_text)
                    
                    # Add HTML version
                    body_html = f"""
<div style="font-family:Segoe UI,PingFang SC,sans-serif;background:#f8f5ef;padding:24px;">
    <div style="max-width:620px;margin:0 auto;background:#fffdf9;border:1px solid #eadfce;border-radius:18px;padding:28px;">
        <h2 style="margin:0 0 12px;color:#b85c38;">备份邮件配置测试</h2>
        <p style="color:#64748b;line-height:1.8;">这是一封测试邮件，用于验证备份系统的邮件发送功能。</p>
        <div style="background:#e8f5e9;border-left:4px solid #4caf50;padding:16px;margin:16px 0;border-radius:4px;">
            <p style="margin:0;color:#2e7d32;"><strong>✓ 测试成功</strong></p>
            <p style="margin:8px 0 0;color:#558b2f;">如果您收到此邮件和附件，说明邮件配置正确，备份系统可以正常发送备份文件。</p>
        </div>
        <div style="background:#f8f5ef;border-radius:8px;padding:16px;margin:16px 0;">
            <p style="margin:4px 0;color:#64748b;"><strong>收件人:</strong> {self.recipient}</p>
            <p style="margin:4px 0;color:#64748b;"><strong>附件大小:</strong> {file_size_kb:.1f} KB</p>
            <p style="margin:4px 0;color:#64748b;"><strong>附件类型:</strong> 测试备份文件 (.tar.gz)</p>
        </div>
        <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:16px;margin:16px 0;border-radius:4px;">
            <p style="margin:0;color:#856404;"><strong>注意:</strong> 这是一个测试文件，不包含真实数据，可以安全删除。</p>
        </div>
        <div style="margin-top:32px;padding-top:20px;border-top:1px solid #eadfce;">
            <p style="margin:0;color:#94a3b8;font-size:13px;line-height:1.6;">
                此邮件由 <strong style="color:#64748b;">{site_name}</strong> 自动备份系统发送
            </p>
        </div>
    </div>
</div>
"""
                    message.add_alternative(body_html, subtype='html')
                    
                    # Attach test backup file
                    with open(test_backup_path, 'rb') as f:
                        file_data = f.read()
                        message.add_attachment(
                            file_data,
                            maintype='application',
                            subtype='gzip',
                            filename=os.path.basename(test_backup_path)
                        )
                    
                    # Send test email
                    if use_ssl:
                        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                            if username:
                                server.login(username, password)
                            server.send_message(message)
                    else:
                        with smtplib.SMTP(host, port, timeout=30) as server:
                            server.ehlo()
                            server.starttls()
                            server.ehlo()
                            if username:
                                server.login(username, password)
                            server.send_message(message)
                    
                    return True, f"Test email with backup attachment ({file_size_kb:.1f} KB) sent successfully to {self.recipient}. Please check your inbox."
                    
            except Exception as e:
                return False, f"Failed to create or send test backup: {str(e)}"
            
        except Exception as e:
            return False, f"Failed to send test email: {str(e)}"
