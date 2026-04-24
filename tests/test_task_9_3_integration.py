# -*- coding: utf-8 -*-
"""
Task 9.3 集成测试
Integration tests for Task 9.3 - Data recovery and rollback functionality
"""

import pytest
import os
import shutil
import tempfile
from services.backup_restorer import BackupRestorer


@pytest.fixture
def app():
    """创建测试Flask应用"""
    from flask import Flask
    from models import db
    
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
def test_data_dirs(tmp_path):
    """创建测试数据目录结构"""
    # 创建data目录结构
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # 创建数据库文件
    db_file = data_dir / "app.db"
    db_file.write_bytes(b"test database content")
    
    # 创建uploads目录和文件
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "file1.txt").write_text("upload file 1", encoding='utf-8')
    (uploads_dir / "file2.txt").write_text("upload file 2", encoding='utf-8')
    
    # 创建jobs目录和文件
    jobs_dir = data_dir / "jobs"
    jobs_dir.mkdir()
    (jobs_dir / "doc1.md").write_text("document 1", encoding='utf-8')
    (jobs_dir / "doc2.md").write_text("document 2", encoding='utf-8')
    
    # 切换到临时目录
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    yield {
        'data_dir': data_dir,
        'db_file': db_file,
        'uploads_dir': uploads_dir,
        'jobs_dir': jobs_dir
    }
    
    # 恢复原始工作目录
    os.chdir(original_cwd)


class TestCreateRollbackPoint:
    """测试_create_rollback_point方法"""
    
    def test_create_rollback_point_success(self, restorer, test_data_dirs):
        """测试成功创建回滚点"""
        rollback_point = restorer._create_rollback_point()
        
        # 验证回滚点目录存在
        assert os.path.exists(rollback_point)
        assert os.path.isdir(rollback_point)
        
        # 验证数据库备份存在
        rollback_db = os.path.join(rollback_point, 'database', 'app.db')
        assert os.path.exists(rollback_db)
        
        # 验证上传文件备份存在
        rollback_uploads = os.path.join(rollback_point, 'uploads')
        assert os.path.exists(rollback_uploads)
        assert os.path.exists(os.path.join(rollback_uploads, 'file1.txt'))
        assert os.path.exists(os.path.join(rollback_uploads, 'file2.txt'))
        
        # 验证文档文件备份存在
        rollback_docs = os.path.join(rollback_point, 'documents')
        assert os.path.exists(rollback_docs)
        assert os.path.exists(os.path.join(rollback_docs, 'doc1.md'))
        assert os.path.exists(os.path.join(rollback_docs, 'doc2.md'))
        
        # 清理
        shutil.rmtree(rollback_point)
    
    def test_create_rollback_point_unique_names(self, restorer, test_data_dirs):
        """测试创建多个回滚点时名称唯一"""
        rollback_point1 = restorer._create_rollback_point()
        rollback_point2 = restorer._create_rollback_point()
        
        # 验证两个回滚点路径不同
        assert rollback_point1 != rollback_point2
        assert os.path.exists(rollback_point1)
        assert os.path.exists(rollback_point2)
        
        # 清理
        shutil.rmtree(rollback_point1)
        shutil.rmtree(rollback_point2)


class TestRestoreDatabase:
    """测试_restore_database方法"""
    
    def test_restore_database_success(self, restorer, test_data_dirs):
        """测试成功恢复数据库"""
        # 创建备份数据库
        backup_db_dir = test_data_dirs['data_dir'] / "backup_db"
        backup_db_dir.mkdir()
        backup_db_file = backup_db_dir / "app.db"
        backup_db_file.write_bytes(b"backup database content")
        
        # 修改当前数据库
        test_data_dirs['db_file'].write_bytes(b"modified database content")
        
        # 恢复数据库
        restorer._restore_database(str(backup_db_file))
        
        # 验证数据库已恢复
        restored_content = test_data_dirs['db_file'].read_bytes()
        assert restored_content == b"backup database content"
    
    def test_restore_database_nonexistent_backup(self, restorer, test_data_dirs):
        """测试恢复不存在的备份数据库"""
        with pytest.raises(ValueError, match="备份数据库文件不存在"):
            restorer._restore_database("/nonexistent/path/app.db")


class TestRestoreUploads:
    """测试_restore_uploads方法"""
    
    def test_restore_uploads_success(self, restorer, test_data_dirs):
        """测试成功恢复上传文件"""
        # 创建备份上传文件目录
        backup_uploads_dir = test_data_dirs['data_dir'] / "backup_uploads"
        backup_uploads_dir.mkdir()
        (backup_uploads_dir / "backup_file1.txt").write_text("backup upload 1", encoding='utf-8')
        (backup_uploads_dir / "backup_file2.txt").write_text("backup upload 2", encoding='utf-8')
        
        # 恢复上传文件
        restorer._restore_uploads(str(backup_uploads_dir))
        
        # 验证文件已恢复
        uploads_dir = test_data_dirs['uploads_dir']
        assert (uploads_dir / "backup_file1.txt").read_text(encoding='utf-8') == "backup upload 1"
        assert (uploads_dir / "backup_file2.txt").read_text(encoding='utf-8') == "backup upload 2"
        
        # 验证旧文件已被清除
        assert not (uploads_dir / "file1.txt").exists()
        assert not (uploads_dir / "file2.txt").exists()
    
    def test_restore_uploads_nonexistent_backup(self, restorer, test_data_dirs):
        """测试恢复不存在的备份上传文件"""
        with pytest.raises(ValueError, match="备份上传文件目录不存在"):
            restorer._restore_uploads("/nonexistent/path/uploads")


