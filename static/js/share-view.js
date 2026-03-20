class ShareViewPage {
    constructor() {
        this.root = document.querySelector('[data-share-view]');
        if (!this.root) {
            return;
        }

        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        this.shareToken = this.root.dataset.shareToken || '';
        this.currentRelativePath = this.root.dataset.currentRelativePath || '';
        this.allowEdit = this.root.dataset.allowEdit === 'true';
        this.viewKind = this.root.dataset.viewKind || '';
        this.shareTitle = this.root.dataset.shareTitle || document.title;
        this.shareUrl = this.root.dataset.shareUrl || window.location.href;
        this.siteName = this.root.dataset.siteName || 'Planning';
        this.editor = null;
        this.layout = document.getElementById('shareLayout');
        this.tocSidebar = document.getElementById('shareTocSidebar');
        this.tocCloseBtn = document.getElementById('shareTocCloseBtn');
        this.tocDockBtn = document.getElementById('shareTocDockBtn');
        this.actionMenuBtn = document.getElementById('shareActionMenuBtn');
        this.actionPopover = document.getElementById('shareActionPopover');
        this.bindEvents();
        this.updateTocToggleButton();
        this.renderQRCode();
        this.enhanceCodeBlocks();
    }

    bindEvents() {
        document.querySelectorAll('[data-share-page-action]').forEach((button) => {
            button.addEventListener('click', async () => {
                await this.handleShareAction(button.dataset.sharePageAction || '');
                this.toggleSharePopover(false);
            });
        });

        this.actionMenuBtn?.addEventListener('click', (event) => {
            event.stopPropagation();
            this.toggleSharePopover();
        });

        this.actionPopover?.addEventListener('click', (event) => {
            event.stopPropagation();
        });

        this.tocCloseBtn?.addEventListener('click', () => {
            this.setTocCollapsed(true);
        });

        this.tocDockBtn?.addEventListener('click', () => {
            this.setTocCollapsed(false);
        });

        document.addEventListener('click', (event) => {
            if (!this.actionPopover || !this.actionMenuBtn) {
                return;
            }

            if (this.actionPopover.contains(event.target) || this.actionMenuBtn.contains(event.target)) {
                return;
            }

            this.toggleSharePopover(false);
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                this.toggleSharePopover(false);
            }
        });

        const editBtn = document.getElementById('shareEditBtn');
        editBtn?.addEventListener('click', async () => {
            await this.enterEditMode();
        });

        const cancelBtn = document.getElementById('shareCancelEditBtn');
        cancelBtn?.addEventListener('click', () => {
            this.exitEditMode();
        });

        const saveBtn = document.getElementById('shareSaveEditBtn');
        saveBtn?.addEventListener('click', async () => {
            await this.saveDocument();
        });
    }

    hasTocSidebar() {
        return Boolean(this.layout && this.tocSidebar);
    }

    setTocCollapsed(collapsed) {
        if (!this.hasTocSidebar()) {
            return;
        }

        const activeElement = document.activeElement;
        if (collapsed && activeElement && this.tocSidebar.contains(activeElement)) {
            if (typeof activeElement.blur === 'function') {
                activeElement.blur();
            }
        }
        if (!collapsed && activeElement === this.tocDockBtn && typeof activeElement.blur === 'function') {
            activeElement.blur();
        }

        this.layout.classList.toggle('toc-collapsed', collapsed);
        this.tocSidebar.hidden = collapsed;
        this.updateTocToggleButton();
    }

    updateTocToggleButton() {
        if (!this.hasTocSidebar()) {
            return;
        }

        const collapsed = this.layout.classList.contains('toc-collapsed');
        this.tocSidebar.hidden = collapsed;

        if (this.tocDockBtn) {
            this.tocDockBtn.classList.toggle('show', collapsed);
            this.tocDockBtn.hidden = !collapsed;
        }

        this.refreshIcons();
    }

    toggleSharePopover(force) {
        if (!this.actionPopover || !this.actionMenuBtn) {
            return;
        }

        const shouldShow = typeof force === 'boolean'
            ? force
            : !this.actionPopover.classList.contains('show');

        this.actionPopover.classList.toggle('show', shouldShow);
        this.actionMenuBtn.setAttribute('aria-expanded', String(shouldShow));
    }

    renderQRCode() {
        const box = document.getElementById('sharePageQrCode');
        window.shareUtils?.renderQRCode(box, this.shareUrl);
    }

    enhanceCodeBlocks() {
        const viewer = document.getElementById('shareDocumentViewer');
        if (!viewer) {
            return;
        }

        viewer.querySelectorAll('pre').forEach((pre) => {
            if (pre.dataset.copyEnhanced === 'true') {
                return;
            }

            const codeElement = pre.querySelector('code');
            const codeText = (codeElement?.innerText || pre.innerText || '').replace(/\s+$/, '');
            if (!codeText) {
                return;
            }

            pre.dataset.copyEnhanced = 'true';

            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'share-code-copy-btn';
            button.textContent = '复制';
            button.addEventListener('click', async () => {
                const copied = await window.shareUtils?.copyText(codeText);
                if (!copied) {
                    this.showToast('复制失败', 'error');
                    return;
                }

                this.showToast('代码已复制', 'success');
                button.textContent = '已复制';
                window.setTimeout(() => {
                    button.textContent = '复制';
                }, 1200);
            });

            pre.appendChild(button);
        });
    }

    getSharePayload() {
        return {
            title: this.shareTitle,
            url: this.shareUrl,
            text: window.shareUtils?.buildShareText({
                title: this.shareTitle,
                url: this.shareUrl,
                siteName: this.siteName,
            }) || this.shareUrl,
        };
    }

    async handleShareAction(action) {
        const payload = this.getSharePayload();

        if (action === 'copy-link') {
            const copied = await window.shareUtils?.copyText(payload.url);
            this.showToast(copied ? '链接已复制' : '复制失败', copied ? 'success' : 'error');
            return;
        }

        if (action === 'copy-text') {
            const copied = await window.shareUtils?.copyText(payload.text);
            this.showToast(copied ? '分享文案已复制' : '复制失败', copied ? 'success' : 'error');
            return;
        }

        if (action === 'system') {
            try {
                const shared = await window.shareUtils?.shareWithSystem(payload);
                if (!shared) {
                    this.showToast('当前浏览器不支持系统分享', 'error');
                }
            } catch (error) {
                this.showToast('系统分享已取消', 'info');
            }
            return;
        }

        if (action === 'wechat') {
            const copied = await window.shareUtils?.copyText(payload.text);
            this.showToast(
                copied ? '已复制分享信息，也可以直接扫码访问' : '请直接让对方扫码访问',
                copied ? 'success' : 'info'
            );
            document.getElementById('sharePageQrCode')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }

        const opened = window.shareUtils?.openPlatformShare(action, payload);
        if (!opened) {
            this.showToast('暂不支持该分享方式', 'error');
        }
    }

    async enterEditMode() {
        if (!this.allowEdit || this.viewKind !== 'file') {
            return;
        }

        this.setTocCollapsed(true);

        const editBtn = document.getElementById('shareEditBtn');
        const viewer = document.getElementById('shareDocumentViewer');
        const panel = document.getElementById('shareEditorPanel');
        const mount = document.getElementById('shareEditorMount');
        if (!viewer || !panel || !mount) {
            return;
        }

        if (editBtn) {
            editBtn.setAttribute('disabled', 'disabled');
        }

        viewer.style.display = 'none';
        panel.style.display = 'block';

        if (!this.editor) {
            try {
                const response = await fetch(`/api/shares/${encodeURIComponent(this.shareToken)}/raw?path=${encodeURIComponent(this.currentRelativePath)}`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.error || '加载文档失败');
                }

                if (!window.toastui?.Editor) {
                    throw new Error('编辑器资源未加载完成');
                }

                mount.innerHTML = '';
                await new Promise((resolve) => window.requestAnimationFrame(resolve));

                this.editor = new window.toastui.Editor({
                    el: mount,
                    initialEditType: 'markdown',
                    previewStyle: 'vertical',
                    height: '520px',
                    initialValue: data.content || '',
                    usageStatistics: false,
                });
            } catch (error) {
                viewer.style.display = '';
                panel.style.display = 'none';
                if (editBtn) {
                    editBtn.removeAttribute('disabled');
                }
                this.showToast(error?.message || '进入编辑模式失败', 'error');
                return;
            }
        }

        window.setTimeout(() => {
            try {
                this.editor?.layout?.();
                this.editor?.focus?.();
            } catch (error) {
                // ignore focus errors
            }
        }, 30);
    }

    exitEditMode() {
        const viewer = document.getElementById('shareDocumentViewer');
        const panel = document.getElementById('shareEditorPanel');
        if (!viewer || !panel) {
            return;
        }

        viewer.style.display = '';
        panel.style.display = 'none';
        document.getElementById('shareEditBtn')?.removeAttribute('disabled');
    }

    async saveDocument() {
        if (!this.editor) {
            return;
        }

        const saveBtn = document.getElementById('shareSaveEditBtn');
        const originalText = saveBtn?.textContent || '保存修改';
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = '保存中...';
        }

        try {
            const response = await fetch(`/api/shares/${encodeURIComponent(this.shareToken)}/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify({
                    path: this.currentRelativePath,
                    content: this.editor.getMarkdown(),
                    ensure_front_matter: true,
                }),
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                this.showToast(data.error || '保存失败', 'error');
                return;
            }

            this.showToast('保存成功，正在刷新内容', 'success');
            window.setTimeout(() => {
                window.location.reload();
            }, 500);
        } catch (error) {
            this.showToast('网络异常，保存失败', 'error');
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
            }
        }
    }

    showToast(message, type = 'success') {
        if (window.uiUtils?.showToast) {
            window.uiUtils.showToast(message, type);
            return;
        }
        console.log(`[${type}] ${message}`);
    }

    refreshIcons() {
        if (window.lucide?.createIcons) {
            window.lucide.createIcons();
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }
    new ShareViewPage();
});
