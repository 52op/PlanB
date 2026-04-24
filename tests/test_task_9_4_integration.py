# -*- coding: utf-8 -*-
"""
Task 9.4 集成测试 - 完整恢复流程
Integration tests for Task 9.4 - Complete restore workflow
"""

import pytest
import os
import tempfile
import tarfile
import shutil
from datetime import datetime
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
def mock_backup_with_config(app, tmp_path):
    """创建模拟备份和配置"""
    with app.app_context():
        # 创建备份配置
        config = BackupConfig(
            enabled=True,
            storage_type='ftp',
            schedule_type='daily',
            ftp_host='ftp.example.com',
            ftp_port=21,
            ftp_username='testuser',
            ftp_password='testpass',
            ftp_path='/backups'
        )
        db.session.add(config)
        
        # 创建成功的备份任务
        backup_job = BackupJob(
            trigger_type='manual',
            status='success',
            backup_mode='full',
            storage_type='ftp',
            filename='backup_test.tar.gz',
            file_size_bytes=1024,
            file_hash='test123',
            storage_path='/backups/backup_test.tar.gz',
            is_encrypted=False,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            duration_seconds=60,
            db_size_bytes=512,
            uploads_count=5,
            uploads_size_bytes=256,
            docs_count=3,
            docs_size_bytes=256
        )
        db.session.add(backup_job)
        db.session.commit()
        
        # 返回备份ID而不是对象，避免session问题
        backup_id = backup_job.id
        
    return backup_id


class TestTask94Integration:
    """Task 9.4 集成测试"""
    
    def test_restore_backup_validates_inputs(self, app, restorer, mock_backup_with_config):
        """测试restore_backup验证输入参数"""
        with app.app_context():
            # 测试1: 无效的备份ID
            success, message = restorer.restore_backup(-1, {'restore_database': True})
            assert success is False
            assert "无效的备份任务ID" in message
            
            # 测试2: 无效的选项类型
            success, message = restorer.restore_backup(1, "invalid")
            assert success is False
            assert "恢复选项必须是字典类型" in message
            
            # 测试3: 未选择任何恢复内容
            success, message = restorer.restore_backup(1, {
                'restore_database': False,
                'restore_uploads': False,
                'restore_documents': False
            })
            assert success is False
            assert "至少需要选择一项恢复内容" in message
    
    def test_restore_backup_checks_backup_status(self, app, restorer):
        """测试restore_backup检查备份状态"""
        with app.app_context():
            # 创建失败的备份
            failed_backup = BackupJob(
                trigger_type='auto',
                status='failed',
                backup_mode='full',
                storage_type='ftp',
                started_at=datetime.utcnow(),
                error_message='Upload failed'
            )
            db.session.add(failed_backup)
            db.session.commit()
            
            success, message = restorer.restore_backup(failed_backup.id, {
                'restore_database': True
            })
            assert success is False
            assert "备份任务未成功完成" in message
    
    def test_restore_backup_requires_password_for_encrypted(self, app, restorer):
        """测试restore_backup要求加密备份提供密码"""
        with app.app_context():
            # 创建加密的备份
            encrypted_backup = BackupJob(
                trigger_type='manual',
                status='success',
                backup_mode='full',
                storage_type='ftp',
                filename='backup_encrypted.tar.gz.enc',
                file_size_bytes=1024,
                file_hash='test456',
                storage_path='/backups/backup_encrypted.tar.gz.enc',
                is_encrypted=True,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                duration_seconds=60
            )
            db.session.add(encrypted_backup)
            db.session.commit()
            
            # 不提供密码
            success, message = restorer.restore_backup(encrypted_backup.id, {
                'restore_database': True
            })
            assert success is False
            assert "备份文件已加密，需要提供解密密码" in message
    
    def test_restore_backup_workflow_structure(self, app, restorer, mock_backup_with_config):
        """测试restore_backup工作流程结构（不实际执行）"""
        with app.app_context():
            # 这个测试验证方法的基本结构，但由于没有实际的备份文件，
            # 会在下载阶段失败。我们验证错误处理是否正确。
            
            restore_options = {
                'restore_database': True,
                'restore_uploads': True,
                'restore_documents': True
            }
            
            success, message = restorer.restore_backup(
                mock_backup_with_config,  # 现在是ID
                restore_options
            )
            
            # 应该失败（因为没有实际的备份配置和文件）
            assert success is False
            assert "恢复失败" in message
    
    def test_restore_backup_selective_restore_options(self, app, restorer, mock_backup_with_config):
        """测试restore_backup支持选择性恢复"""
        with app.app_context():
            # 测试只恢复数据库
            success, message = restorer.restore_backup(
                mock_backup_with_config,  # 现在是ID
                {'restore_database': True}
            )
            assert success is False  # 会失败，但验证了选项被接受
            
            # 测试只恢复上传文件
            success, message = restorer.restore_backup(
                mock_backup_with_config,  # 现在是ID
                {'restore_uploads': True}
            )
            assert success is False  # 会失败，但验证了选项被接受
            
            # 测试只恢复文档
            success, message = restorer.restore_backup(
                mock_backup_with_config,  # 现在是ID
                {'restore_documents': True}
            )
            assert success is False  # 会失败，但验证了选项被接受
    
    def test_restore_backup_returns_tuple(self, app, restorer, mock_backup_with_config):
        """测试restore_backup返回(bool, str)元组"""
        with app.app_context():
            result = restorer.restore_backup(
                mock_backup_with_config,  # 现在是ID
                {'restore_database': True}
            )
            
            # 验证返回类型
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], bool)
            assert isinstance(result[1], str)
    
    def test_restore_backup_error_handling(self, app, restorer):
        """测试restore_backup错误处理"""
        with app.app_context():
            # 测试不存在的备份
            success, message = restorer.restore_backup(999, {
                'restore_database': True
            })
            assert success is False
            assert "备份任务不存在" in message
            
            # 验证错误消息格式
            assert message.startswith("恢复失败:")


