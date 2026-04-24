# -*- coding: utf-8 -*-
"""
备份执行引擎测试
Backup Engine Tests
"""

import unittest
from datetime import datetime
from tests.support import PlanningTestCase
from models import db, BackupJob, BackupConfig
from services.backup_engine import BackupEngine


class TestBackupEngineInit(PlanningTestCase):
    """测试备份引擎初始化"""
    
    def test_init_with_app(self):
        """测试使用app初始化"""
        engine = BackupEngine(self.app)
        self.assertEqual(engine.app, self.app)
    
    def test_init_without_app(self):
        """测试不使用app初始化"""
        engine = BackupEngine()
        self.assertIsNone(engine.app)


class TestExecuteBackup(PlanningTestCase):
    """测试执行备份方法"""
    
    def _create_valid_ftp_config(self):
        """创建有效的FTP备份配置"""
        config = BackupConfig(
            enabled=True,
            storage_type='ftp',
            schedule_type='daily',
            retention_count=10,
            backup_mode='full',
            encryption_enabled=False,
            ftp_host='ftp.example.com',
            ftp_port=21,
            ftp_username='testuser',
            ftp_password='testpass',
            ftp_path='/backups',
            notification_enabled=False
        )
        db.session.add(config)
        db.session.commit()
        return config
    
    def _create_valid_email_config(self):
        """创建有效的邮件备份配置"""
        config = BackupConfig(
            enabled=True,
            storage_type='email',
            schedule_type='weekly',
            retention_count=5,
            backup_mode='full',
            encryption_enabled=False,
            email_recipient='backup@example.com',
            notification_enabled=False
        )
        db.session.add(config)
        db.session.commit()
        return config
    
    def _create_valid_s3_config(self):
        """创建有效的S3备份配置"""
        config = BackupConfig(
            enabled=True,
            storage_type='s3',
            schedule_type='hourly',
            retention_count=20,
            backup_mode='full',
            encryption_enabled=False,
            s3_endpoint='https://s3.amazonaws.com',
            s3_bucket='my-backup-bucket',
            s3_access_key='AKIAIOSFODNN7EXAMPLE',
            s3_secret_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            s3_path_prefix='backups/',
            s3_region='us-east-1',
            notification_enabled=False
        )
        db.session.add(config)
        db.session.commit()
        return config
    
    def test_execute_backup_invalid_trigger_type(self):
        """测试无效的触发类型"""
        with self.app.app_context():
            self._create_valid_ftp_config()
            engine = BackupEngine(self.app)
            
            with self.assertRaises(ValueError) as context:
                engine.execute_backup(trigger_type='invalid')
            
            self.assertIn('无效的触发类型', str(context.exception))
    
    def test_execute_backup_no_config(self):
        """测试没有配置时执行备份"""
        with self.app.app_context():
            engine = BackupEngine(self.app)
            
            with self.assertRaises(ValueError) as context:
                engine.execute_backup()
            
            self.assertIn('备份配置不存在', str(context.exception))
    
    def test_execute_backup_invalid_config(self):
        """测试配置无效时执行备份"""
        with self.app.app_context():
            # 创建无效配置（缺少必需字段）
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                # 缺少 ftp_host, ftp_username, ftp_password
            )
            db.session.add(config)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            with self.assertRaises(ValueError) as context:
                engine.execute_backup()
            
            self.assertIn('备份配置无效', str(context.exception))
    
    def test_execute_backup_auto_trigger(self):
        """测试自动触发备份"""
        with self.app.app_context():
            self._create_valid_ftp_config()
            engine = BackupEngine(self.app)
            
            # 由于实际备份步骤未实现，这里会成功创建任务记录
            backup_job = engine.execute_backup(trigger_type='auto')
            
            self.assertIsNotNone(backup_job)
            self.assertIsNotNone(backup_job.id)
            self.assertEqual(backup_job.trigger_type, 'auto')
            self.assertEqual(backup_job.status, 'success')
            self.assertEqual(backup_job.backup_mode, 'full')
            self.assertEqual(backup_job.storage_type, 'ftp')
            self.assertFalse(backup_job.is_encrypted)
            self.assertIsNotNone(backup_job.started_at)
            self.assertIsNotNone(backup_job.completed_at)
            self.assertIsNotNone(backup_job.duration_seconds)
            self.assertGreaterEqual(backup_job.duration_seconds, 0)
    
    def test_execute_backup_manual_trigger(self):
        """测试手动触发备份"""
        with self.app.app_context():
            self._create_valid_email_config()
            engine = BackupEngine(self.app)
            
            backup_job = engine.execute_backup(trigger_type='manual')
            
            self.assertIsNotNone(backup_job)
            self.assertEqual(backup_job.trigger_type, 'manual')
            self.assertEqual(backup_job.status, 'success')
            self.assertEqual(backup_job.backup_mode, 'full')
            self.assertEqual(backup_job.storage_type, 'email')
    
    def test_execute_backup_with_encryption_enabled(self):
        """测试启用加密的备份"""
        with self.app.app_context():
            config = self._create_valid_s3_config()
            # 启用加密并配置密码
            config.encryption_enabled = True
            config.encryption_key_hash = 'test_encryption_password'
            db.session.commit()
            
            engine = BackupEngine(self.app)
            backup_job = engine.execute_backup()
            
            self.assertTrue(backup_job.is_encrypted)
    
    def test_execute_backup_incremental_mode_no_base(self):
        """测试增量备份模式（没有基准备份）"""
        with self.app.app_context():
            config = self._create_valid_ftp_config()
            # 设置为增量备份模式
            config.backup_mode = 'incremental'
            db.session.commit()
            
            engine = BackupEngine(self.app)
            backup_job = engine.execute_backup()
            
            self.assertEqual(backup_job.backup_mode, 'incremental')
            self.assertIsNone(backup_job.base_backup_id)  # 没有基准备份
    
    def test_execute_backup_incremental_mode_with_base(self):
        """测试增量备份模式（有基准备份）"""
        with self.app.app_context():
            # 先创建一个完整备份作为基准
            base_job = BackupJob(
                trigger_type='auto',
                status='success',
                backup_mode='full',
                storage_type='ftp',
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(base_job)
            db.session.commit()
            base_job_id = base_job.id
            
            config = self._create_valid_ftp_config()
            # 设置为增量备份模式
            config.backup_mode = 'incremental'
            db.session.commit()
            
            engine = BackupEngine(self.app)
            backup_job = engine.execute_backup()
            
            self.assertEqual(backup_job.backup_mode, 'incremental')
            self.assertEqual(backup_job.base_backup_id, base_job_id)


class TestCreateBackupJob(PlanningTestCase):
    """测试创建备份任务记录"""
    
    def _create_valid_ftp_config(self):
        """创建有效的FTP备份配置"""
        config = BackupConfig(
            enabled=True,
            storage_type='ftp',
            schedule_type='daily',
            retention_count=10,
            backup_mode='full',
            encryption_enabled=False,
            ftp_host='ftp.example.com',
            ftp_port=21,
            ftp_username='testuser',
            ftp_password='testpass',
            ftp_path='/backups',
            notification_enabled=False
        )
        db.session.add(config)
        db.session.commit()
        return config
    
    def _create_valid_email_config(self):
        """创建有效的邮件备份配置"""
        config = BackupConfig(
            enabled=True,
            storage_type='email',
            schedule_type='weekly',
            retention_count=5,
            backup_mode='full',
            encryption_enabled=False,
            email_recipient='backup@example.com',
            notification_enabled=False
        )
        db.session.add(config)
        db.session.commit()
        return config
    
    def _create_valid_s3_config(self):
        """创建有效的S3备份配置"""
        config = BackupConfig(
            enabled=True,
            storage_type='s3',
            schedule_type='hourly',
            retention_count=20,
            backup_mode='full',
            encryption_enabled=False,
            s3_endpoint='https://s3.amazonaws.com',
            s3_bucket='my-backup-bucket',
            s3_access_key='AKIAIOSFODNN7EXAMPLE',
            s3_secret_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            s3_path_prefix='backups/',
            s3_region='us-east-1',
            notification_enabled=False
        )
        db.session.add(config)
        db.session.commit()
        return config
    
    def test_create_backup_job_auto(self):
        """测试创建自动触发的备份任务"""
        with self.app.app_context():
            config = self._create_valid_ftp_config()
            engine = BackupEngine(self.app)
            
            backup_job = engine._create_backup_job('auto', config)
            
            self.assertIsNotNone(backup_job.id)
            self.assertEqual(backup_job.trigger_type, 'auto')
            self.assertEqual(backup_job.status, 'running')
            self.assertEqual(backup_job.backup_mode, 'full')
            self.assertEqual(backup_job.storage_type, 'ftp')
            self.assertFalse(backup_job.is_encrypted)
            self.assertIsNotNone(backup_job.started_at)
            self.assertIsNone(backup_job.base_backup_id)
    
    def test_create_backup_job_manual(self):
        """测试创建手动触发的备份任务"""
        with self.app.app_context():
            config = self._create_valid_email_config()
            engine = BackupEngine(self.app)
            
            backup_job = engine._create_backup_job('manual', config)
            
            self.assertEqual(backup_job.trigger_type, 'manual')
            self.assertEqual(backup_job.storage_type, 'email')
    
    def test_create_backup_job_with_encryption(self):
        """测试创建启用加密的备份任务"""
        with self.app.app_context():
            config = self._create_valid_s3_config()
            config.encryption_enabled = True
            db.session.commit()
            
            engine = BackupEngine(self.app)
            backup_job = engine._create_backup_job('auto', config)
            
            self.assertTrue(backup_job.is_encrypted)
    
    def test_create_backup_job_incremental_with_base(self):
        """测试创建增量备份任务（有基准备份）"""
        with self.app.app_context():
            # 创建基准完整备份
            base_job = BackupJob(
                trigger_type='auto',
                status='success',
                backup_mode='full',
                storage_type='ftp',
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(base_job)
            db.session.commit()
            base_job_id = base_job.id
            
            config = self._create_valid_ftp_config()
            # 设置为增量模式
            config.backup_mode = 'incremental'
            db.session.commit()
            
            engine = BackupEngine(self.app)
            backup_job = engine._create_backup_job('auto', config)
            
            self.assertEqual(backup_job.backup_mode, 'incremental')
            self.assertEqual(backup_job.base_backup_id, base_job_id)


class TestUpdateBackupJobSuccess(PlanningTestCase):
    """测试更新备份任务为成功状态"""
    
    def test_update_success(self):
        """测试更新为成功状态"""
        with self.app.app_context():
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                retention_count=10,
                backup_mode='full',
                encryption_enabled=False,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups',
                notification_enabled=False
            )
            db.session.add(config)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            backup_job = engine._create_backup_job('auto', config)
            
            engine._update_backup_job_success(backup_job, config)
            
            self.assertEqual(backup_job.status, 'success')
            self.assertIsNotNone(backup_job.completed_at)
            self.assertIsNotNone(backup_job.duration_seconds)
            self.assertGreaterEqual(backup_job.duration_seconds, 0)
            self.assertIsNone(backup_job.error_message)


class TestUpdateBackupJobFailure(PlanningTestCase):
    """测试更新备份任务为失败状态"""
    
    def test_update_failure(self):
        """测试更新为失败状态"""
        with self.app.app_context():
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                retention_count=10,
                backup_mode='full',
                encryption_enabled=False,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups',
                notification_enabled=False
            )
            db.session.add(config)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            backup_job = engine._create_backup_job('auto', config)
            error_msg = "测试错误信息"
            
            engine._update_backup_job_failure(backup_job, error_msg)
            
            self.assertEqual(backup_job.status, 'failed')
            self.assertIsNotNone(backup_job.completed_at)
            self.assertIsNotNone(backup_job.duration_seconds)
            self.assertGreaterEqual(backup_job.duration_seconds, 0)
            self.assertEqual(backup_job.error_message, error_msg)


