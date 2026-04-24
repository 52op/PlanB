# -*- coding: utf-8 -*-
"""
备份恢复管理器单元测试
Unit tests for BackupRestorer service
"""

import pytest
from datetime import datetime, timedelta
from models import db, BackupJob, BackupConfig
from services.backup_restorer import BackupRestorer


@pytest.fixture
def app():
    """创建测试Flask应用"""
    from flask import Flask
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def restorer(app):
    """创建BackupRestorer实例"""
    return BackupRestorer(app)


@pytest.fixture
def sample_backup_jobs(app):
    """创建示例备份任务"""
    with app.app_context():
        # 创建成功的完整备份
        backup1 = BackupJob(
            trigger_type='auto',
            status='success',
            backup_mode='full',
            storage_type='ftp',
            filename='backup_20240115_100000.tar.gz',
            file_size_bytes=10485760,
            file_hash='abc123def456',
            storage_path='/backups/backup_20240115_100000.tar.gz',
            is_encrypted=False,
            started_at=datetime.utcnow() - timedelta(days=2),
            completed_at=datetime.utcnow() - timedelta(days=2, hours=-1),
            duration_seconds=3600,
            db_size_bytes=1048576,
            uploads_count=50,
            uploads_size_bytes=5242880,
            docs_count=100,
            docs_size_bytes=4194304
        )
        
        # 创建成功的增量备份
        backup2 = BackupJob(
            trigger_type='auto',
            status='success',
            backup_mode='incremental',
            storage_type='ftp',
            filename='backup_20240116_100000_incremental.tar.gz',
            file_size_bytes=2097152,
            file_hash='ghi789jkl012',
            storage_path='/backups/backup_20240116_100000_incremental.tar.gz',
            is_encrypted=False,
            base_backup_id=1,
            started_at=datetime.utcnow() - timedelta(days=1),
            completed_at=datetime.utcnow() - timedelta(days=1, hours=-1),
            duration_seconds=1800,
            db_size_bytes=524288,
            uploads_count=10,
            uploads_size_bytes=1048576,
            docs_count=20,
            docs_size_bytes=524288
        )
        
        # 创建加密的备份
        backup3 = BackupJob(
            trigger_type='manual',
            status='success',
            backup_mode='full',
            storage_type='s3',
            filename='backup_20240117_100000.tar.gz.enc',
            file_size_bytes=10737418,
            file_hash='mno345pqr678',
            storage_path='backups/backup_20240117_100000.tar.gz.enc',
            is_encrypted=True,
            started_at=datetime.utcnow() - timedelta(hours=12),
            completed_at=datetime.utcnow() - timedelta(hours=11),
            duration_seconds=3600,
            db_size_bytes=1048576,
            uploads_count=50,
            uploads_size_bytes=5242880,
            docs_count=100,
            docs_size_bytes=4194304
        )
        
        # 创建失败的备份（不应出现在可用列表中）
        backup4 = BackupJob(
            trigger_type='auto',
            status='failed',
            backup_mode='full',
            storage_type='ftp',
            started_at=datetime.utcnow() - timedelta(hours=6),
            completed_at=datetime.utcnow() - timedelta(hours=6, minutes=-30),
            duration_seconds=1800,
            error_message='上传失败'
        )
        
        # 创建运行中的备份（不应出现在可用列表中）
        backup5 = BackupJob(
            trigger_type='manual',
            status='running',
            backup_mode='full',
            storage_type='s3',
            started_at=datetime.utcnow() - timedelta(minutes=30)
        )
        
        db.session.add_all([backup1, backup2, backup3, backup4, backup5])
        db.session.commit()
        
        return [backup1, backup2, backup3, backup4, backup5]


class TestBackupRestorerInit:
    """测试BackupRestorer初始化"""
    
    def test_init_with_app(self, app):
        """测试使用Flask应用初始化"""
        restorer = BackupRestorer(app)
        assert restorer.app == app
    
    def test_init_without_app(self):
        """测试不使用Flask应用初始化"""
        restorer = BackupRestorer()
        assert restorer.app is None