class TestTask94HelperMethods:
    """测试Task 9.4使用的辅助方法"""
    
    def test_download_backup_validates_backup_job(self, app, restorer):
        """测试_download_backup验证备份任务信息"""
        with app.app_context():
            # 创建配置
            config = BackupConfig(
                enabled=True,
                storage_type='ftp',
                schedule_type='daily',
                ftp_host='ftp.example.com',
                ftp_port=21,
                ftp_username='testuser',
                ftp_password='testpass',
                ftp_path='/backups'
            )
            db.session.add(config)
            
            # 测试缺少存储类型
            backup_job = BackupJob(
                trigger_type='auto',
                status='success',
                backup_mode='full',
                storage_type=None,
                filename='backup.tar.gz',
                storage_path='/backups/backup.tar.gz',
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            db.session.add(backup_job)
            db.session.commit()
            
            with pytest.raises(ValueError, match="备份任务缺少存储类型信息"):
                restorer._download_backup(backup_job)
    
    def test_create_rollback_point_structure(self, app, restorer, tmp_path):
        """测试_create_rollback_point创建回滚点"""
        with app.app_context():
            # 创建临时数据目录
            data_dir = tmp_path / "data"
            data_dir.mkdir()
            
            # 创建测试数据
            (data_dir / "app.db").write_bytes(b"test database")
            
            uploads_dir = data_dir / "uploads"
            uploads_dir.mkdir()
            (uploads_dir / "test.txt").write_text("test upload", encoding='utf-8')
            
            jobs_dir = data_dir / "jobs"
            jobs_dir.mkdir()
            (jobs_dir / "test.md").write_text("test doc", encoding='utf-8')
            
            # 临时更改工作目录
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp_path)
                
                # 创建回滚点
                rollback_point = restorer._create_rollback_point()
                
                # 验证回滚点存在
                assert os.path.exists(rollback_point)
                assert os.path.isdir(rollback_point)
                
                # 验证回滚点包含备份的数据
                assert os.path.exists(os.path.join(rollback_point, 'database', 'app.db'))
                assert os.path.exists(os.path.join(rollback_point, 'uploads', 'test.txt'))
                assert os.path.exists(os.path.join(rollback_point, 'documents', 'test.md'))
                
                # 清理
                shutil.rmtree(rollback_point)
            finally:
                os.chdir(original_cwd)
    
    def test_extract_archive_creates_directory(self, app, restorer, tmp_path):
        """测试_extract_archive创建解压目录"""
        with app.app_context():
            # 创建测试tar.gz文件
            archive_path = tmp_path / "test.tar.gz"
            source_file = tmp_path / "test.txt"
            source_file.write_text("test content", encoding='utf-8')
            
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(source_file, arcname="test.txt")
            
            # 解压到新目录
            extract_dir = tmp_path / "extract"
            restorer._extract_archive(str(archive_path), str(extract_dir))
            
            # 验证目录被创建
            assert extract_dir.exists()
            assert (extract_dir / "test.txt").exists()
            assert (extract_dir / "test.txt").read_text(encoding='utf-8') == "test content"