class TestCreateArchive(PlanningTestCase):
    """测试备份归档创建功能"""
    
    def setUp(self):
        """设置测试环境"""
        super().setUp()
        import os
        import tempfile
        from runtime_paths import get_data_dir
        
        # 创建测试数据目录
        self.data_dir = get_data_dir()
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试环境"""
        import os
        import shutil
        
        # 清理测试目录
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir, ignore_errors=True)
        
        super().tearDown()
    
    def _create_test_file(self, directory, filename, content=b"test content"):
        """创建测试文件"""
        import os
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, filename)
        with open(file_path, 'wb') as f:
            f.write(content)
        return file_path
    
    def test_create_archive_empty_files(self):
        """测试创建空归档（无文件）"""
        with self.app.app_context():
            import os
            
            engine = BackupEngine(self.app)
            
            archive_path, file_size, file_hash = engine._create_archive([], self.output_dir)
            
            # 验证归档文件创建成功
            self.assertTrue(os.path.exists(archive_path))
            self.assertGreater(file_size, 0)
            self.assertEqual(len(file_hash), 64)  # SHA256
            
            # 验证文件名格式
            filename = os.path.basename(archive_path)
            self.assertTrue(filename.startswith('backup_'))
            self.assertTrue(filename.endswith('.tar.gz'))
            
            # 清理
            os.remove(archive_path)
    
    def test_create_archive_with_files(self):
        """测试创建包含文件的归档"""
        with self.app.app_context():
            import os
            from datetime import datetime
            
            # 创建测试文件
            test_file1 = self._create_test_file(self.test_dir, 'test1.txt', b'content 1')
            test_file2 = self._create_test_file(self.test_dir, 'test2.txt', b'content 2')
            
            engine = BackupEngine(self.app)
            
            # 准备文件列表
            files = [
                {
                    'source_path': test_file1,
                    'archive_path': 'uploads/test1.txt',
                    'file_type': 'upload',
                    'size': os.path.getsize(test_file1),
                    'hash': engine._calculate_file_hash(test_file1),
                    'modified': datetime.now(),
                    'is_temp': False
                },
                {
                    'source_path': test_file2,
                    'archive_path': 'documents/test2.txt',
                    'file_type': 'document',
                    'size': os.path.getsize(test_file2),
                    'hash': engine._calculate_file_hash(test_file2),
                    'modified': datetime.now(),
                    'is_temp': False
                }
            ]
            
            archive_path, file_size, file_hash = engine._create_archive(files, self.output_dir)
            
            # 验证归档文件
            self.assertTrue(os.path.exists(archive_path))
            self.assertGreater(file_size, 0)
            self.assertEqual(len(file_hash), 64)
            
            # 验证归档内容
            import tarfile
            with tarfile.open(archive_path, 'r:gz') as tar:
                members = tar.getnames()
                self.assertIn('metadata.json', members)
                self.assertIn('uploads/test1.txt', members)
                self.assertIn('documents/test2.txt', members)
            
            # 清理
            os.remove(archive_path)
    
    def test_create_archive_with_temp_files(self):
        """测试创建归档并清理临时文件"""
        with self.app.app_context():
            import os
            from datetime import datetime
            
            # 创建临时文件
            temp_file = self._create_test_file(self.test_dir, 'temp.db', b'temp database')
            
            engine = BackupEngine(self.app)
            
            files = [
                {
                    'source_path': temp_file,
                    'archive_path': 'database/app.db',
                    'file_type': 'database',
                    'size': os.path.getsize(temp_file),
                    'hash': engine._calculate_file_hash(temp_file),
                    'modified': datetime.now(),
                    'is_temp': True  # 标记为临时文件
                }
            ]
            
            archive_path, file_size, file_hash = engine._create_archive(files, self.output_dir)
            
            # 验证归档创建成功
            self.assertTrue(os.path.exists(archive_path))
            
            # 验证临时文件已被清理
            self.assertFalse(os.path.exists(temp_file))
            
            # 清理
            os.remove(archive_path)
    
    def test_create_archive_filename_format(self):
        """测试归档文件名格式"""
        with self.app.app_context():
            import os
            import re
            
            engine = BackupEngine(self.app)
            archive_path, _, _ = engine._create_archive([], self.output_dir)
            
            filename = os.path.basename(archive_path)
            
            # 验证文件名格式：backup_YYYYMMDD_HHMMSS.tar.gz
            pattern = r'^backup_\d{8}_\d{6}\.tar\.gz$'
            self.assertIsNotNone(re.match(pattern, filename))
            
            # 清理
            os.remove(archive_path)
    
    def test_create_archive_metadata_content(self):
        """测试归档元数据内容"""
        with self.app.app_context():
            import os
            import tarfile
            import json
            from datetime import datetime
            
            # 创建测试文件
            test_file = self._create_test_file(self.test_dir, 'test.jpg', b'image data')
            
            engine = BackupEngine(self.app)
            
            files = [
                {
                    'source_path': test_file,
                    'archive_path': 'uploads/test.jpg',
                    'file_type': 'upload',
                    'size': os.path.getsize(test_file),
                    'hash': engine._calculate_file_hash(test_file),
                    'modified': datetime.now(),
                    'is_temp': False
                }
            ]
            
            archive_path, _, _ = engine._create_archive(files, self.output_dir)
            
            # 提取并验证元数据
            with tarfile.open(archive_path, 'r:gz') as tar:
                metadata_member = tar.getmember('metadata.json')
                metadata_file = tar.extractfile(metadata_member)
                metadata = json.load(metadata_file)
                
                # 验证元数据结构
                self.assertIn('version', metadata)
                self.assertEqual(metadata['version'], '1.0')
                self.assertIn('created_at', metadata)
                self.assertIn('files', metadata)
                self.assertIn('statistics', metadata)
                
                # 验证统计信息
                stats = metadata['statistics']
                self.assertEqual(stats['total_files'], 1)
                self.assertEqual(stats['uploads_count'], 1)
                self.assertEqual(stats['docs_count'], 0)
                self.assertGreater(stats['total_size_bytes'], 0)
                
                # 验证文件列表
                self.assertEqual(len(metadata['files']['uploads']), 1)
                self.assertEqual(metadata['files']['uploads'][0]['path'], 'uploads/test.jpg')
            
            # 清理
            os.remove(archive_path)
    
    def test_create_archive_with_database_file(self):
        """测试创建包含数据库文件的归档"""
        with self.app.app_context():
            import os
            import tarfile
            import json
            from datetime import datetime
            
            # 创建测试数据库文件
            db_file = self._create_test_file(self.test_dir, 'app.db', b'database content')
            
            engine = BackupEngine(self.app)
            
            files = [
                {
                    'source_path': db_file,
                    'archive_path': 'database/app.db',
                    'file_type': 'database',
                    'size': os.path.getsize(db_file),
                    'hash': engine._calculate_file_hash(db_file),
                    'modified': datetime.now(),
                    'is_temp': False
                }
            ]
            
            archive_path, _, _ = engine._create_archive(files, self.output_dir)
            
            # 验证归档内容
            with tarfile.open(archive_path, 'r:gz') as tar:
                members = tar.getnames()
                self.assertIn('database/app.db', members)
                
                # 验证元数据
                metadata_file = tar.extractfile('metadata.json')
                metadata = json.load(metadata_file)
                
                self.assertIsNotNone(metadata['files']['database'])
                self.assertEqual(metadata['files']['database']['path'], 'database/app.db')
                self.assertGreater(metadata['statistics']['db_size_bytes'], 0)
            
            # 清理
            os.remove(archive_path)
    
    def test_create_archive_hash_calculation(self):
        """测试归档文件哈希计算"""
        with self.app.app_context():
            import os
            import hashlib
            
            engine = BackupEngine(self.app)
            archive_path, file_size, file_hash = engine._create_archive([], self.output_dir)
            
            # 手动计算哈希值进行验证
            sha256_hash = hashlib.sha256()
            with open(archive_path, 'rb') as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            expected_hash = sha256_hash.hexdigest()
            
            self.assertEqual(file_hash, expected_hash)
            
            # 清理
            os.remove(archive_path)
    
    def test_create_archive_error_handling(self):
        """测试归档创建错误处理"""
        with self.app.app_context():
            import os
            from datetime import datetime
            
            engine = BackupEngine(self.app)
            
            # 使用不存在的源文件路径
            files = [
                {
                    'source_path': '/nonexistent/path/file.txt',
                    'archive_path': 'uploads/file.txt',
                    'file_type': 'upload',
                    'size': 100,
                    'hash': 'abc123',
                    'modified': datetime.now(),
                    'is_temp': False
                }
            ]
            
            # tarfile会在添加不存在的文件时抛出FileNotFoundError
            # 我们的_create_archive会捕获并转换为RuntimeError
            with self.assertRaises(RuntimeError) as context:
                engine._create_archive(files, self.output_dir)
            
            self.assertIn('创建备份归档失败', str(context.exception))
    
    def test_generate_backup_metadata(self):
        """测试生成备份元数据"""
        with self.app.app_context():
            from datetime import datetime
            
            engine = BackupEngine(self.app)
            
            files = [
                {
                    'archive_path': 'database/app.db',
                    'file_type': 'database',
                    'size': 1000,
                    'hash': 'hash1'
                },
                {
                    'archive_path': 'uploads/file1.jpg',
                    'file_type': 'upload',
                    'size': 500,
                    'hash': 'hash2'
                },
                {
                    'archive_path': 'uploads/file2.jpg',
                    'file_type': 'upload',
                    'size': 300,
                    'hash': 'hash3'
                },
                {
                    'archive_path': 'documents/doc1.md',
                    'file_type': 'document',
                    'size': 200,
                    'hash': 'hash4'
                }
            ]
            
            metadata = engine._generate_backup_metadata(files)
            
            # 验证元数据结构
            self.assertEqual(metadata['version'], '1.0')
            self.assertIn('created_at', metadata)
            
            # 验证统计信息
            stats = metadata['statistics']
            self.assertEqual(stats['total_files'], 4)
            self.assertEqual(stats['total_size_bytes'], 2000)
            self.assertEqual(stats['db_size_bytes'], 1000)
            self.assertEqual(stats['uploads_count'], 2)
            self.assertEqual(stats['uploads_size_bytes'], 800)
            self.assertEqual(stats['docs_count'], 1)
            self.assertEqual(stats['docs_size_bytes'], 200)
            
            # 验证文件列表
            self.assertIsNotNone(metadata['files']['database'])
            self.assertEqual(len(metadata['files']['uploads']), 2)
            self.assertEqual(len(metadata['files']['documents']), 1)


class TestCollectFiles(PlanningTestCase):
    """测试文件收集功能"""
    
    def setUp(self):
        """设置测试环境"""
        super().setUp()
        import os
        import tempfile
        from runtime_paths import get_data_dir
        
        # 创建测试数据目录结构
        self.data_dir = get_data_dir()
        self.uploads_dir = os.path.join(self.data_dir, 'uploads')
        self.jobs_dir = os.path.join(self.data_dir, 'jobs')
        
        os.makedirs(self.uploads_dir, exist_ok=True)
        os.makedirs(self.jobs_dir, exist_ok=True)
    
    def tearDown(self):
        """清理测试环境"""
        import os
        import shutil
        
        # 清理测试文件
        if os.path.exists(self.uploads_dir):
            for root, dirs, files in os.walk(self.uploads_dir):
                for f in files:
                    try:
                        os.remove(os.path.join(root, f))
                    except:
                        pass
        
        if os.path.exists(self.jobs_dir):
            for root, dirs, files in os.walk(self.jobs_dir):
                for f in files:
                    try:
                        os.remove(os.path.join(root, f))
                    except:
                        pass
        
        super().tearDown()
    
    def _create_test_file(self, directory, filename, content=b"test content"):
        """创建测试文件"""
        import os
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, filename)
        with open(file_path, 'wb') as f:
            f.write(content)
        return file_path
    
    def test_collect_files_full_backup_empty(self):
        """测试完整备份（无文件）"""
        with self.app.app_context():
            engine = BackupEngine(self.app)
            files = engine._collect_files('full')
            
            # 应该至少包含数据库文件
            self.assertGreaterEqual(len(files), 1)
            
            # 检查数据库文件
            db_files = [f for f in files if f['file_type'] == 'database']
            self.assertEqual(len(db_files), 1)
            self.assertEqual(db_files[0]['archive_path'], 'database/app.db')
            self.assertTrue(db_files[0]['is_temp'])
    
    def test_collect_files_full_backup_with_uploads(self):
        """测试完整备份（包含上传文件）"""
        with self.app.app_context():
            import os
            # 创建测试上传文件
            self._create_test_file(self.uploads_dir, 'test1.jpg', b'image data 1')
            self._create_test_file(os.path.join(self.uploads_dir, 'avatars'), 'user1.png', b'avatar data')
            
            engine = BackupEngine(self.app)
            files = engine._collect_files('full')
            
            # 检查上传文件
            upload_files = [f for f in files if f['file_type'] == 'upload']
            self.assertEqual(len(upload_files), 2)
            
            # 验证文件路径
            archive_paths = [f['archive_path'] for f in upload_files]
            self.assertIn('uploads/test1.jpg', archive_paths)
            self.assertIn('uploads/avatars/user1.png', archive_paths)
    
    def test_collect_files_full_backup_with_documents(self):
        """测试完整备份（包含文档文件）"""
        with self.app.app_context():
            import os
            # 创建测试文档文件
            self._create_test_file(self.jobs_dir, 'readme.md', b'# README')
            self._create_test_file(os.path.join(self.jobs_dir, 'project1'), 'doc1.md', b'# Doc 1')
            self._create_test_file(os.path.join(self.jobs_dir, 'project1'), 'notes.txt', b'notes')  # 非.md文件
            
            engine = BackupEngine(self.app)
            files = engine._collect_files('full')
            
            # 检查文档文件（仅.md文件）
            doc_files = [f for f in files if f['file_type'] == 'document']
            self.assertEqual(len(doc_files), 2)
            
            # 验证文件路径
            archive_paths = [f['archive_path'] for f in doc_files]
            self.assertIn('documents/readme.md', archive_paths)
            self.assertIn('documents/project1/doc1.md', archive_paths)
            
            # 确认非.md文件未被收集
            self.assertNotIn('documents/project1/notes.txt', archive_paths)
    
    def test_collect_files_full_backup_complete(self):
        """测试完整备份（包含所有类型文件）"""
        with self.app.app_context():
            # 创建各类测试文件
            self._create_test_file(self.uploads_dir, 'image.jpg', b'image')
            self._create_test_file(self.jobs_dir, 'doc.md', b'# Doc')
            
            engine = BackupEngine(self.app)
            files = engine._collect_files('full')
            
            # 验证包含所有类型
            file_types = set(f['file_type'] for f in files)
            self.assertIn('database', file_types)
            self.assertIn('upload', file_types)
            self.assertIn('document', file_types)
            
            # 验证文件信息完整性
            for file_info in files:
                self.assertIn('source_path', file_info)
                self.assertIn('archive_path', file_info)
                self.assertIn('file_type', file_info)
                self.assertIn('size', file_info)
                self.assertIn('hash', file_info)
                self.assertIn('modified', file_info)
                self.assertGreater(file_info['size'], 0)
                self.assertEqual(len(file_info['hash']), 64)  # SHA256
    
    def test_collect_files_incremental_backup_no_changes(self):
        """测试增量备份（无变更）"""
        with self.app.app_context():
            from models import BackupFileTracker
            from datetime import datetime
            import os
            
            # 创建测试文件
            test_file = self._create_test_file(self.uploads_dir, 'test.jpg', b'test data')
            
            # 先执行完整备份
            engine = BackupEngine(self.app)
            full_files = engine._collect_files('full')
            
            # 创建文件追踪记录
            for file_info in full_files:
                if not file_info.get('is_temp'):
                    tracker = BackupFileTracker(
                        file_path=file_info['original_path'],
                        file_type=file_info['file_type'],
                        last_modified=file_info['modified'],
                        file_size_bytes=file_info['size'],
                        file_hash=file_info['hash'],
                        last_backup_id=1
                    )
                    db.session.add(tracker)
            db.session.commit()
            
            # 执行增量备份（文件未变更）
            incremental_files = engine._collect_files('incremental')
            
            # 数据库文件可能会变化（因为添加了追踪记录），但上传文件应该被跳过
            upload_files = [f for f in incremental_files if f['file_type'] == 'upload']
            self.assertEqual(len(upload_files), 0)
    
    def test_collect_files_incremental_backup_with_changes(self):
        """测试增量备份（有变更）"""
        with self.app.app_context():
            from models import BackupFileTracker
            from datetime import datetime, timedelta
            import os
            import time
            
            # 创建测试文件
            test_file1 = self._create_test_file(self.uploads_dir, 'old.jpg', b'old data')
            
            # 先执行完整备份
            engine = BackupEngine(self.app)
            full_files = engine._collect_files('full')
            
            # 创建文件追踪记录
            for file_info in full_files:
                if not file_info.get('is_temp'):
                    tracker = BackupFileTracker(
                        file_path=file_info['original_path'],
                        file_type=file_info['file_type'],
                        last_modified=file_info['modified'] - timedelta(seconds=10),  # 设置为更早的时间
                        file_size_bytes=file_info['size'],
                        file_hash=file_info['hash'],
                        last_backup_id=1
                    )
                    db.session.add(tracker)
            db.session.commit()
            
            # 等待一小段时间确保文件时间戳不同
            time.sleep(0.1)
            
            # 创建新文件
            test_file2 = self._create_test_file(self.uploads_dir, 'new.jpg', b'new data')
            
            # 修改旧文件
            with open(test_file1, 'wb') as f:
                f.write(b'modified data')
            
            # 执行增量备份
            incremental_files = engine._collect_files('incremental')
            
            # 应该包含新文件和修改的文件
            upload_files = [f for f in incremental_files if f['file_type'] == 'upload']
            self.assertGreaterEqual(len(upload_files), 2)
            
            # 验证包含新文件
            archive_paths = [f['archive_path'] for f in upload_files]
            self.assertIn('uploads/new.jpg', archive_paths)
    
    def test_collect_files_incremental_backup_new_files_only(self):
        """测试增量备份（仅新文件）"""
        with self.app.app_context():
            from models import BackupFileTracker
            from datetime import datetime
            import time
            
            # 创建初始文件
            test_file1 = self._create_test_file(self.uploads_dir, 'existing.jpg', b'existing')
            
            # 执行完整备份
            engine = BackupEngine(self.app)
            full_files = engine._collect_files('full')
            
            # 创建追踪记录
            for file_info in full_files:
                if not file_info.get('is_temp'):
                    tracker = BackupFileTracker(
                        file_path=file_info['original_path'],
                        file_type=file_info['file_type'],
                        last_modified=file_info['modified'],
                        file_size_bytes=file_info['size'],
                        file_hash=file_info['hash'],
                        last_backup_id=1
                    )
                    db.session.add(tracker)
            db.session.commit()
            
            # 等待确保时间戳不同
            time.sleep(0.1)
            
            # 添加新文件
            test_file2 = self._create_test_file(self.uploads_dir, 'new_file.jpg', b'new content')
            
            # 执行增量备份
            incremental_files = engine._collect_files('incremental')
            
            # 应该只包含新文件
            upload_files = [f for f in incremental_files if f['file_type'] == 'upload']
            self.assertEqual(len(upload_files), 1)
            self.assertEqual(upload_files[0]['archive_path'], 'uploads/new_file.jpg')
    
    def test_calculate_file_hash(self):
        """测试文件哈希计算"""
        with self.app.app_context():
            import hashlib
            
            # 创建测试文件
            test_content = b'test content for hashing'
            test_file = self._create_test_file(self.uploads_dir, 'hash_test.txt', test_content)
            
            engine = BackupEngine(self.app)
            calculated_hash = engine._calculate_file_hash(test_file)
            
            # 验证哈希值
            expected_hash = hashlib.sha256(test_content).hexdigest()
            self.assertEqual(calculated_hash, expected_hash)
            self.assertEqual(len(calculated_hash), 64)
    
    def test_collect_database_file_with_locking(self):
        """测试收集数据库文件（处理锁定）"""
        with self.app.app_context():
            from runtime_paths import get_default_database_path
            import os
            
            db_path = get_default_database_path()
            
            # 确保数据库文件存在
            self.assertTrue(os.path.exists(db_path))
            
            engine = BackupEngine(self.app)
            db_file_info = engine._collect_database_file(db_path, 'full', None)
            
            # 验证返回的文件信息
            self.assertIsNotNone(db_file_info)
            self.assertEqual(db_file_info['file_type'], 'database')
            self.assertEqual(db_file_info['archive_path'], 'database/app.db')
            self.assertTrue(db_file_info['is_temp'])
            self.assertGreater(db_file_info['size'], 0)
            self.assertEqual(len(db_file_info['hash']), 64)
            
            # 验证临时文件存在
            self.assertTrue(os.path.exists(db_file_info['source_path']))
            
            # 清理临时文件
            if os.path.exists(db_file_info['source_path']):
                os.remove(db_file_info['source_path'])
    
    def test_collect_directory_files_recursive(self):
        """测试递归收集目录文件"""
        with self.app.app_context():
            import os
            # 创建多层目录结构
            self._create_test_file(self.uploads_dir, 'root.jpg', b'root')
            self._create_test_file(os.path.join(self.uploads_dir, 'level1'), 'file1.jpg', b'level1')
            self._create_test_file(os.path.join(self.uploads_dir, 'level1', 'level2'), 'file2.jpg', b'level2')
            
            engine = BackupEngine(self.app)
            files = engine._collect_directory_files(self.uploads_dir, 'upload', 'full', None)
            
            # 验证收集了所有层级的文件
            self.assertEqual(len(files), 3)
            
            # 验证路径结构
            archive_paths = [f['archive_path'] for f in files]
            self.assertIn('uploads/root.jpg', archive_paths)
            self.assertIn('uploads/level1/file1.jpg', archive_paths)
            self.assertIn('uploads/level1/level2/file2.jpg', archive_paths)
    
    def test_collect_directory_files_with_pattern(self):
        """测试按模式收集文件"""
        with self.app.app_context():
            # 创建不同类型的文件
            self._create_test_file(self.jobs_dir, 'doc1.md', b'# Doc 1')
            self._create_test_file(self.jobs_dir, 'doc2.md', b'# Doc 2')
            self._create_test_file(self.jobs_dir, 'readme.txt', b'readme')
            self._create_test_file(self.jobs_dir, 'config.yaml', b'config')
            
            engine = BackupEngine(self.app)
            files = engine._collect_directory_files(self.jobs_dir, 'document', 'full', None, file_pattern='.md')
            
            # 应该只收集.md文件
            self.assertEqual(len(files), 2)
            
            # 验证文件名
            archive_paths = [f['archive_path'] for f in files]
            self.assertIn('documents/doc1.md', archive_paths)
            self.assertIn('documents/doc2.md', archive_paths)
            self.assertNotIn('documents/readme.txt', archive_paths)
            self.assertNotIn('documents/config.yaml', archive_paths)



class TestEncryptArchive(PlanningTestCase):
    """测试备份加密功能 - Task 5.4"""
    
    def setUp(self):
        """设置测试环境"""
        super().setUp()
        import tempfile
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """清理测试环境"""
        import os
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        super().tearDown()
    
    def _create_test_archive(self, content=b"test archive content"):
        """创建测试归档文件"""
        import os
        archive_path = os.path.join(self.test_dir, 'test_backup.tar.gz')
        with open(archive_path, 'wb') as f:
            f.write(content)
        return archive_path
    
    def test_encrypt_archive_basic(self):
        """测试基本加密功能"""
        with self.app.app_context():
            import os
            
            # 创建测试归档
            archive_path = self._create_test_archive(b"test content for encryption")
            original_size = os.path.getsize(archive_path)
            
            engine = BackupEngine(self.app)
            password = "test_password_123"
            
            # 执行加密
            encrypted_path = engine._encrypt_archive(archive_path, password)
            
            # 验证加密文件存在
            self.assertTrue(os.path.exists(encrypted_path))
            self.assertEqual(encrypted_path, archive_path + '.enc')
            
            # 验证原始文件已删除
            self.assertFalse(os.path.exists(archive_path))
            
            # 验证加密文件大小（应该包含256字节头部 + 填充后的数据）
            encrypted_size = os.path.getsize(encrypted_path)
            self.assertGreater(encrypted_size, 256)  # 至少包含头部
    
    def test_encrypt_archive_header_format(self):
        """测试加密文件头部格式"""
        with self.app.app_context():
            import os
            import struct
            
            # 创建测试归档
            archive_path = self._create_test_archive(b"test content")
            
            engine = BackupEngine(self.app)
            encrypted_path = engine._encrypt_archive(archive_path, "password123")
            
            # 读取并验证头部
            with open(encrypted_path, 'rb') as f:
                header = f.read(256)
            
            # 解析头部
            magic, salt, iv, iterations, reserved = struct.unpack('8s32s16sI196s', header)
            
            # 验证魔数
            self.assertEqual(magic, b'BKPENC01')
            
            # 验证盐值和IV长度
            self.assertEqual(len(salt), 32)
            self.assertEqual(len(iv), 16)
            
            # 验证迭代次数
            self.assertEqual(iterations, 100000)
            
            # 验证保留字段
            self.assertEqual(reserved, b'\x00' * 196)
    
    def test_encrypt_archive_different_passwords(self):
        """测试不同密码产生不同的加密结果"""
        with self.app.app_context():
            import os
            
            # 创建两个相同内容的归档
            content = b"same content for both files"
            archive_path1 = self._create_test_archive(content)
            archive_path2 = os.path.join(self.test_dir, 'test_backup2.tar.gz')
            with open(archive_path2, 'wb') as f:
                f.write(content)
            
            engine = BackupEngine(self.app)
            
            # 使用不同密码加密
            encrypted_path1 = engine._encrypt_archive(archive_path1, "password1")
            encrypted_path2 = engine._encrypt_archive(archive_path2, "password2")
            
            # 读取加密内容
            with open(encrypted_path1, 'rb') as f:
                encrypted_content1 = f.read()
            with open(encrypted_path2, 'rb') as f:
                encrypted_content2 = f.read()
            
            # 验证加密结果不同
            self.assertNotEqual(encrypted_content1, encrypted_content2)
    
    def test_encrypt_archive_same_password_different_salt(self):
        """测试相同密码但不同盐值产生不同结果"""
        with self.app.app_context():
            import os
            
            # 创建两个相同内容的归档
            content = b"same content"
            archive_path1 = self._create_test_archive(content)
            archive_path2 = os.path.join(self.test_dir, 'test_backup2.tar.gz')
            with open(archive_path2, 'wb') as f:
                f.write(content)
            
            engine = BackupEngine(self.app)
            password = "same_password"
            
            # 使用相同密码加密
            encrypted_path1 = engine._encrypt_archive(archive_path1, password)
            encrypted_path2 = engine._encrypt_archive(archive_path2, password)
            
            # 读取加密内容
            with open(encrypted_path1, 'rb') as f:
                encrypted_content1 = f.read()
            with open(encrypted_path2, 'rb') as f:
                encrypted_content2 = f.read()
            
            # 验证加密结果不同（因为盐值和IV不同）
            self.assertNotEqual(encrypted_content1, encrypted_content2)
    
    def test_encrypt_archive_large_file(self):
        """测试加密大文件"""
        with self.app.app_context():
            import os
            
            # 创建较大的测试文件（1MB）
            large_content = b"x" * (1024 * 1024)
            archive_path = self._create_test_archive(large_content)
            
            engine = BackupEngine(self.app)
            encrypted_path = engine._encrypt_archive(archive_path, "password")
            
            # 验证加密成功
            self.assertTrue(os.path.exists(encrypted_path))
            
            # 验证文件大小合理（应该略大于原始大小，因为有头部和填充）
            encrypted_size = os.path.getsize(encrypted_path)
            self.assertGreater(encrypted_size, len(large_content))
            self.assertLessEqual(encrypted_size, len(large_content) + 256 + 16)  # 头部 + 最大填充
    
    def test_encrypt_archive_empty_file(self):
        """测试加密空文件"""
        with self.app.app_context():
            import os
            
            # 创建空文件
            archive_path = self._create_test_archive(b"")
            
            engine = BackupEngine(self.app)
            encrypted_path = engine._encrypt_archive(archive_path, "password")
            
            # 验证加密成功
            self.assertTrue(os.path.exists(encrypted_path))
            
            # 验证文件大小（头部 + 填充后的空数据）
            encrypted_size = os.path.getsize(encrypted_path)
            self.assertEqual(encrypted_size, 256 + 16)  # 头部 + 一个AES块
    
    def test_encrypt_archive_unicode_password(self):
        """测试使用Unicode密码加密"""
        with self.app.app_context():
            import os
            
            archive_path = self._create_test_archive(b"test content")
            
            engine = BackupEngine(self.app)
            # 使用包含中文的密码
            password = "密码测试123"
            
            encrypted_path = engine._encrypt_archive(archive_path, password)
            
            # 验证加密成功
            self.assertTrue(os.path.exists(encrypted_path))
    
    def test_encrypt_archive_special_characters_password(self):
        """测试使用特殊字符密码加密"""
        with self.app.app_context():
            import os
            
            archive_path = self._create_test_archive(b"test content")
            
            engine = BackupEngine(self.app)
            # 使用包含特殊字符的密码
            password = "p@ssw0rd!#$%^&*()"
            
            encrypted_path = engine._encrypt_archive(archive_path, password)
            
            # 验证加密成功
            self.assertTrue(os.path.exists(encrypted_path))
    
    def test_encrypt_archive_error_handling(self):
        """测试加密错误处理"""
        with self.app.app_context():
            engine = BackupEngine(self.app)
            
            # 使用不存在的文件路径
            with self.assertRaises(RuntimeError) as context:
                engine._encrypt_archive('/nonexistent/file.tar.gz', 'password')
            
            self.assertIn('加密备份文件失败', str(context.exception))
    
    def test_encrypt_archive_cleanup_on_error(self):
        """测试加密失败时清理临时文件"""
        with self.app.app_context():
            import os
            
            # 创建测试文件
            archive_path = self._create_test_archive(b"test")
            encrypted_path = archive_path + '.enc'
            
            engine = BackupEngine(self.app)
            
            # 模拟加密过程中的错误（通过删除原始文件）
            os.remove(archive_path)
            
            # 尝试加密应该失败
            with self.assertRaises(RuntimeError):
                engine._encrypt_archive(archive_path, 'password')
            
            # 验证没有留下加密文件
            self.assertFalse(os.path.exists(encrypted_path))
    
    def test_encrypt_archive_pkcs7_padding(self):
        """测试PKCS7填充"""
        with self.app.app_context():
            import os
            
            # 创建不同大小的文件测试填充
            for size in [1, 15, 16, 17, 31, 32, 33]:
                archive_path = self._create_test_archive(b"x" * size)
                
                engine = BackupEngine(self.app)
                encrypted_path = engine._encrypt_archive(archive_path, "password")
                
                # 读取加密数据（跳过头部）
                with open(encrypted_path, 'rb') as f:
                    f.read(256)  # 跳过头部
                    encrypted_data = f.read()
                
                # 验证加密数据是16字节的倍数（AES块大小）
                self.assertEqual(len(encrypted_data) % 16, 0)
                
                # 清理
                os.remove(encrypted_path)
    
    def test_encrypt_archive_aes256_key_derivation(self):
        """测试AES-256密钥派生"""
        with self.app.app_context():
            import os
            import struct
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.backends import default_backend
            
            archive_path = self._create_test_archive(b"test content")
            password = "test_password"
            
            engine = BackupEngine(self.app)
            encrypted_path = engine._encrypt_archive(archive_path, password)
            
            # 读取头部获取盐值和迭代次数
            with open(encrypted_path, 'rb') as f:
                header = f.read(256)
            
            magic, salt, iv, iterations, reserved = struct.unpack('8s32s16sI196s', header)
            
            # 验证可以使用相同参数派生密钥
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,  # AES-256需要32字节
                salt=salt,
                iterations=iterations,
                backend=default_backend()
            )
            derived_key = kdf.derive(password.encode('utf-8'))
            
            # 验证密钥长度
            self.assertEqual(len(derived_key), 32)


class TestEncryptArchiveIntegration(PlanningTestCase):
    """测试加密功能集成 - Task 5.4"""
    
    def _create_valid_config_with_encryption(self):
        """创建启用加密的有效配置"""
        config = BackupConfig(
            enabled=True,
            storage_type='ftp',
            schedule_type='daily',
            retention_count=10,
            backup_mode='full',
            encryption_enabled=True,
            encryption_key_hash='test_encryption_password_123',
            ftp_host='ftp.example.com',
            ftp_port=21,
            ftp_username='testuser',
            ftp_password='testpass',
            ftp_path='/backups',
            notification_enabled=False
        )
        db.session.add(config)
        db.session.commit()
        return config
    
    def test_execute_backup_with_encryption(self):
        """测试执行加密备份"""
        with self.app.app_context():
            config = self._create_valid_config_with_encryption()
            
            engine = BackupEngine(self.app)
            backup_job = engine.execute_backup(trigger_type='manual')
            
            # 验证备份任务标记为已加密
            self.assertTrue(backup_job.is_encrypted)
            self.assertEqual(backup_job.status, 'success')
            
            # 验证文件名包含.enc扩展名
            self.assertTrue(backup_job.filename.endswith('.tar.gz.enc'))
    
    def test_execute_backup_encryption_without_password(self):
        """测试加密启用但未配置密码"""
        with self.app.app_context():
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                retention_count=10,
                backup_mode='full',
                encryption_enabled=True,
                encryption_key_hash=None,  # 未配置密码
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups',
                notification_enabled=False
            )
            db.session.add(config)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # 应该抛出RuntimeError（包装了ValueError）
            with self.assertRaises(RuntimeError) as context:
                engine.execute_backup()
            
            self.assertIn('加密已启用但未配置加密密码', str(context.exception))
    
    def test_execute_backup_without_encryption(self):
        """测试不加密的备份"""
        with self.app.app_context():
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                retention_count=10,
                backup_mode='full',
                encryption_enabled=False,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups',
                notification_enabled=False
            )
            db.session.add(config)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            backup_job = engine.execute_backup()
            
            # 验证备份未加密
            self.assertFalse(backup_job.is_encrypted)
            
            # 验证文件名不包含.enc扩展名
            self.assertTrue(backup_job.filename.endswith('.tar.gz'))
            self.assertFalse(backup_job.filename.endswith('.enc'))
    
    def test_encrypted_backup_file_hash_updated(self):
        """测试加密后文件哈希值更新"""
        with self.app.app_context():
            config = self._create_valid_config_with_encryption()
            
            engine = BackupEngine(self.app)
            backup_job = engine.execute_backup()
            
            # 验证文件哈希值存在且为SHA256格式
            self.assertIsNotNone(backup_job.file_hash)
            self.assertEqual(len(backup_job.file_hash), 64)
            
            # 验证文件大小已更新（加密后的大小）
            self.assertIsNotNone(backup_job.file_size_bytes)
            self.assertGreater(backup_job.file_size_bytes, 256)  # 至少包含头部



class TestUploadBackup(PlanningTestCase):
    """测试备份上传功能"""
    
    def setUp(self):
        """设置测试环境"""
        super().setUp()
        import os
        import tempfile
        
        # 创建临时测试文件
        self.test_dir = tempfile.mkdtemp()
        self.test_archive = os.path.join(self.test_dir, 'backup_20240115_120000.tar.gz')
        with open(self.test_archive, 'wb') as f:
            f.write(b'test backup content')
    
    def tearDown(self):
        """清理测试环境"""
        import os
        import shutil
        
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        
        super().tearDown()
    
    def test_upload_backup_ftp_success(self):
        """测试FTP上传成功"""
        with self.app.app_context():
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='ftp',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            
            engine = BackupEngine(self.app)
            
            # Mock FTP adapter
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.upload.return_value = (True, 'Successfully uploaded to /backups/backup_20240115_120000.tar.gz')
                MockAdapter.return_value = mock_adapter
                
                success, message = engine._upload_backup(self.test_archive, config)
                
                self.assertTrue(success)
                self.assertIn('Successfully uploaded', message)
                
                # 验证适配器被正确初始化
                MockAdapter.assert_called_once_with(
                    host='ftp.example.com',
                    port=21,
                    username='testuser',
                    password='testpass',
                    base_path='/backups'
                )
                
                # 验证upload方法被调用
                mock_adapter.upload.assert_called_once()
    
    def test_upload_backup_email_success(self):
        """测试邮件上传成功"""
        with self.app.app_context():
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='email',
                email_recipient='backup@example.com'
            )
            
            engine = BackupEngine(self.app)
            
            # Mock Email adapter
            with patch('services.storage.email_adapter.EmailStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.upload.return_value = (True, 'Backup file sent to backup@example.com')
                MockAdapter.return_value = mock_adapter
                
                success, message = engine._upload_backup(self.test_archive, config)
                
                self.assertTrue(success)
                self.assertIn('sent to', message)
                
                # 验证适配器被正确初始化
                MockAdapter.assert_called_once_with(recipient='backup@example.com')
    
    def test_upload_backup_s3_success(self):
        """测试S3上传成功"""
        with self.app.app_context():
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='s3',
                s3_endpoint='https://s3.amazonaws.com',
                s3_bucket='my-backup-bucket',
                s3_access_key='AKIAIOSFODNN7EXAMPLE',
                s3_secret_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                s3_path_prefix='backups/',
                s3_region='us-east-1'
            )
            
            engine = BackupEngine(self.app)
            
            # Mock S3 adapter
            with patch('services.storage.s3_adapter.S3StorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.upload.return_value = (True, 'Successfully uploaded to s3://my-backup-bucket/backups/backup_20240115_120000.tar.gz')
                MockAdapter.return_value = mock_adapter
                
                success, message = engine._upload_backup(self.test_archive, config)
                
                self.assertTrue(success)
                self.assertIn('Successfully uploaded', message)
                
                # 验证适配器被正确初始化
                MockAdapter.assert_called_once_with(
                    endpoint='https://s3.amazonaws.com',
                    bucket='my-backup-bucket',
                    access_key='AKIAIOSFODNN7EXAMPLE',
                    secret_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                    path_prefix='backups/',
                    region='us-east-1'
                )
    
    def test_upload_backup_ftp_failure(self):
        """测试FTP上传失败"""
        with self.app.app_context():
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='ftp',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            
            engine = BackupEngine(self.app)
            
            # Mock FTP adapter with failure
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.upload.return_value = (False, 'Connection timeout')
                MockAdapter.return_value = mock_adapter
                
                success, message = engine._upload_backup(self.test_archive, config)
                
                self.assertFalse(success)
                self.assertIn('Connection timeout', message)
    
    def test_upload_backup_unsupported_storage_type(self):
        """测试不支持的存储类型"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='unsupported'
            )
            
            engine = BackupEngine(self.app)
            success, message = engine._upload_backup(self.test_archive, config)
            
            self.assertFalse(success)
            self.assertIn('不支持的存储类型', message)
    
    def test_upload_backup_exception_handling(self):
        """测试上传异常处理"""
        with self.app.app_context():
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='ftp',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            
            engine = BackupEngine(self.app)
            
            # Mock FTP adapter to raise exception
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                MockAdapter.side_effect = Exception('Adapter initialization failed')
                
                success, message = engine._upload_backup(self.test_archive, config)
                
                self.assertFalse(success)
                self.assertIn('上传备份文件失败', message)


