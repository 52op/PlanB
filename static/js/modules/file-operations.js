/**
 * 文件操作模块 - 处理文档和目录的创建、重命名、删除等操作
 */
class FileOperations {
    constructor() {
        this.csrfToken = '';
        this.currentFilePath = '';
        this.currentDirPath = '';
    }

    setCSRFToken(token) {
        this.csrfToken = token;
    }

    setCurrentPaths(filePath, dirPath) {
        this.currentFilePath = filePath;
        this.currentDirPath = dirPath;
    }

    getWorkingDirectory() {
        if (this.currentDirPath) {
            return this.currentDirPath;
        }
        if (this.currentFilePath) {
            const lastSlashIndex = this.currentFilePath.lastIndexOf('/');
            return lastSlashIndex !== -1 ? this.currentFilePath.substring(0, lastSlashIndex) : '';
        }
        return '';
    }

    async createDocument(targetDir = '') {
        const fileName = await window.uiUtils?.showPromptDialog(
            '新建文档',
            '请输入文档名称（无需 .md 后缀）：',
            ''
        );

        if (!fileName) return;

        try {
            const response = await fetch('/api/documents/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    target_dir: targetDir,
                    filename: fileName
                })
            });

            const data = await response.json();

            if (data.success) {
                window.uiUtils?.showToast('文档创建成功', 'success');
                window.location.href = `/docs/doc/${encodeURIComponent(data.path).replace(/%2F/g, '/')}`;
            } else {
                window.uiUtils?.showAlertDialog('创建失败', data.error || '请稍后再试');
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('创建失败', '网络异常，请稍后再试');
        }
    }

    async createDirectory(parentDir = '') {
        const dirName = await window.uiUtils?.showPromptDialog(
            '新建目录',
            '请输入目录名称：',
            ''
        );

        if (!dirName) return;

        try {
            const response = await fetch('/api/directories/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    parent_dir: parentDir,
                    name: dirName
                })
            });

            const data = await response.json();

            if (data.success) {
                window.uiUtils?.showToast('目录创建成功', 'success');
                window.location.reload();
            } else {
                window.uiUtils?.showAlertDialog('创建目录失败', data.error || '请稍后再试');
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('创建目录失败', '网络异常，请稍后再试');
        }
    }

    async renameDocument(filePath, currentName) {
        const baseName = currentName.replace(/\.md$/i, '');
        const newName = await window.uiUtils?.showPromptDialog(
            '重命名文档',
            '请输入新的文档名称（无需 .md 后缀）：',
            baseName
        );

        if (!newName || newName === baseName) return;

        try {
            const response = await fetch('/api/documents/rename', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    source_path: filePath,
                    new_name: newName
                })
            });

            const data = await response.json();

            if (data.success) {
                window.uiUtils?.showToast('重命名成功', 'success');
                if (this.currentFilePath === filePath) {
                    window.location.href = `/docs/doc/${encodeURIComponent(data.path).replace(/%2F/g, '/')}`;
                } else {
                    window.location.reload();
                }
            } else {
                window.uiUtils?.showAlertDialog('重命名失败', data.error || '请稍后再试');
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('重命名失败', '网络异常，请稍后再试');
        }
    }

    async renameDirectory(dirPath, currentName) {
        const newName = await window.uiUtils?.showPromptDialog(
            '重命名目录',
            '请输入新的目录名称：',
            currentName
        );

        if (!newName || newName === currentName) return;

        try {
            const response = await fetch('/api/directories/rename', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    source_path: dirPath,
                    new_name: newName
                })
            });

            const data = await response.json();

            if (data.success) {
                window.uiUtils?.showToast('重命名成功', 'success');
                const targetPath = this.currentDirPath === dirPath ? data.path : this.currentDirPath;
                window.location.href = targetPath ? `/docs/dir/${encodeURIComponent(targetPath).replace(/%2F/g, '/')}` : '/docs';
            } else {
                window.uiUtils?.showAlertDialog('重命名目录失败', data.error || '请稍后再试');
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('重命名目录失败', '网络异常，请稍后再试');
        }
    }

    async deleteDocument(filePath, fileName) {
        const confirmed = await window.uiUtils?.showConfirmDialog(
            '删除文档',
            `确定删除文档"${fileName}"吗？此操作不可撤销。`,
            '删除'
        );

        if (!confirmed) return;

        try {
            const response = await fetch(`/api/documents/delete?filename=${encodeURIComponent(filePath)}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });

            const data = await response.json();

            if (data.success) {
                if (this.currentFilePath === filePath) {
                    const targetDir = this.getWorkingDirectory();
                    window.location.href = targetDir ? `/docs/dir/${encodeURIComponent(targetDir).replace(/%2F/g, '/')}` : '/docs';
                } else {
                    window.location.reload();
                }
            } else {
                window.uiUtils?.showAlertDialog('删除失败', data.error || '请稍后再试');
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('删除失败', '网络异常，请稍后再试');
        }
    }

    async deleteDirectory(dirPath, dirName) {
        const confirmed = await window.uiUtils?.showConfirmDialog(
            '删除目录',
            `确定删除空目录"${dirName}"吗？`,
            '删除'
        );

        if (!confirmed) return;

        try {
            const response = await fetch(`/api/directories/delete?dirname=${encodeURIComponent(dirPath)}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });

            const data = await response.json();

            if (data.success) {
                const parentDir = dirPath.includes('/') ? dirPath.slice(0, dirPath.lastIndexOf('/')) : '';
                const targetPath = this.currentDirPath === dirPath ? parentDir : this.currentDirPath;
                window.location.href = targetPath ? `/docs/dir/${encodeURIComponent(targetPath).replace(/%2F/g, '/')}` : '/docs';
            } else {
                window.uiUtils?.showAlertDialog('删除目录失败', data.error || '请稍后再试');
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('删除目录失败', '网络异常，请稍后再试');
        }
    }

    bindEvents() {
        // 绑定创建文档按钮
        const createDocBtn = document.getElementById('createDocBtn');
        if (createDocBtn) {
            createDocBtn.addEventListener('click', () => {
                this.createDocument(this.getWorkingDirectory());
            });
        }

        // 绑定创建目录按钮
        const createDirBtn = document.getElementById('createDirBtn');
        if (createDirBtn) {
            createDirBtn.addEventListener('click', () => {
                this.createDirectory(this.getWorkingDirectory());
            });
        }

        // 绑定目录内创建文档按钮
        document.querySelectorAll('.create-doc-in-dir').forEach(button => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                this.createDocument(button.dataset.dirPath || '');
            });
        });

        // 绑定重命名文档按钮
        document.querySelectorAll('.rename-doc-btn').forEach(button => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                this.renameDocument(button.dataset.filePath || '', button.dataset.fileName || '');
            });
        });

        // 绑定删除文档按钮
        document.querySelectorAll('.delete-doc-btn').forEach(button => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                this.deleteDocument(button.dataset.filePath || '', button.dataset.fileName || '');
            });
        });

        // 绑定重命名目录按钮
        document.querySelectorAll('.rename-dir-btn').forEach(button => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                this.renameDirectory(button.dataset.dirPath || '', button.dataset.dirName || '');
            });
        });

        // 绑定删除目录按钮
        document.querySelectorAll('.delete-dir-btn').forEach(button => {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                this.deleteDirectory(button.dataset.dirPath || '', button.dataset.dirName || '');
            });
        });
    }
}

// 导出单例
window.fileOperations = new FileOperations();