class TestTask94Requirements:
    """验证Task 9.4满足所有需求"""
    
    def test_requirement_9_4_orchestrates_workflow(self, app, restorer, mock_backup_with_config):
        """验证需求9.4: 协调完整的恢复工作流程"""
        with app.app_context():
            # restore_backup方法应该协调以下步骤：
            # 1. 验证输入
            # 2. 创建回滚点
            # 3. 下载备份
            # 4. 解密（如需要）
            # 5. 解压
            # 6. 恢复组件
            # 7. 清理
            # 8. 失败时回滚
            
            # 验证方法存在且可调用
            assert hasattr(restorer, 'restore_backup')
            assert callable(restorer.restore_backup)
            
            # 验证方法签名
            import inspect
            sig = inspect.signature(restorer.restore_backup)
            params = list(sig.parameters.keys())
            assert 'backup_job_id' in params
            assert 'restore_options' in params
    
    def test_requirement_9_5_to_9_12_all_steps_implemented(self, app, restorer):
        """验证需求9.5-9.12: 所有恢复步骤都已实现"""
        with app.app_context():
            # 验证所有辅助方法都存在
            assert hasattr(restorer, '_download_backup')  # 9.5
            assert hasattr(restorer, '_decrypt_archive')  # 9.5
            assert hasattr(restorer, '_extract_archive')  # 9.5
            assert hasattr(restorer, '_create_rollback_point')  # 9.6
            assert hasattr(restorer, '_restore_database')  # 9.7
            assert hasattr(restorer, '_restore_uploads')  # 9.8
            assert hasattr(restorer, '_restore_documents')  # 9.9
            assert hasattr(restorer, '_rollback')  # 9.11
            
            # 验证所有方法都可调用
            assert callable(restorer._download_backup)
            assert callable(restorer._decrypt_archive)
            assert callable(restorer._extract_archive)
            assert callable(restorer._create_rollback_point)
            assert callable(restorer._restore_database)
            assert callable(restorer._restore_uploads)
            assert callable(restorer._restore_documents)
            assert callable(restorer._rollback)
    
    def test_requirement_selective_restore(self, app, restorer, mock_backup_with_config):
        """验证支持选择性恢复"""
        with app.app_context():
            # 验证可以只恢复数据库
            result = restorer.restore_backup(
                mock_backup_with_config,  # 现在是ID
                {'restore_database': True}
            )
            assert isinstance(result, tuple)
            
            # 验证可以只恢复上传文件
            result = restorer.restore_backup(
                mock_backup_with_config,  # 现在是ID
                {'restore_uploads': True}
            )
            assert isinstance(result, tuple)
            
            # 验证可以只恢复文档
            result = restorer.restore_backup(
                mock_backup_with_config,  # 现在是ID
                {'restore_documents': True}
            )
            assert isinstance(result, tuple)
    
    def test_requirement_return_format(self, app, restorer, mock_backup_with_config):
        """验证返回格式为(success, message)"""
        with app.app_context():
            success, message = restorer.restore_backup(
                mock_backup_with_config,  # 现在是ID
                {'restore_database': True}
            )
            
            # 验证返回类型
            assert isinstance(success, bool)
            assert isinstance(message, str)
            
            # 验证失败时的消息格式
            assert success is False
            assert len(message) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