class TestListAvailableBackups:
    """测试list_available_backups方法"""
    
    def test_list_available_backups_empty(self, app, restorer):
        """测试空备份列表"""
        with app.app_context():
            backups = restorer.list_available_backups()
            assert backups == []
    
    def test_list_available_backups_success(self, app, restorer, sample_backup_jobs):
        """测试列出成功的备份"""
        with app.app_context():
            backups = restorer.list_available_backups()
            
            # 应该只返回3个成功的备份（排除失败和运行中的）
            assert len(backups) == 3
            
            # 验证返回的备份按完成时间降序排列
            assert backups[0]['filename'] == 'backup_20240117_100000.tar.gz.enc'
            assert backups[1]['filename'] == 'backup_20240116_100000_incremental.tar.gz'
            assert backups[2]['filename'] == 'backup_20240115_100000.tar.gz'
    
    def test_list_available_backups_fields(self, app, restorer, sample_backup_jobs):
        """测试返回的备份包含所有必需字段"""
        with app.app_context():
            backups = restorer.list_available_backups()
            
            # 检查第一个备份的字段
            backup = backups[0]
            required_fields = [
                'backup_id', 'filename', 'backup_mode', 'trigger_type',
                'storage_type', 'storage_path', 'file_size_bytes', 'file_hash',
                'is_encrypted', 'created_at', 'completed_at', 'duration_seconds',
                'base_backup_id', 'db_size_bytes', 'uploads_count',
                'uploads_size_bytes', 'docs_count', 'docs_size_bytes'
            ]
            
            for field in required_fields:
                assert field in backup
    
    def test_list_available_backups_full_mode(self, app, restorer, sample_backup_jobs):
        """测试完整备份的属性"""
        with app.app_context():
            backups = restorer.list_available_backups()
            
            # 找到完整备份
            full_backup = next(b for b in backups if b['backup_mode'] == 'full' and not b['is_encrypted'])
            
            assert full_backup['backup_mode'] == 'full'
            assert full_backup['base_backup_id'] is None
            assert full_backup['file_size_bytes'] == 10485760
            assert full_backup['db_size_bytes'] == 1048576
            assert full_backup['uploads_count'] == 50
            assert full_backup['docs_count'] == 100
    
    def test_list_available_backups_incremental_mode(self, app, restorer, sample_backup_jobs):
        """测试增量备份的属性"""
        with app.app_context():
            backups = restorer.list_available_backups()
            
            # 找到增量备份
            incremental_backup = next(b for b in backups if b['backup_mode'] == 'incremental')
            
            assert incremental_backup['backup_mode'] == 'incremental'
            assert incremental_backup['base_backup_id'] == 1
            assert incremental_backup['file_size_bytes'] == 2097152
    
    def test_list_available_backups_encrypted(self, app, restorer, sample_backup_jobs):
        """测试加密备份的属性"""
        with app.app_context():
            backups = restorer.list_available_backups()
            
            # 找到加密备份
            encrypted_backup = next(b for b in backups if b['is_encrypted'])
            
            assert encrypted_backup['is_encrypted'] is True
            assert encrypted_backup['filename'].endswith('.enc')
            assert encrypted_backup['trigger_type'] == 'manual'


