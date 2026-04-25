"""
备份通知服务

提供备份成功、失败和存储空间警告的邮件通知功能。
"""

import logging
from datetime import datetime
from typing import Optional

from models import BackupConfig, BackupJob
from .mailer import mailer_is_configured, send_logged_mail

logger = logging.getLogger(__name__)


class NotificationService:
    """备份通知服务类"""
    
    @staticmethod
    def send_backup_success_notification(backup_job: BackupJob, config: BackupConfig) -> bool:
        """
        发送备份成功通知
        
        Args:
            backup_job: 备份任务对象
            config: 备份配置对象
            
        Returns:
            bool: 是否成功发送通知
        """
        # 检查通知是否启用
        if not config.notification_enabled:
            logger.info(f"备份通知已禁用，跳过成功通知 (Job ID: {backup_job.id})")
            return False
        
        # 检查通知邮箱是否配置
        if not config.notification_email:
            logger.warning(f"未配置通知邮箱，跳过成功通知 (Job ID: {backup_job.id})")
            return False
        
        # 检查SMTP是否配置
        if not mailer_is_configured():
            logger.warning(f"SMTP未配置，跳过成功通知 (Job ID: {backup_job.id})")
            return False
        
        # 格式化邮件内容
        email_data = NotificationService._format_backup_notification_email(backup_job, is_success=True)
        
        try:
            # 发送邮件
            result = send_logged_mail(
                event_type='backup_success',
                recipient=config.notification_email,
                subject=email_data['subject'],
                plain_text=email_data['plain_text'],
                title=email_data['title'],
                intro=email_data['intro'],
                body_html=email_data['body_html'],
                cooldown_seconds=300  # 5分钟冷却时间
            )
            
            if result:
                logger.info(f"备份成功通知已发送到 {config.notification_email} (Job ID: {backup_job.id})")
            else:
                logger.warning(f"备份成功通知被冷却限制跳过 (Job ID: {backup_job.id})")
            
            return result
        except Exception as e:
            logger.error(f"发送备份成功通知失败: {str(e)} (Job ID: {backup_job.id})")
            return False
    
    @staticmethod
    def send_backup_failure_notification(backup_job: BackupJob, config: BackupConfig) -> bool:
        """
        发送备份失败通知
        
        Args:
            backup_job: 备份任务对象
            config: 备份配置对象
            
        Returns:
            bool: 是否成功发送通知
        """
        # 检查通知是否启用
        if not config.notification_enabled:
            logger.info(f"备份通知已禁用，跳过失败通知 (Job ID: {backup_job.id})")
            return False
        
        # 检查通知邮箱是否配置
        if not config.notification_email:
            logger.warning(f"未配置通知邮箱，跳过失败通知 (Job ID: {backup_job.id})")
            return False
        
        # 检查SMTP是否配置
        if not mailer_is_configured():
            logger.warning(f"SMTP未配置，跳过失败通知 (Job ID: {backup_job.id})")
            return False
        
        # 格式化邮件内容
        email_data = NotificationService._format_backup_notification_email(backup_job, is_success=False)
        
        try:
            # 发送邮件
            result = send_logged_mail(
                event_type='backup_failure',
                recipient=config.notification_email,
                subject=email_data['subject'],
                plain_text=email_data['plain_text'],
                title=email_data['title'],
                intro=email_data['intro'],
                body_html=email_data['body_html'],
                cooldown_seconds=300  # 5分钟冷却时间
            )
            
            if result:
                logger.info(f"备份失败通知已发送到 {config.notification_email} (Job ID: {backup_job.id})")
            else:
                logger.warning(f"备份失败通知被冷却限制跳过 (Job ID: {backup_job.id})")
            
            return result
        except Exception as e:
            logger.error(f"发送备份失败通知失败: {str(e)} (Job ID: {backup_job.id})")
            return False
    
    @staticmethod
    def send_storage_warning_notification(config: BackupConfig, usage_info: dict) -> bool:
        """
        发送存储空间警告通知
        
        Args:
            config: 备份配置对象
            usage_info: 存储使用信息字典，包含:
                - total_size_mb: 总使用空间(MB)
                - backup_count: 备份文件数量
                - available_space_mb: 可用空间(MB) (可选)
                - threshold_mb: 警告阈值(MB)
                
        Returns:
            bool: 是否成功发送通知
        """
        # 检查通知是否启用
        if not config.notification_enabled:
            logger.info("备份通知已禁用，跳过存储警告通知")
            return False
        
        # 检查通知邮箱是否配置
        if not config.notification_email:
            logger.warning("未配置通知邮箱，跳过存储警告通知")
            return False
        
        # 检查SMTP是否配置
        if not mailer_is_configured():
            logger.warning("SMTP未配置，跳过存储警告通知")
            return False
        
        # 格式化邮件内容
        total_size_mb = usage_info.get('total_size_mb', 0)
        backup_count = usage_info.get('backup_count', 0)
        available_space_mb = usage_info.get('available_space_mb')
        threshold_mb = usage_info.get('threshold_mb', config.storage_warning_threshold_mb)
        
        # 构建邮件内容
        subject = "⚠️ 备份存储空间警告"
        title = "存储空间不足警告"
        intro = "备份系统检测到存储空间使用量已接近或超过警告阈值，请及时处理。"
        
        # 构建详细信息HTML
        details_html = f'''
            <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:16px;margin-top:16px;">
                <p style="margin:0 0 8px;color:#856404;font-weight:bold;">存储使用情况：</p>
                <ul style="margin:8px 0;padding-left:20px;color:#856404;">
                    <li>当前备份文件数量: <strong>{backup_count}</strong></li>
                    <li>总使用空间: <strong>{total_size_mb:.2f} MB</strong></li>
                    <li>警告阈值: <strong>{threshold_mb} MB</strong></li>
        '''
        
        if available_space_mb is not None:
            details_html += f'<li>可用空间: <strong>{available_space_mb:.2f} MB</strong></li>'
        
        details_html += '''
                </ul>
            </div>
        '''
        
        body_html = f'''
            {details_html}
            <p style="margin-top:16px;color:#64748b;line-height:1.8;">
                建议操作：<br>
                • 清理不需要的旧备份文件<br>
                • 增加存储空间配额<br>
                • 调整备份保留策略
            </p>
        '''
        
        # 纯文本版本
        plain_text = f"""
存储空间不足警告

备份系统检测到存储空间使用量已接近或超过警告阈值。

存储使用情况：
- 当前备份文件数量: {backup_count}
- 总使用空间: {total_size_mb:.2f} MB
- 警告阈值: {threshold_mb} MB
"""
        
        if available_space_mb is not None:
            plain_text += f"- 可用空间: {available_space_mb:.2f} MB\n"
        
        plain_text += """
建议操作：
• 清理不需要的旧备份文件
• 增加存储空间配额
• 调整备份保留策略
"""
        
        try:
            # 发送邮件
            result = send_logged_mail(
                event_type='backup_storage_warning',
                recipient=config.notification_email,
                subject=subject,
                plain_text=plain_text,
                title=title,
                intro=intro,
                body_html=body_html,
                cooldown_seconds=3600  # 1小时冷却时间，避免频繁发送警告
            )
            
            if result:
                logger.info(f"存储空间警告通知已发送到 {config.notification_email}")
            else:
                logger.warning("存储空间警告通知被冷却限制跳过")
            
            return result
        except Exception as e:
            logger.error(f"发送存储空间警告通知失败: {str(e)}")
            return False
    
    @staticmethod
    def _format_backup_notification_email(backup_job: BackupJob, is_success: bool) -> dict:
        """
        格式化备份通知邮件内容
        
        Args:
            backup_job: 备份任务对象
            is_success: 是否为成功通知
            
        Returns:
            dict: 包含邮件各部分内容的字典
        """
        from flask import current_app
        from datetime import timezone
        from zoneinfo import ZoneInfo
        
        # 获取配置的时区
        try:
            tz_name = current_app.config.get('APP_TIMEZONE', 'Asia/Shanghai')
            local_tz = ZoneInfo(tz_name)
        except Exception:
            # 如果时区配置无效，使用 Asia/Shanghai
            local_tz = ZoneInfo('Asia/Shanghai')
        
        # 格式化时间（将 UTC 时间转换为本地时区）
        if backup_job.started_at:
            # 假设数据库中的时间是 UTC（无时区信息）
            started_at_utc = backup_job.started_at.replace(tzinfo=timezone.utc)
            started_at_local = started_at_utc.astimezone(local_tz)
            started_at_str = started_at_local.strftime('%Y-%m-%d %H:%M:%S')
        else:
            started_at_str = '未知'
        
        if backup_job.completed_at:
            completed_at_utc = backup_job.completed_at.replace(tzinfo=timezone.utc)
            completed_at_local = completed_at_utc.astimezone(local_tz)
            completed_at_str = completed_at_local.strftime('%Y-%m-%d %H:%M:%S')
        else:
            completed_at_str = '未完成'
        
        # 格式化文件大小
        file_size_mb = backup_job.file_size_bytes / (1024 * 1024) if backup_job.file_size_bytes else 0
        
        # 格式化执行时长
        duration_str = f"{backup_job.duration_seconds}秒" if backup_job.duration_seconds else "未知"
        
        if is_success:
            subject = "✅ 备份任务执行成功"
            title = "备份成功"
            intro = "备份任务已成功完成，数据已安全保存到远程存储。"
            status_color = "#28a745"
            status_text = "成功"
            
            # 构建成功通知的详细信息
            details_html = f'''
                <div style="background:#d4edda;border:1px solid #c3e6cb;border-radius:8px;padding:16px;margin-top:16px;">
                    <p style="margin:0 0 8px;color:#155724;font-weight:bold;">备份详情：</p>
                    <ul style="margin:8px 0;padding-left:20px;color:#155724;">
                        <li>任务ID: <strong>#{backup_job.id}</strong></li>
                        <li>触发方式: <strong>{'手动' if backup_job.trigger_type == 'manual' else '自动'}</strong></li>
                        <li>备份模式: <strong>{'完整备份' if backup_job.backup_mode == 'full' else '增量备份'}</strong></li>
                        <li>开始时间: <strong>{started_at_str}</strong></li>
                        <li>完成时间: <strong>{completed_at_str}</strong></li>
                        <li>执行时长: <strong>{duration_str}</strong></li>
                        <li>文件名: <strong>{backup_job.filename or '未知'}</strong></li>
                        <li>文件大小: <strong>{file_size_mb:.2f} MB</strong></li>
                        <li>存储方式: <strong>{backup_job.storage_type or '未知'}</strong></li>
            '''
            
            if backup_job.is_encrypted:
                details_html += '<li>加密状态: <strong>已加密</strong></li>'
            
            details_html += '''
                    </ul>
                </div>
            '''
            
            body_html = details_html
            
            # 纯文本版本
            plain_text = f"""
备份任务执行成功

备份任务已成功完成，数据已安全保存到远程存储。

备份详情：
- 任务ID: #{backup_job.id}
- 触发方式: {'手动' if backup_job.trigger_type == 'manual' else '自动'}
- 备份模式: {'完整备份' if backup_job.backup_mode == 'full' else '增量备份'}
- 开始时间: {started_at_str}
- 完成时间: {completed_at_str}
- 执行时长: {duration_str}
- 文件名: {backup_job.filename or '未知'}
- 文件大小: {file_size_mb:.2f} MB
- 存储方式: {backup_job.storage_type or '未知'}
"""
            
            if backup_job.is_encrypted:
                plain_text += "- 加密状态: 已加密\n"
        
        else:
            subject = "❌ 备份任务执行失败"
            title = "备份失败"
            intro = "备份任务执行过程中发生错误，请及时检查并处理。"
            status_color = "#dc3545"
            status_text = "失败"
            
            # 构建失败通知的详细信息
            error_message = backup_job.error_message or "未知错误"
            
            details_html = f'''
                <div style="background:#f8d7da;border:1px solid #f5c6cb;border-radius:8px;padding:16px;margin-top:16px;">
                    <p style="margin:0 0 8px;color:#721c24;font-weight:bold;">备份详情：</p>
                    <ul style="margin:8px 0;padding-left:20px;color:#721c24;">
                        <li>任务ID: <strong>#{backup_job.id}</strong></li>
                        <li>触发方式: <strong>{'手动' if backup_job.trigger_type == 'manual' else '自动'}</strong></li>
                        <li>备份模式: <strong>{'完整备份' if backup_job.backup_mode == 'full' else '增量备份'}</strong></li>
                        <li>开始时间: <strong>{started_at_str}</strong></li>
                        <li>失败时间: <strong>{completed_at_str}</strong></li>
                        <li>存储方式: <strong>{backup_job.storage_type or '未知'}</strong></li>
                    </ul>
                </div>
                <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:16px;margin-top:12px;">
                    <p style="margin:0 0 8px;color:#856404;font-weight:bold;">错误信息：</p>
                    <p style="margin:0;color:#856404;font-family:monospace;font-size:13px;word-break:break-word;">
                        {error_message}
                    </p>
                </div>
            '''
            
            body_html = details_html
            
            # 纯文本版本
            plain_text = f"""
备份任务执行失败

备份任务执行过程中发生错误，请及时检查并处理。

备份详情：
- 任务ID: #{backup_job.id}
- 触发方式: {'手动' if backup_job.trigger_type == 'manual' else '自动'}
- 备份模式: {'完整备份' if backup_job.backup_mode == 'full' else '增量备份'}
- 开始时间: {started_at_str}
- 失败时间: {completed_at_str}
- 存储方式: {backup_job.storage_type or '未知'}

错误信息：
{error_message}
"""
        
        return {
            'subject': subject,
            'title': title,
            'intro': intro,
            'body_html': body_html,
            'plain_text': plain_text
        }