class TestCleanupOldBackups(PlanningTestCase):
    """测试旧备份清理功能"""
    
    def test_cleanup_no_backups(self):
        """测试没有备份时的清理"""
        with self.app.app_context():
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                retention_count=10,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            db.session.add(config)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # 应该不抛出异常
            engine._cleanup_old_backups(config)
            
            # 验证没有备份被删除
            backups = BackupJob.query.all()
            self.assertEqual(len(backups), 0)
    
    def test_cleanup_below_retention_count(self):
        """测试备份数量未超过保留数量"""
        with self.app.app_context():
            from datetime import datetime, timedelta
            
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                retention_count=10,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            db.session.add(config)
            db.session.commit()
            
            # 创建5个成功的备份
            for i in range(5):
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type='ftp',
                    filename=f'backup_{i}.tar.gz',
                    started_at=datetime.utcnow() - timedelta(days=i),
                    completed_at=datetime.utcnow() - timedelta(days=i)
                )
                db.session.add(backup)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            engine._cleanup_old_backups(config)
            
            # 验证所有备份仍然存在
            backups = BackupJob.query.filter_by(storage_type='ftp', status='success').all()
            self.assertEqual(len(backups), 5)
    
    def test_cleanup_exceeds_retention_count_ftp(self):
        """测试FTP备份超过保留数量时的清理"""
        with self.app.app_context():
            from datetime import datetime, timedelta
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                retention_count=5,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            db.session.add(config)
            db.session.commit()
            
            # 创建10个成功的备份
            for i in range(10):
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type='ftp',
                    filename=f'backup_{i:02d}.tar.gz',
                    started_at=datetime.utcnow() - timedelta(days=9-i),
                    completed_at=datetime.utcnow() - timedelta(days=9-i)
                )
                db.session.add(backup)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # Mock FTP adapter
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.delete.return_value = (True, 'Deleted successfully')
                MockAdapter.return_value = mock_adapter
                
                engine._cleanup_old_backups(config)
                
                # 验证只保留了5个最新的备份
                remaining_backups = BackupJob.query.filter_by(
                    storage_type='ftp',
                    status='success'
                ).all()
                self.assertEqual(len(remaining_backups), 5)
                
                # 验证delete方法被调用了5次（删除5个旧备份）
                self.assertEqual(mock_adapter.delete.call_count, 5)
    
    def test_cleanup_exceeds_retention_count_s3(self):
        """测试S3备份超过保留数量时的清理"""
        with self.app.app_context():
            from datetime import datetime, timedelta
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='s3',
                schedule_type='daily',
                retention_count=3,
                s3_endpoint='https://s3.amazonaws.com',
                s3_bucket='my-backup-bucket',
                s3_access_key='AKIAIOSFODNN7EXAMPLE',
                s3_secret_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                s3_path_prefix='backups/',
                s3_region='us-east-1'
            )
            db.session.add(config)
            db.session.commit()
            
            # 创建7个成功的备份
            for i in range(7):
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type='s3',
                    filename=f'backup_{i:02d}.tar.gz',
                    started_at=datetime.utcnow() - timedelta(days=6-i),
                    completed_at=datetime.utcnow() - timedelta(days=6-i)
                )
                db.session.add(backup)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # Mock S3 adapter
            with patch('services.storage.s3_adapter.S3StorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.delete.return_value = (True, 'Deleted successfully')
                MockAdapter.return_value = mock_adapter
                
                engine._cleanup_old_backups(config)
                
                # 验证只保留了3个最新的备份
                remaining_backups = BackupJob.query.filter_by(
                    storage_type='s3',
                    status='success'
                ).all()
                self.assertEqual(len(remaining_backups), 3)
                
                # 验证delete方法被调用了4次（删除4个旧备份）
                self.assertEqual(mock_adapter.delete.call_count, 4)
    
    def test_cleanup_email_storage(self):
        """测试邮件存储的清理（仅删除数据库记录）"""
        with self.app.app_context():
            from datetime import datetime, timedelta
            
            config = BackupConfig(
                storage_type='email',
                schedule_type='daily',
                retention_count=2,
                email_recipient='backup@example.com'
            )
            db.session.add(config)
            db.session.commit()
            
            # 创建5个成功的邮件备份
            for i in range(5):
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type='email',
                    filename=f'backup_{i:02d}.tar.gz',
                    started_at=datetime.utcnow() - timedelta(days=4-i),
                    completed_at=datetime.utcnow() - timedelta(days=4-i)
                )
                db.session.add(backup)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            engine._cleanup_old_backups(config)
            
            # 验证只保留了2个最新的备份记录
            remaining_backups = BackupJob.query.filter_by(
                storage_type='email',
                status='success'
            ).all()
            self.assertEqual(len(remaining_backups), 2)
    
    def test_cleanup_only_affects_same_storage_type(self):
        """测试清理只影响相同存储类型的备份"""
        with self.app.app_context():
            from datetime import datetime, timedelta
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                retention_count=2,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            db.session.add(config)
            db.session.commit()
            
            # 创建5个FTP备份
            for i in range(5):
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type='ftp',
                    filename=f'backup_ftp_{i:02d}.tar.gz',
                    started_at=datetime.utcnow() - timedelta(days=4-i),
                    completed_at=datetime.utcnow() - timedelta(days=4-i)
                )
                db.session.add(backup)
            
            # 创建3个S3备份
            for i in range(3):
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type='s3',
                    filename=f'backup_s3_{i:02d}.tar.gz',
                    started_at=datetime.utcnow() - timedelta(days=2-i),
                    completed_at=datetime.utcnow() - timedelta(days=2-i)
                )
                db.session.add(backup)
            
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # Mock FTP adapter
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.delete.return_value = (True, 'Deleted successfully')
                MockAdapter.return_value = mock_adapter
                
                engine._cleanup_old_backups(config)
                
                # 验证FTP备份只保留了2个
                ftp_backups = BackupJob.query.filter_by(
                    storage_type='ftp',
                    status='success'
                ).all()
                self.assertEqual(len(ftp_backups), 2)
                
                # 验证S3备份未受影响
                s3_backups = BackupJob.query.filter_by(
                    storage_type='s3',
                    status='success'
                ).all()
                self.assertEqual(len(s3_backups), 3)
    
    def test_cleanup_delete_failure_continues(self):
        """测试删除失败时继续处理其他备份"""
        with self.app.app_context():
            from datetime import datetime, timedelta
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                retention_count=2,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            db.session.add(config)
            db.session.commit()
            
            # 创建5个备份
            for i in range(5):
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type='ftp',
                    filename=f'backup_{i:02d}.tar.gz',
                    started_at=datetime.utcnow() - timedelta(days=4-i),
                    completed_at=datetime.utcnow() - timedelta(days=4-i)
                )
                db.session.add(backup)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # Mock FTP adapter with intermittent failures
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                # 第一次删除失败，其他成功
                mock_adapter.delete.side_effect = [
                    (False, 'Delete failed'),
                    (True, 'Deleted successfully'),
                    (True, 'Deleted successfully')
                ]
                MockAdapter.return_value = mock_adapter
                
                engine._cleanup_old_backups(config)
                
                # 验证仍然保留了2个最新的备份
                remaining_backups = BackupJob.query.filter_by(
                    storage_type='ftp',
                    status='success'
                ).all()
                self.assertEqual(len(remaining_backups), 2)
    
    def test_cleanup_exception_handling(self):
        """测试清理过程中的异常处理"""
        with self.app.app_context():
            from datetime import datetime, timedelta
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                storage_type='ftp',
                schedule_type='daily',
                retention_count=2,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            db.session.add(config)
            db.session.commit()
            
            # 创建5个备份
            for i in range(5):
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type='ftp',
                    filename=f'backup_{i:02d}.tar.gz',
                    started_at=datetime.utcnow() - timedelta(days=4-i),
                    completed_at=datetime.utcnow() - timedelta(days=4-i)
                )
                db.session.add(backup)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # Mock FTP adapter to raise exception
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                MockAdapter.side_effect = Exception('Adapter initialization failed')
                
                # 应该不抛出异常，只记录警告
                engine._cleanup_old_backups(config)
                
                # 验证备份未被删除（因为异常导致回滚）
                remaining_backups = BackupJob.query.filter_by(
                    storage_type='ftp',
                    status='success'
                ).all()
                self.assertEqual(len(remaining_backups), 5)