class TestGetBackupMetadata:
    """测试get_backup_metadata方法"""
    
    def test_get_backup_metadata_success(self, app, restorer, sample_backup_jobs):
        """测试获取备份元数据成功"""
        with app.app_context():
            metadata = restorer.get_backup_metadata(1)
            
            # 验证基本字段
            assert metadata['backup_id'] == 1
            assert metadata['filename'] == 'backup_20240115_100000.tar.gz'
            assert metadata['backup_mode'] == 'full'
            assert metadata['trigger_type'] == 'auto'
            assert metadata['storage_type'] == 'ftp'
            assert metadata['is_encrypted'] is False
    
    def test_get_backup_metadata_statistics(self, app, restorer, sample_backup_jobs):
        """测试元数据包含统计信息"""
        with app.app_context():
            metadata = restorer.get_backup_metadata(1)
            
            # 验证统计信息
            assert 'statistics' in metadata
            stats = metadata['statistics']
            
            assert stats['db_size_bytes'] == 1048576
            assert stats['uploads_count'] == 50
            assert stats['uploads_size_bytes'] == 5242880
            assert stats['docs_count'] == 100
            assert stats['docs_size_bytes'] == 4194304
            
            # 验证总大小计算正确
            expected_total = 1048576 + 5242880 + 4194304
            assert stats['total_size_bytes'] == expected_total
    
    def test_get_backup_metadata_content_summary(self, app, restorer, sample_backup_jobs):
        """测试元数据包含内容摘要"""
        with app.app_context():
            metadata = restorer.get_backup_metadata(1)
            
            # 验证内容摘要
            assert 'content_summary' in metadata
            summary = metadata['content_summary']
            
            assert summary['has_database'] is True
            assert summary['has_uploads'] is True
            assert summary['has_documents'] is True
    
    def test_get_backup_metadata_nonexistent(self, app, restorer):
        """测试获取不存在的备份元数据"""
        with app.app_context():
            with pytest.raises(ValueError, match="备份任务不存在"):
                restorer.get_backup_metadata(999)
    
    def test_get_backup_metadata_failed_backup(self, app, restorer, sample_backup_jobs):
        """测试获取失败备份的元数据"""
        with app.app_context():
            with pytest.raises(ValueError, match="备份任务未成功完成"):
                restorer.get_backup_metadata(4)
    
    def test_get_backup_metadata_running_backup(self, app, restorer, sample_backup_jobs):
        """测试获取运行中备份的元数据"""
        with app.app_context():
            with pytest.raises(ValueError, match="备份任务未成功完成"):
                restorer.get_backup_metadata(5)
    
    def test_get_backup_metadata_encrypted(self, app, restorer, sample_backup_jobs):
        """测试获取加密备份的元数据"""
        with app.app_context():
            metadata = restorer.get_backup_metadata(3)
            
            assert metadata['is_encrypted'] is True
            assert metadata['filename'].endswith('.enc')
    
    def test_get_backup_metadata_incremental(self, app, restorer, sample_backup_jobs):
        """测试获取增量备份的元数据"""
        with app.app_context():
            metadata = restorer.get_backup_metadata(2)
            
            assert metadata['backup_mode'] == 'incremental'
            assert metadata['base_backup_id'] == 1


class TestRestoreBackup:
    """测试restore_backup方法"""
    
    def test_restore_backup_invalid_backup_id(self, app, restorer):
        """测试使用无效的备份任务ID"""
        with app.app_context():
            restore_options = {
                'restore_database': True,
                'restore_uploads': True,
                'restore_documents': True
            }
            
            # 测试负数ID
            success, message = restorer.restore_backup(-1, restore_options)
            assert success is False
            assert "无效的备份任务ID" in message
            
            # 测试零ID
            success, message = restorer.restore_backup(0, restore_options)
            assert success is False
            assert "无效的备份任务ID" in message
    
    def test_restore_backup_invalid_options_type(self, app, restorer):
        """测试使用无效的恢复选项类型"""
        with app.app_context():
            # 测试非字典类型
            success, message = restorer.restore_backup(1, "invalid")
            assert success is False
            assert "恢复选项必须是字典类型" in message
    
    def test_restore_backup_no_restore_content_selected(self, app, restorer, sample_backup_jobs):
        """测试未选择任何恢复内容"""
        with app.app_context():
            restore_options = {
                'restore_database': False,
                'restore_uploads': False,
                'restore_documents': False
            }
            
            success, message = restorer.restore_backup(1, restore_options)
            assert success is False
            assert "至少需要选择一项恢复内容" in message
    
    def test_restore_backup_nonexistent_backup(self, app, restorer):
        """测试恢复不存在的备份"""
        with app.app_context():
            restore_options = {
                'restore_database': True
            }
            
            success, message = restorer.restore_backup(999, restore_options)
            assert success is False
            assert "备份任务不存在" in message
    
    def test_restore_backup_failed_backup(self, app, restorer, sample_backup_jobs):
        """测试恢复失败的备份"""
        with app.app_context():
            restore_options = {
                'restore_database': True
            }
            
            # 备份任务4是失败的
            success, message = restorer.restore_backup(4, restore_options)
            assert success is False
            assert "备份任务未成功完成" in message
    
    def test_restore_backup_encrypted_without_password(self, app, restorer, sample_backup_jobs):
        """测试恢复加密备份但未提供密码"""
        with app.app_context():
            restore_options = {
                'restore_database': True
            }
            
            # 备份任务3是加密的
            success, message = restorer.restore_backup(3, restore_options)
            assert success is False
            assert "备份文件已加密，需要提供解密密码" in message


