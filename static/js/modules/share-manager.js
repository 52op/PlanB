class ShareManager {
    constructor() {
        this.csrfToken = '';
        this.currentFilePath = '';
        this.currentDirPath = '';
        this.bound = false;
        this.currentTarget = null;
        this.initializeElements();
        this.ensureModal();
    }

    initializeElements() {
        this.shareBtn = document.getElementById('shareBtn');
        this.shareModal = document.getElementById('shareModal');
    }

    ensureModal() {
        if (document.getElementById('shareModal')) {
            this.cacheModalElements();
            return;
        }

        const modal = document.createElement('div');
        modal.id = 'shareModal';
        modal.className = 'share-modal-backdrop';
        modal.innerHTML = `
            <div class="share-modal" role="dialog" aria-modal="true" aria-labelledby="shareModalTitle">
                <div class="share-modal-header">
                    <div>
                        <div class="share-modal-eyebrow">分享设置</div>
                        <h3 id="shareModalTitle">创建分享</h3>
                    </div>
                    <button type="button" class="share-modal-close" id="shareModalClose" aria-label="关闭">
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="share-modal-body">
                    <section class="share-modal-panel" id="shareSetupPanel">
                        <div class="share-target-card">
                            <div class="share-target-icon" id="shareTargetIcon">
                                <i data-lucide="file-text"></i>
                            </div>
                            <div class="share-target-main">
                                <strong id="shareTargetName">当前内容</strong>
                                <span id="shareTargetPath">/</span>
                            </div>
                        </div>
                        <form id="shareForm" class="share-form">
                            <label class="share-form-field">
                                <span>有效期限</span>
                                <select id="shareExpirySelect">
                                    <option value="never">永久有效</option>
                                    <option value="1d">1 天</option>
                                    <option value="7d" selected>7 天</option>
                                    <option value="30d">30 天</option>
                                    <option value="90d">90 天</option>
                                    <option value="custom">自定义时间</option>
                                </select>
                            </label>
                            <label class="share-form-field" id="shareCustomExpiryField" style="display:none;">
                                <span>自定义到期时间</span>
                                <input type="datetime-local" id="shareCustomExpiryInput">
                            </label>
                            <label class="share-switch-row">
                                <span>
                                    <strong>是否加密</strong>
                                    <small>访问前需要输入分享密码</small>
                                </span>
                                <input type="checkbox" id="sharePasswordToggle">
                            </label>
                            <label class="share-form-field" id="sharePasswordField" style="display:none;">
                                <span>分享密码</span>
                                <input type="text" id="sharePasswordInput" placeholder="请输入访问密码">
                            </label>
                            <label class="share-switch-row">
                                <span>
                                    <strong>是否允许编辑</strong>
                                    <small>开启后，分享页中的文档可在浏览器内直接编辑保存</small>
                                </span>
                                <input type="checkbox" id="shareAllowEditToggle">
                            </label>
                            <div class="share-form-footer">
                                <div class="share-form-hint">目录分享支持继续浏览子目录和文档；如果开启编辑，分享页里的文档可以直接修改。</div>
                                <button type="submit" class="action-btn save" id="createShareSubmitBtn">生成分享</button>
                            </div>
                        </form>
                    </section>
                    <section class="share-modal-panel" id="shareResultPanel" style="display:none;">
                        <div class="share-result-hero">
                            <div>
                                <div class="share-modal-eyebrow">分享已生成</div>
                                <h4 id="shareResultTitle">分享链接已准备好</h4>
                                <p id="shareResultDescription">你可以复制链接、发送文案，或者直接让对方扫码访问。</p>
                            </div>
                            <button type="button" class="share-secondary-btn" id="shareCreateAnotherBtn">重新设置</button>
                        </div>
                        <div class="share-link-box">
                            <input type="text" id="shareLinkInput" readonly>
                            <button type="button" class="share-primary-btn" id="copyShareLinkBtn">复制链接</button>
                        </div>
                        <div class="share-result-layout">
                            <div class="share-qrcode-card">
                                <div class="share-qrcode-title">扫码访问</div>
                                <div class="share-qrcode-box" id="shareQrCodeBox"></div>
                                <div class="share-qrcode-tip">微信中可直接扫码，桌面端也可以截图转发。</div>
                            </div>
                            <div class="share-result-actions">
                                <button type="button" class="share-secondary-btn" data-share-action="copy-text">复制分享文案</button>
                                <button type="button" class="share-secondary-btn" data-share-action="system">系统分享</button>
                                <button type="button" class="share-secondary-btn" data-share-action="wechat">微信</button>
                                <button type="button" class="share-secondary-btn" data-share-action="qq">QQ</button>
                                <button type="button" class="share-secondary-btn" data-share-action="qzone">QZone</button>
                                <button type="button" class="share-secondary-btn" data-share-action="weibo">微博</button>
                            </div>
                        </div>
                    </section>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.shareModal = modal;
        this.cacheModalElements();
    }

    cacheModalElements() {
        this.shareModal = document.getElementById('shareModal');
        this.shareForm = document.getElementById('shareForm');
        this.shareSetupPanel = document.getElementById('shareSetupPanel');
        this.shareResultPanel = document.getElementById('shareResultPanel');
        this.shareTargetIcon = document.getElementById('shareTargetIcon');
        this.shareTargetName = document.getElementById('shareTargetName');
        this.shareTargetPath = document.getElementById('shareTargetPath');
        this.sharePasswordToggle = document.getElementById('sharePasswordToggle');
        this.sharePasswordField = document.getElementById('sharePasswordField');
        this.sharePasswordInput = document.getElementById('sharePasswordInput');
        this.shareAllowEditToggle = document.getElementById('shareAllowEditToggle');
        this.shareExpirySelect = document.getElementById('shareExpirySelect');
        this.shareCustomExpiryField = document.getElementById('shareCustomExpiryField');
        this.shareCustomExpiryInput = document.getElementById('shareCustomExpiryInput');
        this.shareLinkInput = document.getElementById('shareLinkInput');
        this.shareQrCodeBox = document.getElementById('shareQrCodeBox');
        this.shareResultTitle = document.getElementById('shareResultTitle');
        this.shareResultDescription = document.getElementById('shareResultDescription');
        this.createShareSubmitBtn = document.getElementById('createShareSubmitBtn');
    }

    setCSRFToken(token) {
        this.csrfToken = token;
    }

    setCurrentPaths(filePath, dirPath) {
        this.currentFilePath = filePath || '';
        this.currentDirPath = dirPath || '';
    }

    bindEvents() {
        if (this.bound) {
            return;
        }
        this.bound = true;

        if (this.shareBtn) {
            this.shareBtn.addEventListener('click', () => {
                this.openCurrentPageShare();
            });
        }

        const closeBtn = document.getElementById('shareModalClose');
        closeBtn?.addEventListener('click', () => this.closeModal());

        this.shareModal?.addEventListener('click', (event) => {
            if (event.target === this.shareModal) {
                this.closeModal();
            }
        });

        this.sharePasswordToggle?.addEventListener('change', () => {
            const showField = this.sharePasswordToggle.checked;
            this.sharePasswordField.style.display = showField ? '' : 'none';
            if (!showField) {
                this.sharePasswordInput.value = '';
            }
        });

        this.shareExpirySelect?.addEventListener('change', () => {
            this.shareCustomExpiryField.style.display = this.shareExpirySelect.value === 'custom' ? '' : 'none';
        });

        this.shareForm?.addEventListener('submit', async (event) => {
            event.preventDefault();
            await this.createShare();
        });

        document.getElementById('copyShareLinkBtn')?.addEventListener('click', async () => {
            const success = await window.shareUtils?.copyText(this.shareLinkInput?.value || '');
            this.showToast(success ? '分享链接已复制' : '复制失败，请手动复制', success ? 'success' : 'error');
        });

        document.getElementById('shareCreateAnotherBtn')?.addEventListener('click', () => {
            this.showSetupPanel();
        });

        this.shareResultPanel?.querySelectorAll('[data-share-action]').forEach((button) => {
            button.addEventListener('click', async () => {
                const action = button.dataset.shareAction;
                await this.handleShareAction(action);
            });
        });
    }

    openCurrentPageShare() {
        const button = this.shareBtn;
        if (!button) {
            return;
        }

        const targetType = button.dataset.targetType || (this.currentFilePath ? 'file' : 'dir');
        const targetPath = button.dataset.targetPath || this.currentFilePath || this.currentDirPath || '';
        const targetName = button.dataset.targetName || '';
        this.openShareModal(targetType, targetPath, targetName);
    }

    openShareModal(targetType, targetPath, targetName) {
        this.currentTarget = {
            type: targetType === 'dir' ? 'dir' : 'file',
            path: targetPath || '',
            name: targetName || targetPath || '根目录',
            siteName: this.shareBtn?.dataset.siteName || document.title || 'Planning',
        };

        this.shareTargetName.textContent = this.currentTarget.name;
        this.shareTargetPath.textContent = this.currentTarget.path || '/';
        this.shareTargetIcon.innerHTML = `<i data-lucide="${this.currentTarget.type === 'dir' ? 'folder-open' : 'file-text'}"></i>`;
        this.sharePasswordToggle.checked = false;
        this.sharePasswordField.style.display = 'none';
        this.sharePasswordInput.value = '';
        this.shareAllowEditToggle.checked = false;
        this.shareExpirySelect.value = '7d';
        this.shareCustomExpiryField.style.display = 'none';
        this.shareCustomExpiryInput.value = '';
        this.showSetupPanel();
        this.shareModal.classList.add('show');

        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    closeModal() {
        this.shareModal?.classList.remove('show');
    }

    showSetupPanel() {
        if (this.shareSetupPanel) {
            this.shareSetupPanel.style.display = '';
        }
        if (this.shareResultPanel) {
            this.shareResultPanel.style.display = 'none';
        }
    }

    showResultPanel() {
        if (this.shareSetupPanel) {
            this.shareSetupPanel.style.display = 'none';
        }
        if (this.shareResultPanel) {
            this.shareResultPanel.style.display = '';
        }
    }

    buildExpiryValue() {
        const selectedValue = this.shareExpirySelect?.value || 'never';
        if (selectedValue !== 'custom') {
            return selectedValue;
        }
        return this.shareCustomExpiryInput?.value || '';
    }

    buildSharePayload() {
        return {
            target_type: this.currentTarget?.type || 'file',
            target_path: this.currentTarget?.path || '',
            target_name: this.currentTarget?.name || '',
            password: this.sharePasswordToggle?.checked ? (this.sharePasswordInput?.value || '') : '',
            allow_edit: Boolean(this.shareAllowEditToggle?.checked),
            expires_at: this.buildExpiryValue(),
        };
    }

    async createShare() {
        const payload = this.buildSharePayload();
        if (payload.expires_at === 'custom' || (this.shareExpirySelect?.value === 'custom' && !payload.expires_at)) {
            this.showToast('请填写自定义到期时间', 'error');
            return;
        }
        if (this.sharePasswordToggle?.checked && !payload.password.trim()) {
            this.showToast('开启加密时请填写分享密码', 'error');
            return;
        }

        const originalLabel = this.createShareSubmitBtn?.textContent || '生成分享';
        if (this.createShareSubmitBtn) {
            this.createShareSubmitBtn.disabled = true;
            this.createShareSubmitBtn.textContent = '生成中...';
        }

        try {
            const response = await fetch('/api/shares', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                this.showToast(data.error || '生成分享失败，请稍后再试', 'error');
                return;
            }

            this.lastShareResult = data.share;
            this.renderShareResult(data.share);
            this.showResultPanel();
        } catch (error) {
            this.showToast('网络异常，生成分享失败', 'error');
        } finally {
            if (this.createShareSubmitBtn) {
                this.createShareSubmitBtn.disabled = false;
                this.createShareSubmitBtn.textContent = originalLabel;
            }
        }
    }

    renderShareResult(share) {
        if (!share) {
            return;
        }

        const shareText = window.shareUtils?.buildShareText({
            title: share.title,
            url: share.url,
            siteName: this.currentTarget?.siteName || 'Planning',
        }) || share.url;

        this.shareLinkInput.value = share.url;
        this.shareResultTitle.textContent = share.title;
        this.shareResultDescription.textContent = share.requires_password
            ? '该分享已开启密码访问。把链接和密码一起发送给对方，或者让对方扫码后输入密码。'
            : '可以直接复制链接、发送分享文案，或者让对方扫码访问。';
        this.shareQrCodeBox.innerHTML = '';
        window.shareUtils?.renderQRCode(this.shareQrCodeBox, share.url);
        this.lastSharePayload = {
            title: share.title,
            url: share.url,
            text: shareText,
        };
    }

    async handleShareAction(action) {
        if (!this.lastSharePayload) {
            return;
        }

        if (action === 'copy-text') {
            const success = await window.shareUtils?.copyText(this.lastSharePayload.text);
            this.showToast(success ? '分享文案已复制' : '复制失败，请手动复制', success ? 'success' : 'error');
            return;
        }

        if (action === 'system') {
            try {
                const shared = await window.shareUtils?.shareWithSystem(this.lastSharePayload);
                if (!shared) {
                    this.showToast('当前浏览器不支持系统分享', 'error');
                }
            } catch (error) {
                this.showToast('系统分享已取消', 'info');
            }
            return;
        }

        if (action === 'wechat') {
            const copied = await window.shareUtils?.copyText(this.lastSharePayload.text);
            this.showToast(
                copied ? '已复制分享信息。你也可以直接让对方扫码访问。' : '可直接让对方扫码访问此分享',
                copied ? 'success' : 'info'
            );
            this.shareQrCodeBox?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }

        const opened = window.shareUtils?.openPlatformShare(action, this.lastSharePayload);
        if (!opened) {
            this.showToast('暂不支持该分享方式', 'error');
        }
    }

    showToast(message, type = 'success') {
        if (window.uiUtils?.showToast) {
            window.uiUtils.showToast(message, type);
            return;
        }
        console.log(`[${type}] ${message}`);
    }
}

window.shareManager = new ShareManager();
