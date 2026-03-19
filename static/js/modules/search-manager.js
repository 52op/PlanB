/**
 * 搜索功能模块 - 处理文档搜索和高亮显示
 */
class SearchManager {
    constructor() {
        this.searchInput = null;
        this.searchResults = null;
        this.currentQuery = '';
        this.debounceTimer = null;
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        this.searchInput = document.querySelector('.search-input, #searchInput');
        this.searchResults = document.querySelector('.search-results, #searchResults');
        this.searchForm = document.querySelector('.search-form, #searchForm');
    }

    performSearch(query) {
        if (!query.trim()) {
            this.clearResults();
            return;
        }

        this.currentQuery = query.trim();

        // 如果是在搜索页面，直接跳转
        if (window.location.pathname === '/search') {
            const url = new URL(window.location);
            url.searchParams.set('q', this.currentQuery);
            window.location.href = url.toString();
            return;
        }

        // 否则跳转到搜索页面
        window.location.href = `/search?q=${encodeURIComponent(this.currentQuery)}`;
    }

    clearResults() {
        if (this.searchResults) {
            this.searchResults.innerHTML = '';
            this.searchResults.style.display = 'none';
        }
    }

    highlightSearchTerms(content, query) {
        if (!query || !content) return content;

        const terms = query.toLowerCase().split(/\s+/).filter(term => term.length > 0);
        let highlightedContent = content;

        terms.forEach(term => {
            const regex = new RegExp(`(${this.escapeRegExp(term)})`, 'gi');
            highlightedContent = highlightedContent.replace(regex, '<mark class="search-hit">$1</mark>');
        });

        return highlightedContent;
    }

    escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    extractSearchSnippet(content, query, maxLength = 200) {
        if (!query || !content) return content.substring(0, maxLength);

        const lowerContent = content.toLowerCase();
        const lowerQuery = query.toLowerCase();
        const index = lowerContent.indexOf(lowerQuery);

        if (index === -1) {
            return content.substring(0, maxLength) + (content.length > maxLength ? '...' : '');
        }

        const start = Math.max(0, index - 50);
        const end = Math.min(content.length, index + query.length + 150);

        let snippet = content.substring(start, end);

        if (start > 0) snippet = '...' + snippet;
        if (end < content.length) snippet = snippet + '...';

        return snippet;
    }

    bindEvents() {
        if (this.searchInput) {
            // 搜索输入事件
            this.searchInput.addEventListener('input', (event) => {
                const query = event.target.value.trim();

                // 防抖处理
                clearTimeout(this.debounceTimer);
                this.debounceTimer = setTimeout(() => {
                    if (query.length >= 2) {
                        // 可以在这里添加实时搜索建议功能
                        this.showSearchSuggestions(query);
                    } else {
                        this.clearResults();
                    }
                }, 300);
            });

            // 回车搜索
            this.searchInput.addEventListener('keypress', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    this.performSearch(event.target.value);
                }
            });
        }

        if (this.searchForm) {
            this.searchForm.addEventListener('submit', (event) => {
                event.preventDefault();
                const query = this.searchInput ? this.searchInput.value : '';
                this.performSearch(query);
            });
        }

        // 搜索快捷键 (Ctrl+K 或 Cmd+K)
        document.addEventListener('keydown', (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
                event.preventDefault();
                if (this.searchInput) {
                    this.searchInput.focus();
                    this.searchInput.select();
                }
            }

            // ESC 清除搜索
            if (event.key === 'Escape' && this.searchInput === document.activeElement) {
                this.searchInput.blur();
                this.clearResults();
            }
        });
    }

    async showSearchSuggestions(query) {
        // 这里可以实现搜索建议功能
        // 暂时留空，可以后续扩展
    }

    // 在搜索结果页面高亮搜索词
    highlightSearchResults() {
        const urlParams = new URLSearchParams(window.location.search);
        const query = urlParams.get('q');

        if (!query) return;

        // 高亮页面中的搜索词
        const contentElements = document.querySelectorAll('.post-title, .post-summary, .search-snippet');

        contentElements.forEach(element => {
            if (element.innerHTML && !element.querySelector('.search-hit')) {
                element.innerHTML = this.highlightSearchTerms(element.innerHTML, query);
            }
        });

        // 设置搜索输入框的值
        if (this.searchInput && !this.searchInput.value) {
            this.searchInput.value = query;
        }
    }

    // 初始化搜索页面
    initializeSearchPage() {
        // 如果在搜索页面，高亮搜索结果
        if (window.location.pathname === '/search') {
            this.highlightSearchResults();
        }
    }
}

// 导出单例
window.searchManager = new SearchManager();