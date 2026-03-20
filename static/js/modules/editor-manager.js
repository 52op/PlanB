class EditorManager {
    constructor() {
        this.editorInstance = null;
        this.currentFilePath = '';
        this.csrfToken = '';
        this.loadedFrontMatterText = '';
        this.loadedFrontMatterMetadata = {};
        this.frontMatterDirty = false;
        this.canResumeHiddenSession = false;
        this.editModeState = { sidebarHidden: false, tocHidden: false };
        this.handleEditorKeydown = this.handleEditorKeydown.bind(this);
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
        this.toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
        this.toggleTocBtn = document.getElementById('toggleTocBtn');
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

    normalizeImageSize(value) {
        const raw = String(value || '').trim();
        if (!raw) return '';
        if (raw.endsWith('%') || raw.endsWith('px') || raw === 'auto') return raw;
        if (/^\d+$/.test(raw)) return `${raw}px`;
        return raw;
    }

    escapeHtmlAttribute(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        }[char] || char));
    }

    buildImageHtmlMarkup(url, altText, widthValue, heightValue) {
        if (!widthValue && !heightValue) return '';

        const styleParts = [];
        if (widthValue) styleParts.push(`width: ${widthValue}`);
        if (heightValue) styleParts.push(`height: ${heightValue}`);

        return `<img src="${this.escapeHtmlAttribute(url)}" alt="${this.escapeHtmlAttribute(altText)}" style="${styleParts.join('; ')};" />`;
    }

    buildSizedImageMarkup(url, altText) {
        return new Promise((resolve) => {
            const dialog = document.createElement('div');
            dialog.className = 'modal-overlay show';
            dialog.innerHTML = `
                <div class="modal-content image-size-modal">
                    <h3>插入图片尺寸</h3>
                    <p class="image-size-modal-hint">留空按原图插入为 Markdown 图片；填写宽度或高度后，会自动插入为带尺寸的 HTML <code>&lt;img&gt;</code> 标签。</p>
                    <div class="image-size-form">
                        <label class="image-size-field">
                            <span>宽度</span>
                            <input type="text" id="imageSizeWidth" class="form-control" placeholder="如 320、50%、240px">
                        </label>
                        <label class="image-size-field">
                            <span>高度</span>
                            <input type="text" id="imageSizeHeight" class="form-control" placeholder="可留空自动">
                        </label>
                    </div>
                    <div class="image-size-presets">
                        <div class="image-size-presets-title">常用预设</div>
                        <div class="image-size-preset-list">
                            <button type="button" class="btn btn-secondary image-size-preset" data-width="" data-height="">原图</button>
                            <button type="button" class="btn btn-secondary image-size-preset" data-width="320px" data-height="">宽 320</button>
                            <button type="button" class="btn btn-secondary image-size-preset" data-width="480px" data-height="">宽 480</button>
                            <button type="button" class="btn btn-secondary image-size-preset" data-width="50%" data-height="">宽 50%</button>
                            <button type="button" class="btn btn-secondary image-size-preset" data-width="100%" data-height="">宽 100%</button>
                            <button type="button" class="btn btn-secondary image-size-preset" data-width="320px" data-height="320px">1:1</button>
                            <button type="button" class="btn btn-secondary image-size-preset" data-width="400px" data-height="300px">4:3</button>
                            <button type="button" class="btn btn-secondary image-size-preset" data-width="480px" data-height="270px">16:9</button>
                        </div>
                    </div>
                    <div class="image-size-preview-tip">
                        你也可以手动输入宽高，支持纯数字、<code>px</code> 和百分比。
                    </div>
                    <div class="modal-actions">
                        <button type="button" class="btn btn-secondary" id="imageSizeCancelBtn">取消</button>
                        <button type="button" class="btn btn-primary" id="imageSizeConfirmBtn">确定插入</button>
                    </div>
                </div>
            `;

            document.body.appendChild(dialog);

            const widthInput = dialog.querySelector('#imageSizeWidth');
            const heightInput = dialog.querySelector('#imageSizeHeight');
            const confirmBtn = dialog.querySelector('#imageSizeConfirmBtn');
            const cancelBtn = dialog.querySelector('#imageSizeCancelBtn');
            const presetButtons = dialog.querySelectorAll('.image-size-preset');

            const cleanup = () => {
                dialog.removeEventListener('click', handleOverlayClick);
                dialog.removeEventListener('keydown', handleKeydown, true);
                confirmBtn?.removeEventListener('click', handleConfirm);
                cancelBtn?.removeEventListener('click', handleCancel);
                presetButtons.forEach((button) => button.removeEventListener('click', handlePresetClick));
                if (dialog.parentNode) {
                    dialog.parentNode.removeChild(dialog);
                }
            };

            const handleConfirm = () => {
                const widthValue = this.normalizeImageSize(widthInput?.value || '');
                const heightValue = this.normalizeImageSize(heightInput?.value || '');
                cleanup();
                resolve({
                    cancelled: false,
                    markup: this.buildImageHtmlMarkup(url, altText, widthValue, heightValue),
                });
            };

            const handleCancel = () => {
                cleanup();
                resolve({ cancelled: true, markup: '' });
            };

            const handlePresetClick = (event) => {
                const button = event.currentTarget;
                if (!(button instanceof HTMLElement)) return;
                widthInput.value = button.dataset.width || '';
                heightInput.value = button.dataset.height || '';
                widthInput.focus();
            };

            const handleOverlayClick = (event) => {
                if (event.target === dialog) {
                    handleCancel();
                }
            };

            const handleKeydown = (event) => {
                if (event.key === 'Escape') {
                    event.preventDefault();
                    handleCancel();
                } else if (event.key === 'Enter' && !(event.target instanceof HTMLButtonElement)) {
                    event.preventDefault();
                    handleConfirm();
                }
            };

            confirmBtn?.addEventListener('click', handleConfirm);
            cancelBtn?.addEventListener('click', handleCancel);
            presetButtons.forEach((button) => button.addEventListener('click', handlePresetClick));
            dialog.addEventListener('click', handleOverlayClick);
            dialog.addEventListener('keydown', handleKeydown, true);

            widthInput?.focus();
            widthInput?.select();
        });
    }

    updateSidebarIcon(isHidden) {
        if (!this.toggleSidebarBtn) return;
        const icon = this.toggleSidebarBtn.querySelector('i');
        if (icon) {
            icon.setAttribute('data-lucide', isHidden ? 'panel-left-open' : 'panel-left-close');
            window.lucide?.createIcons?.();
        }
        this.toggleSidebarBtn.title = isHidden ? '显示侧边栏' : '隐藏侧边栏';
    }

    updateTocIcon(isHidden) {
        if (!this.toggleTocBtn) return;
        const icon = this.toggleTocBtn.querySelector('i');
        if (icon) {
            icon.setAttribute('data-lucide', isHidden ? 'panel-right-open' : 'panel-right-close');
            window.lucide?.createIcons?.();
        }
        this.toggleTocBtn.title = isHidden ? '显示目录' : '隐藏目录';
    }

    handleEditorKeydown(event) {
        const isSaveShortcut = (event.ctrlKey || event.metaKey) && String(event.key || '').toLowerCase() === 's';
        if (!isSaveShortcut || !this.editorInstance) return;

        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === 'function') {
            event.stopImmediatePropagation();
        }

        this.saveContent().then((success) => {
            if (success) {
                window.uiUtils?.showToast?.('保存成功', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 800);
            }
        });
    }

    bindEditorShortcuts() {
        const editorRoot = document.querySelector('#toastEditor');
        if (!editorRoot || editorRoot.dataset.saveShortcutBound === 'true') return;

        editorRoot.addEventListener('keydown', this.handleEditorKeydown, true);
        editorRoot.dataset.saveShortcutBound = 'true';
    }

    isEditorVisible() {
        return !!this.editorView && this.editorView.style.display !== 'none';
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

        this.bindEditorShortcuts();
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
                const customImage = await this.buildSizedImageMarkup(result.url, 'Image');

                if (customImage.cancelled) {
                    return;
                }

                if (customImage.markup) {
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

    replaceRecentlyInsertedImage(url, markup, attempt = 0) {
        if (!this.editorInstance) return;

        const standardMarkup = `![Image](${url})`;
        const content = this.editorInstance.getMarkdown?.();
        if (!content) {
            return;
        }

        const replaceIndex = content.lastIndexOf(standardMarkup);
        if (replaceIndex === -1) {
            if (attempt < 6) {
                setTimeout(() => this.replaceRecentlyInsertedImage(url, markup, attempt + 1), 60);
            } else {
                window.uiUtils?.showToast?.('图片已插入，但未能自动应用尺寸，请删除后重试', 'warning');
            }
            return;
        }

        const nextContent = `${content.slice(0, replaceIndex)}${markup}${content.slice(replaceIndex + standardMarkup.length)}`;
        if (nextContent !== content) {
            this.editorInstance.setMarkdown(nextContent, false);
            this.editorInstance.focus?.();
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
        this.canResumeHiddenSession = true;
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
                this.updateSidebarIcon(true);
            }
            if (!this.editModeState.tocHidden) {
                this.appShell.classList.add('toc-hidden');
                this.updateTocIcon(true);
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
                this.updateSidebarIcon(false);
            }
            if (!this.editModeState.tocHidden) {
                this.appShell.classList.remove('toc-hidden');
                this.updateTocIcon(false);
            }
        }
    }

    cancelEditing() {
        this.canResumeHiddenSession = false;
        this.frontMatterDirty = false;
        this.loadedFrontMatterText = '';
        this.loadedFrontMatterMetadata = {};
        this.hideEditor();
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
        if (content === null) return false;
        this.showEditor();
        await this.initializeEditor(content);
        return true;
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
                this.cancelEditing();
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

                if (this.editorView.style.display === 'none') {
                    if (this.editorInstance && this.canResumeHiddenSession) {
                        this.showEditor();
                        if (this.metaPanel) this.metaPanel.classList.add('show');
                        return;
                    }

                    this.openEditor().then((opened) => {
                        if (opened && this.metaPanel) this.metaPanel.classList.add('show');
                    });
                    return;
                }

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
