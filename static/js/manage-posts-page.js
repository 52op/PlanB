class ManagePostsPage {
    constructor() {
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        this.items = [];
        this.filteredItems = [];
        this.currentPage = 1;
        this.pageSize = 30;
        this.sortMode = 'updated_desc';
    }

    initialize() {
        this.cacheElements();
        this.bindEvents();
        this.load();
    }

    cacheElements() {
        this.searchInput = document.getElementById('managePostsSearch');
        this.sortSelect = document.getElementById('managePostsSort');
        this.publicFilter = document.getElementById('managePostsPublicFilter');
        this.blogFilter = document.getElementById('managePostsBlogFilter');
        this.editableOnly = document.getElementById('managePostsEditableOnly');
        this.pageSizeSelect = document.getElementById('managePostsPageSize');
        this.refreshBtn = document.getElementById('managePostsRefreshBtn');
        this.resetBtn = document.getElementById('managePostsResetBtn');
        this.statusNode = document.getElementById('managePostsStatus');
        this.currentHintNode = document.getElementById('managePostsCurrentHint');
        this.filterSummaryNode = document.getElementById('managePostsFilterSummary');
        this.tableBody = document.getElementById('managePostsTableBody');
        this.paginationSummary = document.getElementById('managePostsPaginationSummary');
        this.pageNumbers = document.getElementById('managePostsPageNumbers');
        this.prevBtn = document.getElementById('managePostsPrevBtn');
        this.nextBtn = document.getElementById('managePostsNextBtn');
        this.heroTotalCount = document.getElementById('heroTotalCount');
        this.heroPublicCount = document.getElementById('heroPublicCount');
        this.heroBlogCount = document.getElementById('heroBlogCount');
        this.heroEditableCount = document.getElementById('heroEditableCount');
    }

    bindEvents() {
        this.searchInput?.addEventListener('input', () => {
            this.currentPage = 1;
            this.render();
        });

        this.sortSelect?.addEventListener('change', () => {
            this.sortMode = this.sortSelect.value || 'updated_desc';
            this.currentPage = 1;
            this.render();
        });

        this.publicFilter?.addEventListener('change', () => {
            this.currentPage = 1;
            this.render();
        });

        this.blogFilter?.addEventListener('change', () => {
            this.currentPage = 1;
            this.render();
        });

        this.editableOnly?.addEventListener('change', () => {
            this.currentPage = 1;
            this.render();
        });

        this.pageSizeSelect?.addEventListener('change', () => {
            this.pageSize = Number(this.pageSizeSelect.value || 30);
            this.currentPage = 1;
            this.render();
        });

        this.refreshBtn?.addEventListener('click', () => this.load(true));
        this.resetBtn?.addEventListener('click', () => this.resetFilters());
        this.prevBtn?.addEventListener('click', () => this.changePage(this.currentPage - 1));
        this.nextBtn?.addEventListener('click', () => this.changePage(this.currentPage + 1));

        this.tableBody?.addEventListener('click', async (event) => {
            const filterTarget = event.target.closest('button[data-filter-action]');
            if (filterTarget instanceof HTMLElement) {
                const filterAction = filterTarget.dataset.filterAction || '';
                if (filterAction === 'clear-all') {
                    this.resetFilters();
                }
                return;
            }

            const target = event.target.closest('button[data-action]');
            if (!(target instanceof HTMLElement)) return;

            const filename = target.dataset.filename || '';
            const title = target.dataset.title || '当前文档';
            const action = target.dataset.action || '';

            if (action === 'toggle-public') {
                await this.togglePublicState(filename, target.dataset.public === 'true');
                return;
            }

            if (action === 'toggle-blog') {
                await this.toggleBlogVisibility(filename, target.dataset.blogVisible === 'true');
                return;
            }

            if (action === 'remove-front-matter') {
                await this.removeFrontMatter(filename, title);
            }
        });

        this.filterSummaryNode?.addEventListener('click', (event) => {
            const target = event.target.closest('button[data-filter-action]');
            if (!(target instanceof HTMLElement)) return;

            const action = target.dataset.filterAction || '';
            if (action === 'clear-all') {
                this.resetFilters();
            }
        });
    }

    async load(showToast = false) {
        this.setStatus('正在读取博客文章管理列表...');
        this.setTableLoading('正在读取博客文章管理列表...');

        try {
            const response = await fetch('/api/public-posts', {
                headers: {
                    'X-CSRFToken': this.csrfToken,
                },
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '读取失败');
            }

            this.items = Array.isArray(data.items) ? data.items : [];
            this.render();
            if (showToast) {
                window.uiUtils?.showToast?.('博客文章管理列表已刷新', 'success');
            }
        } catch (error) {
            const message = error.message || '读取失败，请稍后重试。';
            this.setStatus(message);
            this.setTableLoading(message);
            window.uiUtils?.showAlertDialog?.('读取失败', message);
        }
    }

    resetFilters() {
        if (this.searchInput) this.searchInput.value = '';
        if (this.sortSelect) this.sortSelect.value = 'updated_desc';
        if (this.publicFilter) this.publicFilter.value = 'all';
        if (this.blogFilter) this.blogFilter.value = 'all';
        if (this.editableOnly) this.editableOnly.checked = false;
        if (this.pageSizeSelect) this.pageSizeSelect.value = '30';

        this.sortMode = 'updated_desc';
        this.pageSize = 30;
        this.currentPage = 1;
        this.render();
    }

    getFilteredItems() {
        const query = (this.searchInput?.value || '').trim().toLowerCase();
        const publicFilter = this.publicFilter?.value || 'all';
        const blogFilter = this.blogFilter?.value || 'all';
        const editableOnly = !!this.editableOnly?.checked;

        let items = [...this.items];

        if (editableOnly) {
            items = items.filter((item) => item.can_edit);
        }

        if (publicFilter === 'public') {
            items = items.filter((item) => item.public);
        } else if (publicFilter === 'private') {
            items = items.filter((item) => !item.public);
        }

        if (blogFilter === 'blog') {
            items = items.filter((item) => item.is_blog_visible);
        } else if (blogFilter === 'doc') {
            items = items.filter((item) => !item.is_blog_visible);
        }

        if (query) {
            items = items.filter((item) => {
                const haystack = [
                    item.title,
                    item.path,
                    item.category_name,
                    item.summary,
                ].join(' ').toLowerCase();
                return haystack.includes(query);
            });
        }

        items.sort((left, right) => this.compareItems(left, right));
        return items;
    }

    compareItems(left, right) {
        if (this.sortMode === 'title_asc') {
            return String(left.title || '').localeCompare(String(right.title || ''), 'zh-CN');
        }

        const field = this.sortMode === 'date_desc' ? 'date' : 'updated';
        const leftValue = String(left[field] || left.date || '').trim();
        const rightValue = String(right[field] || right.date || '').trim();
        if (leftValue === rightValue) {
            return String(left.title || '').localeCompare(String(right.title || ''), 'zh-CN');
        }
        return rightValue.localeCompare(leftValue);
    }

    render() {
        this.filteredItems = this.getFilteredItems();
        this.renderHeroStats();
        this.renderFilterSummary();
        this.renderTable();
        this.renderPagination();
    }

    renderFilterSummary() {
        if (!this.filterSummaryNode) return;

        const chips = [];
        const query = (this.searchInput?.value || '').trim();
        const publicFilter = this.publicFilter?.value || 'all';
        const blogFilter = this.blogFilter?.value || 'all';
        const editableOnly = !!this.editableOnly?.checked;
        const sortMode = this.sortMode || 'updated_desc';

        if (query) {
            chips.push(`搜索：${query}`);
        }

        if (publicFilter === 'public') {
            chips.push('仅公开内容');
        } else if (publicFilter === 'private') {
            chips.push('仅未公开');
        }

        if (blogFilter === 'blog') {
            chips.push('仅博客可见');
        } else if (blogFilter === 'doc') {
            chips.push('仅文档可见');
        }

        if (editableOnly) {
            chips.push('仅我可编辑');
        }

        if (sortMode === 'date_desc') {
            chips.push('按发布时间排序');
        } else if (sortMode === 'title_asc') {
            chips.push('按标题 A-Z 排序');
        } else {
            chips.push('按最近更新排序');
        }

        chips.push(`每页 ${this.pageSize} 篇`);

        const hasCustomFilters = !!query || publicFilter !== 'all' || blogFilter !== 'all' || editableOnly;
        this.filterSummaryNode.hidden = false;
        this.filterSummaryNode.innerHTML = `
            <div class="manage-posts-filter-summary-inner">
                <span class="manage-posts-filter-label">当前视图</span>
                <div class="manage-posts-filter-chips">
                    ${chips.map((chip) => `<span class="manage-posts-filter-chip">${this.escapeHtml(chip)}</span>`).join('')}
                </div>
                ${hasCustomFilters ? '<button type="button" class="manage-posts-filter-clear" data-filter-action="clear-all">清空筛选</button>' : ''}
            </div>
        `;
    }

    renderHeroStats() {
        const publicCount = this.items.filter((item) => item.public).length;
        const blogCount = this.items.filter((item) => item.is_blog_visible).length;
        const editableCount = this.items.filter((item) => item.can_edit).length;

        if (this.heroTotalCount) this.heroTotalCount.textContent = String(this.items.length);
        if (this.heroPublicCount) this.heroPublicCount.textContent = String(publicCount);
        if (this.heroBlogCount) this.heroBlogCount.textContent = String(blogCount);
        if (this.heroEditableCount) this.heroEditableCount.textContent = String(editableCount);
    }

    getPaginationData() {
        const total = this.filteredItems.length;
        const totalPages = Math.max(1, Math.ceil(total / this.pageSize));
        this.currentPage = Math.min(Math.max(1, this.currentPage), totalPages);
        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;
        return {
            total,
            totalPages,
            start,
            end,
            items: this.filteredItems.slice(start, end),
        };
    }

    renderTable() {
        if (!this.tableBody) return;

        const pagination = this.getPaginationData();
        const items = pagination.items;

        if (!items.length) {
            const emptyMessage = this.filteredItems.length
                ? '当前页没有内容。'
                : '没有符合当前条件的文档。';
            const showReset = this.hasActiveFilters();
            this.tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="manage-posts-empty-cell">
                        <div class="manage-posts-empty-state">
                            <div class="manage-posts-empty-icon">
                                <i data-lucide="${showReset ? 'search-x' : 'file-search'}"></i>
                            </div>
                            <strong>${this.escapeHtml(emptyMessage)}</strong>
                            <p>${this.escapeHtml(showReset ? '可以放宽筛选条件，或直接一键恢复默认视图。' : '这里暂时还没有可管理的带头部 Markdown 文档。')}</p>
                            ${showReset ? '<button type="button" class="manage-posts-btn" data-filter-action="clear-all">恢复默认筛选</button>' : ''}
                        </div>
                    </td>
                </tr>
            `;
            this.setStatus(this.filteredItems.length ? `共筛选到 ${this.filteredItems.length} 篇文档。` : '没有符合当前条件的文档。');
            if (window.lucide?.createIcons) {
                window.lucide.createIcons();
            }
            return;
        }

        this.tableBody.innerHTML = items.map((item) => this.renderRow(item)).join('');
        this.setStatus(`共筛选到 ${this.filteredItems.length} 篇文档，当前显示第 ${pagination.start + 1}-${Math.min(pagination.end, pagination.total)} 篇。`);
        if (window.lucide?.createIcons) {
            window.lucide.createIcons();
        }
    }

    renderRow(item) {
        const primaryDate = this.sortMode === 'date_desc'
            ? (item.date_display || item.timeline_display || '未设置日期')
            : (item.updated_display || item.date_display || item.timeline_display || '未设置日期');

        const publicButtonLabel = item.public ? '取消公开' : '设为公开';
        const publicButtonValue = item.public ? 'false' : 'true';
        const blogButtonLabel = item.is_blog_visible ? '取消博客显示' : '显示到博客';
        const blogButtonValue = item.is_blog_visible ? 'false' : 'true';

        const summary = item.summary
            ? `<p class="manage-posts-doc-summary">${this.escapeHtml(item.summary)}</p>`
            : '';

        const previewLink = item.is_blog_visible && item.post_url
            ? `<a class="manage-posts-btn is-soft is-preview" href="${this.escapeHtml(item.post_url)}" target="_blank" rel="noopener">博客预览</a>`
            : '';

        const actionButtons = item.can_edit
            ? `
                <button class="manage-posts-btn is-soft ${item.public ? 'is-warn' : 'is-success'}" type="button" data-action="toggle-public" data-filename="${this.escapeHtml(item.path)}" data-public="${publicButtonValue}" data-title="${this.escapeHtml(item.title || '未命名文档')}">${publicButtonLabel}</button>
                <button class="manage-posts-btn is-soft ${item.is_blog_visible ? 'is-doc-mode' : 'is-blog-mode'}" type="button" data-action="toggle-blog" data-filename="${this.escapeHtml(item.path)}" data-blog-visible="${blogButtonValue}" data-title="${this.escapeHtml(item.title || '未命名文档')}">${blogButtonLabel}</button>
                <button class="manage-posts-btn is-soft is-danger" type="button" data-action="remove-front-matter" data-filename="${this.escapeHtml(item.path)}" data-title="${this.escapeHtml(item.title || '未命名文档')}">移除头部</button>
            `
            : `<span class="manage-posts-status-badge">只读</span>`;

        return `
            <tr>
                <td>
                    <div class="manage-posts-doc-main">
                        <a class="manage-posts-doc-title" href="${this.escapeHtml(item.doc_url || '#')}">
                            <i data-lucide="file-text"></i>
                            <span>${this.escapeHtml(item.title || '未命名文档')}</span>
                        </a>
                        <div class="manage-posts-meta-line">
                            <span class="manage-posts-meta-chip"><i data-lucide="folder-tree"></i>${this.escapeHtml(item.category_name || '未分类')}</span>
                            <span class="manage-posts-meta-chip"><i data-lucide="route"></i>${this.escapeHtml(item.path || '')}</span>
                        </div>
                        ${summary}
                    </div>
                </td>
                <td>
                    <div class="manage-posts-status-group">
                        <span class="manage-posts-status-badge ${item.public ? 'is-public' : 'is-private'}">
                            <i data-lucide="${item.public ? 'shield-check' : 'shield-off'}"></i>
                            ${item.public ? '公开内容' : '未公开'}
                        </span>
                        <span class="manage-posts-status-badge ${item.is_blog_visible ? 'is-blog' : 'is-doc'}">
                            <i data-lucide="${item.is_blog_visible ? 'newspaper' : 'file-text'}"></i>
                            ${item.is_blog_visible ? '博客可见' : '仅文档可见'}
                        </span>
                    </div>
                </td>
                <td>
                    <div class="manage-posts-time-block">
                        <strong>${this.escapeHtml(primaryDate)}</strong>
                        <span>发布日期：${this.escapeHtml(item.date_display || '未设置')}</span>
                        <span>更新日期：${this.escapeHtml(item.updated_display || item.date_display || '未设置')}</span>
                    </div>
                </td>
                <td>
                    <div class="manage-posts-views-block">
                        <strong>${Number(item.view_count || 0)}</strong>
                        <span>次阅读</span>
                    </div>
                </td>
                <td>
                    <div class="manage-posts-row-actions">
                        <a class="manage-posts-btn is-primary-lite" href="${this.escapeHtml(item.doc_url || '#')}">打开文档</a>
                        ${previewLink}
                        ${actionButtons}
                    </div>
                </td>
            </tr>
        `;
    }

    renderPagination() {
        const { total, totalPages } = this.getPaginationData();
        if (this.paginationSummary) {
            this.paginationSummary.textContent = `第 ${this.currentPage} / ${totalPages} 页，共 ${total} 篇`;
        }

        if (this.prevBtn) this.prevBtn.disabled = this.currentPage <= 1;
        if (this.nextBtn) this.nextBtn.disabled = this.currentPage >= totalPages;
        if (!this.pageNumbers) return;

        const pages = [];
        for (let page = 1; page <= totalPages; page += 1) {
            if (
                page === 1 ||
                page === totalPages ||
                (page >= this.currentPage - 2 && page <= this.currentPage + 2)
            ) {
                pages.push(page);
            } else if (pages[pages.length - 1] !== '...') {
                pages.push('...');
            }
        }

        this.pageNumbers.innerHTML = pages.map((page) => {
            if (page === '...') {
                return `<span class="manage-posts-btn">...</span>`;
            }
            return `
                <button
                    class="manage-posts-btn ${page === this.currentPage ? 'is-current' : ''}"
                    type="button"
                    data-page="${page}"
                >${page}</button>
            `;
        }).join('');

        this.pageNumbers.querySelectorAll('button[data-page]').forEach((button) => {
            button.addEventListener('click', () => {
                this.changePage(Number(button.dataset.page || 1));
            });
        });
    }

    changePage(page) {
        const { totalPages } = this.getPaginationData();
        if (page < 1 || page > totalPages || page === this.currentPage) return;
        this.currentPage = page;
        this.renderTable();
        this.renderPagination();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    async togglePublicState(filename, nextPublicState) {
        if (!filename) return;
        await this.performMutation(
            '/api/public-posts/toggle',
            { filename, public: nextPublicState },
            nextPublicState ? '文档已设为公开' : '文档已取消公开',
            (item, data) => ({
                ...item,
                public: !!data.public,
                template: data.template || item.template || 'doc',
                is_blog_visible: !!data.is_blog_visible,
                post_url: data.is_blog_visible ? (data.post_url || item.post_url || '') : '',
            }),
            filename,
        );
    }

    async toggleBlogVisibility(filename, nextBlogVisibleState) {
        if (!filename) return;
        await this.performMutation(
            '/api/public-posts/toggle',
            { filename, show_in_blog: nextBlogVisibleState },
            nextBlogVisibleState ? '文档已显示到博客' : '文档已从博客隐藏',
            (item, data) => ({
                ...item,
                template: data.template || (nextBlogVisibleState ? 'post' : 'doc'),
                is_blog_visible: !!data.is_blog_visible,
                post_url: data.is_blog_visible ? (data.post_url || item.post_url || '') : '',
            }),
            filename,
        );
    }

    async removeFrontMatter(filename, title) {
        if (!filename) return;

        const confirmed = await window.uiUtils?.showConfirmDialog?.(
            '移除头部',
            `确定要移除“${title}”的头部信息吗？移除后会保留正文内容，并退出博客文章管理。`,
            '移除'
        );
        if (!confirmed) return;

        try {
            const response = await fetch('/api/public-posts/remove-front-matter', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify({ filename }),
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '移除头部失败');
            }

            this.items = this.items.filter((item) => item.path !== filename);
            this.currentPage = 1;
            this.render();
            window.uiUtils?.showToast?.('头部已移除，文档已退出博客文章管理', 'success');
        } catch (error) {
            window.uiUtils?.showAlertDialog?.('移除失败', error.message || '请稍后重试');
        }
    }

    async performMutation(url, body, successMessage, itemUpdater, filename) {
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
                body: JSON.stringify(body),
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || '更新失败');
            }

            this.items = this.items.map((item) => (
                item.path === filename ? itemUpdater(item, data) : item
            ));
            this.render();
            window.uiUtils?.showToast?.(successMessage, 'success');
        } catch (error) {
            window.uiUtils?.showAlertDialog?.('更新失败', error.message || '请稍后重试');
        }
    }

    setStatus(message) {
        if (this.statusNode) {
            this.statusNode.textContent = message;
        }
    }

    setTableLoading(message) {
        if (!this.tableBody) return;
        this.tableBody.innerHTML = `<tr><td colspan="5" class="manage-posts-empty-cell">${this.escapeHtml(message)}</td></tr>`;
    }

    hasActiveFilters() {
        return !!(this.searchInput?.value || '').trim()
            || (this.publicFilter?.value || 'all') !== 'all'
            || (this.blogFilter?.value || 'all') !== 'all'
            || !!this.editableOnly?.checked;
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

document.addEventListener('DOMContentLoaded', () => {
    const page = new ManagePostsPage();
    page.initialize();
    window.managePostsPage = page;
});
