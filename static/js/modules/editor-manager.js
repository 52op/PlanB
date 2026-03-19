class EditorManager {
    constructor() {
        this.editorInstance = null;
        this.currentFilePath = '';
        this.csrfToken = '';
        this.loadedFrontMatterText = '';
        this.loadedFrontMatterMetadata = {};
        this.frontMatterDirty = false;
        this.editModeState = { sidebarHidden: false, tocHidden: false };
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
        this.clearCoverBtn = document.getElementById('clearCoverBtn');
        this.appShell = document.querySelector('.app-shell');
        this.commentsSection = document.getElementById('comments');
        this.postNav = document.querySelector('.post-nav');
        this.siteFooter = document.querySelector('.site-footer');
    }

    setCurrentFile(filePath) {
        this.currentFilePath = filePath || '';
    }

    setCSRFToken(token) {
        this.csrfToken = token || '';
    }

    syncLoadedFrontMatterState(content) {
        const parsed = window.frontMatterUtils?.splitFrontMatter(content || '') || {
            metadata: {},
            body: content || '',
            frontMatterText: '',
            hasFrontMatter: false,
        };
        this.loadedFrontMatterText = parsed.frontMatterText || '';
        this.loadedFrontMatterMetadata = parsed.metadata || {};
        this.frontMatterDirty = false;
        return parsed;
    }

    composeDocumentContent(bodyContent) {
        const normalizedBody = String(bodyContent || '').replace(/^\n+/, '');

        if (this.frontMatterDirty) {
            return window.frontMatterUtils?.buildFrontMatterFromPanel(normalizedBody) || normalizedBody;
        }

        if (this.loadedFrontMatterText) {
            return `${this.loadedFrontMatterText}\n\n${normalizedBody}`;
        }

        return bodyContent || '';
    }

    fillMetaPanel() {
        if (!this.editorInstance || !window.frontMatterUtils) return;
        window.frontMatterUtils.fillMetaPanelFromState({
            bodyContent: this.editorInstance.getMarkdown(),
            metadata: this.loadedFrontMatterMetadata || {},
            currentFilePath: this.currentFilePath,
        });
    }

    async initializeEditor(content) {
        const parsed = this.syncLoadedFrontMatterState(content);
        const editorBody = parsed.body || '';

        if (!this.editorInstance) {
            this.editorInstance = new toastui.Editor({
                el: document.querySelector('#toastEditor'),
                initialValue: editorBody,
                previewStyle: 'vertical',
                height: '100%',
                initialEditType: 'markdown',
                hooks: {
                    addImageBlobHook: (blob, callback) => {
                        this.handleImageUpload(blob, callback);
                    },
                },
            });
        } else {
            this.editorInstance.setMarkdown(editorBody, false);
        }

        this.fillMetaPanel();
    }

    async handleImageUpload(blob, callback) {
        const formData = new FormData();
        formData.append('file', blob);

        try {
            const response = await fetch('/api/media_upload', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
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
        if (!this.currentFilePath) return null;

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

    showEditor() {
        if (this.renderView) this.renderView.style.display = 'none';
        if (this.editorView) this.editorView.style.display = 'block';
        if (this.editBtn) this.editBtn.style.display = 'none';
        if (this.frontMatterBtn) this.frontMatterBtn.style.display = 'inline-block';

        if (this.commentsSection) this.commentsSection.style.display = 'none';
        if (this.postNav) this.postNav.style.display = 'none';
        if (this.siteFooter) this.siteFooter.style.display = 'none';

        if (this.appShell) {
            this.editModeState.sidebarHidden = this.appShell.classList.contains('sidebar-hidden');
            this.editModeState.tocHidden = this.appShell.classList.contains('toc-hidden');

            if (!this.editModeState.sidebarHidden) {
                this.appShell.classList.add('sidebar-hidden');
            }
            if (!this.editModeState.tocHidden) {
                this.appShell.classList.add('toc-hidden');
            }
        }
    }

    hideEditor() {
        if (this.editorView) this.editorView.style.display = 'none';
        if (this.renderView) this.renderView.style.display = 'block';
        if (this.editBtn) this.editBtn.style.display = 'inline-block';
        if (this.frontMatterBtn) this.frontMatterBtn.style.display = 'inline-block';
        if (this.metaPanel) this.metaPanel.classList.remove('show');

        if (this.commentsSection) this.commentsSection.style.display = '';
        if (this.postNav) this.postNav.style.display = '';
        if (this.siteFooter) this.siteFooter.style.display = '';

        if (this.appShell) {
            if (!this.editModeState.sidebarHidden) {
                this.appShell.classList.remove('sidebar-hidden');
            }
            if (!this.editModeState.tocHidden) {
                this.appShell.classList.remove('toc-hidden');
            }
        }
    }

    async saveContent() {
        if (!this.editorInstance) return false;

        const bodyContent = this.editorInstance.getMarkdown();
        if (!bodyContent || !bodyContent.trim()) {
            window.uiUtils?.showToast?.('内容不能为空', 'error');
            return false;
        }

        const newContent = this.composeDocumentContent(bodyContent);
        const btnOriginalText = this.saveEditBtn?.innerText || '';

        if (this.saveEditBtn) {
            this.saveEditBtn.innerText = '保存中...';
            this.saveEditBtn.disabled = true;
        }

        try {
            const response = await fetch('/api/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify({
                    filename: this.currentFilePath,
                    content: newContent,
                    ensure_front_matter: newContent.trim().startsWith('---'),
                }),
            });

            const data = await response.json();

            if (data.success) {
                if (data.content && this.editorInstance) {
                    const parsed = this.syncLoadedFrontMatterState(data.content);
                    this.editorInstance.setMarkdown(parsed.body || '', false);
                    this.fillMetaPanel();
                }
                return true;
            }

            window.uiUtils?.showAlertDialog('保存失败', data.error || '请稍后再试');
            return false;
        } catch (error) {
            window.uiUtils?.showAlertDialog('保存失败', '网络异常，请稍后再试');
            return false;
        } finally {
            if (this.saveEditBtn) {
                this.saveEditBtn.innerText = btnOriginalText;
                this.saveEditBtn.disabled = false;
            }
        }
    }

    async openEditor() {
        const content = await this.loadFileContent();
        if (content === null) return;
        this.showEditor();
        await this.initializeEditor(content);
    }

    applyFrontMatter() {
        if (!this.editorInstance) return;

        const bodyContent = this.editorInstance.getMarkdown();
        const contentWithMeta = window.frontMatterUtils?.buildFrontMatterFromPanel(bodyContent);
        const parsed = window.frontMatterUtils?.splitFrontMatter(contentWithMeta || '') || {
            metadata: {},
            frontMatterText: '',
        };
        this.loadedFrontMatterText = parsed.frontMatterText || '';
        this.loadedFrontMatterMetadata = parsed.metadata || {};
        this.frontMatterDirty = true;
        this.fillMetaPanel();

        if (this.metaPanel) this.metaPanel.classList.remove('show');
        window.uiUtils?.showToast?.('头部已应用，请点击“保存编辑”提交更改', 'info');
    }

    bindEvents() {
        if (this.editBtn) {
            this.editBtn.addEventListener('click', () => {
                this.openEditor();
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
                    window.uiUtils?.showToast?.('保存成功', 'success');
                    setTimeout(() => {
                        window.location.reload();
                    }, 800);
                }
            });
        }

        if (this.frontMatterBtn) {
            this.frontMatterBtn.addEventListener('click', () => {
                if (!this.editorView || !this.renderView) return;

                if (this.editorView.style.display === 'none' && this.editBtn) {
                    this.openEditor().then(() => {
                        setTimeout(() => {
                            window.frontMatterUtils?.ensureFrontMatterBlock();
                            if (this.metaPanel) this.metaPanel.classList.add('show');
                        }, 240);
                    });
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

        if (this.clearCoverBtn) {
            this.clearCoverBtn.addEventListener('click', () => {
                const metaCoverInput = document.getElementById('metaCover');
                if (metaCoverInput) {
                    metaCoverInput.value = 'none';
                    window.uiUtils?.showToast?.('封面已设置为 none，应用后将不显示封面', 'info');
                }
            });
        }

        if (this.applyMetaBtn) {
            this.applyMetaBtn.addEventListener('click', () => {
                this.applyFrontMatter();
            });
        }
    }
}

window.editorManager = new EditorManager();