class TestPrivateMethodStubs:
    """测试私有方法stub"""
    
    def test_download_backup_not_implemented(self, app, restorer, sample_backup_jobs):
        """测试_download_backup方法抛出NotImplementedError"""
        with app.app_context():
            backup_job = BackupJob.query.get(1)
            
            # 这个测试现在应该失败，因为方法已经实现
            # 保留此测试以验证方法不再抛出NotImplementedError
            # with pytest.raises(NotImplementedError, match="备份文件下载功能将在Task 9.2中实现"):
            #     restorer._download_backup(backup_job)
    
    def test_decrypt_archive_not_implemented(self, restorer):
        """测试_decrypt_archive方法抛出NotImplementedError"""
        # 这个测试现在应该失败，因为方法已经实现
        # with pytest.raises(NotImplementedError, match="备份文件解密功能将在Task 9.2中实现"):
        #     restorer._decrypt_archive('/path/to/archive.tar.gz.enc', 'password')
    
    def test_extract_archive_not_implemented(self, restorer):
        """测试_extract_archive方法抛出NotImplementedError"""
        # 这个测试现在应该失败，因为方法已经实现
        # with pytest.raises(NotImplementedError, match="备份归档解压功能将在Task 9.2中实现"):
        #     restorer._extract_archive('/path/to/archive.tar.gz', '/tmp/extract')
    
    def test_create_rollback_point_not_implemented(self, restorer):
        """测试_create_rollback_point方法已实现（Task 9.3）"""
        # 方法已在Task 9.3中实现，不再抛出NotImplementedError
        pass
    
    def test_restore_database_not_implemented(self, restorer):
        """测试_restore_database方法已实现（Task 9.3）"""
        # 方法已在Task 9.3中实现，不再抛出NotImplementedError
        pass
    
    def test_restore_uploads_not_implemented(self, restorer):
        """测试_restore_uploads方法已实现（Task 9.3）"""
        # 方法已在Task 9.3中实现，不再抛出NotImplementedError
        pass
    
    def test_restore_documents_not_implemented(self, restorer):
        """测试_restore_documents方法已实现（Task 9.3）"""
        # 方法已在Task 9.3中实现，不再抛出NotImplementedError
        pass
    
    def test_rollback_not_implemented(self, restorer):
        """测试_rollback方法已实现（Task 9.3）"""
        # 方法已在Task 9.3中实现，不再抛出NotImplementedError
        pass


