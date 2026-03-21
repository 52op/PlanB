class PublicPostManager {
    constructor() {
        this.csrfToken = '';
        this.currentFilePath = '';
        this.items = [];
        this.sortMode = 'updated_desc';
        this.searchQuery = '';
        this.editableOnly = false;
        this.bound = false;
    }

    setCSRFToken(token) {
        this.csrfToken = token || '';
    }

    setCurrentFile(filePath) {
        this.currentFilePath = filePath || '';
    }

    ensureElements() {
        this.desktopButton = document.getElementById('publicPostsBtnDesktop');
        this.mobileButton = document.getElementById('publicPostsBtnMobile');

        if (document.getElementById('publicPostsModal')) {
            this.modal = document.getElementById('publicPostsModal');
            this.closeButton = document.getElementById('closePublicPostsModal');
            this.refreshButton = document.getElementById('refreshPublicPostsBtn');
            this.sortSelect = document.getElementById('publicPostsSort');
            this.searchInput = document.getElementById('publicPostsSearch');
            this.editableCheckbox = document.getElementById('publicPostsEditableOnly');
            this.summaryNode = document.getElementById('publicPostsSummary');
            this.timelineNode = document.getElementById('publicPostsTimeline');
            this.statusNode = document.getElementById('publicPostsStatus');
            return;
        }

        if (!this.desktopButton && !this.mobileButton) {
            return;
        }

        const modal = document.createElement('div');
        modal.id = 'publicPostsModal';
        modal.className = 'modal-overlay public-posts-modal';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="public-posts-dialog" role="dialog" aria-modal="true" aria-labelledby="publicPostsTitle">
                <div class="public-posts-header">
                    <div>
                        <div class="public-posts-kicker">博客文章管理</div>
                        <h3 id="publicPostsTitle">博客文章管理</h3>
                        <p>按时间轴查看全部带头部信息的文档，并分别控制公开状态和博客展示状态。</p>
                    </div>
                    <div class="public-posts-header-actions">
                        <button type="button" class="btn btn-secondary" id="refreshPublicPostsBtn">刷新</button>
                        <button type="button" class="btn btn-secondary" id="closePublicPostsModal">关闭</button>
                    </div>
                </div>
                <div class="public-posts-toolbar">
                    <label class="public-posts-search">
                        <i data-lucide="search"></i>
                        <input type="text" id="publicPostsSearch" placeholder="搜索标题、路径或分类">
                    </label>
                    <label class="public-posts-sort">
                        <span>排序</span>
                        <select id="publicPostsSort">
                            <option value="updated_desc">按最近更新</option>
                            <option value="date_desc">按发布时间</option>
                        </select>
                    </label>
                    <label class="public-posts-filter">
                        <input type="checkbox" id="publicPostsEditableOnly">
                        <span>仅显示我可编辑的文档</span>
                    </label>
                </div>
                <div class="public-posts-summary" id="publicPostsSummary"></div>
                <div class="public-posts-status" id="publicPostsStatus">正在读取博客文章管理列表...</div>
                <div class="public-posts-timeline" id="publicPostsTimeline"></div>
            </div>
        `;

        document.body.appendChild(modal);
        this.modal = modal;
        this.closeButton = document.getElementById('closePublicPostsModal');
        this.refreshButton = document.getElementById('refreshPublicPostsBtn');
        this.sortSelect = document.getElementById('publicPostsSort');
        this.searchInput = document.getElementById('publicPostsSearch');
        this.editableCheckbox = document.getElementById('publicPostsEditableOnly');
        this.summaryNode = document.getElementById('publicPostsSummary');
        this.timelineNode = document.getElementById('publicPostsTimeline');
        this.statusNode = document.getElementById('publicPostsStatus');
    }

    bindEvents() {
        this.ensureElements();
        if (!this.desktopButton && !this.mobileButton) return;
        if (this.bound) return;

        [this.desktopButton, this.mobileButton].forEach((button) => {
            if (!button) return;
            button.addEventListener('click', () => {
                this.open();
            });
        });

        this.closeButton?.addEventListener('click', () => this.close());
        this.refreshButton?.addEventListener('click', () => this.load(true));
        this.sortSelect?.addEventListener('change', () => {
            this.sortMode = this.sortSelect.value || 'updated_desc';
            this.render();
        });
        this.searchInput?.addEventListener('input', () => {
            this.searchQuery = (this.searchInput.value || '').trim().toLowerCase();
            this.render();
        });
        this.editableCheckbox?.addEventListener('change', () => {
            this.editableOnly = !!this.editableCheckbox.checked;
            this.render();
        });

        this.modal?.addEventListener('click', (event) => {
            if (event.target === this.modal) {
                this.close();
                return;
            }

            const actionButton = event.target.closest('[data-public-toggle]');
            if (actionButton instanceof HTMLElement) {
                this.togglePublicState(actionButton.dataset.filename || '', actionButton.dataset.public === 'true');
                return;
            }

            const blogButton = event.target.closest('[data-blog-toggle]');
            if (blogButton instanceof HTMLElement) {
                this.toggleBlogVisibility(blogButton.dataset.filename || '', blogButton.dataset.blogVisible === 'true');
            }
        });

        this.bound = true;
    }

    async open() {
        this.ensureElements();
        if (!this.modal) return;

        this.modal.style.display = 'flex';
        await this.load(false);
    }

    close() {
        if (this.modal) {
            this.modal.style.display = 'none';
        }
    }

    async load(forceRefresh = false) {
        this.ensureElements();
        if (!this.statusNode || !this.timelineNode) return;

        if (!forceRefresh && this.items.length) {
            this.render();
            return;
        }

        this.statusNode.textContent = '正在读取博客文章管理列表...';
        this.timelineNode.innerHTML = '';

        try {
            const response = await fetch('/api/public-posts', {
                headers: { 'X-CSRFToken': this.csrfToken },
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '读取失败');
            }

            this.items = Array.isArray(data.items) ? data.items : [];
            this.render();
        } catch (error) {
            this.statusNode.textContent = error.message || '读取失败，请稍后重试。';
        }
    }

    getFilteredItems() {
        let items = [...this.items];

        if (this.editableOnly) {
            items = items.filter((item) => item.can_edit);
        }

        if (this.searchQuery) {
            items = items.filter((item) => {
                const haystack = [
                    item.title,
                    item.path,
                    item.category_name,
                    item.summary,
                ].join(' ').toLowerCase();
                return haystack.includes(this.searchQuery);
            });
        }

        const sortField = this.sortMode === 'date_desc' ? 'date' : 'updated';
        items.sort((left, right) => {
            const leftValue = String(left[sortField] || left.date || '').trim();
            const rightValue = String(right[sortField] || right.date || '').trim();
            if (leftValue === rightValue) {
                return String(left.title || '').localeCompare(String(right.title || ''), 'zh-CN');
            }
            return rightValue.localeCompare(leftValue);
        });

        return items;
    }

    getTimelineGroups(items) {
        const field = this.sortMode === 'date_desc' ? 'date' : 'updated';
        const groups = [];
        const groupMap = new Map();

        items.forEach((item) => {
            const value = String(item[field] || item.date || '').trim();
            const key = /^\d{4}-\d{2}/.test(value) ? value.slice(0, 7) : '未设置日期';
            if (!groupMap.has(key)) {
                const label = key === '未设置日期'
                    ? key
                    : `${key.slice(0, 4)} 年 ${String(parseInt(key.slice(5, 7), 10))} 月`;
                const group = { key, label, items: [] };
                groupMap.set(key, group);
                groups.push(group);
            }
            groupMap.get(key).items.push(item);
        });

        return groups;
    }

    renderSummary(items) {
        if (!this.summaryNode) return;

        const editableCount = items.filter((item) => item.can_edit).length;
        const blogVisibleCount = items.filter((item) => item.is_blog_visible).length;
        const publicCount = items.filter((item) => item.public).length;
        const currentItem = items.find((item) => item.path === this.currentFilePath);
        this.summaryNode.innerHTML = `
            <div class="public-posts-stat">
                <strong>${items.length}</strong>
                <span>带头部文档</span>
            </div>
            <div class="public-posts-stat">
                <strong>${publicCount}</strong>
                <span>公开内容</span>
            </div>
            <div class="public-posts-stat">
                <strong>${blogVisibleCount}</strong>
                <span>显示在博客</span>
            </div>
            <div class="public-posts-stat">
                <strong>${editableCount}</strong>
                <span>可管理</span>
            </div>
            <div class="public-posts-stat">
                <strong>${currentItem ? '当前文档已收录' : '当前未命中'}</strong>
                <span>${currentItem ? `${currentItem.title} · ${currentItem.public ? '公开内容' : '未公开'} · ${currentItem.is_blog_visible ? '博客可见' : '仅文档可见'}` : '可用搜索快速定位'}</span>
            </div>
        `;
    }

    render() {
        if (!this.statusNode || !this.timelineNode) return;

        const items = this.getFilteredItems();
        this.renderSummary(items);

        if (!items.length) {
            this.statusNode.textContent = '没有符合条件的带头部文档。';
            this.timelineNode.innerHTML = '';
            return;
        }

        this.statusNode.textContent = `共找到 ${items.length} 篇带头部信息的文档。`;
        const groups = this.getTimelineGroups(items);

        this.timelineNode.innerHTML = groups.map((group) => `
            <section class="public-posts-group">
                <div class="public-posts-group-head">
                    <div>
                        <p class="public-posts-group-kicker">Timeline</p>
                        <h4>${group.label}</h4>
                    </div>
                    <span>${group.items.length} 篇</span>
                </div>
                <div class="public-posts-group-list">
                    ${group.items.map((item) => this.renderItem(item)).join('')}
                </div>
            </section>
        `).join('');

        window.lucide?.createIcons?.();
    }

    renderItem(item) {
        const isCurrent = item.path === this.currentFilePath;
        const primaryDate = this.sortMode === 'date_desc'
            ? (item.date_display || item.timeline_display || '未设置日期')
            : (item.updated_display || item.date_display || item.timeline_display || '未设置日期');
        const publicToggleLabel = item.public ? '取消公开' : '设为公开';
        const publicToggleValue = item.public ? 'false' : 'true';
        const publicToggleButton = item.can_edit
            ? `<button type="button" class="btn btn-secondary public-posts-toggle-btn" data-public-toggle="1" data-filename="${this.escapeHtml(item.path)}" data-public="${publicToggleValue}">
                    <i data-lucide="${item.public ? 'eye-off' : 'eye'}"></i>
                    ${publicToggleLabel}
               </button>`
            : `<span class="public-posts-readonly-badge">只读</span>`;
        const blogToggleButton = item.can_edit
            ? `<button type="button" class="btn btn-secondary public-posts-toggle-btn" data-blog-toggle="1" data-filename="${this.escapeHtml(item.path)}" data-blog-visible="${item.is_blog_visible ? 'false' : 'true'}">
                    <i data-lucide="${item.is_blog_visible ? 'newspaper' : 'file-text'}"></i>
                    ${item.is_blog_visible ? '取消博客显示' : '显示到博客'}
               </button>`
            : '';
        const statusBadges = [
            item.public
                ? '<span class="public-posts-visibility-badge is-public"><i data-lucide="shield-check"></i>公开内容</span>'
                : '<span class="public-posts-visibility-badge is-private"><i data-lucide="shield-off"></i>未公开</span>',
            item.is_blog_visible
                ? '<span class="public-posts-visibility-badge is-blog"><i data-lucide="newspaper"></i>博客可见</span>'
                : '<span class="public-posts-visibility-badge is-doc"><i data-lucide="file-text"></i>仅文档可见</span>',
        ].join('');

        return `
            <article class="public-posts-item${isCurrent ? ' is-current' : ''}">
                <div class="public-posts-item-line"></div>
                <div class="public-posts-item-body">
                    <div class="public-posts-item-top">
                        <div class="public-posts-item-date">${primaryDate}</div>
                        <div class="public-posts-item-actions">
                            <a href="${this.escapeHtml(item.doc_url || '#')}" class="btn btn-secondary">打开文档</a>
                            ${item.is_blog_visible && item.post_url ? `<a href="${this.escapeHtml(item.post_url)}" class="btn btn-secondary" target="_blank" rel="noopener">博客预览</a>` : ''}
                            ${blogToggleButton}
                            ${publicToggleButton}
                        </div>
                    </div>
                    <h5 class="public-posts-item-title">
                        <a href="${this.escapeHtml(item.doc_url || '#')}">${this.escapeHtml(item.title || '未命名文档')}</a>
                    </h5>
                    <div class="public-posts-item-status">${statusBadges}</div>
                    <div class="public-posts-item-meta">
                        <span><i data-lucide="folder-tree"></i>${this.escapeHtml(item.category_name || '未分类')}</span>
                        <span><i data-lucide="file-text"></i>${this.escapeHtml(item.path || '')}</span>
                        <span><i data-lucide="eye"></i>${Number(item.view_count || 0)} 次阅读</span>
                    </div>
                    ${item.summary ? `<p class="public-posts-item-summary">${this.escapeHtml(item.summary)}</p>` : ''}
                </div>
            </article>
        `;
    }

    async togglePublicState(filename, nextPublicState) {
        if (!filename) return;

        try {
            const response = await fetch('/api/public-posts/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify({
                    filename,
                    public: nextPublicState,
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '状态更新失败');
            }

            this.items = this.items.map((item) => (
                item.path === filename
                    ? {
                        ...item,
                        public: !!data.public,
                        template: data.template || item.template || 'doc',
                        is_blog_visible: !!data.is_blog_visible,
                        post_url: data.is_blog_visible ? (data.post_url || item.post_url || '') : '',
                    }
                    : item
            ));
            this.render();
            this.syncCurrentPageState(filename, {
                public: !!data.public,
                template: data.template || 'doc',
                is_blog_visible: !!data.is_blog_visible,
            });
            window.uiUtils?.showToast?.(nextPublicState ? '文档已设为公开' : '文档已取消公开', 'success');
        } catch (error) {
            window.uiUtils?.showAlertDialog('更新失败', error.message || '请稍后重试');
        }
    }

    async toggleBlogVisibility(filename, nextBlogVisibleState) {
        if (!filename) return;

        try {
            const response = await fetch('/api/public-posts/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify({
                    filename,
                    show_in_blog: nextBlogVisibleState,
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '博客显示状态更新失败');
            }

            this.items = this.items.map((item) => (
                item.path === filename
                    ? {
                        ...item,
                        template: data.template || (nextBlogVisibleState ? 'post' : 'doc'),
                        is_blog_visible: !!data.is_blog_visible,
                        post_url: data.is_blog_visible ? (data.post_url || item.post_url || '') : '',
                    }
                    : item
            ));
            this.render();
            this.syncCurrentPageState(filename, {
                public: !!data.public,
                template: data.template || 'doc',
                is_blog_visible: !!data.is_blog_visible,
            });
            window.uiUtils?.showToast?.(nextBlogVisibleState ? '文档已显示到博客' : '文档已从博客隐藏', 'success');
        } catch (error) {
            window.uiUtils?.showAlertDialog('更新失败', error.message || '请稍后重试');
        }
    }

    syncCurrentPageState(filename, state) {
        if (filename !== this.currentFilePath) return;

        const isPublic = !!state?.public;
        const template = state?.template || 'doc';
        const isBlogVisible = !!state?.is_blog_visible;

        const publicBadge = document.getElementById('postPublicBadge');
        if (publicBadge) {
            publicBadge.style.display = isPublic && isBlogVisible ? 'inline-flex' : 'none';
        }

        const metaPublicCheckbox = document.getElementById('metaPublic');
        if (metaPublicCheckbox) {
            metaPublicCheckbox.checked = !!isPublic;
        }

        const metaTemplateSelect = document.getElementById('metaTemplate');
        if (metaTemplateSelect) {
            metaTemplateSelect.value = template;
        }
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
}

window.publicPostManager = new PublicPostManager();