class TestRestoreDocuments:
    """测试_restore_documents方法"""
    
    def test_restore_documents_success(self, restorer, test_data_dirs):
        """测试成功恢复文档文件"""
        # 创建备份文档文件目录
        backup_docs_dir = test_data_dirs['data_dir'] / "backup_docs"
        backup_docs_dir.mkdir()
        (backup_docs_dir / "backup_doc1.md").write_text("backup document 1", encoding='utf-8')
        (backup_docs_dir / "backup_doc2.md").write_text("backup document 2", encoding='utf-8')
        
        # 恢复文档文件
        restorer._restore_documents(str(backup_docs_dir))
        
        # 验证文件已恢复
        jobs_dir = test_data_dirs['jobs_dir']
        assert (jobs_dir / "backup_doc1.md").read_text(encoding='utf-8') == "backup document 1"
        assert (jobs_dir / "backup_doc2.md").read_text(encoding='utf-8') == "backup document 2"
        
        # 验证旧文件已被清除
        assert not (jobs_dir / "doc1.md").exists()
        assert not (jobs_dir / "doc2.md").exists()
    
    def test_restore_documents_nonexistent_backup(self, restorer, test_data_dirs):
        """测试恢复不存在的备份文档文件"""
        with pytest.raises(ValueError, match="备份文档文件目录不存在"):
            restorer._restore_documents("/nonexistent/path/documents")


class TestRollback:
    """测试_rollback方法"""
    
    def test_rollback_success(self, restorer, test_data_dirs):
        """测试成功回滚"""
        # 创建回滚点
        rollback_point = restorer._create_rollback_point()
        
        # 修改当前数据
        test_data_dirs['db_file'].write_bytes(b"modified database")
        test_data_dirs['uploads_dir'] / "new_file.txt"
        (test_data_dirs['uploads_dir'] / "new_file.txt").write_text("new upload", encoding='utf-8')
        (test_data_dirs['jobs_dir'] / "new_doc.md").write_text("new document", encoding='utf-8')
        
        # 执行回滚
        restorer._rollback(rollback_point)
        
        # 验证数据已回滚
        assert test_data_dirs['db_file'].read_bytes() == b"test database content"
        assert (test_data_dirs['uploads_dir'] / "file1.txt").read_text(encoding='utf-8') == "upload file 1"
        assert (test_data_dirs['jobs_dir'] / "doc1.md").read_text(encoding='utf-8') == "document 1"
        
        # 验证新文件已被清除
        assert not (test_data_dirs['uploads_dir'] / "new_file.txt").exists()
        assert not (test_data_dirs['jobs_dir'] / "new_doc.md").exists()
        
        # 验证回滚点已被清理
        assert not os.path.exists(rollback_point)
    
    def test_rollback_nonexistent_point(self, restorer, test_data_dirs):
        """测试回滚不存在的回滚点"""
        with pytest.raises(ValueError, match="回滚点不存在"):
            restorer._rollback("/nonexistent/rollback/point")


class TestIntegrationScenario:
    """测试完整的恢复和回滚场景"""
    
    def test_full_restore_with_rollback_on_failure(self, restorer, test_data_dirs):
        """测试完整恢复流程：创建回滚点 -> 尝试恢复 -> 失败时回滚"""
        # 记录原始数据
        original_db_content = test_data_dirs['db_file'].read_bytes()
        original_upload1 = (test_data_dirs['uploads_dir'] / "file1.txt").read_text(encoding='utf-8')
        original_doc1 = (test_data_dirs['jobs_dir'] / "doc1.md").read_text(encoding='utf-8')
        
        # 创建回滚点
        rollback_point = restorer._create_rollback_point()
        
        try:
            # 创建备份数据
            backup_db_dir = test_data_dirs['data_dir'] / "backup_db"
            backup_db_dir.mkdir()
            backup_db_file = backup_db_dir / "app.db"
            backup_db_file.write_bytes(b"restored database content")
            
            # 恢复数据库
            restorer._restore_database(str(backup_db_file))
            
            # 验证数据库已恢复
            assert test_data_dirs['db_file'].read_bytes() == b"restored database content"
            
            # 模拟恢复失败（例如上传文件恢复失败）
            # 这里我们故意不恢复上传文件，模拟部分恢复失败的情况
            
            # 执行回滚
            restorer._rollback(rollback_point)
            
            # 验证所有数据已回滚到原始状态
            assert test_data_dirs['db_file'].read_bytes() == original_db_content
            assert (test_data_dirs['uploads_dir'] / "file1.txt").read_text(encoding='utf-8') == original_upload1
            assert (test_data_dirs['jobs_dir'] / "doc1.md").read_text(encoding='utf-8') == original_doc1
            
        except Exception as e:
            # 如果发生异常，确保回滚点被清理
            if os.path.exists(rollback_point):
                shutil.rmtree(rollback_point)
            raise