class TestExecuteBackupWithUploadAndCleanup(PlanningTestCase):
    """测试完整的备份执行流程（包含上传和清理）"""
    
    def test_execute_backup_with_successful_upload(self):
        """测试备份执行成功并上传"""
        with self.app.app_context():
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                retention_count=10,
                backup_mode='full',
                encryption_enabled=False,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups',
                notification_enabled=False
            )
            db.session.add(config)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # Mock storage adapter
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.upload.return_value = (True, 'Successfully uploaded to /backups/backup.tar.gz')
                mock_adapter.delete.return_value = (True, 'Deleted successfully')
                MockAdapter.return_value = mock_adapter
                
                backup_job = engine.execute_backup(trigger_type='manual')
                
                # 验证备份任务成功
                self.assertEqual(backup_job.status, 'success')
                self.assertIsNotNone(backup_job.storage_path)
                self.assertIn('Successfully uploaded', backup_job.storage_path)
                
                # 验证上传方法被调用
                self.assertEqual(mock_adapter.upload.call_count, 1)
    
    def test_execute_backup_with_failed_upload(self):
        """测试备份上传失败"""
        with self.app.app_context():
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                retention_count=10,
                backup_mode='full',
                encryption_enabled=False,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups',
                notification_enabled=False
            )
            db.session.add(config)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # Mock storage adapter with upload failure
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.upload.return_value = (False, 'Connection timeout')
                MockAdapter.return_value = mock_adapter
                
                with self.assertRaises(RuntimeError) as context:
                    engine.execute_backup(trigger_type='manual')
                
                self.assertIn('备份上传失败', str(context.exception))
                
                # 验证备份任务被标记为失败
                backup_job = BackupJob.query.first()
                self.assertEqual(backup_job.status, 'failed')
                self.assertIn('备份上传失败', backup_job.error_message)
    
    def test_execute_backup_cleanup_called_after_upload(self):
        """测试上传成功后调用清理"""
        with self.app.app_context():
            from datetime import datetime, timedelta
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                retention_count=2,
                backup_mode='full',
                encryption_enabled=False,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups',
                notification_enabled=False
            )
            db.session.add(config)
            db.session.commit()
            
            # 创建3个旧备份
            for i in range(3):
                backup = BackupJob(
                    trigger_type='auto',
                    status='success',
                    backup_mode='full',
                    storage_type='ftp',
                    filename=f'old_backup_{i:02d}.tar.gz',
                    started_at=datetime.utcnow() - timedelta(days=3-i),
                    completed_at=datetime.utcnow() - timedelta(days=3-i)
                )
                db.session.add(backup)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # Mock storage adapter
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.upload.return_value = (True, 'Successfully uploaded')
                mock_adapter.delete.return_value = (True, 'Deleted successfully')
                MockAdapter.return_value = mock_adapter
                
                backup_job = engine.execute_backup(trigger_type='manual')
                
                # 验证备份成功
                self.assertEqual(backup_job.status, 'success')
                
                # 验证清理被调用（应该删除2个旧备份，保留最新的2个）
                remaining_backups = BackupJob.query.filter_by(
                    storage_type='ftp',
                    status='success'
                ).all()
                self.assertEqual(len(remaining_backups), 2)
                
                # 验证delete方法被调用了2次
                self.assertEqual(mock_adapter.delete.call_count, 2)