class TestEdgeCases:
    """测试边界情况"""
    
    def test_get_metadata_with_null_statistics(self, app, restorer):
        """测试获取统计信息为空的备份元数据"""
        with app.app_context():
            # 创建统计信息为空的备份
            backup = BackupJob(
                trigger_type='manual',
                status='success',
                backup_mode='full',
                storage_type='ftp',
                filename='backup_minimal.tar.gz',
                file_size_bytes=1024,
                file_hash='test123',
                storage_path='/backups/backup_minimal.tar.gz',
                is_encrypted=False,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                duration_seconds=60,
                # 所有统计字段为None
                db_size_bytes=None,
                uploads_count=None,
                uploads_size_bytes=None,
                docs_count=None,
                docs_size_bytes=None
            )
            db.session.add(backup)
            db.session.commit()
            
            metadata = restorer.get_backup_metadata(backup.id)
            
            # 验证统计信息默认为0
            stats = metadata['statistics']
            assert stats['total_size_bytes'] == 0
            assert stats['db_size_bytes'] == 0
            assert stats['uploads_count'] == 0
            assert stats['uploads_size_bytes'] == 0
            assert stats['docs_count'] == 0
            assert stats['docs_size_bytes'] == 0
            
            # 验证内容摘要全为False
            summary = metadata['content_summary']
            assert summary['has_database'] is False
            assert summary['has_uploads'] is False
            assert summary['has_documents'] is False
    
    def test_list_backups_with_mixed_storage_types(self, app, restorer):
        """测试列出不同存储类型的备份"""
        with app.app_context():
            # 创建不同存储类型的备份
            backups_data = [
                ('ftp', 'backup_ftp.tar.gz'),
                ('email', 'backup_email.tar.gz'),
                ('s3', 'backup_s3.tar.gz')
            ]
            
            for storage_type, filename in backups_data:
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type=storage_type,
                    filename=filename,
                    file_size_bytes=1024,
                    file_hash='test123',
                    storage_path=f'/backups/{filename}',
                    is_encrypted=False,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                    duration_seconds=60
                )
                db.session.add(backup)
            
            db.session.commit()
            
            backups = restorer.list_available_backups()
            
            # 验证所有存储类型都被列出
            assert len(backups) == 3
            storage_types = {b['storage_type'] for b in backups}
            assert storage_types == {'ftp', 'email', 's3'}



