class ArticleCrawler {
    constructor() {
        this.csrfToken = '';
        this.currentFilePath = '';
        this.bound = false;
        this.previewData = null;
        this.previewRenderTimer = null;
        this.markdownViewer = null;
        this.handleBodyInput = this.handleBodyInput.bind(this);
        this.initializeElements();
        this.ensureModal();
    }

    initializeElements() {
        this.crawlBtn = document.getElementById('crawlBtn');
    }

    setCSRFToken(token) {
        this.csrfToken = token || '';
    }

    setCurrentFile(filePath) {
        this.currentFilePath = filePath || '';
    }

    ensureModal() {
        if (document.getElementById('articleCrawlerModal')) {
            this.cacheModalElements();
            return;
        }

        const modal = document.createElement('div');
        modal.id = 'articleCrawlerModal';
        modal.className = 'modal-overlay article-crawler-modal';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="article-crawler-dialog" role="dialog" aria-modal="true" aria-labelledby="articleCrawlerTitle">
                <div class="article-crawler-header">
                    <div>
                        <div class="article-crawler-kicker">内容导入</div>
                        <h3 id="articleCrawlerTitle">爬取文章</h3>
                        <p>输入文章链接后先抓取预览，确认满意再插入到当前文档。首次预览不会下载图片。</p>
                    </div>
                    <button type="button" class="article-crawler-close btn btn-secondary" id="articleCrawlerCloseBtn">关闭</button>
                </div>

                <div class="article-crawler-toolbar">
                    <label class="article-crawler-url-field">
                        <span>文章链接</span>
                        <div class="article-crawler-url-row">
                            <input type="url" id="articleCrawlerUrlInput" class="form-control" placeholder="https://example.com/post/..." autocomplete="off">
                            <button type="button" class="btn btn-primary" id="articleCrawlerFetchBtn">开始爬取</button>
                        </div>
                    </label>
                    <div class="article-crawler-options">
                        <label class="article-crawler-select-field">
                            <span>图片处理</span>
                            <select id="articleCrawlerImageMode" class="form-control">
                                <option value="remote">保留原图地址</option>
                                <option value="download_local">插入时下载到本地</option>
                            </select>
                        </label>
                        <label class="article-crawler-select-field">
                            <span>插入方式</span>
                            <select id="articleCrawlerInsertMode" class="form-control">
                                <option value="append">追加到正文末尾</option>
                                <option value="replace">替换当前正文</option>
                                <option value="cursor">插入到当前光标</option>
                            </select>
                        </label>
                        <label class="article-crawler-check-field">
                            <input type="checkbox" id="articleCrawlerSyncMeta" checked>
                            <span>同步标题、日期、标签和首图到头部</span>
                        </label>
                    </div>
                </div>

                <div class="article-crawler-status" id="articleCrawlerStatus">请输入文章链接，然后点击“开始爬取”。</div>

                <div class="article-crawler-preview" id="articleCrawlerPreview" hidden>
                    <div class="article-crawler-preview-grid">
                        <label class="article-crawler-field">
                            <span>标题</span>
                            <input type="text" id="articleCrawlerTitleInput" class="form-control">
                        </label>
                        <label class="article-crawler-field">
                            <span>日期</span>
                            <input type="date" id="articleCrawlerDateInput" class="form-control">
                        </label>
                        <label class="article-crawler-field article-crawler-field-wide">
                            <span>标签</span>
                            <input type="text" id="articleCrawlerTagsInput" class="form-control" placeholder="多个标签用逗号分隔">
                        </label>
                        <label class="article-crawler-field article-crawler-field-wide">
                            <span>首图地址</span>
                            <input type="text" id="articleCrawlerCoverInput" class="form-control" placeholder="未识别到首图时可手动补充">
                        </label>
                    </div>

                    <div class="article-crawler-cover-box" id="articleCrawlerCoverBox" hidden>
                        <div class="article-crawler-cover-head">
                            <strong>首图预览</strong>
                            <span id="articleCrawlerSourceUrl"></span>
                        </div>
                        <img id="articleCrawlerCoverPreview" alt="抓取首图预览" referrerpolicy="no-referrer" loading="lazy">
                        <div class="article-crawler-cover-tip" id="articleCrawlerCoverTip" hidden>
                            当前站点可能限制直接展示封面图，你仍然可以保留这个地址，或手动替换成别的图片。
                        </div>
                    </div>

                    <div class="article-crawler-body-layout">
                        <label class="article-crawler-body-field">
                            <span>Markdown 源码（可直接微调）</span>
                            <textarea id="articleCrawlerBodyInput" class="form-control" spellcheck="false"></textarea>
                        </label>
                        <div class="article-crawler-render-field">
                            <span>渲染预览</span>
                            <div class="article-crawler-render-box">
                                <div id="articleCrawlerBodyPreview" class="toastui-editor-contents article-crawler-render-view"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="modal-actions article-crawler-actions">
                    <button type="button" class="btn btn-secondary" id="articleCrawlerCancelBtn">取消</button>
                    <button type="button" class="btn btn-primary" id="articleCrawlerInsertBtn" disabled>插入到文档</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.cacheModalElements();
    }

