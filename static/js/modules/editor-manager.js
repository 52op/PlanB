class EditorManager {
    constructor() {
        this.editorInstance = null;
        this.currentFilePath = '';
        this.csrfToken = '';
        this.loadedFrontMatterText = '';
        this.loadedFrontMatterMetadata = {};
        this.frontMatterDirty = false;
        this.metaPanelDirty = false;
        this.metaPanelSnapshot = '';
        this.canResumeHiddenSession = false;
        this.editModeState = { sidebarHidden: false, tocHidden: false };
        this.slugValidationTimer = null;
        this.slugValidationRequestId = 0;
        this.handleEditorKeydown = this.handleEditorKeydown.bind(this);
        this.handleMetaPanelFieldChange = this.handleMetaPanelFieldChange.bind(this);
        this.handleSlugFieldBlur = this.handleSlugFieldBlur.bind(this);
        this.handleSlugHintClick = this.handleSlugHintClick.bind(this);
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
        this.metaTitleInput = document.getElementById('metaTitle');
        this.metaSlugInput = document.getElementById('metaSlug');
        this.metaSlugHint = document.getElementById('metaSlugHint');
        this.metaUpdatedInput = document.getElementById('metaUpdated');
        this.metaTemplateSelect = document.getElementById('metaTemplate');
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
        this.metaPanelDirty = false;
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
        this.prepareMetaPanelState().catch(() => {});
    }

    async prepareMetaPanelState() {
        this.captureMetaPanelSnapshot();
        const hasExplicitSlug = !!String(this.loadedFrontMatterMetadata?.slug || '').trim();
        await this.validateSlugAvailability({
            silent: true,
            autoSuggest: !hasExplicitSlug,
        });
        this.captureMetaPanelSnapshot();
    }

    serializeMetaPanelState() {
        const panelState = window.frontMatterUtils?.getPanelState?.() || {};
        return JSON.stringify(panelState);
    }

    captureMetaPanelSnapshot() {
        this.metaPanelSnapshot = this.serializeMetaPanelState();
        this.metaPanelDirty = false;
    }

    updateMetaPanelDirtyState() {
        this.metaPanelDirty = this.serializeMetaPanelState() !== this.metaPanelSnapshot;
    }

    setSlugHint(message, tone = '') {
        if (!this.metaSlugHint) return;

        this.metaSlugHint.textContent = message || '用于博客文章链接，保存前会自动检查唯一性。';
        this.metaSlugHint.classList.remove('is-success', 'is-error', 'is-warning');
        if (tone) {
            this.metaSlugHint.classList.add(tone);
        }

        if (this.metaSlugInput) {
            this.metaSlugInput.classList.remove('is-valid', 'is-invalid');
            if (tone === 'is-success') {
                this.metaSlugInput.classList.add('is-valid');
            } else if (tone === 'is-error') {
                this.metaSlugInput.classList.add('is-invalid');
            }
        }
    }

    setSlugHintWithSuggestion(message, tone = '', suggestedSlug = '') {
        if (!this.metaSlugHint || !suggestedSlug) {
            this.setSlugHint(message, tone);
            return;
        }

        this.metaSlugHint.classList.remove('is-success', 'is-error', 'is-warning');
        if (tone) {
            this.metaSlugHint.classList.add(tone);
        }

        this.metaSlugHint.innerHTML = `${this.escapeHtml(message)} <button type="button" class="meta-slug-suggestion" data-suggested-slug="${this.escapeHtmlAttribute(suggestedSlug)}">${this.escapeHtml(suggestedSlug)}</button>`;

        if (this.metaSlugInput) {
            this.metaSlugInput.classList.remove('is-valid', 'is-invalid');
            if (tone === 'is-success') {
                this.metaSlugInput.classList.add('is-valid');
            } else if (tone === 'is-error') {
                this.metaSlugInput.classList.add('is-invalid');
            }
        }
    }

    getSlugValidationSource() {
        const fileBaseName = (String(this.currentFilePath || '').split('/').pop() || 'post').replace(/\.md$/i, '');
        return this.metaSlugInput?.value.trim()
            || this.metaTitleInput?.value.trim()
            || fileBaseName;
    }

    async requestSlugCheck(rawSlug) {
        const params = new URLSearchParams({
            slug: rawSlug || '',
            filename: this.currentFilePath || '',
            template: this.metaTemplateSelect?.value || 'post',
        });

        const response = await fetch(`/api/front-matter/slug-check?${params.toString()}`, {
            headers: {
                'X-CSRFToken': this.csrfToken,
            },
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Slug 校验失败');
        }
        return data;
    }

    scheduleSlugValidation(options = {}) {
        window.clearTimeout(this.slugValidationTimer);
        this.slugValidationTimer = window.setTimeout(() => {
            this.validateSlugAvailability(options).catch(() => {});
        }, options.immediate ? 0 : 260);
    }

    applySuggestedSlug(suggestedSlug, options = {}) {
        const normalized = window.frontMatterUtils?.slugifyValue?.(suggestedSlug || '') || String(suggestedSlug || '').trim();
        if (!normalized || !this.metaSlugInput) return;

        this.metaSlugInput.value = normalized;
        this.updateMetaPanelDirtyState();
        this.setSlugHint('已自动填入建议值，可继续保存或应用头部。', 'is-warning');

        if (options.focus) {
            this.metaSlugInput.focus();
        }
        if (options.select) {
            this.metaSlugInput.select();
        }
        if (options.validate) {
            this.scheduleSlugValidation({ silent: true, immediate: true });
        }
    }

    syncMetaUpdatedFieldForSave() {
        if (!this.metaUpdatedInput) return;
        const today = new Date().toISOString().slice(0, 10);
        this.metaUpdatedInput.value = today;
        if (!this.metaPanelDirty) {
            this.captureMetaPanelSnapshot();
        }
    }

    async validateSlugAvailability(options = {}) {
        const {
            silent = false,
            autoSuggest = false,
            focusOnError = false,
        } = options;

        if (!this.metaSlugInput || !window.frontMatterUtils) return true;

        const template = this.metaTemplateSelect?.value || 'post';
        const normalizedSlug = window.frontMatterUtils.slugifyValue(this.getSlugValidationSource());
        this.metaSlugInput.value = normalizedSlug;

        if (template !== 'post') {
            this.setSlugHint('当前模板是文档，slug 暂不参与博客路由唯一性校验。切换为文章时会再次检查。', 'is-warning');
            return true;
        }

        const requestId = ++this.slugValidationRequestId;

        try {
            const result = await this.requestSlugCheck(normalizedSlug);
            if (requestId !== this.slugValidationRequestId) {
                return false;
            }

            if (result.available) {
                this.metaSlugInput.value = result.slug || normalizedSlug;
                this.setSlugHint('当前 slug 可用。', 'is-success');
                return true;
            }

            if (autoSuggest && result.suggested_slug && result.suggested_slug !== (result.slug || normalizedSlug)) {
                this.metaSlugInput.value = result.suggested_slug;
                this.setSlugHint(`已自动调整为可用 slug：${result.suggested_slug}`, 'is-warning');
                return true;
            }

            const suggestedText = result.suggested_slug ? `，建议改为 ${result.suggested_slug}` : '';
            const message = `当前 slug 已被其他文章占用${suggestedText}`;
            if (result.suggested_slug) {
                this.setSlugHintWithSuggestion('当前 slug 已被其他文章占用，建议改为', 'is-error', result.suggested_slug);
            } else {
                this.setSlugHint(message, 'is-error');
            }
            if (!silent) {
                await window.uiUtils?.showAlertDialog?.('Slug 冲突', `${message}。`);
            }
            if (focusOnError) {
                if (result.suggested_slug) {
                    this.applySuggestedSlug(result.suggested_slug, {
                        focus: true,
                        select: true,
                        validate: true,
                    });
                } else {
                    this.metaSlugInput.focus();
                    this.metaSlugInput.select();
                }
            }
            return false;
        } catch (error) {
            this.setSlugHint(error.message || 'Slug 校验失败，请稍后重试。', 'is-error');
            if (!silent) {
                await window.uiUtils?.showAlertDialog?.('Slug 校验失败', error.message || '请稍后重试');
            }
            return false;
        }
    }

    bindMetaPanelStateTracking() {
        if (!this.metaPanel || this.metaPanel.dataset.stateBound === 'true') return;

        this.metaPanel.querySelectorAll('input, textarea, select').forEach((field) => {
            field.addEventListener('input', this.handleMetaPanelFieldChange);
            field.addEventListener('change', this.handleMetaPanelFieldChange);
        });

        this.metaSlugInput?.addEventListener('blur', this.handleSlugFieldBlur);
        this.metaSlugHint?.addEventListener('click', this.handleSlugHintClick);
        this.metaPanel.dataset.stateBound = 'true';
    }

    handleMetaPanelFieldChange(event) {
        this.updateMetaPanelDirtyState();

        const target = event.target;
        if (!(target instanceof HTMLElement)) return;

        if (target === this.metaSlugInput || target === this.metaTemplateSelect || target === this.metaTitleInput) {
            this.scheduleSlugValidation({ silent: true });
        }
    }

    handleSlugFieldBlur() {
        this.scheduleSlugValidation({ silent: true, immediate: true });
    }

    handleSlugHintClick(event) {
        const target = event.target.closest('button[data-suggested-slug]');
        if (!(target instanceof HTMLElement)) return;

        this.applySuggestedSlug(target.dataset.suggestedSlug || '', {
            focus: true,
            select: true,
            validate: true,
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

    escapeHtml(value) {
        return this.escapeHtmlAttribute(value);
    }

    buildImageHtmlMarkup(url, altText, widthValue, heightValue) {
        if (!widthValue && !heightValue) return '';

        const styleParts = [];
        if (widthValue) styleParts.push(`width: ${widthValue}`);
        if (heightValue) styleParts.push(`height: ${heightValue}`);

        return `<img src="${this.escapeHtmlAttribute(url)}" alt="${this.escapeHtmlAttribute(altText)}" style="${styleParts.join('; ')};" />`;
    }

    markdownIndexToEditorPosition(content, index) {
        const safeIndex = Math.max(0, Math.min(index, String(content || '').length));
        const before = String(content || '').slice(0, safeIndex);
        const lines = before.split('\n');
        return [Math.max(1, lines.length), lines[lines.length - 1].length];
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
        this.bindMetaPanelStateTracking();
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
            const cursorAt = this.markdownIndexToEditorPosition(nextContent, replaceIndex + markup.length);
            const markdownScroll = document.querySelector('#toastEditor .CodeMirror-scroll');
            const previousScrollTop = markdownScroll ? markdownScroll.scrollTop : null;
            this.editorInstance.setMarkdown(nextContent, false);
            requestAnimationFrame(() => {
                if (markdownScroll && previousScrollTop !== null) {
                    markdownScroll.scrollTop = previousScrollTop;
                }
                this.editorInstance.setSelection?.(cursorAt, cursorAt);
                this.editorInstance.focus?.();
            });
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
        this.metaPanelDirty = false;
        this.metaPanelSnapshot = '';
        this.loadedFrontMatterText = '';
        this.loadedFrontMatterMetadata = {};
        this.setSlugHint('');
        this.hideEditor();
    }

    async saveContent() {
        if (!this.editorInstance) return false;

        const bodyContent = this.editorInstance.getMarkdown();
        if (!bodyContent || !bodyContent.trim()) {
            window.uiUtils?.showToast?.('内容不能为空', 'error');
            return false;
        }

        this.syncMetaUpdatedFieldForSave();
        let newContent = this.composeDocumentContent(bodyContent);
        if (this.metaPanelDirty) {
            const shouldSaveMeta = await window.uiUtils?.showConfirmDialog?.(
                '检测到头部未应用',
                '头部信息已经修改，但还没有点击“应用头部”。是否连同这些头部更改一起保存？选择“取消”则只保存正文和已应用的头部。',
                '同时保存头部'
            );

            if (shouldSaveMeta) {
                const slugReady = await this.validateSlugAvailability({
                    silent: false,
                    autoSuggest: false,
                    focusOnError: true,
                });
                if (!slugReady) {
                    return false;
                }
                newContent = window.frontMatterUtils?.buildFrontMatterFromPanel(bodyContent) || bodyContent;
            }
        }

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

    async applyFrontMatter() {
        if (!this.editorInstance) return;

        this.syncMetaUpdatedFieldForSave();
        const slugReady = await this.validateSlugAvailability({
            silent: false,
            autoSuggest: false,
            focusOnError: true,
        });
        if (!slugReady) return;

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
        this.captureMetaPanelSnapshot();

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
            this.applyMetaBtn.addEventListener('click', async () => {
                await this.applyFrontMatter();
            });
        }
    }
}

window.editorManager = new EditorManager();