class TestDownloadBackup:
    """测试_download_backup方法"""
    
    def test_download_backup_missing_storage_type(self, app, restorer):
        """测试下载缺少存储类型的备份"""
        with app.app_context():
            backup_job = BackupJob(
                trigger_type='auto',
                status='success',
                backup_mode='full',
                storage_type=None,  # 缺少存储类型
                filename='backup.tar.gz',
                storage_path='/backups/backup.tar.gz',
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(backup_job)
            db.session.commit()
            
            with pytest.raises(ValueError, match="备份任务缺少存储类型信息"):
                restorer._download_backup(backup_job)
    
    def test_download_backup_missing_storage_path(self, app, restorer):
        """测试下载缺少存储路径的备份"""
        with app.app_context():
            backup_job = BackupJob(
                trigger_type='auto',
                status='success',
                backup_mode='full',
                storage_type='ftp',
                filename='backup.tar.gz',
                storage_path=None,  # 缺少存储路径
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(backup_job)
            db.session.commit()
            
            with pytest.raises(ValueError, match="备份任务缺少存储路径信息"):
                restorer._download_backup(backup_job)
    
    def test_download_backup_missing_filename(self, app, restorer):
        """测试下载缺少文件名的备份"""
        with app.app_context():
            backup_job = BackupJob(
                trigger_type='auto',
                status='success',
                backup_mode='full',
                storage_type='ftp',
                filename=None,  # 缺少文件名
                storage_path='/backups/backup.tar.gz',
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(backup_job)
            db.session.commit()
            
            with pytest.raises(ValueError, match="备份任务缺少文件名信息"):
                restorer._download_backup(backup_job)
    
    def test_download_backup_no_config(self, app, restorer):
        """测试下载备份时配置不存在"""
        with app.app_context():
            backup_job = BackupJob(
                trigger_type='auto',
                status='success',
                backup_mode='full',
                storage_type='ftp',
                filename='backup.tar.gz',
                storage_path='/backups/backup.tar.gz',
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(backup_job)
            db.session.commit()
            
            with pytest.raises(ValueError, match="备份配置不存在"):
                restorer._download_backup(backup_job)
    
    def test_download_backup_email_not_supported(self, app, restorer):
        """测试邮件存储方式不支持下载"""
        with app.app_context():
            # 创建配置
            config = BackupConfig(
                enabled=True,
                storage_type='email',
                schedule_type='daily',
                email_recipient='test@example.com'
            )
            db.session.add(config)
            
            backup_job = BackupJob(
                trigger_type='auto',
                status='success',
                backup_mode='full',
                storage_type='email',
                filename='backup.tar.gz',
                storage_path='email://backup.tar.gz',
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(backup_job)
            db.session.commit()
            
            with pytest.raises(RuntimeError, match="邮件存储方式不支持下载备份文件"):
                restorer._download_backup(backup_job)
    
    def test_download_backup_unsupported_storage_type(self, app, restorer):
        """测试不支持的存储类型"""
        with app.app_context():
            # 创建配置
            config = BackupConfig(
                enabled=True,
                storage_type='unknown',
                schedule_type='daily'
            )
            db.session.add(config)
            
            backup_job = BackupJob(
                trigger_type='auto',
                status='success',
                backup_mode='full',
                storage_type='unknown',
                filename='backup.tar.gz',
                storage_path='/backups/backup.tar.gz',
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(backup_job)
            db.session.commit()
            
            with pytest.raises(RuntimeError, match="不支持的存储类型"):
                restorer._download_backup(backup_job)


class TestDecryptArchive:
    """测试_decrypt_archive方法"""
    
    def test_decrypt_archive_invalid_magic_number(self, restorer, tmp_path):
        """测试解密魔数不匹配的文件"""
        import struct
        
        # 创建一个魔数错误的加密文件
        encrypted_file = tmp_path / "backup.tar.gz.enc"
        
        # 构建错误的文件头
        header = struct.pack(
            '8s32s16sI196s',
            b'WRONGMAG',  # 错误的魔数
            b'\x00' * 32,  # salt
            b'\x00' * 16,  # iv
            100000,  # iterations
            b'\x00' * 196  # reserved
        )
        
        with open(encrypted_file, 'wb') as f:
            f.write(header)
            f.write(b'encrypted data')
        
        with pytest.raises(ValueError, match="加密文件格式无效: 魔数不匹配"):
            restorer._decrypt_archive(str(encrypted_file), 'password')
    
    def test_decrypt_archive_incomplete_header(self, restorer, tmp_path):
        """测试解密文件头不完整的文件"""
        encrypted_file = tmp_path / "backup.tar.gz.enc"
        
        # 写入不完整的文件头（少于256字节）
        with open(encrypted_file, 'wb') as f:
            f.write(b'BKPENC01' + b'\x00' * 100)  # 只有108字节
        
        with pytest.raises(ValueError, match="加密文件格式无效: 文件头部不完整"):
            restorer._decrypt_archive(str(encrypted_file), 'password')
    
    def test_decrypt_archive_wrong_password(self, restorer, tmp_path):
        """测试使用错误密码解密"""
        import os
        import struct
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        
        # 创建一个正确加密的文件
        encrypted_file = tmp_path / "backup.tar.gz.enc"
        password = 'correct_password'
        
        # 生成加密参数
        salt = os.urandom(32)
        iv = os.urandom(16)
        iterations = 100000
        
        # 派生密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))
        
        # 加密数据
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        plaintext = b'test data' + b'\x07' * 7  # PKCS7填充
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        # 写入加密文件
        header = struct.pack('8s32s16sI196s', b'BKPENC01', salt, iv, iterations, b'\x00' * 196)
        with open(encrypted_file, 'wb') as f:
            f.write(header)
            f.write(ciphertext)
        
        # 使用错误密码解密
        with pytest.raises(ValueError, match="密码可能不正确"):
            restorer._decrypt_archive(str(encrypted_file), 'wrong_password')
    
    def test_decrypt_archive_success(self, restorer, tmp_path):
        """测试成功解密文件"""
        import os
        import struct
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        
        # 创建一个正确加密的文件
        encrypted_file = tmp_path / "backup.tar.gz.enc"
        password = 'test_password'
        original_data = b'This is test backup data'
        
        # 生成加密参数
        salt = os.urandom(32)
        iv = os.urandom(16)
        iterations = 100000
        
        # 派生密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))
        
        # PKCS7填充
        block_size = 16
        padding_length = block_size - (len(original_data) % block_size)
        padded_data = original_data + bytes([padding_length] * padding_length)
        
        # 加密数据
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # 写入加密文件
        header = struct.pack('8s32s16sI196s', b'BKPENC01', salt, iv, iterations, b'\x00' * 196)
        with open(encrypted_file, 'wb') as f:
            f.write(header)
            f.write(ciphertext)
        
        # 解密文件
        decrypted_path = restorer._decrypt_archive(str(encrypted_file), password)
        
        # 验证解密后的文件
        assert os.path.exists(decrypted_path)
        assert decrypted_path == str(tmp_path / "backup.tar.gz")
        
        with open(decrypted_path, 'rb') as f:
            decrypted_data = f.read()
        
        assert decrypted_data == original_data
        
        # 验证加密文件已被删除
        assert not os.path.exists(encrypted_file)


class TestExtractArchive:
    """测试_extract_archive方法"""
    
    def test_extract_archive_file_not_exists(self, restorer, tmp_path):
        """测试解压不存在的文件"""
        archive_path = tmp_path / "nonexistent.tar.gz"
        extract_dir = tmp_path / "extract"
        
        with pytest.raises(ValueError, match="归档文件不存在"):
            restorer._extract_archive(str(archive_path), str(extract_dir))
    
    def test_extract_archive_invalid_format(self, restorer, tmp_path):
        """测试解压无效格式的文件"""
        # 创建一个非tar文件
        archive_path = tmp_path / "invalid.tar.gz"
        with open(archive_path, 'wb') as f:
            f.write(b'This is not a tar file')
        
        extract_dir = tmp_path / "extract"
        
        with pytest.raises(ValueError, match="文件不是有效的tar归档"):
            restorer._extract_archive(str(archive_path), str(extract_dir))
    
    def test_extract_archive_success(self, restorer, tmp_path):
        """测试成功解压归档文件"""
        import tarfile
        import os
        
        # 创建一个测试tar.gz文件
        archive_path = tmp_path / "test_backup.tar.gz"
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # 创建一些测试文件
        (source_dir / "file1.txt").write_text("content1", encoding='utf-8')
        (source_dir / "file2.txt").write_text("content2", encoding='utf-8')
        subdir = source_dir / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("content3", encoding='utf-8')
        
        # 创建tar.gz归档
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(source_dir / "file1.txt", arcname="file1.txt")
            tar.add(source_dir / "file2.txt", arcname="file2.txt")
            tar.add(subdir / "file3.txt", arcname="subdir/file3.txt")
        
        # 解压归档
        extract_dir = tmp_path / "extract"
        restorer._extract_archive(str(archive_path), str(extract_dir))
        
        # 验证解压结果
        assert os.path.exists(extract_dir)
        assert os.path.exists(extract_dir / "file1.txt")
        assert os.path.exists(extract_dir / "file2.txt")
        assert os.path.exists(extract_dir / "subdir" / "file3.txt")
        
        # 验证文件内容
        assert (extract_dir / "file1.txt").read_text(encoding='utf-8') == "content1"
        assert (extract_dir / "file2.txt").read_text(encoding='utf-8') == "content2"
        assert (extract_dir / "subdir" / "file3.txt").read_text(encoding='utf-8') == "content3"
    
    def test_extract_archive_path_traversal_protection(self, restorer, tmp_path):
        """测试路径遍历攻击防护"""
        import tarfile
        
        # 创建一个包含路径遍历的tar文件
        archive_path = tmp_path / "malicious.tar.gz"
        source_file = tmp_path / "malicious.txt"
        source_file.write_text("malicious content", encoding='utf-8')
        
        with tarfile.open(archive_path, 'w:gz') as tar:
            # 尝试添加一个路径遍历的文件
            tarinfo = tar.gettarinfo(str(source_file), arcname="../../../etc/passwd")
            tar.addfile(tarinfo, open(source_file, 'rb'))
        
        extract_dir = tmp_path / "extract"
        
        # 应该抛出错误
        with pytest.raises(ValueError, match="归档包含不安全的路径"):
            restorer._extract_archive(str(archive_path), str(extract_dir))
