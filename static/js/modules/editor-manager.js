/**
 * 编辑器管理模块 - 处理Toast UI Editor的初始化和管理
 */
class EditorManager {
    constructor() {
        this.editorInstance = null;
        this.currentFilePath = '';
        this.csrfToken = '';
        this.initializeElements();
    }

    initializeElements() {
        this.editBtn = document.getElementById('editBtn');
        this.saveEditBtn = document.getElementById('saveEditBtn');
        this.cancelEditBtn = document.getElementById('cancelEditBtn');
        this.frontMatterBtn = document.getElementById('frontMatterBtn');
        this.editorView = document.getElementById('editorView');
        this.renderView = document.getElementById('renderView');
        this.metaPanel = document.getElementById('metaPanel');
        this.closeMetaBtn = document.getElementById('closeMetaBtn');
        this.applyMetaBtn = document.getElementById('applyMetaBtn');
    }

    setCurrentFile(filePath) {
        this.currentFilePath = filePath;
    }

    setCSRFToken(token) {
        this.csrfToken = token;
    }

    async initializeEditor(content) {
        if (!this.editorInstance) {
            this.editorInstance = new toastui.Editor({
                el: document.querySelector('#toastEditor'),
                initialValue: content,
                previewStyle: 'vertical',
                height: '100%',
                initialEditType: 'markdown',
                hooks: {
                    addImageBlobHook: (blob, callback) => {
                        this.handleImageUpload(blob, callback);
                    }
                }
            });
        } else {
            this.editorInstance.setMarkdown(content, false);
        }
    }

    async handleImageUpload(blob, callback) {
        const formData = new FormData();
        formData.append('file', blob);

        try {
            const response = await fetch('/api/media_upload', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken
                },
                body: formData,
            });

            const result = await response.json();

            if (result.success) {
                const customImage = window.imageUtils?.buildSizedImageMarkup(result.url, 'Image');

                if (customImage?.cancelled) {
                    callback(result.url, 'Image');
                    return;
                }

                if (customImage?.markup) {
                    callback(result.url, 'Image');
                    setTimeout(() => {
                        this.replaceRecentlyInsertedImage(result.url, customImage.markup);
                    }, 0);
                    return;
                }

                callback(result.url, 'Image');
            } else {
                window.uiUtils?.showAlertDialog('图片上传失败', result.error || '请稍后重试');
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('图片上传失败', '网络错误，请稍后重试');
        }
    }

    replaceRecentlyInsertedImage(url, markup) {
        if (!this.editorInstance) return;

        const content = this.editorInstance.getMarkdown();
        const imagePattern = new RegExp(`!\\[Image\\]\\(${url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\)`, 'g');
        const newContent = content.replace(imagePattern, markup);

        if (newContent !== content) {
            this.editorInstance.setMarkdown(newContent, false);
        }
    }

    async loadFileContent() {
        if (!this.currentFilePath) return;

        try {
            const response = await fetch(`/api/get_raw?filename=${encodeURIComponent(this.currentFilePath)}`);
            const data = await response.json();

            if (data.error) {
                window.uiUtils?.showAlertDialog('读取失败', data.error || '无权限或文件不存在');
                return null;
            }

            return data.content;
        } catch (error) {
            window.uiUtils?.showAlertDialog('读取失败', '网络错误或无权限');
            return null;
        }
    }

    async saveContent() {
        if (!this.editorInstance) return false;

        const newContent = this.editorInstance.getMarkdown();
        const btnOriginalText = this.saveEditBtn.innerText;

        this.saveEditBtn.innerText = "保存中...";
        this.saveEditBtn.disabled = true;

        try {
            const response = await fetch('/api/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    filename: this.currentFilePath,
                    content: newContent,
                    ensure_front_matter: newContent.startsWith('---\n')
                })
            });

            const data = await response.json();

            if (data.success) {
                if (data.content && this.editorInstance) {
                    this.editorInstance.setMarkdown(data.content, false);
                    window.frontMatterUtils?.fillMetaPanel();
                }
                return true;
            } else {
                window.uiUtils?.showAlertDialog('保存失败', data.error || '请稍后再试');
                return false;
            }
        } catch (error) {
            window.uiUtils?.showAlertDialog('保存失败', '网络异常，请稍后再试');
            return false;
        } finally {
            this.saveEditBtn.innerText = btnOriginalText;
            this.saveEditBtn.disabled = false;
        }
    }

    showEditor() {
        if (this.renderView) this.renderView.style.display = 'none';
        if (this.editorView) this.editorView.style.display = 'block';
        if (this.editBtn) this.editBtn.style.display = 'none';
        if (this.frontMatterBtn) this.frontMatterBtn.style.display = 'none';
    }

    hideEditor() {
        if (this.editorView) this.editorView.style.display = 'none';
        if (this.renderView) this.renderView.style.display = 'block';
        if (this.editBtn) this.editBtn.style.display = 'inline-block';
        if (this.frontMatterBtn) this.frontMatterBtn.style.display = 'inline-block';
        if (this.metaPanel) this.metaPanel.classList.remove('show');
    }

    getMarkdown() {
        return this.editorInstance ? this.editorInstance.getMarkdown() : '';
    }

    setMarkdown(content, cursorToEnd = false) {
        if (this.editorInstance) {
            this.editorInstance.setMarkdown(content, cursorToEnd);
        }
    }

    bindEvents() {
        if (this.editBtn) {
            this.editBtn.addEventListener('click', async () => {
                const content = await this.loadFileContent();
                if (content !== null) {
                    this.showEditor();
                    await this.initializeEditor(content);
                    window.frontMatterUtils?.fillMetaPanel();
                }
            });
        }

        if (this.cancelEditBtn) {
            this.cancelEditBtn.addEventListener('click', () => {
                this.hideEditor();
            });
        }

        if (this.saveEditBtn) {
            this.saveEditBtn.addEventListener('click', async () => {
                const success = await this.saveContent();
                if (success) {
                    window.uiUtils?.showToast?.('保存成功');
                    this.hideEditor();
                    window.location.href = window.location.href.split('#')[0];
                }
            });
        }

        if (this.frontMatterBtn) {
            this.frontMatterBtn.addEventListener('click', () => {
                if (!this.editorView || !this.renderView) return;

                if (this.editorView.style.display === 'none' && this.editBtn) {
                    this.editBtn.click();
                    setTimeout(() => {
                        window.frontMatterUtils?.ensureFrontMatterBlock();
                        if (this.metaPanel) this.metaPanel.classList.add('show');
                    }, 240);
                    return;
                }

                window.frontMatterUtils?.ensureFrontMatterBlock();
                if (this.metaPanel) this.metaPanel.classList.toggle('show');
            });
        }

        if (this.closeMetaBtn) {
            this.closeMetaBtn.addEventListener('click', () => {
                if (this.metaPanel) this.metaPanel.classList.remove('show');
            });
        }

        if (this.applyMetaBtn) {
            this.applyMetaBtn.addEventListener('click', () => {
                if (!this.editorInstance) return;

                const parsed = window.frontMatterUtils?.splitFrontMatter(this.editorInstance.getMarkdown());
                const contentWithMeta = window.frontMatterUtils?.buildFrontMatterFromPanel(parsed?.body || '');

                if (contentWithMeta) {
                    this.editorInstance.setMarkdown(contentWithMeta, false);
                }
            });
        }
    }
}

// 导出单例
window.editorManager = new EditorManager();