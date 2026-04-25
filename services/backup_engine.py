# -*- coding: utf-8 -*-
"""
备份执行引擎服务
Backup Execution Engine Service
"""

from datetime import datetime
from typing import Optional
from models import db, BackupJob, BackupConfig
from services.backup_config import BackupConfigManager


class BackupEngine:
    """备份执行引擎"""
    
    def __init__(self, app=None):
        """
        初始化备份引擎
        Initialize backup engine
        
        Args:
            app: Flask应用实例
        """
        self.app = app
    
    def execute_backup(self, trigger_type: str = 'auto') -> BackupJob:
        """
        执行备份任务
        Execute backup task
        
        这是备份执行的主方法，负责协调整个备份流程：
        1. 创建备份任务记录
        2. 收集备份内容（待实现）
        3. 创建备份归档（待实现）
        4. 上传到远程存储（待实现）
        5. 清理旧备份（待实现）
        6. 更新任务状态
        
        Args:
            trigger_type: 触发类型，'auto'（自动）或 'manual'（手动）
            
        Returns:
            BackupJob: 备份任务记录对象
            
        Raises:
            ValueError: 当配置无效或触发类型无效时抛出
            RuntimeError: 当备份执行过程中发生错误时抛出
        """
        # 验证触发类型
        if trigger_type not in ['auto', 'manual']:
            raise ValueError(f"无效的触发类型: {trigger_type}，必须是 'auto' 或 'manual'")
        
        # 获取备份配置
        config = BackupConfigManager.get_config()
        if config is None:
            raise ValueError("备份配置不存在，请先配置备份参数")
        
        # 验证配置有效性
        is_valid, error_msg = BackupConfigManager.validate_config(config)
        if not is_valid:
            raise ValueError(f"备份配置无效: {error_msg}")
        
        # 创建备份任务记录
        backup_job = self._create_backup_job(trigger_type, config)
        
        try:
            # Task 5.2 - 收集备份内容
            base_backup_id = backup_job.base_backup_id if config.backup_mode == 'incremental' else None
            files = self._collect_files(config.backup_mode, base_backup_id)
            
            # Task 5.3 - 创建备份归档
            import tempfile
            output_dir = tempfile.gettempdir()
            archive_path, file_size, file_hash = self._create_archive(files, output_dir)
            
            # 更新备份任务的文件信息
            import os
            backup_job.filename = os.path.basename(archive_path)
            backup_job.file_size_bytes = file_size
            backup_job.file_hash = file_hash
            
            # 更新备份内容统计
            db_files = [f for f in files if f['file_type'] == 'database']
            upload_files = [f for f in files if f['file_type'] == 'upload']
            doc_files = [f for f in files if f['file_type'] == 'document']
            
            backup_job.db_size_bytes = sum(f['size'] for f in db_files)
            backup_job.uploads_count = len(upload_files)
            backup_job.uploads_size_bytes = sum(f['size'] for f in upload_files)
            backup_job.docs_count = len(doc_files)
            backup_job.docs_size_bytes = sum(f['size'] for f in doc_files)
            
            # Task 5.4 - 实现备份文件加密（如果启用）
            if config.encryption_enabled:
                if not config.encryption_key_hash:
                    raise ValueError("加密已启用但未配置加密密码")
                
                # 获取加密密码
                encryption_password = getattr(config, '_test_encryption_password', None)
                
                if not encryption_password:
                    # 从数据库解密密码
                    try:
                        from cryptography.fernet import Fernet
                        import base64
                        import hashlib
                        
                        # 从Flask secret_key派生加密密钥
                        key_material = hashlib.sha256(self.app.secret_key.encode()).digest()
                        fernet_key = base64.urlsafe_b64encode(key_material)
                        fernet = Fernet(fernet_key)
                        
                        # 解密密码
                        encryption_password = fernet.decrypt(config.encryption_key_hash.encode()).decode('utf-8')
                    except Exception as e:
                        raise ValueError(f"无法解密加密密码: {str(e)}")
                
                archive_path = self._encrypt_archive(archive_path, encryption_password)
                # 更新文件信息
                backup_job.filename = os.path.basename(archive_path)
                backup_job.file_size_bytes = os.path.getsize(archive_path)
                backup_job.file_hash = self._calculate_file_hash(archive_path)
                backup_job.is_encrypted = True
            
            # Task 5.5 - 实现备份上传
            success, storage_path_or_error = self._upload_backup(archive_path, config)
            
            if success:
                # 上传成功，更新存储路径
                backup_job.storage_path = storage_path_or_error
                
                # 删除本地临时文件
                if os.path.exists(archive_path):
                    try:
                        os.remove(archive_path)
                    except Exception as e:
                        print(f"警告: 无法删除临时归档文件 {archive_path}: {str(e)}")
                
                # Task 5.5 - 清理旧备份
                self._cleanup_old_backups(config)
            else:
                # 上传失败，保留本地文件
                print(f"备份上传失败: {storage_path_or_error}")
                print(f"本地备份文件已保留: {archive_path}")
                raise RuntimeError(f"备份上传失败: {storage_path_or_error}")
            
            # Task 5.6 - 更新文件追踪记录（用于增量备份）
            self._update_file_tracker(files, backup_job.id)
            
            # 标记为成功
            self._update_backup_job_success(backup_job, config)
            
        except Exception as e:
            # 备份失败，更新任务状态
            self._update_backup_job_failure(backup_job, str(e))
            raise RuntimeError(f"备份执行失败: {str(e)}") from e
        
        return backup_job
    
    def _create_backup_job(self, trigger_type: str, config: BackupConfig) -> BackupJob:
        """
        创建备份任务记录
        Create backup job record
        
        Args:
            trigger_type: 触发类型（auto/manual）
            config: 备份配置对象
            
        Returns:
            BackupJob: 创建的备份任务对象
        """
        backup_job = BackupJob(
            trigger_type=trigger_type,
            status='running',
            backup_mode=config.backup_mode,
            storage_type=config.storage_type,
            is_encrypted=config.encryption_enabled,
            started_at=datetime.utcnow()
        )
        
        # 如果是增量备份，查找最近的完整备份作为基准
        if config.backup_mode == 'incremental':
            base_backup = BackupJob.query.filter_by(
                backup_mode='full',
                status='success'
            ).order_by(BackupJob.completed_at.desc()).first()
            
            if base_backup:
                backup_job.base_backup_id = base_backup.id
        
        db.session.add(backup_job)
        db.session.commit()
        
        return backup_job
    
    def _update_backup_job_success(self, backup_job: BackupJob, config: BackupConfig):
        """
        更新备份任务为成功状态
        Update backup job to success status
        
        Args:
            backup_job: 备份任务对象
            config: 备份配置对象
        """
        backup_job.status = 'success'
        backup_job.completed_at = datetime.utcnow()
        
        # 计算执行时长（秒）
        if backup_job.started_at and backup_job.completed_at:
            duration = backup_job.completed_at - backup_job.started_at
            backup_job.duration_seconds = int(duration.total_seconds())
        
        # TODO: 在后续任务中，这里会填充实际的备份文件信息
        # backup_job.filename = filename
        # backup_job.file_size_bytes = file_size
        # backup_job.file_hash = file_hash
        # backup_job.storage_path = storage_path
        # backup_job.db_size_bytes = db_size
        # backup_job.uploads_count = uploads_count
        # backup_job.uploads_size_bytes = uploads_size
        # backup_job.docs_count = docs_count
        # backup_job.docs_size_bytes = docs_size
        
        db.session.commit()
        
        # 发送成功通知
        try:
            from services.backup_notification import NotificationService
            NotificationService.send_backup_success_notification(backup_job, config)
        except Exception as e:
            print(f"[BackupEngine] 发送成功通知失败: {str(e)}")
    
    def _update_backup_job_failure(self, backup_job: BackupJob, error_message: str):
        """
        更新备份任务为失败状态
        Update backup job to failed status
        
        Args:
            backup_job: 备份任务对象
            error_message: 错误信息
        """
        backup_job.status = 'failed'
        backup_job.completed_at = datetime.utcnow()
        backup_job.error_message = error_message
        
        # 计算执行时长（秒）
        if backup_job.started_at and backup_job.completed_at:
            duration = backup_job.completed_at - backup_job.started_at
            backup_job.duration_seconds = int(duration.total_seconds())
        
        db.session.commit()
        
        # 发送失败通知
        try:
            from services.backup_notification import NotificationService
            from services.backup_config import BackupConfigManager
            config = BackupConfigManager.get_config()
            if config:
                NotificationService.send_backup_failure_notification(backup_job, config)
        except Exception as e:
            print(f"[BackupEngine] 发送失败通知失败: {str(e)}")
    
    # 以下方法将在后续任务中实现
    
    def _collect_files(self, backup_mode: str, base_backup_id: Optional[int] = None) -> list:
        """
        收集需要备份的文件
        Collect files to backup
        
        Args:
            backup_mode: 备份模式（full/incremental）
            base_backup_id: 基准备份ID（增量备份时使用）
            
        Returns:
            list: 需要备份的文件列表，每个元素为字典：
                {
                    'source_path': str,  # 源文件绝对路径
                    'archive_path': str,  # 归档中的相对路径
                    'file_type': str,    # 文件类型：database, upload, document
                    'size': int,         # 文件大小（字节）
                    'hash': str,         # SHA256哈希值
                    'modified': datetime # 修改时间
                }
        """
        import os
        import hashlib
        import shutil
        import sqlite3
        import tempfile
        from datetime import datetime
        from runtime_paths import get_data_dir, get_default_database_path
        from models import BackupFileTracker
        
        collected_files = []
        data_dir = get_data_dir()
        
        # 1. 收集数据库文件
        db_path = get_default_database_path()
        if os.path.exists(db_path):
            db_file_info = self._collect_database_file(db_path, backup_mode, base_backup_id)
            if db_file_info:
                collected_files.append(db_file_info)
        
        # 2. 收集上传文件（data/uploads/目录）
        uploads_dir = os.path.join(data_dir, 'uploads')
        if os.path.exists(uploads_dir):
            upload_files = self._collect_directory_files(
                uploads_dir, 
                'upload', 
                backup_mode, 
                base_backup_id,
                file_pattern=None  # 收集所有文件
            )
            collected_files.extend(upload_files)
        
        # 3. 收集文档文件（data/jobs/目录下的.md文件）
        jobs_dir = os.path.join(data_dir, 'jobs')
        if os.path.exists(jobs_dir):
            doc_files = self._collect_directory_files(
                jobs_dir, 
                'document', 
                backup_mode, 
                base_backup_id,
                file_pattern='.md'  # 仅收集.md文件
            )
            collected_files.extend(doc_files)
        
        return collected_files
    
    def _collect_database_file(self, db_path: str, backup_mode: str, base_backup_id: Optional[int]) -> Optional[dict]:
        """
        收集数据库文件（处理文件锁定情况）
        Collect database file (handle file locking)
        
        Args:
            db_path: 数据库文件路径
            backup_mode: 备份模式
            base_backup_id: 基准备份ID
            
        Returns:
            dict: 文件信息字典，如果文件未变更则返回None
        """
        import os
        import hashlib
        import shutil
        import sqlite3
        import tempfile
        from datetime import datetime
        from models import BackupFileTracker
        
        # 获取文件修改时间
        modified_time = datetime.fromtimestamp(os.path.getmtime(db_path))
        
        # 增量备份：检查文件是否需要备份
        if backup_mode == 'incremental':
            tracker = BackupFileTracker.query.filter_by(
                file_path=db_path,
                file_type='database'
            ).first()
            
            if tracker and tracker.last_modified >= modified_time:
                # 文件未修改，跳过
                return None
        
        # 创建临时副本以避免文件锁定问题
        # 使用 VACUUM INTO 或直接复制
        temp_db_path = None
        try:
            # 尝试使用 VACUUM INTO（SQLite 3.27.0+）
            temp_fd, temp_db_path = tempfile.mkstemp(suffix='.db')
            os.close(temp_fd)
            
            try:
                conn = sqlite3.connect(db_path)
                conn.execute(f"VACUUM INTO '{temp_db_path}'")
                conn.close()
            except sqlite3.OperationalError:
                # VACUUM INTO 不支持，使用直接复制并重试
                conn.close()
                os.remove(temp_db_path)
                temp_db_path = None
                
                # 重试直接复制
                for attempt in range(3):
                    try:
                        temp_fd, temp_db_path = tempfile.mkstemp(suffix='.db')
                        os.close(temp_fd)
                        shutil.copy2(db_path, temp_db_path)
                        break
                    except (IOError, OSError) as e:
                        if temp_db_path and os.path.exists(temp_db_path):
                            os.remove(temp_db_path)
                            temp_db_path = None
                        if attempt == 2:
                            raise RuntimeError(f"无法复制数据库文件: {str(e)}")
                        import time
                        time.sleep(1)
            
            # 计算文件哈希
            file_hash = self._calculate_file_hash(temp_db_path)
            file_size = os.path.getsize(temp_db_path)
            
            # 增量备份：检查哈希是否变更
            if backup_mode == 'incremental':
                tracker = BackupFileTracker.query.filter_by(
                    file_path=db_path,
                    file_type='database'
                ).first()
                
                if tracker and tracker.file_hash == file_hash:
                    # 文件内容未变更，跳过
                    if temp_db_path and os.path.exists(temp_db_path):
                        os.remove(temp_db_path)
                    return None
            
            return {
                'source_path': temp_db_path,  # 使用临时副本
                'archive_path': 'database/app.db',
                'file_type': 'database',
                'size': file_size,
                'hash': file_hash,
                'modified': modified_time,
                'original_path': db_path,  # 保存原始路径用于追踪
                'is_temp': True  # 标记为临时文件，需要清理
            }
            
        except Exception as e:
            # 清理临时文件
            if temp_db_path and os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except:
                    pass
            raise RuntimeError(f"收集数据库文件失败: {str(e)}")
    
    def _collect_directory_files(self, directory: str, file_type: str, backup_mode: str, 
                                 base_backup_id: Optional[int], file_pattern: Optional[str] = None) -> list:
        """
        递归收集目录中的文件
        Recursively collect files from directory
        
        Args:
            directory: 目录路径
            file_type: 文件类型（upload/document）
            backup_mode: 备份模式
            base_backup_id: 基准备份ID
            file_pattern: 文件模式（如'.md'），None表示所有文件
            
        Returns:
            list: 文件信息字典列表
        """
        import os
        from datetime import datetime
        from models import BackupFileTracker
        
        collected_files = []
        
        for root, dirs, files in os.walk(directory):
            for filename in files:
                # 检查文件模式
                if file_pattern and not filename.endswith(file_pattern):
                    continue
                
                file_path = os.path.join(root, filename)
                
                # 获取文件信息
                try:
                    file_stat = os.stat(file_path)
                    modified_time = datetime.fromtimestamp(file_stat.st_mtime)
                    file_size = file_stat.st_size
                    
                    # 增量备份：检查文件是否需要备份
                    if backup_mode == 'incremental':
                        tracker = BackupFileTracker.query.filter_by(
                            file_path=file_path,
                            file_type=file_type
                        ).first()
                        
                        if tracker:
                            # 检查修改时间
                            if tracker.last_modified >= modified_time:
                                # 文件未修改，跳过
                                continue
                            
                            # 检查文件大小（快速检查）
                            if tracker.file_size_bytes == file_size:
                                # 计算哈希进行精确比较
                                file_hash = self._calculate_file_hash(file_path)
                                if tracker.file_hash == file_hash:
                                    # 文件内容未变更，跳过
                                    continue
                            else:
                                # 文件大小变化，需要备份
                                file_hash = self._calculate_file_hash(file_path)
                        else:
                            # 新文件，需要备份
                            file_hash = self._calculate_file_hash(file_path)
                    else:
                        # 完整备份：计算哈希
                        file_hash = self._calculate_file_hash(file_path)
                    
                    # 计算归档中的相对路径
                    rel_path = os.path.relpath(file_path, directory)
                    if file_type == 'upload':
                        archive_path = f'uploads/{rel_path}'
                    else:  # document
                        archive_path = f'documents/{rel_path}'
                    
                    # 规范化路径分隔符为正斜杠
                    archive_path = archive_path.replace('\\', '/')
                    
                    collected_files.append({
                        'source_path': file_path,
                        'archive_path': archive_path,
                        'file_type': file_type,
                        'size': file_size,
                        'hash': file_hash,
                        'modified': modified_time,
                        'original_path': file_path,
                        'is_temp': False
                    })
                    
                except (OSError, IOError) as e:
                    # 记录错误但继续处理其他文件
                    print(f"警告: 无法访问文件 {file_path}: {str(e)}")
                    continue
        
        return collected_files
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        计算文件的SHA256哈希值
        Calculate SHA256 hash of file
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: SHA256哈希值（十六进制字符串）
        """
        import hashlib
        
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # 分块读取以处理大文件
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _create_archive(self, files: list, output_path: str) -> tuple:
        """
        创建备份归档文件
        Create backup archive file
        
        Args:
            files: 文件列表，每个元素为字典：
                {
                    'source_path': str,  # 源文件绝对路径
                    'archive_path': str,  # 归档中的相对路径
                    'file_type': str,    # 文件类型：database, upload, document
                    'size': int,         # 文件大小（字节）
                    'hash': str,         # SHA256哈希值
                    'modified': datetime,# 修改时间
                    'is_temp': bool      # 是否为临时文件
                }
            output_path: 输出目录路径
            
        Returns:
            tuple: (归档文件路径, 文件大小, SHA256哈希值)
            
        Raises:
            RuntimeError: 当归档创建失败时抛出
        """
        import os
        import tarfile
        import json
        import tempfile
        from datetime import datetime
        
        try:
            # 生成带时间戳的归档文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_filename = f'backup_{timestamp}.tar.gz'
            archive_path = os.path.join(output_path, archive_filename)
            
            # 确保输出目录存在
            os.makedirs(output_path, exist_ok=True)
            
            # 创建备份元数据
            metadata = self._generate_backup_metadata(files)
            
            # 创建临时元数据文件
            metadata_fd, metadata_path = tempfile.mkstemp(suffix='.json', text=True)
            try:
                with os.fdopen(metadata_fd, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
                
                # 创建tar.gz归档
                with tarfile.open(archive_path, 'w:gz') as tar:
                    # 添加元数据文件
                    tar.add(metadata_path, arcname='metadata.json')
                    
                    # 添加所有收集的文件
                    for file_info in files:
                        source_path = file_info['source_path']
                        archive_name = file_info['archive_path']
                        
                        # 检查文件是否存在
                        if not os.path.exists(source_path):
                            raise FileNotFoundError(f"源文件不存在: {source_path}")
                        
                        tar.add(source_path, arcname=archive_name)
                
            finally:
                # 清理临时元数据文件
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
            
            # 清理临时文件（标记为is_temp的文件）
            for file_info in files:
                if file_info.get('is_temp', False):
                    temp_path = file_info['source_path']
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception as e:
                            # 记录警告但不中断流程
                            print(f"警告: 无法删除临时文件 {temp_path}: {str(e)}")
            
            # 计算归档文件大小和哈希值
            archive_size = os.path.getsize(archive_path)
            archive_hash = self._calculate_file_hash(archive_path)
            
            return (archive_path, archive_size, archive_hash)
            
        except Exception as e:
            # 清理可能创建的归档文件
            if 'archive_path' in locals() and os.path.exists(archive_path):
                try:
                    os.remove(archive_path)
                except:
                    pass
            raise RuntimeError(f"创建备份归档失败: {str(e)}") from e
    
    def _generate_backup_metadata(self, files: list) -> dict:
        """
        生成备份元数据
        Generate backup metadata
        
        Args:
            files: 文件列表
            
        Returns:
            dict: 备份元数据字典
        """
        from datetime import datetime
        
        # 统计各类文件
        db_files = [f for f in files if f['file_type'] == 'database']
        upload_files = [f for f in files if f['file_type'] == 'upload']
        doc_files = [f for f in files if f['file_type'] == 'document']
        
        # 计算统计信息
        db_size = sum(f['size'] for f in db_files)
        uploads_size = sum(f['size'] for f in upload_files)
        docs_size = sum(f['size'] for f in doc_files)
        total_size = db_size + uploads_size + docs_size
        
        # 构建元数据
        metadata = {
            'version': '1.0',
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'files': {
                'database': None,
                'uploads': [],
                'documents': []
            },
            'statistics': {
                'total_files': len(files),
                'total_size_bytes': total_size,
                'db_size_bytes': db_size,
                'uploads_count': len(upload_files),
                'uploads_size_bytes': uploads_size,
                'docs_count': len(doc_files),
                'docs_size_bytes': docs_size
            }
        }
        
        # 添加数据库文件信息
        if db_files:
            db_file = db_files[0]
            metadata['files']['database'] = {
                'path': db_file['archive_path'],
                'size_bytes': db_file['size'],
                'hash': db_file['hash']
            }
        
        # 添加上传文件信息
        for upload_file in upload_files:
            metadata['files']['uploads'].append({
                'path': upload_file['archive_path'],
                'size_bytes': upload_file['size'],
                'hash': upload_file['hash']
            })
        
        # 添加文档文件信息
        for doc_file in doc_files:
            metadata['files']['documents'].append({
                'path': doc_file['archive_path'],
                'size_bytes': doc_file['size'],
                'hash': doc_file['hash']
            })
        
        return metadata
    
    def _encrypt_archive(self, archive_path: str, password: str) -> str:
        """
        加密备份归档文件
        Encrypt backup archive file
        
        使用AES-256-CBC加密算法加密备份文件。
        加密文件格式：
        - Header (256 bytes):
          - Magic Number (8 bytes): "BKPENC01"
          - Salt (32 bytes): PBKDF2盐值
          - IV (16 bytes): AES初始化向量
          - Iterations (4 bytes): PBKDF2迭代次数
          - Reserved (196 bytes): 保留字段
        - Encrypted Data: AES-256-CBC加密的原始文件内容
        
        Args:
            archive_path: 归档文件路径
            password: 加密密码
            
        Returns:
            str: 加密后的文件路径（原文件路径 + .enc）
            
        Raises:
            RuntimeError: 当加密失败时抛出
        """
        import os
        import struct
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        
        try:
            # 生成加密参数
            salt = os.urandom(32)  # 32字节盐值
            iv = os.urandom(16)    # 16字节IV
            iterations = 100000    # PBKDF2迭代次数
            
            # 使用PBKDF2从密码派生密钥
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,  # AES-256需要32字节密钥
                salt=salt,
                iterations=iterations,
                backend=default_backend()
            )
            key = kdf.derive(password.encode('utf-8'))
            
            # 创建AES-256-CBC加密器
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # 读取原始文件
            with open(archive_path, 'rb') as f:
                plaintext = f.read()
            
            # PKCS7填充
            block_size = 16  # AES块大小
            padding_length = block_size - (len(plaintext) % block_size)
            plaintext += bytes([padding_length] * padding_length)
            
            # 加密数据
            ciphertext = encryptor.update(plaintext) + encryptor.finalize()
            
            # 构建加密文件头部
            magic_number = b'BKPENC01'  # 8字节魔数
            header = struct.pack(
                '8s32s16sI196s',
                magic_number,
                salt,
                iv,
                iterations,
                b'\x00' * 196  # 保留字段
            )
            
            # 写入加密文件
            encrypted_path = archive_path + '.enc'
            with open(encrypted_path, 'wb') as f:
                f.write(header)
                f.write(ciphertext)
            
            # 删除原始未加密文件
            os.remove(archive_path)
            
            return encrypted_path
            
        except Exception as e:
            # 清理可能创建的加密文件
            encrypted_path = archive_path + '.enc'
            if os.path.exists(encrypted_path):
                try:
                    os.remove(encrypted_path)
                except:
                    pass
            raise RuntimeError(f"加密备份文件失败: {str(e)}") from e
    
    def _upload_backup(self, archive_path: str, config: BackupConfig) -> tuple:
        """
        上传备份文件到远程存储（支持多目标）
        Upload backup file to remote storage (supports multiple targets)
        
        Args:
            archive_path: 归档文件路径
            config: 备份配置对象
            
        Returns:
            tuple: (是否成功, 存储路径列表或错误信息)
        """
        import os
        import json
        from services.storage.ftp_adapter import FTPStorageAdapter
        from services.storage.email_adapter import EmailStorageAdapter
        from services.storage.s3_adapter import S3StorageAdapter
        
        try:
            # 获取文件名
            filename = os.path.basename(archive_path)
            
            # 解析存储类型（支持JSON数组）
            try:
                storage_types = json.loads(config.storage_type)
                if not isinstance(storage_types, list):
                    storage_types = [config.storage_type]
            except (json.JSONDecodeError, TypeError):
                # 兼容旧的单一存储类型
                storage_types = [config.storage_type]
            
            # 存储上传结果
            upload_results = []
            all_success = True
            error_messages = []
            
            # 循环上传到所有选中的存储目标
            for storage_type in storage_types:
                adapter = None
                
                if storage_type == 'ftp':
                    # FTP存储适配器
                    adapter = FTPStorageAdapter(
                        host=config.ftp_host,
                        port=config.ftp_port,
                        username=config.ftp_username,
                        password=config.ftp_password,
                        base_path=config.ftp_path
                    )
                elif storage_type == 'email':
                    # 邮件存储适配器
                    adapter = EmailStorageAdapter(
                        recipient=config.email_recipient
                    )
                elif storage_type == 's3':
                    # S3存储适配器
                    adapter = S3StorageAdapter(
                        endpoint=config.s3_endpoint,
                        bucket=config.s3_bucket,
                        access_key=config.s3_access_key,
                        secret_key=config.s3_secret_key,
                        path_prefix=config.s3_path_prefix,
                        region=config.s3_region
                    )
                else:
                    error_messages.append(f"不支持的存储类型: {storage_type}")
                    all_success = False
                    continue
                
                # 上传文件
                success, message = adapter.upload(archive_path, filename)
                
                if success:
                    upload_results.append({
                        'storage_type': storage_type,
                        'success': True,
                        'path': message
                    })
                else:
                    upload_results.append({
                        'storage_type': storage_type,
                        'success': False,
                        'error': message
                    })
                    error_messages.append(f"{storage_type}: {message}")
                    all_success = False
            
            # 返回结果
            if all_success:
                # 所有上传都成功，返回第一个存储路径（兼容旧逻辑）
                return True, upload_results[0]['path'] if upload_results else ''
            elif upload_results and any(r['success'] for r in upload_results):
                # 部分成功
                success_count = sum(1 for r in upload_results if r['success'])
                total_count = len(upload_results)
                return True, f"部分成功 ({success_count}/{total_count}): " + "; ".join(error_messages)
            else:
                # 全部失败
                return False, "上传失败: " + "; ".join(error_messages)
                
        except Exception as e:
            return False, f"上传备份文件失败: {str(e)}"
    
    def _cleanup_old_backups(self, config: BackupConfig):
        """
        清理旧备份文件（支持多存储类型）
        Clean up old backup files (supports multiple storage types)
        
        根据保留策略删除旧的备份文件：
        1. 查询所有存储类型的成功备份任务
        2. 保留最近的 retention_count 个备份
        3. 删除超出保留数量的旧备份（从远程存储和数据库）
        
        Args:
            config: 备份配置对象
        """
        import json
        from services.storage.ftp_adapter import FTPStorageAdapter
        from services.storage.email_adapter import EmailStorageAdapter
        from services.storage.s3_adapter import S3StorageAdapter
        
        try:
            # 解析存储类型
            try:
                storage_types = json.loads(config.storage_type)
                if not isinstance(storage_types, list):
                    storage_types = [config.storage_type]
            except (json.JSONDecodeError, TypeError):
                storage_types = [config.storage_type]
            
            # 对每个存储类型分别清理
            for storage_type in storage_types:
                # 查询该存储类型的成功备份任务，按完成时间降序排列
                successful_backups = BackupJob.query.filter_by(
                    storage_type=storage_type,
                    status='success'
                ).order_by(BackupJob.completed_at.desc()).all()
                
                # 如果备份数量未超过保留数量，无需清理
                if len(successful_backups) <= config.retention_count:
                    continue
                
                # 获取需要删除的旧备份（保留最近的 retention_count 个）
                old_backups = successful_backups[config.retention_count:]
                
                # 邮件存储不支持删除，跳过清理
                if storage_type == 'email':
                    # 仅从数据库中删除记录（邮件需要用户手动管理）
                    for backup_job in old_backups:
                        print(f"删除旧备份记录: {backup_job.filename} (ID: {backup_job.id})")
                        db.session.delete(backup_job)
                    db.session.commit()
                    continue
                
                # 实例化存储适配器
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
                    adapter = S3StorageAdapter(
                        endpoint=config.s3_endpoint,
                        bucket=config.s3_bucket,
                        access_key=config.s3_access_key,
                        secret_key=config.s3_secret_key,
                        path_prefix=config.s3_path_prefix,
                        region=config.s3_region
                    )
                
                # 删除旧备份文件
                for backup_job in old_backups:
                    if backup_job.filename:
                        # 从远程存储删除
                        success, message = adapter.delete(backup_job.filename)
                        
                        if success:
                            print(f"已删除旧备份文件: {backup_job.filename}")
                        else:
                            print(f"警告: 删除旧备份文件失败 {backup_job.filename}: {message}")
                    
                    # 从数据库删除记录
                    db.session.delete(backup_job)
                
                # 提交数据库更改
                db.session.commit()
            
        except Exception as e:
            # 记录错误但不中断备份流程
            print(f"警告: 清理旧备份失败: {str(e)}")
            # 回滚数据库更改
            db.session.rollback()
    
    def _update_file_tracker(self, files: list, backup_job_id: int):
        """
        更新文件变更追踪记录
        Update file change tracking records
        
        为每个备份的文件更新或创建追踪记录，用于增量备份时识别文件变更。
        
        Args:
            files: 文件列表，每个元素为字典：
                {
                    'source_path': str,  # 源文件绝对路径
                    'archive_path': str,  # 归档中的相对路径
                    'file_type': str,    # 文件类型：database, upload, document
                    'size': int,         # 文件大小（字节）
                    'hash': str,         # SHA256哈希值
                    'modified': datetime,# 修改时间
                    'original_path': str,# 原始文件路径（用于追踪）
                    'is_temp': bool      # 是否为临时文件
                }
            backup_job_id: 备份任务ID
        """
        from models import BackupFileTracker
        
        try:
            for file_info in files:
                # 获取原始文件路径（用于追踪）
                file_path = file_info.get('original_path', file_info['source_path'])
                file_type = file_info['file_type']
                last_modified = file_info['modified']
                file_size = file_info['size']
                file_hash = file_info['hash']
                
                # 查询现有追踪记录
                tracker = BackupFileTracker.query.filter_by(
                    file_path=file_path,
                    file_type=file_type
                ).first()
                
                if tracker:
                    # 更新现有记录
                    tracker.last_modified = last_modified
                    tracker.file_size_bytes = file_size
                    tracker.file_hash = file_hash
                    tracker.last_backup_id = backup_job_id
                else:
                    # 创建新记录
                    tracker = BackupFileTracker(
                        file_path=file_path,
                        file_type=file_type,
                        last_modified=last_modified,
                        file_size_bytes=file_size,
                        file_hash=file_hash,
                        last_backup_id=backup_job_id
                    )
                    db.session.add(tracker)
            
            # 提交所有更改
            db.session.commit()
            
        except Exception as e:
            # 回滚数据库更改
            db.session.rollback()
            # 记录错误但不中断备份流程
            print(f"警告: 更新文件追踪记录失败: {str(e)}")