    cacheModalElements() {
        this.modal = document.getElementById('articleCrawlerModal');
        this.urlInput = document.getElementById('articleCrawlerUrlInput');
        this.fetchBtn = document.getElementById('articleCrawlerFetchBtn');
        this.closeBtn = document.getElementById('articleCrawlerCloseBtn');
        this.cancelBtn = document.getElementById('articleCrawlerCancelBtn');
        this.insertBtn = document.getElementById('articleCrawlerInsertBtn');
        this.statusNode = document.getElementById('articleCrawlerStatus');
        this.previewNode = document.getElementById('articleCrawlerPreview');
        this.titleInput = document.getElementById('articleCrawlerTitleInput');
        this.dateInput = document.getElementById('articleCrawlerDateInput');
        this.tagsInput = document.getElementById('articleCrawlerTagsInput');
        this.coverInput = document.getElementById('articleCrawlerCoverInput');
        this.coverBox = document.getElementById('articleCrawlerCoverBox');
        this.coverPreview = document.getElementById('articleCrawlerCoverPreview');
        this.coverTip = document.getElementById('articleCrawlerCoverTip');
        this.sourceUrlNode = document.getElementById('articleCrawlerSourceUrl');
        this.bodyInput = document.getElementById('articleCrawlerBodyInput');
        this.bodyPreview = document.getElementById('articleCrawlerBodyPreview');
        this.imageModeSelect = document.getElementById('articleCrawlerImageMode');
        this.insertModeSelect = document.getElementById('articleCrawlerInsertMode');
        this.syncMetaCheckbox = document.getElementById('articleCrawlerSyncMeta');
    }

