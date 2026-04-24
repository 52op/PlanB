# -*- coding: utf-8 -*-
"""
备份恢复管理服务
Backup Restore Manager Service

Requirements: 9.1, 9.2, 9.3
"""

from typing import Optional, Tuple, Dict, List
from models import db, BackupJob, BackupConfig


class BackupRestorer:
    """备份恢复管理器"""
    
    def __init__(self, app=None):
        """
        初始化备份恢复管理器
        Initialize backup restorer
        
        Args:
            app: Flask应用实例
        """
        self.app = app
    
    def list_available_backups(self, include_remote=True, include_orphaned=True) -> List[Dict]:
        """
        列出所有可用的备份
        List all available backups
        
        返回本地备份、远程备份和孤立文件（本地存在但数据库无记录）。
        
        Args:
            include_remote: 是否包含远程备份（FTP/S3）
            include_orphaned: 是否包含孤立文件（本地存在但数据库无记录）
        
        Returns:
            list[dict]: 备份列表，每个备份包含：
                {
                    'source': 'local' | 'local_orphaned' | 'local_missing' | 'ftp' | 's3',
                    'job': BackupJob对象或None（孤立文件为None）,
                    'filename': str,
                    'file_size_bytes': int,
                    'is_encrypted': bool,
                    'created_at': datetime或None,
                    'storage_path': str（远程路径或本地路径）,
                    'file_exists': bool（文件是否实际存在）
                }
        """
        import os
        from datetime import datetime
        from runtime_paths import get_data_subdir
        from services.storage.ftp_adapter import FTPStorageAdapter
        from services.storage.s3_adapter import S3StorageAdapter
        
        backups = []
        
        # 1. 获取数据库中的备份记录
        db_backups = BackupJob.query.filter_by(
            status='success'
        ).order_by(BackupJob.completed_at.desc()).all()
        
        # 获取本地备份目录
        local_backup_dir = get_data_subdir('backups')
        
        # 2. 处理数据库中的备份记录
        local_filenames = set()  # 记录已处理的本地文件名
        
        for backup in db_backups:
            if not backup.filename:
                continue
            
            # 检查是否为本地备份
            if backup.storage_type == 'local':
                local_path = os.path.join(local_backup_dir, backup.filename)
                file_exists = os.path.exists(local_path)
                
                if file_exists:
                    # 文件存在
                    backups.append({
                        'source': 'local',
                        'job': backup,
                        'filename': backup.filename,
                        'file_size_bytes': backup.file_size_bytes or os.path.getsize(local_path),
                        'is_encrypted': backup.is_encrypted,
                        'created_at': backup.completed_at,
                        'storage_path': local_path,
                        'file_exists': True
                    })
                    local_filenames.add(backup.filename)
                else:
                    # 文件缺失（有记录但文件不存在）
                    backups.append({
                        'source': 'local_missing',
                        'job': backup,
                        'filename': backup.filename,
                        'file_size_bytes': backup.file_size_bytes,
                        'is_encrypted': backup.is_encrypted,
                        'created_at': backup.completed_at,
                        'storage_path': local_path,
                        'file_exists': False
                    })
            
            # 检查是否为远程备份（FTP/S3）
            elif include_remote and backup.storage_type in ('ftp', 's3'):
                backups.append({
                    'source': backup.storage_type,
                    'job': backup,
                    'filename': backup.filename,
                    'file_size_bytes': backup.file_size_bytes,
                    'is_encrypted': backup.is_encrypted,
                    'created_at': backup.completed_at,
                    'storage_path': backup.storage_path,
                    'file_exists': True  # 假设远程文件存在
                })
        
        # 3. 扫描本地目录，查找孤立文件（数据库无记录）
        if include_orphaned and os.path.exists(local_backup_dir):
            try:
                for filename in os.listdir(local_backup_dir):
                    # 只处理备份文件（.tar.gz 或 .tar.gz.enc）
                    if not (filename.endswith('.tar.gz') or filename.endswith('.tar.gz.enc')):
                        continue
                    
                    # 跳过已处理的文件
                    if filename in local_filenames:
                        continue
                    
                    # 这是一个孤立文件
                    local_path = os.path.join(local_backup_dir, filename)
                    file_size = os.path.getsize(local_path)
                    is_encrypted = filename.endswith('.enc')
                    
                    # 尝试从文件名解析时间戳
                    import re
                    match = re.search(r'(\d{8}_\d{6})', filename)
                    created_at = None
                    if match:
                        try:
                            created_at = datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')
                        except:
                            pass
                    
                    backups.append({
                        'source': 'local_orphaned',
                        'job': None,
                        'filename': filename,
                        'file_size_bytes': file_size,
                        'is_encrypted': is_encrypted,
                        'created_at': created_at,
                        'storage_path': local_path,
                        'file_exists': True
                    })
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"扫描本地备份目录失败: {str(e)}")
        
        # 4. 按时间排序（最新的在前）
        backups.sort(key=lambda x: x['created_at'] if x['created_at'] else datetime.min, reverse=True)
        
        return backups
    
    def cleanup_invalid_records(self) -> Tuple[int, str]:
        """
        清理无效的备份记录
        Cleanup invalid backup records
        
        删除文件不存在的本地备份记录。
        
        Returns:
            Tuple[int, str]: (删除的记录数, 消息)
        """
        import os
        from runtime_paths import get_data_subdir
        
        local_backup_dir = get_data_subdir('backups')
        
        # 查询所有本地备份记录
        local_backups = BackupJob.query.filter_by(
            storage_type='local',
            status='success'
        ).all()
        
        deleted_count = 0
        
        for backup in local_backups:
            if not backup.filename:
                continue
            
            local_path = os.path.join(local_backup_dir, backup.filename)
            
            # 如果文件不存在，删除记录
            if not os.path.exists(local_path):
                db.session.delete(backup)
                deleted_count += 1
        
        db.session.commit()
        
        if deleted_count > 0:
            return (deleted_count, f"已清理 {deleted_count} 条无效记录")
        else:
            return (0, "没有发现无效记录")
    
    def delete_backup_record(self, backup_job_id: int, delete_file: bool = False) -> Tuple[bool, str]:
        """
        删除备份记录
        Delete backup record
        
        删除指定的备份记录，可选择是否同时删除文件。
        
        Args:
            backup_job_id: 备份任务ID
            delete_file: 是否同时删除备份文件
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        import os
        from runtime_paths import get_data_subdir
        
        try:
            backup_job = BackupJob.query.get(backup_job_id)
            
            if not backup_job:
                return (False, "备份记录不存在")
            
            # 如果需要删除文件
            if delete_file and backup_job.storage_type == 'local' and backup_job.filename:
                local_backup_dir = get_data_subdir('backups')
                local_path = os.path.join(local_backup_dir, backup_job.filename)
                
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except Exception as e:
                        return (False, f"删除文件失败: {str(e)}")
            
            # 删除数据库记录
            db.session.delete(backup_job)
            db.session.commit()
            
            if delete_file:
                return (True, "备份记录和文件已删除")
            else:
                return (True, "备份记录已删除")
                
        except Exception as e:
            db.session.rollback()
            return (False, f"删除失败: {str(e)}")
    
    def create_orphaned_backup_job(self, filename: str) -> BackupJob:
        """
        为孤立文件创建临时的 BackupJob 记录
        Create temporary BackupJob record for orphaned file
        
        当恢复孤立文件时，创建一个临时的数据库记录以便恢复流程使用。
        
        Args:
            filename: 孤立文件的文件名
            
        Returns:
            BackupJob: 临时创建的备份任务对象
            
        Raises:
            ValueError: 当文件不存在时抛出
        """
        import os
        from datetime import datetime
        from runtime_paths import get_data_subdir
        
        # 验证文件存在
        local_backup_dir = get_data_subdir('backups')
        local_path = os.path.join(local_backup_dir, filename)
        
        if not os.path.exists(local_path):
            raise ValueError(f"孤立文件不存在: {filename}")
        
        # 创建临时的 BackupJob 记录
        backup_job = BackupJob()
        backup_job.filename = filename
        backup_job.storage_type = 'local'
        backup_job.storage_path = local_path
        backup_job.file_size_bytes = os.path.getsize(local_path)
        backup_job.is_encrypted = filename.endswith('.enc')
        backup_job.status = 'success'
        backup_job.backup_mode = 'full'
        backup_job.trigger_type = 'manual'
        
        # 尝试从文件名解析时间戳
        import re
        match = re.search(r'(\d{8}_\d{6})', filename)
        if match:
            try:
                timestamp = datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')
                backup_job.started_at = timestamp
                backup_job.completed_at = timestamp
            except:
                backup_job.started_at = datetime.now()
                backup_job.completed_at = datetime.now()
        else:
            backup_job.started_at = datetime.now()
            backup_job.completed_at = datetime.now()
        
        # 保存到数据库
        db.session.add(backup_job)
        db.session.commit()
        
        return backup_job
    
    def get_backup_metadata(self, backup_job_id: int) -> Dict:
        """
        获取备份元数据
        Get backup metadata
        
        获取指定备份任务的详细元数据信息，包括备份内容、统计信息等。
        
        Args:
            backup_job_id: 备份任务ID
            
        Returns:
            dict: 备份元数据字典：
                {
                    'backup_id': int,           # 备份任务ID
                    'filename': str,            # 备份文件名
                    'backup_mode': str,         # 备份模式
                    'trigger_type': str,        # 触发类型
                    'storage_type': str,        # 存储类型
                    'storage_path': str,        # 存储路径
                    'file_size_bytes': int,     # 文件大小
                    'file_hash': str,           # 文件哈希
                    'is_encrypted': bool,       # 是否加密
                    'created_at': datetime,     # 备份时间
                    'completed_at': datetime,   # 完成时间
                    'duration_seconds': int,    # 执行时长
                    'base_backup_id': int,      # 基准备份ID
                    'statistics': {             # 统计信息
                        'total_size_bytes': int,
                        'db_size_bytes': int,
                        'uploads_count': int,
                        'uploads_size_bytes': int,
                        'docs_count': int,
                        'docs_size_bytes': int
                    },
                    'content_summary': {        # 内容摘要
                        'has_database': bool,
                        'has_uploads': bool,
                        'has_documents': bool
                    }
                }
                
        Raises:
            ValueError: 当备份任务不存在时抛出
        """
        # 查询备份任务
        backup_job = BackupJob.query.get(backup_job_id)
        if backup_job is None:
            raise ValueError(f"备份任务不存在: ID={backup_job_id}")
        
        # 检查备份任务状态
        if backup_job.status != 'success':
            raise ValueError(f"备份任务未成功完成: ID={backup_job_id}, 状态={backup_job.status}")
        
        # 计算总大小
        total_size = 0
        if backup_job.db_size_bytes:
            total_size += backup_job.db_size_bytes
        if backup_job.uploads_size_bytes:
            total_size += backup_job.uploads_size_bytes
        if backup_job.docs_size_bytes:
            total_size += backup_job.docs_size_bytes
        
        # 构建元数据
        metadata = {
            'backup_id': backup_job.id,
            'filename': backup_job.filename,
            'backup_mode': backup_job.backup_mode,
            'trigger_type': backup_job.trigger_type,
            'storage_type': backup_job.storage_type,
            'storage_path': backup_job.storage_path,
            'file_size_bytes': backup_job.file_size_bytes,
            'file_hash': backup_job.file_hash,
            'is_encrypted': backup_job.is_encrypted,
            'created_at': backup_job.started_at,
            'completed_at': backup_job.completed_at,
            'duration_seconds': backup_job.duration_seconds,
            'base_backup_id': backup_job.base_backup_id,
            'statistics': {
                'total_size_bytes': total_size,
                'db_size_bytes': backup_job.db_size_bytes or 0,
                'uploads_count': backup_job.uploads_count or 0,
                'uploads_size_bytes': backup_job.uploads_size_bytes or 0,
                'docs_count': backup_job.docs_count or 0,
                'docs_size_bytes': backup_job.docs_size_bytes or 0
            },
            'content_summary': {
                'has_database': backup_job.db_size_bytes is not None and backup_job.db_size_bytes > 0,
                'has_uploads': backup_job.uploads_count is not None and backup_job.uploads_count > 0,
                'has_documents': backup_job.docs_count is not None and backup_job.docs_count > 0
            }
        }
        
        return metadata
    
    def restore_backup(self, backup_job_id: int, restore_options: Dict) -> Tuple[bool, str]:
        """
        恢复备份
        Restore backup
        
        从指定的备份文件恢复数据。支持完整恢复或选择性恢复（数据库、上传文件、文档文件）。
        
        工作流程：
        1. 验证输入参数和备份任务
        2. 创建回滚点（备份当前数据）
        3. 下载备份文件
        4. 解密（如果需要）
        5. 解压归档文件
        6. 根据选项恢复各组件
        7. 清理临时文件
        8. 失败时自动回滚
        
        Args:
            backup_job_id: 备份任务ID
            restore_options: 恢复选项字典：
                {
                    'restore_database': bool,    # 是否恢复数据库
                    'restore_uploads': bool,     # 是否恢复上传文件
                    'restore_documents': bool,   # 是否恢复文档文件
                    'decryption_password': str   # 解密密码（如果备份已加密）
                }
                
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
            
        Raises:
            ValueError: 当输入参数无效时抛出
            RuntimeError: 当恢复操作失败时抛出
        """
        import os
        import shutil
        import tempfile
        import logging
        
        logger = logging.getLogger(__name__)
        rollback_point = None
        temp_dir = None
        
        try:
            # 1. 验证输入参数
            if not isinstance(backup_job_id, int) or backup_job_id <= 0:
                raise ValueError(f"无效的备份任务ID: {backup_job_id}")
            
            if not isinstance(restore_options, dict):
                raise ValueError("恢复选项必须是字典类型")
            
            # 获取恢复选项
            restore_database = restore_options.get('restore_database', False)
            restore_uploads = restore_options.get('restore_uploads', False)
            restore_documents = restore_options.get('restore_documents', False)
            decryption_password = restore_options.get('decryption_password', None)
            
            # 至少需要恢复一项内容
            if not (restore_database or restore_uploads or restore_documents):
                raise ValueError("至少需要选择一项恢复内容（数据库、上传文件或文档文件）")
            
            # 2. 获取备份任务信息
            logger.info(f"开始恢复备份: 任务ID={backup_job_id}")
            backup_job = BackupJob.query.get(backup_job_id)
            
            if backup_job is None:
                raise ValueError(f"备份任务不存在: ID={backup_job_id}")
            
            if backup_job.status != 'success':
                raise ValueError(
                    f"备份任务未成功完成，无法恢复: ID={backup_job_id}, "
                    f"状态={backup_job.status}"
                )
            
            # 检查是否需要解密密码
            if backup_job.is_encrypted and not decryption_password:
                raise ValueError("备份文件已加密，需要提供解密密码")
            
            logger.info(
                f"备份任务信息: 文件名={backup_job.filename}, "
                f"存储类型={backup_job.storage_type}, "
                f"是否加密={backup_job.is_encrypted}"
            )
            
            # 3. 创建回滚点
            logger.info("创建回滚点...")
            rollback_point = self._create_rollback_point(
                backup_database=restore_database,
                backup_uploads=restore_uploads,
                backup_documents=restore_documents
            )
            logger.info(f"回滚点已创建: {rollback_point}")
            
            # 4. 下载备份文件
            logger.info("下载备份文件...")
            archive_path = self._download_backup(backup_job)
            logger.info(f"备份文件已下载: {archive_path}")
            
            # 5. 解密（如果需要）
            if backup_job.is_encrypted:
                logger.info("解密备份文件...")
                try:
                    archive_path = self._decrypt_archive(archive_path, decryption_password)
                    logger.info(f"备份文件已解密: {archive_path}")
                except ValueError as e:
                    # 解密失败，可能是密码错误
                    raise ValueError(f"解密失败: {str(e)}")
            
            # 6. 解压归档文件
            logger.info("解压备份归档...")
            temp_dir = tempfile.mkdtemp(prefix='backup_extract_')
            self._extract_archive(archive_path, temp_dir)
            logger.info(f"备份归档已解压: {temp_dir}")
            
            # 7. 根据选项恢复各组件
            restore_summary = []
            
            # 恢复数据库
            if restore_database:
                backup_db_path = os.path.join(temp_dir, 'database', 'app.db')
                if os.path.exists(backup_db_path):
                    logger.info("恢复数据库...")
                    self._restore_database(backup_db_path)
                    restore_summary.append("数据库")
                    logger.info("数据库恢复成功")
                else:
                    logger.warning("备份中不包含数据库文件")
            
            # 恢复上传文件
            if restore_uploads:
                backup_uploads_dir = os.path.join(temp_dir, 'uploads')
                if os.path.exists(backup_uploads_dir):
                    logger.info("恢复上传文件...")
                    self._restore_uploads(backup_uploads_dir)
                    restore_summary.append("上传文件")
                    logger.info("上传文件恢复成功")
                else:
                    logger.warning("备份中不包含上传文件")
            
            # 恢复文档文件
            if restore_documents:
                backup_docs_dir = os.path.join(temp_dir, 'documents')
                if os.path.exists(backup_docs_dir):
                    logger.info("恢复文档文件...")
                    self._restore_documents(backup_docs_dir)
                    restore_summary.append("文档文件")
                    logger.info("文档文件恢复成功")
                else:
                    logger.warning("备份中不包含文档文件")
            
            # 8. 清理临时文件
            logger.info("清理临时文件...")
            try:
                # 清理解压目录
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                
                # 清理下载的归档文件
                if archive_path and os.path.exists(archive_path):
                    # 获取归档文件所在的临时目录
                    archive_temp_dir = os.path.dirname(archive_path)
                    if archive_temp_dir.startswith(tempfile.gettempdir()):
                        shutil.rmtree(archive_temp_dir)
                
                # 清理回滚点
                if rollback_point and os.path.exists(rollback_point):
                    shutil.rmtree(rollback_point)
                
                logger.info("临时文件清理完成")
            except Exception as e:
                # 清理失败不影响恢复结果
                logger.warning(f"清理临时文件失败: {str(e)}")
            
            # 9. 返回成功消息
            if restore_summary:
                success_message = f"备份恢复成功！已恢复: {', '.join(restore_summary)}"
            else:
                success_message = "备份恢复完成，但未找到需要恢复的内容"
            
            logger.info(success_message)
            return (True, success_message)
            
        except ValueError as e:
            # 参数错误或验证失败
            error_message = f"恢复失败: {str(e)}"
            logger.error(error_message)
            
            # 清理临时文件
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            
            # 不需要回滚（还没有修改数据）
            if rollback_point and os.path.exists(rollback_point):
                try:
                    shutil.rmtree(rollback_point)
                except:
                    pass
            
            return (False, error_message)
            
        except Exception as e:
            # 恢复过程中发生错误，需要回滚
            error_message = f"恢复失败: {str(e)}"
            logger.error(error_message)
            
            # 尝试回滚
            if rollback_point and os.path.exists(rollback_point):
                try:
                    logger.info("恢复失败，正在回滚...")
                    self._rollback(rollback_point)
                    logger.info("回滚成功")
                    error_message += " (已回滚到恢复前状态)"
                except Exception as rollback_error:
                    logger.error(f"回滚失败: {str(rollback_error)}")
                    error_message += f" (回滚失败: {str(rollback_error)})"
            
            # 清理临时文件
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            
            return (False, error_message)
    
    def _download_backup(self, backup_job: BackupJob) -> str:
        """
        下载备份文件到临时目录
        Download backup file to temporary directory
        
        从远程存储或本地目录获取备份文件。
        
        Args:
            backup_job: 备份任务对象
            
        Returns:
            str: 下载后的本地文件路径
            
        Raises:
            ValueError: 当备份任务信息不完整时抛出
            RuntimeError: 当下载失败时抛出
        """
        import os
        import shutil
        import tempfile
        from runtime_paths import get_data_subdir
        from services.storage.ftp_adapter import FTPStorageAdapter
        from services.storage.email_adapter import EmailStorageAdapter
        from services.storage.s3_adapter import S3StorageAdapter
        
        # 验证备份任务信息
        if not backup_job.storage_type:
            raise ValueError("备份任务缺少存储类型信息")
        if not backup_job.storage_path:
            raise ValueError("备份任务缺少存储路径信息")
        if not backup_job.filename:
            raise ValueError("备份任务缺少文件名信息")
        
        # 如果是本地存储，直接返回本地路径
        if backup_job.storage_type == 'local':
            local_backup_dir = get_data_subdir('backups')
            local_path = os.path.join(local_backup_dir, backup_job.filename)
            
            if not os.path.exists(local_path):
                raise ValueError(f"本地备份文件不存在: {local_path}")
            
            # 验证文件大小（如果有记录）
            if backup_job.file_size_bytes:
                actual_size = os.path.getsize(local_path)
                if actual_size != backup_job.file_size_bytes:
                    raise RuntimeError(
                        f"本地备份文件大小不匹配: 期望 {backup_job.file_size_bytes} 字节, "
                        f"实际 {actual_size} 字节"
                    )
            
            return local_path
        
        # 获取备份配置（远程存储需要）
        config = BackupConfig.query.first()
        if not config:
            raise ValueError("备份配置不存在")
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix='backup_restore_')
        local_path = os.path.join(temp_dir, backup_job.filename)
        
        try:
            # 根据存储类型创建适配器
            if backup_job.storage_type == 'ftp':
                adapter = FTPStorageAdapter(
                    host=config.ftp_host,
                    port=config.ftp_port,
                    username=config.ftp_username,
                    password=config.ftp_password,
                    base_path=config.ftp_path
                )
            elif backup_job.storage_type == 's3':
                adapter = S3StorageAdapter(
                    endpoint=config.s3_endpoint,
                    bucket=config.s3_bucket,
                    access_key=config.s3_access_key,
                    secret_key=config.s3_secret_key,
                    path_prefix=config.s3_path_prefix,
                    region=config.s3_region
                )
            elif backup_job.storage_type == 'email':
                raise RuntimeError("邮件存储方式不支持下载备份文件，请手动从邮箱下载")
            else:
                raise ValueError(f"不支持的存储类型: {backup_job.storage_type}")
            
            # 下载备份文件
            success, message = adapter.download(backup_job.storage_path, local_path)
            
            if not success:
                raise RuntimeError(f"下载备份文件失败: {message}")
            
            # 验证下载的文件大小（如果有记录）
            if backup_job.file_size_bytes:
                actual_size = os.path.getsize(local_path)
                if actual_size != backup_job.file_size_bytes:
                    raise RuntimeError(
                        f"下载的文件大小不匹配: 期望 {backup_job.file_size_bytes} 字节, "
                        f"实际 {actual_size} 字节"
                    )
            
            return local_path
            
        except Exception as e:
            # 清理临时目录
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
            raise RuntimeError(f"下载备份文件失败: {str(e)}") from e
    
    def _decrypt_archive(self, archive_path: str, password: str) -> str:
        """
        解密备份文件
        Decrypt backup file
        
        使用提供的密码解密备份归档文件。解密格式必须与BackupEngine._encrypt_archive()的加密格式匹配。
        
        加密文件格式：
        - Header (256 bytes):
          - Magic Number (8 bytes): "BKPENC01"
          - Salt (32 bytes): PBKDF2盐值
          - IV (16 bytes): AES初始化向量
          - Iterations (4 bytes): PBKDF2迭代次数
          - Reserved (196 bytes): 保留字段
        - Encrypted Data: AES-256-CBC加密的原始文件内容
        
        Args:
            archive_path: 加密的归档文件路径
            password: 解密密码
            
        Returns:
            str: 解密后的文件路径（移除.enc后缀）
            
        Raises:
            ValueError: 当文件格式无效或密码错误时抛出
            RuntimeError: 当解密失败时抛出
        """
        import os
        import struct
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        
        try:
            # 读取加密文件
            with open(archive_path, 'rb') as f:
                # 读取文件头部（256字节）
                header = f.read(256)
                if len(header) != 256:
                    raise ValueError("加密文件格式无效: 文件头部不完整")
                
                # 解析文件头部
                magic_number, salt, iv, iterations, reserved = struct.unpack(
                    '8s32s16sI196s',
                    header
                )
                
                # 验证魔数
                if magic_number != b'BKPENC01':
                    raise ValueError(
                        f"加密文件格式无效: 魔数不匹配 (期望 BKPENC01, 实际 {magic_number})"
                    )
                
                # 读取加密数据
                ciphertext = f.read()
            
            # 使用PBKDF2从密码派生密钥
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,  # AES-256需要32字节密钥
                salt=salt,
                iterations=iterations,
                backend=default_backend()
            )
            
            try:
                key = kdf.derive(password.encode('utf-8'))
            except Exception as e:
                raise ValueError(f"密钥派生失败: {str(e)}")
            
            # 创建AES-256-CBC解密器
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # 解密数据
            try:
                plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            except Exception as e:
                raise ValueError(f"解密失败，密码可能不正确: {str(e)}")
            
            # 移除PKCS7填充
            try:
                padding_length = plaintext[-1]
                if padding_length < 1 or padding_length > 16:
                    raise ValueError("填充长度无效")
                # 验证填充
                for i in range(padding_length):
                    if plaintext[-(i+1)] != padding_length:
                        raise ValueError("填充格式无效")
                plaintext = plaintext[:-padding_length]
            except (IndexError, ValueError) as e:
                raise ValueError(f"移除填充失败，密码可能不正确: {str(e)}")
            
            # 生成解密后的文件路径（移除.enc后缀）
            if archive_path.endswith('.enc'):
                decrypted_path = archive_path[:-4]
            else:
                decrypted_path = archive_path + '.decrypted'
            
            # 写入解密后的文件
            with open(decrypted_path, 'wb') as f:
                f.write(plaintext)
            
            # 删除加密文件
            os.remove(archive_path)
            
            return decrypted_path
            
        except ValueError:
            # 密码错误或格式错误，直接抛出
            raise
        except Exception as e:
            # 清理可能创建的解密文件
            decrypted_path = archive_path[:-4] if archive_path.endswith('.enc') else archive_path + '.decrypted'
            if os.path.exists(decrypted_path):
                try:
                    os.remove(decrypted_path)
                except:
                    pass
            raise RuntimeError(f"解密备份文件失败: {str(e)}") from e
    
    def _extract_archive(self, archive_path: str, extract_dir: str):
        """
        解压备份归档
        Extract backup archive
        
        将备份归档文件（tar.gz格式）解压到指定目录。
        
        Args:
            archive_path: 归档文件路径
            extract_dir: 解压目标目录
            
        Raises:
            ValueError: 当归档文件格式无效时抛出
            RuntimeError: 当解压失败时抛出
        """
        import os
        import tarfile
        
        try:
            # 验证文件存在
            if not os.path.exists(archive_path):
                raise ValueError(f"归档文件不存在: {archive_path}")
            
            # 创建解压目标目录
            os.makedirs(extract_dir, exist_ok=True)
            
            # 验证是否为有效的tar.gz文件
            if not tarfile.is_tarfile(archive_path):
                raise ValueError(f"文件不是有效的tar归档: {archive_path}")
            
            # 解压归档文件
            with tarfile.open(archive_path, 'r:gz') as tar:
                # 安全检查：防止路径遍历攻击
                for member in tar.getmembers():
                    member_path = os.path.join(extract_dir, member.name)
                    if not os.path.abspath(member_path).startswith(os.path.abspath(extract_dir)):
                        raise ValueError(f"归档包含不安全的路径: {member.name}")
                
                # 解压所有文件
                tar.extractall(path=extract_dir)
            
            # 验证解压结果
            if not os.path.exists(extract_dir) or not os.listdir(extract_dir):
                raise RuntimeError("解压后目录为空")
            
        except tarfile.TarError as e:
            raise RuntimeError(f"解压归档文件失败: {str(e)}") from e
        except ValueError:
            # 格式错误，直接抛出
            raise
        except Exception as e:
            raise RuntimeError(f"解压归档文件失败: {str(e)}") from e
    
    def _create_rollback_point(self, backup_database=True, backup_uploads=True, backup_documents=True) -> str:
        """
        创建回滚点
        Create rollback point
        
        在恢复操作前创建当前数据的备份，以便恢复失败时回滚。
        只备份需要恢复的组件。
        
        Args:
            backup_database: 是否备份数据库
            backup_uploads: 是否备份上传文件
            backup_documents: 是否备份文档文件
        
        Returns:
            str: 回滚点标识符（临时备份路径）
            
        Raises:
            RuntimeError: 当创建回滚点失败时抛出
        """
        import os
        import shutil
        import tempfile
        import time
        
        try:
            # 创建唯一的临时目录作为回滚点
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            rollback_dir = tempfile.mkdtemp(prefix=f'rollback_{timestamp}_')
            
            # 备份数据库文件（如果需要）
            if backup_database:
                db_path = os.path.join('data', 'app.db')
                if os.path.exists(db_path):
                    rollback_db_dir = os.path.join(rollback_dir, 'database')
                    os.makedirs(rollback_db_dir, exist_ok=True)
                    
                    # 处理SQLite文件锁定问题 - 创建副本
                    rollback_db_path = os.path.join(rollback_db_dir, 'app.db')
                    try:
                        shutil.copy2(db_path, rollback_db_path)
                    except PermissionError:
                        # 如果文件被锁定，尝试使用只读方式复制
                        with open(db_path, 'rb') as src:
                            with open(rollback_db_path, 'wb') as dst:
                                shutil.copyfileobj(src, dst)
            
            # 备份上传文件目录（如果需要）
            if backup_uploads:
                uploads_path = os.path.join('data', 'uploads')
                if os.path.exists(uploads_path):
                    rollback_uploads_path = os.path.join(rollback_dir, 'uploads')
                    shutil.copytree(uploads_path, rollback_uploads_path, dirs_exist_ok=True)
            
            # 备份文档文件目录（如果需要）
            if backup_documents:
                docs_path = os.path.join('data', 'jobs')
                if os.path.exists(docs_path):
                    rollback_docs_path = os.path.join(rollback_dir, 'documents')
                    shutil.copytree(docs_path, rollback_docs_path, dirs_exist_ok=True)
            
            return rollback_dir
            
        except Exception as e:
            # 清理可能创建的回滚点目录
            if 'rollback_dir' in locals() and os.path.exists(rollback_dir):
                try:
                    shutil.rmtree(rollback_dir)
                except:
                    pass
            raise RuntimeError(f"创建回滚点失败: {str(e)}") from e
    
    def _restore_database(self, backup_db_path: str):
        """
        恢复数据库
        Restore database
        
        从备份文件恢复数据库。使用 SQLite 的在线备份 API 来避免文件锁定问题。
        
        Args:
            backup_db_path: 备份的数据库文件路径
            
        Raises:
            ValueError: 当备份数据库文件不存在时抛出
            RuntimeError: 当恢复失败时抛出
        """
        import os
        import shutil
        import time
        import sqlite3
        
        try:
            # 验证备份数据库文件存在
            if not os.path.exists(backup_db_path):
                raise ValueError(f"备份数据库文件不存在: {backup_db_path}")
            
            # 目标数据库路径
            target_db_path = os.path.join('data', 'app.db')
            
            # 确保目标目录存在
            os.makedirs(os.path.dirname(target_db_path), exist_ok=True)
            
            # 方法1: 尝试使用 SQLite 在线备份 API（推荐）
            try:
                # 关闭 Flask-SQLAlchemy 的连接
                if self.app:
                    try:
                        db.session.remove()
                        db.engine.dispose()
                    except:
                        pass
                
                # 等待连接关闭
                time.sleep(0.5)
                
                # 使用 SQLite 的备份 API
                # 打开源数据库（备份文件）
                source_conn = sqlite3.connect(backup_db_path)
                
                # 打开目标数据库
                target_conn = sqlite3.connect(target_db_path)
                
                # 执行在线备份
                with source_conn:
                    source_conn.backup(target_conn)
                
                # 关闭连接
                source_conn.close()
                target_conn.close()
                
                # 验证恢复的数据库文件
                if not os.path.exists(target_db_path):
                    raise RuntimeError("数据库文件恢复后不存在")
                
                return
                
            except Exception as e:
                # 如果在线备份失败，尝试方法2
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"SQLite 在线备份失败，尝试文件替换方法: {str(e)}")
            
            # 方法2: 文件替换（备用方案）
            # 关闭所有数据库连接
            if self.app:
                try:
                    db.session.remove()
                    db.engine.dispose()
                except:
                    pass
            
            # 等待连接关闭
            time.sleep(1)
            
            # 处理Windows文件锁定问题 - 多次尝试
            max_retries = 10
            retry_delay = 2  # 秒
            
            for attempt in range(max_retries):
                try:
                    # 删除旧数据库文件
                    if os.path.exists(target_db_path):
                        os.remove(target_db_path)
                    
                    # 复制备份数据库到目标位置
                    shutil.copy2(backup_db_path, target_db_path)
                    
                    # 验证恢复的数据库文件
                    if not os.path.exists(target_db_path):
                        raise RuntimeError("数据库文件恢复后不存在")
                    
                    # 验证文件大小
                    backup_size = os.path.getsize(backup_db_path)
                    restored_size = os.path.getsize(target_db_path)
                    if backup_size != restored_size:
                        raise RuntimeError(
                            f"数据库文件大小不匹配: 备份 {backup_size} 字节, "
                            f"恢复后 {restored_size} 字节"
                        )
                    
                    # 成功，退出重试循环
                    break
                    
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        # 还有重试机会，等待后重试
                        time.sleep(retry_delay)
                        continue
                    else:
                        # 重试次数用尽
                        raise RuntimeError(
                            f"数据库文件被锁定，无法恢复。\n\n"
                            f"解决方案：\n"
                            f"1. 请关闭所有使用数据库的程序\n"
                            f"2. 或者重启应用后再尝试恢复\n"
                            f"3. 如果问题持续，请先恢复其他内容（上传文件、文档文件），然后手动替换数据库文件\n\n"
                            f"错误详情: {str(e)}"
                        ) from e
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise
            
        except ValueError:
            # 参数错误，直接抛出
            raise
        except Exception as e:
            raise RuntimeError(f"恢复数据库失败: {str(e)}") from e
    
    def _restore_uploads(self, backup_uploads_dir: str):
        """
        恢复上传文件
        Restore upload files
        
        从备份恢复上传文件到data/uploads/目录。
        
        Args:
            backup_uploads_dir: 备份的上传文件目录路径
            
        Raises:
            ValueError: 当备份目录不存在时抛出
            RuntimeError: 当恢复失败时抛出
        """
        import os
        import shutil
        
        try:
            # 验证备份目录存在
            if not os.path.exists(backup_uploads_dir):
                raise ValueError(f"备份上传文件目录不存在: {backup_uploads_dir}")
            
            # 目标上传文件目录
            target_uploads_dir = os.path.join('data', 'uploads')
            
            # 清空目标目录（如果存在）
            if os.path.exists(target_uploads_dir):
                # 删除目录中的所有内容
                for item in os.listdir(target_uploads_dir):
                    item_path = os.path.join(target_uploads_dir, item)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.unlink(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                    except Exception as e:
                        # 记录错误但继续处理其他文件
                        print(f"警告: 删除文件失败 {item_path}: {str(e)}")
            else:
                # 创建目标目录
                os.makedirs(target_uploads_dir, exist_ok=True)
            
            # 复制备份文件到目标目录
            for item in os.listdir(backup_uploads_dir):
                src_path = os.path.join(backup_uploads_dir, item)
                dst_path = os.path.join(target_uploads_dir, item)
                
                try:
                    if os.path.isfile(src_path):
                        # 复制文件
                        shutil.copy2(src_path, dst_path)
                    elif os.path.isdir(src_path):
                        # 复制目录
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                except Exception as e:
                    raise RuntimeError(f"复制文件失败 {src_path}: {str(e)}") from e
            
        except ValueError:
            # 参数错误，直接抛出
            raise
        except Exception as e:
            raise RuntimeError(f"恢复上传文件失败: {str(e)}") from e
    
    def _restore_documents(self, backup_docs_dir: str):
        """
        恢复文档文件
        Restore document files
        
        从备份恢复文档文件到data/jobs/目录。
        
        Args:
            backup_docs_dir: 备份的文档文件目录路径
            
        Raises:
            ValueError: 当备份目录不存在时抛出
            RuntimeError: 当恢复失败时抛出
        """
        import os
        import shutil
        
        try:
            # 验证备份目录存在
            if not os.path.exists(backup_docs_dir):
                raise ValueError(f"备份文档文件目录不存在: {backup_docs_dir}")
            
            # 目标文档文件目录
            target_docs_dir = os.path.join('data', 'jobs')
            
            # 清空目标目录（如果存在）
            if os.path.exists(target_docs_dir):
                # 删除目录中的所有内容
                for item in os.listdir(target_docs_dir):
                    item_path = os.path.join(target_docs_dir, item)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.unlink(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                    except Exception as e:
                        # 记录错误但继续处理其他文件
                        print(f"警告: 删除文件失败 {item_path}: {str(e)}")
            else:
                # 创建目标目录
                os.makedirs(target_docs_dir, exist_ok=True)
            
            # 复制备份文件到目标目录
            for item in os.listdir(backup_docs_dir):
                src_path = os.path.join(backup_docs_dir, item)
                dst_path = os.path.join(target_docs_dir, item)
                
                try:
                    if os.path.isfile(src_path):
                        # 复制文件
                        shutil.copy2(src_path, dst_path)
                    elif os.path.isdir(src_path):
                        # 复制目录
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                except Exception as e:
                    raise RuntimeError(f"复制文件失败 {src_path}: {str(e)}") from e
            
        except ValueError:
            # 参数错误，直接抛出
            raise
        except Exception as e:
            raise RuntimeError(f"恢复文档文件失败: {str(e)}") from e
    
    def _rollback(self, rollback_point: str):
        """
        回滚到恢复前状态
        Rollback to pre-restore state
        
        当恢复操作失败时，回滚到恢复前的状态。
        
        Args:
            rollback_point: 回滚点标识符（临时备份目录路径）
            
        Raises:
            ValueError: 当回滚点不存在时抛出
            RuntimeError: 当回滚失败时抛出
        """
        import os
        import shutil
        
        try:
            # 验证回滚点存在
            if not os.path.exists(rollback_point):
                raise ValueError(f"回滚点不存在: {rollback_point}")
            
            # 回滚数据库
            rollback_db_path = os.path.join(rollback_point, 'database', 'app.db')
            if os.path.exists(rollback_db_path):
                try:
                    self._restore_database(rollback_db_path)
                except Exception as e:
                    # 数据库回滚失败，记录错误但继续尝试回滚其他内容
                    print(f"警告: 数据库回滚失败: {str(e)}")
            
            # 回滚上传文件
            rollback_uploads_dir = os.path.join(rollback_point, 'uploads')
            if os.path.exists(rollback_uploads_dir):
                try:
                    self._restore_uploads(rollback_uploads_dir)
                except Exception as e:
                    print(f"警告: 上传文件回滚失败: {str(e)}")
            
            # 回滚文档文件
            rollback_docs_dir = os.path.join(rollback_point, 'documents')
            if os.path.exists(rollback_docs_dir):
                try:
                    self._restore_documents(rollback_docs_dir)
                except Exception as e:
                    print(f"警告: 文档文件回滚失败: {str(e)}")
            
            # 清理回滚点
            try:
                shutil.rmtree(rollback_point)
            except Exception as e:
                # 清理失败不影响回滚结果
                print(f"警告: 清理回滚点失败: {str(e)}")
            
        except ValueError:
            # 参数错误，直接抛出
            raise
        except Exception as e:
            raise RuntimeError(f"回滚失败: {str(e)}") from e

    def scan_remote_backups(self) -> Tuple[int, int, str]:
        """
        扫描远程存储中的备份文件
        Scan remote storage for backup files
        
        从配置的远程存储（FTP/S3）中扫描所有备份文件，
        并为数据库中不存在的备份文件创建记录。
        
        Returns:
            Tuple[int, int, str]: (发现的文件数, 新增的记录数, 消息)
        """
        import os
        import re
        from datetime import datetime
        from models import BackupConfig
        from services.storage.ftp_adapter import FTPStorageAdapter
        from services.storage.s3_adapter import S3StorageAdapter
        
        try:
            # 获取备份配置
            config = BackupConfig.query.first()
            if not config:
                return (0, 0, "备份配置不存在")
            
            # 解析存储类型（支持JSON数组格式的多目标备份）
            import json
            storage_types = []
            if config.storage_type:
                try:
                    storage_types = json.loads(config.storage_type)
                    if not isinstance(storage_types, list):
                        storage_types = [config.storage_type]
                except (json.JSONDecodeError, TypeError):
                    storage_types = [config.storage_type]
            
            # 检查是否有支持扫描的存储类型
            scannable_types = [st for st in storage_types if st in ('ftp', 's3')]
            
            if not scannable_types:
                return (0, 0, f"当前配置的存储类型不支持扫描功能（仅支持 FTP 和 S3）")
            
            # 扫描所有支持的存储类型
            total_found = 0
            total_new = 0
            messages = []
            
            for storage_type in scannable_types:
                # 创建存储适配器
                adapter = None
                if storage_type == 'ftp':
                    adapter = FTPStorageAdapter(
                        host=config.ftp_host,
                        port=config.ftp_port,
                        username=config.ftp_username,
                        password=config.ftp_password,
                        base_path=config.ftp_path
                    )
                elif storage_type == 's3':
                    try:
                        adapter = S3StorageAdapter(
                            endpoint=config.s3_endpoint,
                            bucket=config.s3_bucket,
                            access_key=config.s3_access_key,
                            secret_key=config.s3_secret_key,
                            path_prefix=config.s3_path_prefix or 'backups/',
                            region=config.s3_region
                        )
                    except Exception as e:
                        messages.append(f"S3: 创建适配器失败 - {str(e)}")
                        continue
                
                # 列出远程文件
                try:
                    remote_files = adapter.list_files()
                except Exception as e:
                    messages.append(f"{storage_type.upper()}: 列出文件失败 - {str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
                
                if not remote_files:
                    messages.append(f"{storage_type.upper()}: 没有找到备份文件（路径前缀: {config.s3_path_prefix if storage_type == 's3' else config.ftp_path}）")
                    continue
                
                # 过滤备份文件（.tar.gz 或 .tar.gz.enc）
                backup_files = [
                    f for f in remote_files 
                    if f['name'].endswith('.tar.gz') or f['name'].endswith('.tar.gz.enc')
                ]
                
                if not backup_files:
                    messages.append(f"{storage_type.upper()}: 找到 {len(remote_files)} 个文件，但没有备份文件")
                    continue
                
                # 获取数据库中已存在的备份记录
                existing_backups = BackupJob.query.filter_by(
                    storage_type=storage_type
                ).all()
                existing_filenames = {b.filename for b in existing_backups if b.filename}
                
                # 为不存在的备份文件创建记录
                new_count = 0
                for file_info in backup_files:
                    filename = file_info['name']
                    
                    # 跳过已存在的记录
                    if filename in existing_filenames:
                        continue
                    
                    # 创建新的备份记录
                    backup_job = BackupJob()
                    backup_job.filename = filename
                    backup_job.storage_type = storage_type
                    backup_job.storage_path = file_info['path']
                    backup_job.file_size_bytes = file_info.get('size', 0)
                    backup_job.is_encrypted = filename.endswith('.enc')
                    backup_job.status = 'success'
                    backup_job.backup_mode = 'full'
                    backup_job.trigger_type = 'manual'
                    
                    # 尝试从文件名解析时间戳
                    match = re.search(r'(\d{8}_\d{6})', filename)
                    if match:
                        try:
                            timestamp = datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')
                            backup_job.started_at = timestamp
                            backup_job.completed_at = timestamp
                        except:
                            backup_job.started_at = datetime.now()
                            backup_job.completed_at = datetime.now()
                    else:
                        backup_job.started_at = datetime.now()
                        backup_job.completed_at = datetime.now()
                    
                    db.session.add(backup_job)
                    new_count += 1
                
                total_found += len(backup_files)
                total_new += new_count
                messages.append(f"{storage_type.upper()}: 发现 {len(backup_files)} 个备份文件，新增 {new_count} 条记录")
            
            # 提交到数据库
            db.session.commit()
            
            if total_found == 0:
                return (0, 0, "所有远程存储中都没有找到备份文件")
            
            return (
                total_found,
                total_new,
                "扫描完成：\n" + "\n".join(messages)
            )
            
        except Exception as e:
            db.session.rollback()
            return (0, 0, f"扫描失败: {str(e)}")
