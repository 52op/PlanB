class ShareManager {
    constructor() {
        this.csrfToken = '';
        this.currentFilePath = '';
        this.currentDirPath = '';
        this.bound = false;
        this.currentTarget = null;
        this.currentShares = [];
        this.lastSharePayload = null;
        this.manageScope = 'current';
        this.manageEditingToken = '';
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
                    <button type="button" class="share-modal-close" id="shareModalClose" aria-label="Close">
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="share-modal-tabs" id="shareModalTabs">
                    <button type="button" class="share-modal-tab active" data-share-tab="create">
                        <i data-lucide="sparkles"></i>
                        创建分享
                    </button>
                    <button type="button" class="share-modal-tab" data-share-tab="manage">
                        <i data-lucide="list-tree"></i>
                        已分享
                        <span class="share-tab-count" id="shareManagedCount">0</span>
                    </button>
                </div>
                <div class="share-modal-body">
                    <section class="share-modal-panel" id="shareSetupPanel">
                        <div class="share-target-card">
                            <div class="share-target-icon" id="shareTargetIcon">
                                <i data-lucide="file-text"></i>
                            </div>
                            <div class="share-target-main">
                                <strong id="shareTargetName">当前对象</strong>
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
                                    <small>访问前需要输入分享密码。</small>
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
                                    <small>开启后，对方可以在分享页中直接编辑并保存文档。</small>
                                </span>
                                <input type="checkbox" id="shareAllowEditToggle">
                            </label>
                            <div class="share-form-footer">
                                <div class="share-form-hint">目录分享支持继续浏览子目录和文档；如果开启编辑，分享页中的文档也可以直接修改保存。</div>
                                <button type="submit" class="action-btn save" id="createShareSubmitBtn">生成分享</button>
                            </div>
                        </form>
                    </section>
                    <section class="share-modal-panel" id="shareResultPanel" style="display:none;">
                        <div class="share-result-hero">
                            <div>
                                <div class="share-modal-eyebrow">分享已生成</div>
                                <h4 id="shareResultTitle">分享链接已准备好</h4>
                                <p id="shareResultDescription">你可以复制链接、转发文案，或者直接让对方扫码访问。</p>
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
                                <div class="share-qrcode-tip">微信可直接扫码，桌面端也可以截图转发。</div>
                            </div>
                            <div class="share-result-actions">
                                <button type="button" class="share-secondary-btn" data-share-action="copy-text">复制分享文案</button>
                                <button type="button" class="share-secondary-btn" data-share-action="system">系统分享</button>
                                <button type="button" class="share-secondary-btn" data-share-action="wechat">WeChat</button>
                                <button type="button" class="share-secondary-btn" data-share-action="qq">QQ</button>
                                <button type="button" class="share-secondary-btn" data-share-action="qzone">QZone</button>
                                <button type="button" class="share-secondary-btn" data-share-action="weibo">微博</button>
                            </div>
                        </div>
                    </section>
                    <section class="share-modal-panel" id="shareManagePanel" style="display:none;">
                        <div class="share-manage-head">
                            <div>
                                <div class="share-modal-eyebrow">已分享管理</div>
                                <div class="share-manage-title" id="shareManageTitle">当前对象的分享链接</div>
                            </div>
                            <button type="button" class="share-secondary-btn" id="refreshShareListBtn">刷新列表</button>
                        </div>
                        <div class="share-manage-summary" id="shareManageSummary"></div>
                        <div class="share-manage-empty" id="shareManageEmpty" style="display:none;">当前范围内还没有分享链接。</div>
                        <div class="share-manage-list" id="shareManageList"></div>
                        <form id="shareManageForm" class="share-manage-editor" style="display:none;">
                            <div class="share-manage-editor-head">
                                <div>
                                    <strong id="shareManageEditorTitle">编辑分享设置</strong>
                                    <span id="shareManageEditorHint">修改当前分享的有效期、密码和编辑权限。</span>
                                </div>
                                <button type="button" class="share-secondary-btn" id="cancelManageEditBtn">Cancel</button>
                            </div>
                            <div class="share-form share-manage-form-grid">
                                <label class="share-form-field">
                                    <span>有效期限</span>
                                    <select id="manageExpirySelect">
                                        <option value="never">永久有效</option>
                                        <option value="1d">1 天</option>
                                        <option value="7d">7 天</option>
                                        <option value="30d">30 天</option>
                                        <option value="90d">90 天</option>
                                        <option value="custom">自定义时间</option>
                                    </select>
                                </label>
                                <label class="share-form-field" id="manageCustomExpiryField" style="display:none;">
                                    <span>自定义到期时间</span>
                                    <input type="datetime-local" id="manageCustomExpiryInput">
                                </label>
                                <label class="share-switch-row">
                                    <span>
                                        <strong>是否加密</strong>
                                        <small>关闭后，将以公开方式访问这个分享。</small>
                                    </span>
                                    <input type="checkbox" id="managePasswordToggle">
                                </label>
                                <label class="share-form-field" id="managePasswordField" style="display:none;">
                                    <span>新的分享密码</span>
                                    <input type="text" id="managePasswordInput" placeholder="留空表示保留当前密码">
                                </label>
                                <label class="share-switch-row">
                                    <span>
                                        <strong>是否允许编辑</strong>
                                        <small>开启后，对方可以在分享页中直接编辑并保存。</small>
                                    </span>
                                    <input type="checkbox" id="manageAllowEditToggle">
                                </label>
                            </div>
                            <div class="share-form-footer">
                                <div class="share-form-hint">停用分享会立刻让当前链接失效；重新启用后会恢复访问，你也可以在这里重新设置期限。</div>
                                <button type="submit" class="action-btn save" id="saveManageShareBtn">保存设置</button>
                            </div>
                        </form>
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
        this.shareModalTitle = document.getElementById('shareModalTitle');
        this.shareModalTabs = document.getElementById('shareModalTabs');
        this.shareManagedCount = document.getElementById('shareManagedCount');
        this.shareForm = document.getElementById('shareForm');
        this.shareSetupPanel = document.getElementById('shareSetupPanel');
        this.shareResultPanel = document.getElementById('shareResultPanel');
        this.shareManagePanel = document.getElementById('shareManagePanel');
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
        this.refreshShareListBtn = document.getElementById('refreshShareListBtn');
        this.shareManageTitle = document.getElementById('shareManageTitle');
        this.shareManageSummary = document.getElementById('shareManageSummary');
        this.shareManageEmpty = document.getElementById('shareManageEmpty');
        this.shareManageList = document.getElementById('shareManageList');
        this.shareManageForm = document.getElementById('shareManageForm');
        this.shareManageEditorTitle = document.getElementById('shareManageEditorTitle');
        this.shareManageEditorHint = document.getElementById('shareManageEditorHint');
        this.manageExpirySelect = document.getElementById('manageExpirySelect');
        this.manageCustomExpiryField = document.getElementById('manageCustomExpiryField');
        this.manageCustomExpiryInput = document.getElementById('manageCustomExpiryInput');
        this.managePasswordToggle = document.getElementById('managePasswordToggle');
        this.managePasswordField = document.getElementById('managePasswordField');
        this.managePasswordInput = document.getElementById('managePasswordInput');
        this.manageAllowEditToggle = document.getElementById('manageAllowEditToggle');
        this.saveManageShareBtn = document.getElementById('saveManageShareBtn');
        this.ensureManageScopeControls();
        this.shareManageScope = document.getElementById('shareManageScope');
    }

    ensureManageScopeControls() {
        const head = this.shareManagePanel?.querySelector('.share-manage-head');
        const refreshButton = document.getElementById('refreshShareListBtn');
        if (!head || !refreshButton || document.getElementById('shareManageScope')) return;

        const actions = document.createElement('div');
        actions.className = 'share-manage-head-actions';
        actions.innerHTML = `
            <div class="share-manage-scope" id="shareManageScope">
                <button type="button" class="share-scope-btn active" data-share-scope="current">当前对象</button>
                <button type="button" class="share-scope-btn" data-share-scope="all">当前账号全部</button>
            </div>
        `;
        refreshButton.parentNode.insertBefore(actions, refreshButton);
        actions.appendChild(refreshButton);
    }

    setCSRFToken(token) {
        this.csrfToken = token;
    }

    setCurrentPaths(filePath, dirPath) {
        this.currentFilePath = filePath || '';
        this.currentDirPath = dirPath || '';
    }

    bindEvents() {
        if (this.bound) return;
        this.bound = true;

        this.shareBtn?.addEventListener('click', () => this.openCurrentPageShare());
        document.getElementById('shareModalClose')?.addEventListener('click', () => this.closeModal());
        this.shareModal?.addEventListener('click', (event) => {
            if (event.target === this.shareModal) this.closeModal();
        });

        this.shareModalTabs?.querySelectorAll('[data-share-tab]').forEach((button) => {
            button.addEventListener('click', async () => {
                if ((button.dataset.shareTab || '') === 'manage') {
                    await this.showManagePanel();
                    return;
                }
                this.showSetupPanel();
            });
        });

        this.sharePasswordToggle?.addEventListener('change', () => this.syncCreatePasswordField());
        this.shareExpirySelect?.addEventListener('change', () => this.syncCreateExpiryField());
        this.shareForm?.addEventListener('submit', async (event) => {
            event.preventDefault();
            await this.createShare();
        });

        document.getElementById('copyShareLinkBtn')?.addEventListener('click', async () => {
            const ok = await window.shareUtils?.copyText(this.shareLinkInput?.value || '');
            this.showToast(ok ? '分享链接已复制' : '复制失败，请手动复制', ok ? 'success' : 'error');
        });

        document.getElementById('shareCreateAnotherBtn')?.addEventListener('click', () => this.showSetupPanel());
        this.shareResultPanel?.querySelectorAll('[data-share-action]').forEach((button) => {
            button.addEventListener('click', async () => this.handleShareAction(button.dataset.shareAction || ''));
        });

        this.refreshShareListBtn?.addEventListener('click', async () => this.loadShareList({ showToastOnSuccess: true }));
        this.shareManageScope?.querySelectorAll('[data-share-scope]').forEach((button) => {
            button.addEventListener('click', async () => {
                await this.setManageScope(button.dataset.shareScope || 'current');
            });
        });
        this.shareManageList?.addEventListener('click', async (event) => this.handleManageListClick(event));
        this.manageExpirySelect?.addEventListener('change', () => this.syncManageExpiryField());
        this.managePasswordToggle?.addEventListener('change', () => this.syncManagePasswordField());
        document.getElementById('cancelManageEditBtn')?.addEventListener('click', () => this.closeManageEditor());
        this.shareManageForm?.addEventListener('submit', async (event) => {
            event.preventDefault();
            await this.saveManagedShare();
        });
    }

    async openCurrentPageShare() {
        const button = this.shareBtn;
        if (!button) return;

        const type = button.dataset.targetType || (this.currentFilePath ? 'file' : 'dir');
        const path = button.dataset.targetPath || this.currentFilePath || this.currentDirPath || '';
        const name = button.dataset.targetName || '';
        await this.openShareModal(type, path, name);
    }

    async openShareModal(targetType, targetPath, targetName) {
        this.manageScope = 'current';
        this.currentTarget = {
            type: targetType === 'dir' ? 'dir' : 'file',
            path: targetPath || '',
            name: targetName || targetPath || '根目录',
            siteName: this.shareBtn?.dataset.siteName || document.title || 'Planning',
        };

        this.updateManageScopeButtons();
        this.updateManageHead();
        this.shareTargetName.textContent = this.currentTarget.name;
        this.shareTargetPath.textContent = this.currentTarget.path || '/';
        this.shareTargetIcon.innerHTML = `<i data-lucide="${this.currentTarget.type === 'dir' ? 'folder-open' : 'file-text'}"></i>`;
        this.resetCreateForm();
        this.closeManageEditor();
        this.showSetupPanel();
        this.shareModal?.classList.add('show');
        await this.loadShareList({ silent: true });
        this.refreshIcons();
    }

    closeModal() {
        this.shareModal?.classList.remove('show');
        this.closeManageEditor();
    }

    resetCreateForm() {
        this.sharePasswordToggle.checked = false;
        this.sharePasswordInput.value = '';
        this.shareAllowEditToggle.checked = false;
        this.shareExpirySelect.value = '7d';
        this.shareCustomExpiryInput.value = '';
        this.syncCreatePasswordField();
        this.syncCreateExpiryField();
    }

    showSetupPanel() {
        this.setActiveTab('create');
        this.shareModalTitle.textContent = '创建分享';
        this.shareSetupPanel.style.display = '';
        this.shareResultPanel.style.display = 'none';
        this.shareManagePanel.style.display = 'none';
    }

    showResultPanel() {
        this.setActiveTab('create');
        this.shareModalTitle.textContent = '分享结果';
        this.shareSetupPanel.style.display = 'none';
        this.shareResultPanel.style.display = '';
        this.shareManagePanel.style.display = 'none';
    }

    async showManagePanel() {
        this.setActiveTab('manage');
        this.shareModalTitle.textContent = '已分享管理';
        this.shareSetupPanel.style.display = 'none';
        this.shareResultPanel.style.display = 'none';
        this.shareManagePanel.style.display = '';
        this.updateManageHead();
        await this.loadShareList({ silent: true });
    }

    setActiveTab(tabName) {
        this.shareModalTabs?.querySelectorAll('[data-share-tab]').forEach((button) => {
            button.classList.toggle('active', button.dataset.shareTab === tabName);
        });
    }

    async setManageScope(scope) {
        this.manageScope = scope === 'all' ? 'all' : 'current';
        this.updateManageScopeButtons();
        this.updateManageHead();
        this.closeManageEditor();
        await this.loadShareList({ silent: true });
    }

    updateManageScopeButtons() {
        this.shareManageScope?.querySelectorAll('[data-share-scope]').forEach((button) => {
            button.classList.toggle('active', (button.dataset.shareScope || 'current') === this.manageScope);
        });
    }

    updateManageHead() {
        if (!this.shareManageTitle) return;

        if (this.manageScope === 'all') {
            this.shareManageTitle.textContent = '当前账号创建的全部分享';
            if (this.shareManageEmpty) this.shareManageEmpty.textContent = '当前账号下还没有分享链接。';
            return;
        }

        const label = this.currentTarget
            ? `${this.currentTarget.type === 'dir' ? '目录' : '文档'}：${this.currentTarget.path || '/'}`
            : '当前对象';
        this.shareManageTitle.textContent = `${label} 的分享链接`;
        if (this.shareManageEmpty) this.shareManageEmpty.textContent = '当前对象还没有分享链接。';
    }

    syncCreatePasswordField() {
        const enabled = Boolean(this.sharePasswordToggle?.checked);
        this.sharePasswordField.style.display = enabled ? '' : 'none';
        if (!enabled) this.sharePasswordInput.value = '';
    }

    syncCreateExpiryField() {
        this.shareCustomExpiryField.style.display = this.shareExpirySelect.value === 'custom' ? '' : 'none';
    }

    syncManagePasswordField() {
        const enabled = Boolean(this.managePasswordToggle?.checked);
        this.managePasswordField.style.display = enabled ? '' : 'none';
        if (!enabled) this.managePasswordInput.value = '';
    }

    syncManageExpiryField() {
        this.manageCustomExpiryField.style.display = this.manageExpirySelect.value === 'custom' ? '' : 'none';
    }

    buildExpiryValue() {
        return this.shareExpirySelect.value !== 'custom' ? this.shareExpirySelect.value : (this.shareCustomExpiryInput.value || '');
    }

    buildManageExpiryValue() {
        return this.manageExpirySelect.value !== 'custom' ? this.manageExpirySelect.value : (this.manageCustomExpiryInput.value || '');
    }

    buildSharePayload() {
        return {
            target_type: this.currentTarget?.type || 'file',
            target_path: this.currentTarget?.path || '',
            target_name: this.currentTarget?.name || '',
            password: this.sharePasswordToggle.checked ? (this.sharePasswordInput.value || '') : '',
            allow_edit: Boolean(this.shareAllowEditToggle?.checked),
            expires_at: this.buildExpiryValue(),
        };
    }

    async createShare() {
        const payload = this.buildSharePayload();
        if (this.shareExpirySelect.value === 'custom' && !payload.expires_at) {
            return this.showToast('请选择自定义到期时间', 'error');
        }
        if (this.sharePasswordToggle.checked && !payload.password.trim()) {
            return this.showToast('请输入分享密码', 'error');
        }

        const original = this.createShareSubmitBtn.textContent;
        this.createShareSubmitBtn.disabled = true;
        this.createShareSubmitBtn.textContent = '生成中...';

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
                return this.showToast(data.error || '生成分享失败', 'error');
            }

            this.renderShareResult(data.share);
            this.showResultPanel();
            await this.loadShareList({ silent: true });
        } catch (_) {
            this.showToast('生成分享时网络异常', 'error');
        } finally {
            this.createShareSubmitBtn.disabled = false;
            this.createShareSubmitBtn.textContent = original;
        }
    }

    renderShareResult(share) {
        const text = window.shareUtils?.buildShareText({
            title: share.title,
            url: share.url,
            siteName: this.currentTarget?.siteName || 'Planning',
        }) || share.url;

        this.shareLinkInput.value = share.url;
        this.shareResultTitle.textContent = share.title || '分享链接已准备好';
        this.shareResultDescription.textContent = share.requires_password
            ? '该分享已开启密码访问。请把链接和密码一起发给对方，或让对方扫码后输入密码。'
            : '可以直接复制链接、转发分享文案，或者让对方扫码访问。';
        this.shareQrCodeBox.innerHTML = '';
        window.shareUtils?.renderQRCode(this.shareQrCodeBox, share.url);
        this.lastSharePayload = { title: share.title, url: share.url, text };
    }

    async handleShareAction(action) {
        if (!this.lastSharePayload) return;

        if (action === 'copy-text') {
            const ok = await window.shareUtils?.copyText(this.lastSharePayload.text);
            this.showToast(ok ? '分享文案已复制' : '复制失败，请手动复制', ok ? 'success' : 'error');
            return;
        }

        if (action === 'system') {
            try {
                const shared = await window.shareUtils?.shareWithSystem(this.lastSharePayload);
                if (!shared) this.showToast('当前浏览器不支持系统分享', 'error');
            } catch (_) {
                this.showToast('系统分享已取消', 'info');
            }
            return;
        }

        if (action === 'wechat') {
            const ok = await window.shareUtils?.copyText(this.lastSharePayload.text);
            this.showToast(ok ? '已复制分享信息，也可以直接让对方扫码访问。' : '对方也可以直接扫码访问。', ok ? 'success' : 'info');
            this.shareQrCodeBox?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }

        if (!window.shareUtils?.openPlatformShare(action, this.lastSharePayload)) {
            this.showToast('暂不支持该分享方式', 'error');
        }
    }

    async loadShareList(options = {}) {
        if (!this.currentTarget) return;

        const { silent = false, showToastOnSuccess = false } = options;
        this.updateManageScopeButtons();
        this.updateManageHead();

        try {
            const endpoint = this.manageScope === 'all' ? '/api/shares/mine' : '/api/shares';
            const params = this.manageScope === 'all'
                ? new URLSearchParams()
                : new URLSearchParams({
                    target_type: this.currentTarget.type,
                    target_path: this.currentTarget.path,
                });
            const query = params.toString();
            const response = await fetch(query ? `${endpoint}?${query}` : endpoint, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                if (!silent) this.showToast(data.error || '读取分享列表失败', 'error');
                return;
            }

            this.currentShares = Array.isArray(data.items) ? data.items : [];
            this.shareManagedCount.textContent = String(this.currentShares.length);
            this.renderManageSummary();
            this.renderShareList();
            if (this.manageEditingToken && !this.findShare(this.manageEditingToken)) {
                this.closeManageEditor();
            }
            if (showToastOnSuccess) this.showToast('分享列表已刷新', 'success');
        } catch (_) {
            if (!silent) this.showToast('读取分享列表时网络异常', 'error');
        }
    }

    renderManageSummary() {
        const total = this.currentShares.length;
        const active = this.currentShares.filter((item) => item.is_active).length;
        const secured = this.currentShares.filter((item) => item.requires_password).length;
        const editable = this.currentShares.filter((item) => item.allow_edit).length;

        this.shareManageSummary.innerHTML = `
            <div class="share-manage-metric"><strong>${total}</strong><span>总数</span></div>
            <div class="share-manage-metric"><strong>${active}</strong><span>启用中</span></div>
            <div class="share-manage-metric"><strong>${secured}</strong><span>已加密</span></div>
            <div class="share-manage-metric"><strong>${editable}</strong><span>可编辑</span></div>
        `;
    }

    renderShareList() {
        if (!this.currentShares.length) {
            this.shareManageList.innerHTML = '';
            this.shareManageEmpty.style.display = '';
            return;
        }

        this.shareManageEmpty.style.display = 'none';
        this.shareManageList.innerHTML = this.currentShares.map((share) => {
            const status = share.is_active ? '启用中' : '已停用';
            const toggleLabel = share.is_active ? '停用' : '启用';
            const expires = share.expires_at ? this.formatDateTime(share.expires_at) : '永久有效';
            const created = share.created_at ? this.formatDateTime(share.created_at) : '--';
            const title = this.escapeHtml(share.title || '未命名分享');
            const url = this.escapeHtml(share.url || '');
            const token = this.escapeHtml(share.token || '');
            const targetMeta = this.manageScope === 'all'
                ? `<span class="share-manage-target">${share.target_type === 'dir' ? '目录' : '文档'}：${this.escapeHtml(share.target_path || '/')}</span>`
                : '';

            return `
                <article class="share-manage-item">
                    <div class="share-manage-item-head">
                        <div class="share-manage-item-main">
                            <strong>${title}</strong>
                            <span>${url}</span>
                            ${targetMeta}
                        </div>
                        <div class="share-manage-badges">
                            <span class="share-manage-badge ${share.is_active ? 'is-active' : 'is-inactive'}">${status}</span>
                            <span class="share-manage-badge">${share.allow_edit ? '允许编辑' : '只读浏览'}</span>
                            <span class="share-manage-badge">${share.requires_password ? '已加密' : '公开访问'}</span>
                        </div>
                    </div>
                    <div class="share-manage-meta">
                        <span>创建于 ${created}</span>
                        <span>到期 ${this.escapeHtml(expires)}</span>
                    </div>
                    <div class="share-manage-actions">
                        <button type="button" class="share-secondary-btn" data-share-manage-action="copy-link" data-share-token="${token}">复制链接</button>
                        <button type="button" class="share-secondary-btn" data-share-manage-action="edit" data-share-token="${token}">编辑设置</button>
                        <button type="button" class="share-secondary-btn" data-share-manage-action="toggle-active" data-share-token="${token}">${toggleLabel}</button>
                        <button type="button" class="share-secondary-btn danger" data-share-manage-action="delete" data-share-token="${token}">删除</button>
                    </div>
                </article>
            `;
        }).join('');
    }

    findShare(token) {
        return this.currentShares.find((item) => item.token === token) || null;
    }

    async handleManageListClick(event) {
        const button = event.target.closest('[data-share-manage-action]');
        if (!button) return;

        const action = button.dataset.shareManageAction || '';
        const token = button.dataset.shareToken || '';
        if (!action || !token) return;

        if (action === 'copy-link') {
            const share = this.findShare(token);
            const ok = await window.shareUtils?.copyText(share?.url || '');
            this.showToast(ok ? '分享链接已复制' : '复制失败，请手动复制', ok ? 'success' : 'error');
            return;
        }

        if (action === 'edit') return this.openManageEditor(token);
        if (action === 'toggle-active') return this.toggleShareActive(token);
        if (action === 'delete') return this.deleteShare(token);
    }

    openManageEditor(token) {
        const share = this.findShare(token);
        if (!share) return;

        this.manageEditingToken = token;
        this.shareManageForm.style.display = '';
        this.shareManageEditorTitle.textContent = '编辑分享设置';
        this.shareManageEditorHint.textContent = `当前链接：${share.url || ''}`;
        this.manageAllowEditToggle.checked = Boolean(share.allow_edit);
        this.managePasswordToggle.checked = Boolean(share.requires_password);
        this.managePasswordInput.value = '';
        this.managePasswordInput.placeholder = share.requires_password ? '留空表示保留当前密码' : '请输入新的分享密码';

        if (!share.expires_at) {
            this.manageExpirySelect.value = 'never';
            this.manageCustomExpiryInput.value = '';
        } else {
            this.manageExpirySelect.value = 'custom';
            this.manageCustomExpiryInput.value = String(share.expires_at).slice(0, 16);
        }

        this.syncManagePasswordField();
        this.syncManageExpiryField();
        this.shareManageForm.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    closeManageEditor() {
        this.manageEditingToken = '';
        if (this.shareManageForm) this.shareManageForm.style.display = 'none';
    }

    async saveManagedShare() {
        const share = this.findShare(this.manageEditingToken);
        if (!share) return this.showToast('未找到需要编辑的分享', 'error');

        const expires = this.buildManageExpiryValue();
        if (this.manageExpirySelect.value === 'custom' && !expires) {
            return this.showToast('请选择自定义到期时间', 'error');
        }

        let passwordMode = 'keep';
        let password = '';
        if (this.managePasswordToggle.checked) {
            password = (this.managePasswordInput.value || '').trim();
            if (password) passwordMode = 'set';
            else if (!share.requires_password) return this.showToast('请输入新的分享密码', 'error');
        } else {
            passwordMode = 'clear';
        }

        const payload = {
            allow_edit: Boolean(this.manageAllowEditToggle.checked),
            expires_at: expires,
            password_mode: passwordMode,
        };
        if (passwordMode === 'set') payload.password = password;

        const original = this.saveManageShareBtn.textContent;
        this.saveManageShareBtn.disabled = true;
        this.saveManageShareBtn.textContent = '保存中...';

        try {
            const response = await fetch(`/api/shares/${encodeURIComponent(share.token)}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                return this.showToast(data.error || '保存分享设置失败', 'error');
            }

            this.replaceShareItem(data.share);
            this.renderManageSummary();
            this.renderShareList();
            this.openManageEditor(data.share.token);
            this.showToast('分享设置已更新', 'success');
        } catch (_) {
            this.showToast('保存分享设置时网络异常', 'error');
        } finally {
            this.saveManageShareBtn.disabled = false;
            this.saveManageShareBtn.textContent = original;
        }
    }

    async toggleShareActive(token) {
        const share = this.findShare(token);
        if (!share) return;

        const nextActive = !share.is_active;
        const ok = await this.showConfirm(
            nextActive ? '启用分享' : '停用分享',
            nextActive
                ? '启用后，这个分享链接会重新恢复访问。确定继续吗？'
                : '停用后，当前分享链接会立刻失效。确定继续吗？',
            nextActive ? '启用' : '停用'
        );
        if (!ok) return;

        try {
            const response = await fetch(`/api/shares/${encodeURIComponent(token)}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify({ active: nextActive }),
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                return this.showToast(data.error || '更新分享状态失败', 'error');
            }

            this.replaceShareItem(data.share);
            this.renderManageSummary();
            this.renderShareList();
            if (this.manageEditingToken === token) this.openManageEditor(token);
            this.showToast(nextActive ? '分享已启用' : '分享已停用', 'success');
        } catch (_) {
            this.showToast('更新分享状态时网络异常', 'error');
        }
    }

    async deleteShare(token) {
        const share = this.findShare(token);
        if (!share) return;

        const ok = await this.showConfirm('删除分享', `确定要删除这个分享吗？\n${share.url || ''}`, '删除');
        if (!ok) return;

        try {
            const response = await fetch(`/api/shares/${encodeURIComponent(token)}`, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': this.csrfToken },
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                return this.showToast(data.error || '删除分享失败', 'error');
            }

            this.currentShares = this.currentShares.filter((item) => item.token !== token);
            this.shareManagedCount.textContent = String(this.currentShares.length);
            this.renderManageSummary();
            this.renderShareList();
            if (this.manageEditingToken === token) this.closeManageEditor();
            this.showToast('分享已删除', 'success');
        } catch (_) {
            this.showToast('删除分享时网络异常', 'error');
        }
    }

    async showConfirm(title, message, confirmText) {
        if (window.uiUtils?.showConfirmDialog) {
            return Boolean(await window.uiUtils.showConfirmDialog(title, message, confirmText));
        }
        return window.confirm(`${title}\n\n${message}`);
    }

    replaceShareItem(nextShare) {
        const index = this.currentShares.findIndex((item) => item.token === nextShare.token);
        if (index >= 0) this.currentShares.splice(index, 1, nextShare);
        else this.currentShares.unshift(nextShare);
    }

    formatDateTime(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime())
            ? String(value || '--')
            : new Intl.DateTimeFormat('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                hour12: false,
            }).format(date).replace(/\//g, '-');
    }

    escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (char) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        }[char] || char));
    }

    refreshIcons() {
        window.lucide?.createIcons?.();
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