class TestUpdateFileTracker(PlanningTestCase):
    """测试文件变更追踪功能 - Task 5.6"""
    
    def test_update_file_tracker_create_new_records(self):
        """测试创建新的文件追踪记录"""
        with self.app.app_context():
            from models import BackupFileTracker
            from datetime import datetime
            
            engine = BackupEngine(self.app)
            
            # 准备文件列表
            files = [
                {
                    'source_path': '/data/uploads/test1.jpg',
                    'archive_path': 'uploads/test1.jpg',
                    'file_type': 'upload',
                    'size': 1024,
                    'hash': 'abc123',
                    'modified': datetime(2024, 1, 15, 10, 30, 0),
                    'original_path': '/data/uploads/test1.jpg',
                    'is_temp': False
                },
                {
                    'source_path': '/data/jobs/doc1.md',
                    'archive_path': 'documents/doc1.md',
                    'file_type': 'document',
                    'size': 2048,
                    'hash': 'def456',
                    'modified': datetime(2024, 1, 15, 11, 0, 0),
                    'original_path': '/data/jobs/doc1.md',
                    'is_temp': False
                }
            ]
            
            # 执行文件追踪更新
            engine._update_file_tracker(files, backup_job_id=1)
            
            # 验证记录已创建
            trackers = BackupFileTracker.query.all()
            self.assertEqual(len(trackers), 2)
            
            # 验证第一个记录
            tracker1 = BackupFileTracker.query.filter_by(
                file_path='/data/uploads/test1.jpg'
            ).first()
            self.assertIsNotNone(tracker1)
            self.assertEqual(tracker1.file_type, 'upload')
            self.assertEqual(tracker1.file_size_bytes, 1024)
            self.assertEqual(tracker1.file_hash, 'abc123')
            self.assertEqual(tracker1.last_backup_id, 1)
            self.assertEqual(tracker1.last_modified, datetime(2024, 1, 15, 10, 30, 0))
            
            # 验证第二个记录
            tracker2 = BackupFileTracker.query.filter_by(
                file_path='/data/jobs/doc1.md'
            ).first()
            self.assertIsNotNone(tracker2)
            self.assertEqual(tracker2.file_type, 'document')
            self.assertEqual(tracker2.file_size_bytes, 2048)
            self.assertEqual(tracker2.file_hash, 'def456')
            self.assertEqual(tracker2.last_backup_id, 1)
    
    def test_update_file_tracker_update_existing_records(self):
        """测试更新现有的文件追踪记录"""
        with self.app.app_context():
            from models import BackupFileTracker
            from datetime import datetime
            
            # 创建现有追踪记录
            existing_tracker = BackupFileTracker(
                file_path='/data/uploads/test.jpg',
                file_type='upload',
                last_modified=datetime(2024, 1, 10, 10, 0, 0),
                file_size_bytes=500,
                file_hash='old_hash',
                last_backup_id=1
            )
            db.session.add(existing_tracker)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # 准备更新的文件列表
            files = [
                {
                    'source_path': '/data/uploads/test.jpg',
                    'archive_path': 'uploads/test.jpg',
                    'file_type': 'upload',
                    'size': 1024,
                    'hash': 'new_hash',
                    'modified': datetime(2024, 1, 15, 12, 0, 0),
                    'original_path': '/data/uploads/test.jpg',
                    'is_temp': False
                }
            ]
            
            # 执行文件追踪更新
            engine._update_file_tracker(files, backup_job_id=2)
            
            # 验证记录已更新
            tracker = BackupFileTracker.query.filter_by(
                file_path='/data/uploads/test.jpg'
            ).first()
            
            self.assertIsNotNone(tracker)
            self.assertEqual(tracker.file_size_bytes, 1024)
            self.assertEqual(tracker.file_hash, 'new_hash')
            self.assertEqual(tracker.last_backup_id, 2)
            self.assertEqual(tracker.last_modified, datetime(2024, 1, 15, 12, 0, 0))
            
            # 验证只有一条记录（更新而非创建新记录）
            all_trackers = BackupFileTracker.query.all()
            self.assertEqual(len(all_trackers), 1)
    
    def test_update_file_tracker_mixed_operations(self):
        """测试混合创建和更新操作"""
        with self.app.app_context():
            from models import BackupFileTracker
            from datetime import datetime
            
            # 创建一个现有记录
            existing_tracker = BackupFileTracker(
                file_path='/data/uploads/existing.jpg',
                file_type='upload',
                last_modified=datetime(2024, 1, 10, 10, 0, 0),
                file_size_bytes=500,
                file_hash='old_hash',
                last_backup_id=1
            )
            db.session.add(existing_tracker)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # 准备文件列表（包含更新和新建）
            files = [
                {
                    'source_path': '/data/uploads/existing.jpg',
                    'archive_path': 'uploads/existing.jpg',
                    'file_type': 'upload',
                    'size': 1024,
                    'hash': 'updated_hash',
                    'modified': datetime(2024, 1, 15, 12, 0, 0),
                    'original_path': '/data/uploads/existing.jpg',
                    'is_temp': False
                },
                {
                    'source_path': '/data/uploads/new.jpg',
                    'archive_path': 'uploads/new.jpg',
                    'file_type': 'upload',
                    'size': 2048,
                    'hash': 'new_hash',
                    'modified': datetime(2024, 1, 15, 13, 0, 0),
                    'original_path': '/data/uploads/new.jpg',
                    'is_temp': False
                }
            ]
            
            # 执行文件追踪更新
            engine._update_file_tracker(files, backup_job_id=2)
            
            # 验证总共有2条记录
            all_trackers = BackupFileTracker.query.all()
            self.assertEqual(len(all_trackers), 2)
            
            # 验证现有记录已更新
            existing = BackupFileTracker.query.filter_by(
                file_path='/data/uploads/existing.jpg'
            ).first()
            self.assertEqual(existing.file_hash, 'updated_hash')
            self.assertEqual(existing.last_backup_id, 2)
            
            # 验证新记录已创建
            new = BackupFileTracker.query.filter_by(
                file_path='/data/uploads/new.jpg'
            ).first()
            self.assertIsNotNone(new)
            self.assertEqual(new.file_hash, 'new_hash')
            self.assertEqual(new.last_backup_id, 2)
    
    def test_update_file_tracker_with_database_file(self):
        """测试追踪数据库文件"""
        with self.app.app_context():
            from models import BackupFileTracker
            from datetime import datetime
            
            engine = BackupEngine(self.app)
            
            # 准备数据库文件
            files = [
                {
                    'source_path': '/tmp/temp_db_copy.db',
                    'archive_path': 'database/app.db',
                    'file_type': 'database',
                    'size': 10240,
                    'hash': 'db_hash',
                    'modified': datetime(2024, 1, 15, 14, 0, 0),
                    'original_path': '/data/app.db',  # 原始路径
                    'is_temp': True
                }
            ]
            
            # 执行文件追踪更新
            engine._update_file_tracker(files, backup_job_id=1)
            
            # 验证使用original_path作为追踪路径
            tracker = BackupFileTracker.query.filter_by(
                file_path='/data/app.db'
            ).first()
            
            self.assertIsNotNone(tracker)
            self.assertEqual(tracker.file_type, 'database')
            self.assertEqual(tracker.file_size_bytes, 10240)
            self.assertEqual(tracker.file_hash, 'db_hash')
    
    def test_update_file_tracker_empty_list(self):
        """测试空文件列表"""
        with self.app.app_context():
            from models import BackupFileTracker
            
            engine = BackupEngine(self.app)
            
            # 执行文件追踪更新（空列表）
            engine._update_file_tracker([], backup_job_id=1)
            
            # 验证没有创建记录
            trackers = BackupFileTracker.query.all()
            self.assertEqual(len(trackers), 0)
    
    def test_update_file_tracker_multiple_file_types(self):
        """测试追踪多种文件类型"""
        with self.app.app_context():
            from models import BackupFileTracker
            from datetime import datetime
            
            engine = BackupEngine(self.app)
            
            # 准备不同类型的文件
            files = [
                {
                    'source_path': '/data/app.db',
                    'archive_path': 'database/app.db',
                    'file_type': 'database',
                    'size': 10240,
                    'hash': 'db_hash',
                    'modified': datetime(2024, 1, 15, 10, 0, 0),
                    'original_path': '/data/app.db',
                    'is_temp': False
                },
                {
                    'source_path': '/data/uploads/avatar.jpg',
                    'archive_path': 'uploads/avatar.jpg',
                    'file_type': 'upload',
                    'size': 2048,
                    'hash': 'upload_hash',
                    'modified': datetime(2024, 1, 15, 11, 0, 0),
                    'original_path': '/data/uploads/avatar.jpg',
                    'is_temp': False
                },
                {
                    'source_path': '/data/jobs/readme.md',
                    'archive_path': 'documents/readme.md',
                    'file_type': 'document',
                    'size': 1024,
                    'hash': 'doc_hash',
                    'modified': datetime(2024, 1, 15, 12, 0, 0),
                    'original_path': '/data/jobs/readme.md',
                    'is_temp': False
                }
            ]
            
            # 执行文件追踪更新
            engine._update_file_tracker(files, backup_job_id=1)
            
            # 验证所有类型的文件都被追踪
            db_tracker = BackupFileTracker.query.filter_by(file_type='database').first()
            upload_tracker = BackupFileTracker.query.filter_by(file_type='upload').first()
            doc_tracker = BackupFileTracker.query.filter_by(file_type='document').first()
            
            self.assertIsNotNone(db_tracker)
            self.assertIsNotNone(upload_tracker)
            self.assertIsNotNone(doc_tracker)
            
            self.assertEqual(db_tracker.file_hash, 'db_hash')
            self.assertEqual(upload_tracker.file_hash, 'upload_hash')
            self.assertEqual(doc_tracker.file_hash, 'doc_hash')
    
    def test_update_file_tracker_called_in_execute_backup(self):
        """测试execute_backup中调用文件追踪更新"""
        with self.app.app_context():
            from models import BackupFileTracker
            from unittest.mock import Mock, patch
            
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                retention_count=10,
                backup_mode='full',
                encryption_enabled=False,
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups',
                notification_enabled=False
            )
            db.session.add(config)
            db.session.commit()
            
            engine = BackupEngine(self.app)
            
            # Mock storage adapter
            with patch('services.storage.ftp_adapter.FTPStorageAdapter') as MockAdapter:
                mock_adapter = Mock()
                mock_adapter.upload.return_value = (True, '/backups/backup_file.tar.gz')
                mock_adapter.delete.return_value = (True, 'Deleted')
                MockAdapter.return_value = mock_adapter
                
                # 执行备份
                backup_job = engine.execute_backup(trigger_type='manual')
                
                # 验证备份成功
                self.assertEqual(backup_job.status, 'success')
                
                # 验证文件追踪记录已创建
                trackers = BackupFileTracker.query.all()
                self.assertGreater(len(trackers), 0)
                
                # 验证所有追踪记录都关联到这个备份任务
                for tracker in trackers:
                    self.assertEqual(tracker.last_backup_id, backup_job.id)


if __name__ == '__main__':
    unittest.main()
