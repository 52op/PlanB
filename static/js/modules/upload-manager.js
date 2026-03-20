/**
 * 上传管理模块 - 处理文件上传功能
 */
class UploadManager {
    constructor() {
        this.csrfToken = '';
        this.uploadTargetDir = '';
        this.currentFilePath = '';
        this.currentDirPath = '';
        this.initializeElements();
    }

    initializeElements() {
        this.uploadBtn = document.getElementById('uploadBtn');
        this.uploadInput = document.getElementById('uploadInput');
    }

    setCSRFToken(token) {
        this.csrfToken = token;
    }

    setUploadTargetDir(dir) {
        this.uploadTargetDir = dir;
    }

    setCurrentPaths(filePath, dirPath) {
        this.currentFilePath = filePath || '';
        this.currentDirPath = dirPath || '';
    }

    async uploadFile(file, targetDir = '') {
        if (!file.name.endsWith('.md')) {
            window.uiUtils?.showAlertDialog('上传失败', '只允许上传 .md 格式文件');
            return false;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('target_dir', targetDir);

        const btnOriginalText = this.uploadBtn?.innerText || '上传';
        if (this.uploadBtn) {
            this.uploadBtn.innerText = "上传中...";
            this.uploadBtn.disabled = true;
        }

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                },
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                window.uiUtils?.showToast('上传成功', 'success');
                return true;
            } else {
                window.uiUtils?.showAlertDialog('上传失败', data.error || '请稍后再试');
                return false;
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('上传失败', '网络异常，请稍后再试');
            return false;
        } finally {
            if (this.uploadBtn) {
                this.uploadBtn.innerText = btnOriginalText;
                this.uploadBtn.disabled = false;
            }
        }
    }

    async uploadMediaFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/media_upload', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                },
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                return data.url;
            } else {
                window.uiUtils?.showAlertDialog('媒体上传失败', data.error || '请稍后再试');
                return null;
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('媒体上传失败', '网络异常，请稍后再试');
            return null;
        }
    }

    getTargetDirectory() {
        if (this.uploadTargetDir) {
            return this.uploadTargetDir;
        }

        const currentDirPath = this.currentDirPath || window.fileOperations?.currentDirPath;
        const currentFilePath = this.currentFilePath || window.fileOperations?.currentFilePath;

        if (currentDirPath) {
            return currentDirPath;
        }

        if (currentFilePath) {
            const lastSlashIndex = currentFilePath.lastIndexOf('/');
            if (lastSlashIndex !== -1) {
                return currentFilePath.substring(0, lastSlashIndex);
            }
        }

        return '';
    }

    setupDragAndDrop() {
        const dropZone = document.body;

        // 防止默认的拖拽行为
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        // 拖拽进入和悬停时的视觉反馈
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('drag-over');
            });
        });

        // 处理文件拖放
        dropZone.addEventListener('drop', async (e) => {
            const files = Array.from(e.dataTransfer.files);

            for (const file of files) {
                if (file.name.endsWith('.md')) {
                    const success = await this.uploadFile(file, this.getTargetDirectory());
                    if (success) {
                        window.location.reload();
                        break; // 只处理第一个成功的文件
                    }
                }
            }
        });
    }

    bindEvents() {
        if (this.uploadBtn && this.uploadInput) {
            this.uploadBtn.addEventListener('click', () => {
                this.uploadInput.click();
            });

            this.uploadInput.addEventListener('change', async () => {
                const file = this.uploadInput.files[0];
                if (!file) {
                    this.uploadTargetDir = '';
                    return;
                }

                const targetDir = this.getTargetDirectory();
                const success = await this.uploadFile(file, targetDir);

                if (success) {
                    setTimeout(() => {
                        window.location.reload();
                    }, 100);
                }

                // 清空 file input，以便同名文件可重复上传
                this.uploadInput.value = '';
                this.uploadTargetDir = '';
            });
        }

        if (document.body?.dataset.enableDragUpload === 'true') {
            this.setupDragAndDrop();
        }
    }
}

// 导出单例
window.uploadManager = new UploadManager();