    bindEvents() {
        if (!this.crawlBtn) return;
        if (this.bound) return;

        this.crawlBtn.addEventListener('click', () => this.open());
        this.closeBtn?.addEventListener('click', () => this.close());
        this.cancelBtn?.addEventListener('click', () => this.close());
        this.fetchBtn?.addEventListener('click', () => this.fetchPreview());
        this.insertBtn?.addEventListener('click', () => this.insertIntoDocument());
        this.coverInput?.addEventListener('input', () => this.updateCoverPreview());
        this.coverPreview?.addEventListener('load', () => {
            if (this.coverTip) this.coverTip.hidden = true;
        });
        this.coverPreview?.addEventListener('error', () => {
            if (this.coverTip) this.coverTip.hidden = false;
        });
        this.bodyInput?.addEventListener('input', this.handleBodyInput);
        this.urlInput?.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                this.fetchPreview();
            }
        });
        this.modal?.addEventListener('click', (event) => {
            if (event.target === this.modal) {
                this.close();
            }
        });

        this.bound = true;
    }

    open() {
        if (!this.modal) return;
        this.resetInsertModeOptions();
        if (this.syncMetaCheckbox) {
            this.syncMetaCheckbox.checked = true;
        }
        this.modal.style.display = 'flex';
        this.urlInput?.focus();
        this.urlInput?.select();
    }

    close() {
        if (!this.modal) return;
        this.modal.style.display = 'none';
    }

    setBusy(isBusy, actionText = '开始爬取') {
        if (this.fetchBtn) {
            this.fetchBtn.disabled = isBusy;
            this.fetchBtn.textContent = isBusy ? '爬取中...' : actionText;
        }
        if (this.insertBtn) {
            this.insertBtn.disabled = isBusy || !this.previewData;
        }
    }

    setStatus(message, tone = '') {
        if (!this.statusNode) return;
        this.statusNode.textContent = message || '';
        this.statusNode.classList.remove('is-error', 'is-success', 'is-muted');
        if (tone) {
            this.statusNode.classList.add(tone);
        }
    }

    resetInsertModeOptions() {
        const cursorAvailable = Boolean(window.editorManager?.isEditorVisible?.());
        const cursorOption = this.insertModeSelect?.querySelector('option[value="cursor"]');
        if (cursorOption) {
            cursorOption.disabled = !cursorAvailable;
        }

        if (!cursorAvailable && this.insertModeSelect?.value === 'cursor') {
            this.insertModeSelect.value = 'append';
        } else if (cursorAvailable) {
            this.insertModeSelect.value = 'cursor';
        }
    }

    populatePreview(data) {
        this.previewData = data || null;
        if (!data) {
            if (this.previewNode) this.previewNode.hidden = true;
            if (this.insertBtn) this.insertBtn.disabled = true;
            this.renderMarkdownPreview('');
            return;
        }

        this.previewNode.hidden = false;
        this.titleInput.value = data.title || '';
        this.dateInput.value = data.date || '';
        this.tagsInput.value = Array.isArray(data.tags) ? data.tags.join(', ') : '';
        this.coverInput.value = data.cover || '';
        this.bodyInput.value = data.markdown || '';
        this.sourceUrlNode.textContent = data.source_url || '';
        this.updateCoverPreview();
        this.renderMarkdownPreview(data.markdown || '');
        this.insertBtn.disabled = false;
    }

    buildCoverPreviewUrl(rawUrl) {
        const normalized = String(rawUrl || '').trim();
        if (!normalized) return '';
        if (!/^https?:\/\//i.test(normalized)) {
            return normalized;
        }

        const params = new URLSearchParams({ url: normalized });
        return `/api/crawl/image-proxy?${params.toString()}`;
    }

    updateCoverPreview() {
        const coverValue = (this.coverInput?.value || '').trim();
        if (!coverValue) {
            if (this.coverBox) this.coverBox.hidden = true;
            if (this.coverPreview) this.coverPreview.removeAttribute('src');
            if (this.coverTip) this.coverTip.hidden = true;
            return;
        }

        if (this.coverPreview) {
            this.coverPreview.src = this.buildCoverPreviewUrl(coverValue);
        }
        if (this.coverBox) {
            this.coverBox.hidden = false;
        }
        if (this.coverTip) {
            this.coverTip.hidden = true;
        }
    }

    handleBodyInput() {
        window.clearTimeout(this.previewRenderTimer);
        this.previewRenderTimer = window.setTimeout(() => {
            this.renderMarkdownPreview(this.bodyInput?.value || '');
        }, 180);
    }

    renderMarkdownPreview(markdown) {
        if (!this.bodyPreview) return;

        const content = String(markdown || '');
        if (!content.trim()) {
            this.bodyPreview.innerHTML = '<p class="article-crawler-render-empty">这里会显示正文的渲染效果，方便你边改边看。</p>';
            return;
        }

        if (window.toastui?.Editor?.factory) {
            if (!this.markdownViewer) {
                this.bodyPreview.innerHTML = '';
                this.markdownViewer = window.toastui.Editor.factory({
                    el: this.bodyPreview,
                    viewer: true,
                    initialValue: content,
                    usageStatistics: false,
                });
                return;
            }

            if (typeof this.markdownViewer.setMarkdown === 'function') {
                this.markdownViewer.setMarkdown(content);
                return;
            }
        }

        this.bodyPreview.textContent = content;
    }

    async fetchPreview() {
        const url = (this.urlInput?.value || '').trim();
        if (!url) {
            this.setStatus('请输入要抓取的文章链接。', 'is-error');
            this.urlInput?.focus();
            return;
        }

        this.setBusy(true);
        this.setStatus('正在抓取文章并整理为 Markdown 预览，请稍候...', 'is-muted');
        this.populatePreview(null);

        try {
            const response = await fetch('/api/crawl/preview', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify({
                    url,
                    filename: this.currentFilePath,
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '抓取失败');
            }

            this.populatePreview(data);
            this.setStatus('预览已生成。你可以微调标题、日期、标签、首图和正文，再决定如何插入。', 'is-success');
        } catch (error) {
            this.setStatus(error.message || '抓取失败，请稍后重试。', 'is-error');
        } finally {
            this.setBusy(false);
        }
    }

    collectMetadata() {
        return {
            title: (this.titleInput?.value || '').trim(),
            date: (this.dateInput?.value || '').trim(),
            tags: (this.tagsInput?.value || '')
                .split(',')
                .map((item) => item.trim())
                .filter(Boolean),
            cover: (this.coverInput?.value || '').trim(),
        };
    }

    async insertIntoDocument() {
        if (!this.previewData) {
            this.setStatus('请先抓取并确认预览内容。', 'is-error');
            return;
        }

        const bodyMarkdown = (this.bodyInput?.value || '').trim();
        if (!bodyMarkdown) {
            this.setStatus('正文内容不能为空，请调整后再插入。', 'is-error');
            this.bodyInput?.focus();
            return;
        }

        const metadata = this.collectMetadata();
        const imageMode = this.imageModeSelect?.value || 'remote';
        const insertMode = this.insertModeSelect?.value || 'append';
        const syncFrontMatter = !!this.syncMetaCheckbox?.checked;

        this.setBusy(true, '开始爬取');
        this.insertBtn.textContent = '处理中...';
        this.setStatus(imageMode === 'download_local' ? '正在下载图片并准备插入文档...' : '正在准备插入文档...', 'is-muted');

        try {
            const response = await fetch('/api/crawl/finalize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify({
                    filename: this.currentFilePath,
                    markdown: bodyMarkdown,
                    cover: metadata.cover,
                    image_mode: imageMode,
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '插入前处理失败');
            }

            const success = await window.editorManager?.importExternalContent?.({
                markdown: data.markdown || bodyMarkdown,
                mode: insertMode,
                syncFrontMatter,
                metadata: {
                    ...metadata,
                    cover: data.cover || metadata.cover,
                },
            });

            if (!success) {
                throw new Error('编辑器未能成功接收导入内容');
            }

            if (Array.isArray(data.warnings) && data.warnings.length) {
                window.uiUtils?.showToast?.(data.warnings[0], 'warning');
            } else {
                window.uiUtils?.showToast?.('文章内容已插入到编辑器', 'success');
            }

            this.close();
        } catch (error) {
            this.setStatus(error.message || '插入失败，请稍后重试。', 'is-error');
        } finally {
            this.setBusy(false);
            this.insertBtn.textContent = '插入到文档';
        }
    }
}

window.articleCrawler = new ArticleCrawler();
