# -*- coding: utf-8 -*-
"""
备份配置管理服务
Backup Configuration Manager Service
"""

import re
from typing import Tuple, Optional
from models import db, BackupConfig


class BackupConfigManager:
    """备份配置管理器"""
    
    @staticmethod
    def get_config() -> Optional[BackupConfig]:
        """
        获取当前备份配置
        Get current backup configuration
        
        Returns:
            BackupConfig: 备份配置对象，如果不存在则返回None
        """
        return BackupConfig.query.first()
    
    @staticmethod
    def update_config(config_data: dict) -> BackupConfig:
        """
        更新备份配置
        Update backup configuration
        
        Args:
            config_data: 配置数据字典
            
        Returns:
            BackupConfig: 更新后的配置对象
            
        Raises:
            ValueError: 配置验证失败时抛出
        """
        # 获取现有配置或创建新配置
        config = BackupConfigManager.get_config()
        if config is None:
            config = BackupConfig()
            db.session.add(config)
        
        # 更新基本配置
        if 'enabled' in config_data:
            config.enabled = bool(config_data['enabled'])
        
        if 'storage_type' in config_data:
            config.storage_type = config_data['storage_type']
        
        if 'schedule_type' in config_data:
            config.schedule_type = config_data['schedule_type']
        
        if 'schedule_value' in config_data:
            config.schedule_value = config_data.get('schedule_value')
        
        if 'retention_count' in config_data:
            config.retention_count = int(config_data['retention_count'])
        
        if 'backup_mode' in config_data:
            config.backup_mode = config_data['backup_mode']
        
        # 更新加密配置
        if 'encryption_enabled' in config_data:
            config.encryption_enabled = bool(config_data['encryption_enabled'])
        
        if 'encryption_key_hash' in config_data:
            config.encryption_key_hash = config_data.get('encryption_key_hash')
        
        # 更新FTP配置
        if 'ftp_host' in config_data:
            config.ftp_host = config_data.get('ftp_host')
        
        if 'ftp_port' in config_data:
            config.ftp_port = int(config_data['ftp_port']) if config_data.get('ftp_port') else 21
        
        if 'ftp_username' in config_data:
            config.ftp_username = config_data.get('ftp_username')
        
        if 'ftp_password' in config_data:
            config.ftp_password = config_data.get('ftp_password')
        
        if 'ftp_path' in config_data:
            config.ftp_path = config_data.get('ftp_path', '/')
        
        # 更新邮件配置
        if 'email_recipient' in config_data:
            config.email_recipient = config_data.get('email_recipient')
        
        # 更新S3配置
        if 's3_endpoint' in config_data:
            config.s3_endpoint = config_data.get('s3_endpoint')
        
        if 's3_bucket' in config_data:
            config.s3_bucket = config_data.get('s3_bucket')
        
        if 's3_access_key' in config_data:
            config.s3_access_key = config_data.get('s3_access_key')
        
        if 's3_secret_key' in config_data:
            config.s3_secret_key = config_data.get('s3_secret_key')
        
        if 's3_path_prefix' in config_data:
            config.s3_path_prefix = config_data.get('s3_path_prefix', 'backups/')
        
        if 's3_region' in config_data:
            config.s3_region = config_data.get('s3_region')
        
        # 更新通知配置
        if 'notification_enabled' in config_data:
            config.notification_enabled = bool(config_data['notification_enabled'])
        
        if 'notification_email' in config_data:
            config.notification_email = config_data.get('notification_email')
        
        # 更新存储监控配置
        if 'storage_warning_threshold_mb' in config_data:
            config.storage_warning_threshold_mb = int(config_data['storage_warning_threshold_mb'])
        
        # 验证配置
        is_valid, error_msg = BackupConfigManager.validate_config(config)
        if not is_valid:
            raise ValueError(error_msg)
        
        # 提交到数据库
        db.session.commit()
        
        return config
    
    @staticmethod
    def validate_config(config: BackupConfig) -> Tuple[bool, str]:
        """
        验证配置有效性
        Validate configuration validity
        
        Args:
            config: 备份配置对象
            
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        # 验证存储类型
        valid_storage_types = ['ftp', 'email', 's3']
        
        # 解析存储类型（支持JSON数组格式的多目标备份）
        import json
        storage_types = []
        if config.storage_type:
            try:
                # 尝试解析为JSON数组
                storage_types = json.loads(config.storage_type)
                if not isinstance(storage_types, list):
                    storage_types = [config.storage_type]
            except (json.JSONDecodeError, TypeError):
                # 如果不是JSON，当作单个字符串处理
                storage_types = [config.storage_type]
        
        if not storage_types:
            return False, "必须至少选择一个存储方式"
        
        # 验证每个存储类型是否有效
        for st in storage_types:
            if st not in valid_storage_types:
                return False, f"存储类型必须是以下之一: {', '.join(valid_storage_types)}"
        
        # 验证调度类型
        valid_schedule_types = ['hourly', 'daily', 'weekly', 'cron']
        if not config.schedule_type or config.schedule_type not in valid_schedule_types:
            return False, f"调度类型必须是以下之一: {', '.join(valid_schedule_types)}"
        
        # 验证cron表达式
        if config.schedule_type == 'cron':
            if not config.schedule_value:
                return False, "使用cron调度类型时必须提供cron表达式"
            if not BackupConfigManager._validate_cron_expression(config.schedule_value):
                return False, "无效的cron表达式格式"
        
        # 根据存储类型验证必填字段（只验证已选中的存储方式）
        if 'ftp' in storage_types:
            if not config.ftp_host:
                return False, "FTP存储方式需要提供FTP主机地址"
            if not config.ftp_username:
                return False, "FTP存储方式需要提供FTP用户名"
            if not config.ftp_password:
                return False, "FTP存储方式需要提供FTP密码"
            if config.ftp_port is None or config.ftp_port < 1 or config.ftp_port > 65535:
                return False, "FTP端口必须在1-65535之间"
        
        if 'email' in storage_types:
            if not config.email_recipient:
                return False, "邮件存储方式需要提供收件人邮箱地址"
            if not BackupConfigManager._validate_email(config.email_recipient):
                return False, "收件人邮箱地址格式无效"
        
        if 's3' in storage_types:
            if not config.s3_bucket:
                return False, "S3存储方式需要提供存储桶名称"
            if not config.s3_access_key:
                return False, "S3存储方式需要提供访问密钥"
            if not config.s3_secret_key:
                return False, "S3存储方式需要提供密钥"
        
        # 验证保留数量（使用默认值如果为None）
        retention_count = config.retention_count if config.retention_count is not None else 10
        if retention_count < 1:
            return False, "保留数量必须大于等于1"
        
        # 验证备份模式（使用默认值如果为None）
        backup_mode = config.backup_mode if config.backup_mode else 'full'
        valid_backup_modes = ['full', 'incremental']
        if backup_mode not in valid_backup_modes:
            return False, f"备份模式必须是以下之一: {', '.join(valid_backup_modes)}"
        
        # 验证通知邮箱
        if config.notification_enabled and config.notification_email:
            if not BackupConfigManager._validate_email(config.notification_email):
                return False, "通知邮箱地址格式无效"
        
        # 验证存储警告阈值（使用默认值如果为None）
        threshold = config.storage_warning_threshold_mb if config.storage_warning_threshold_mb is not None else 1024
        if threshold < 0:
            return False, "存储警告阈值必须大于等于0"
        
        return True, ""
    
    @staticmethod
    def _validate_email(email: str) -> bool:
        """
        验证邮箱地址格式
        Validate email address format
        
        Args:
            email: 邮箱地址
            
        Returns:
            bool: 是否有效
        """
        if not email:
            return False
        
        # 简单的邮箱格式验证
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def _validate_cron_expression(cron_expr: str) -> bool:
        """
        验证cron表达式格式
        Validate cron expression format
        
        Args:
            cron_expr: cron表达式
            
        Returns:
            bool: 是否有效
        """
        if not cron_expr:
            return False
        
        # 分割cron表达式
        parts = cron_expr.strip().split()
        
        # 标准cron表达式应该有5个或6个部分
        # 5部分: 分 时 日 月 周
        # 6部分: 秒 分 时 日 月 周
        if len(parts) not in [5, 6]:
            return False
        
        # 基本格式验证（允许数字、*、-、,、/）
        pattern = r'^[\d\*\-\,\/]+$'
        for part in parts:
            if not re.match(pattern, part):
                return False
        
        return True
    
    @staticmethod
    def test_connection(config: BackupConfig = None) -> Tuple[bool, str]:
        """
        测试存储连接
        Test storage connection
        
        Args:
            config: 备份配置对象，如果为None则使用当前配置
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        # 如果未提供配置，获取当前配置
        if config is None:
            config = BackupConfigManager.get_config()
            if config is None:
                return False, "备份配置不存在"
        
        # 验证配置有效性
        is_valid, error_msg = BackupConfigManager.validate_config(config)
        if not is_valid:
            return False, f"配置验证失败: {error_msg}"
        
        # 根据存储类型测试连接
        try:
            if config.storage_type == 'ftp':
                from services.storage.ftp_adapter import FTPStorageAdapter
                adapter = FTPStorageAdapter(
                    host=config.ftp_host,
                    port=config.ftp_port or 21,
                    username=config.ftp_username,
                    password=config.ftp_password,
                    remote_dir=config.ftp_path or '/'
                )
                success, message = adapter.test_connection()
                return success, message
            
            elif config.storage_type == 'email':
                from services.storage.email_adapter import EmailStorageAdapter
                adapter = EmailStorageAdapter(
                    recipient=config.email_recipient
                )
                success, message = adapter.test_connection()
                return success, message
            
            elif config.storage_type == 's3':
                from services.storage.s3_adapter import S3StorageAdapter
                adapter = S3StorageAdapter(
                    bucket_name=config.s3_bucket,
                    access_key=config.s3_access_key,
                    secret_key=config.s3_secret_key,
                    region=config.s3_region or 'us-east-1',
                    endpoint_url=config.s3_endpoint
                )
                success, message = adapter.test_connection()
                return success, message
            
            else:
                return False, f"不支持的存储类型: {config.storage_type}"
        
        except Exception as e:
            return False, f"连接测试失败: {str(e)}"
    
    @staticmethod
    def export_config() -> dict:
        """
        导出配置（排除敏感信息）
        Export configuration (excluding sensitive information)
        
        Returns:
            dict: 配置数据字典（不包含密码、密钥等敏感信息）
        """
        config = BackupConfigManager.get_config()
        if config is None:
            return {}
        
        # 导出配置，排除敏感字段
        exported_config = {
            'enabled': config.enabled,
            'storage_type': config.storage_type,
            'schedule_type': config.schedule_type,
            'schedule_value': config.schedule_value,
            'retention_count': config.retention_count,
            'backup_mode': config.backup_mode,
            'encryption_enabled': config.encryption_enabled,
            'notification_enabled': config.notification_enabled,
            'notification_email': config.notification_email,
            'storage_warning_threshold_mb': config.storage_warning_threshold_mb,
        }
        
        # 根据存储类型添加非敏感字段
        if config.storage_type == 'ftp':
            exported_config['ftp_host'] = config.ftp_host
            exported_config['ftp_port'] = config.ftp_port
            exported_config['ftp_username'] = config.ftp_username
            exported_config['ftp_path'] = config.ftp_path
            # 不导出 ftp_password
        
        elif config.storage_type == 'email':
            exported_config['email_recipient'] = config.email_recipient
        
        elif config.storage_type == 's3':
            exported_config['s3_endpoint'] = config.s3_endpoint
            exported_config['s3_bucket'] = config.s3_bucket
            exported_config['s3_path_prefix'] = config.s3_path_prefix
            exported_config['s3_region'] = config.s3_region
            # 不导出 s3_access_key 和 s3_secret_key
        
        return exported_config
    
    @staticmethod
    def import_config(config_data: dict) -> BackupConfig:
        """
        导入配置
        Import configuration
        
        Args:
            config_data: 配置数据字典
            
        Returns:
            BackupConfig: 导入后的配置对象
            
        Raises:
            ValueError: 配置数据无效时抛出
        """
        if not config_data:
            raise ValueError("配置数据不能为空")
        
        # 验证必需字段
        required_fields = ['storage_type', 'schedule_type']
        for field in required_fields:
            if field not in config_data:
                raise ValueError(f"缺少必需字段: {field}")
        
        # 验证存储类型
        valid_storage_types = ['ftp', 'email', 's3']
        if config_data['storage_type'] not in valid_storage_types:
            raise ValueError(f"无效的存储类型: {config_data['storage_type']}")
        
        # 验证调度类型
        valid_schedule_types = ['hourly', 'daily', 'weekly', 'cron']
        if config_data['schedule_type'] not in valid_schedule_types:
            raise ValueError(f"无效的调度类型: {config_data['schedule_type']}")
        
        # 根据存储类型验证必需字段（敏感信息除外）
        if config_data['storage_type'] == 'ftp':
            if 'ftp_host' not in config_data or not config_data['ftp_host']:
                raise ValueError("FTP配置缺少主机地址")
            if 'ftp_username' not in config_data or not config_data['ftp_username']:
                raise ValueError("FTP配置缺少用户名")
            # ftp_password 需要用户在导入后手动补充
        
        elif config_data['storage_type'] == 'email':
            if 'email_recipient' not in config_data or not config_data['email_recipient']:
                raise ValueError("邮件配置缺少收件人地址")
        
        elif config_data['storage_type'] == 's3':
            if 's3_bucket' not in config_data or not config_data['s3_bucket']:
                raise ValueError("S3配置缺少存储桶名称")
            # s3_access_key 和 s3_secret_key 需要用户在导入后手动补充
        
        # 使用 update_config 方法导入配置
        # 注意：由于敏感信息未包含在导入数据中，配置可能不完整
        # 需要提示用户补充敏感信息
        try:
            config = BackupConfigManager.update_config(config_data)
            return config
        except ValueError as e:
            # 如果验证失败（通常是因为缺少敏感信息），重新抛出更友好的错误
            raise ValueError(f"配置导入失败: {str(e)}。请确保补充所有必需的敏感信息（密码、密钥等）")
