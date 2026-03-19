/**
 * 主应用模块 - 协调所有功能模块的初始化和交互
 */
class PlanningApp {
    constructor() {
        this.csrfToken = '';
        this.currentFilePath = '';
        this.currentDirPath = '';
        this.config = {};
        this.initialized = false;
    }

    async initialize() {
        if (this.initialized) return;

        // 获取页面配置
        this.loadPageConfig();

        // 获取CSRF令牌
        this.csrfToken = this.getCSRFToken();

        // 初始化所有模块
        this.initializeModules();

        // 绑定全局事件
        this.bindGlobalEvents();

        // 设置页面特定功能
        this.setupPageSpecificFeatures();

        this.initialized = true;

        console.log('Planning App initialized successfully');
    }

    loadPageConfig() {
        // 从页面中获取配置信息
        const configScript = document.querySelector('script[data-config]');
        if (configScript) {
            try {
                this.config = JSON.parse(configScript.textContent);
            } catch (error) {
                console.warn('Failed to parse page config:', error);
            }
        }

        // 获取当前文件和目录路径
        this.currentFilePath = this.getMetaContent('current-file') || '';
        this.currentDirPath = this.getMetaContent('current-dir') || '';
    }

    getMetaContent(name) {
        const meta = document.querySelector(`meta[name="${name}"]`);
        return meta ? meta.getAttribute('content') : '';
    }

    getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) {
            return meta.getAttribute('content');
        }

        // 尝试从cookie中获取
        const cookies = document.cookie.split(';');
        for (const cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token') {
                return decodeURIComponent(value);
            }
        }

        return '';
    }

    initializeModules() {
        // 设置CSRF令牌
        if (window.editorManager) {
            window.editorManager.setCSRFToken(this.csrfToken);
            window.editorManager.setCurrentFile(this.currentFilePath);
        }

        if (window.fileOperations) {
            window.fileOperations.setCSRFToken(this.csrfToken);
            window.fileOperations.setCurrentPaths(this.currentFilePath, this.currentDirPath);
        }

        if (window.uploadManager) {
            window.uploadManager.setCSRFToken(this.csrfToken);
        }

        // 绑定模块事件
        if (window.editorManager) {
            window.editorManager.bindEvents();
        }

        if (window.fileOperations) {
            window.fileOperations.bindEvents();
        }

        if (window.uploadManager) {
            window.uploadManager.bindEvents();
        }

        // 初始化搜索页面
        if (window.searchManager) {
            window.searchManager.initializeSearchPage();
        }

        // 初始化图片预览
        if (window.imageUtils) {
            // 延迟初始化，确保DOM完全加载
            setTimeout(() => {
                window.imageUtils.setupDocumentImagePreview();
            }, 100);
        }

        // 初始化主题管理器
        if (window.themeManager) {
            window.themeManager.initialize();
        }
    }

    bindGlobalEvents() {
        // 页面加载完成后的处理
        document.addEventListener('DOMContentLoaded', () => {
            this.onDOMContentLoaded();
        });

        // 页面可见性变化处理
        document.addEventListener('visibilitychange', () => {
            this.onVisibilityChange();
        });

        // 窗口大小变化处理
        window.addEventListener('resize', window.uiUtils?.debounce(() => {
            this.onWindowResize();
        }, 250));

        // 全局键盘快捷键
        document.addEventListener('keydown', (event) => {
            this.handleGlobalKeyboard(event);
        });

        // 注意：已移除 beforeunload 警告，因为编辑器有自动保存功能
    }

    onDOMContentLoaded() {
        // 初始化Lucide图标
        if (window.lucide) {
            try {
                window.lucide.createIcons();
            } catch (error) {
                console.warn('Failed to initialize Lucide icons:', error);
            }
        }

        // 设置焦点管理
        this.setupFocusManagement();

        // 初始化工具提示
        this.initializeTooltips();
    }

    onVisibilityChange() {
        if (document.hidden) {
            // 页面隐藏时的处理
            this.onPageHidden();
        } else {
            // 页面显示时的处理
            this.onPageVisible();
        }
    }

    onWindowResize() {
        // 响应式布局调整
        this.adjustResponsiveLayout();
    }

    onPageHidden() {
        // 可以在这里添加页面隐藏时的逻辑
        // 比如暂停某些定时器等
    }

    onPageVisible() {
        // 可以在这里添加页面显示时的逻辑
        // 比如刷新数据等
    }

    handleGlobalKeyboard(event) {
        // Ctrl+S 保存
        if ((event.ctrlKey || event.metaKey) && event.key === 's') {
            if (window.editorManager?.editorInstance) {
                event.preventDefault();
                window.editorManager.saveContent().then(success => {
                    if (success) {
                        window.uiUtils?.showToast?.('保存成功');
                        window.editorManager.hideEditor?.();
                        window.location.href = window.location.href.split('#')[0];
                    }
                });
            }
        }

        // Escape 键处理
        if (event.key === 'Escape') {
            this.handleEscapeKey();
        }
    }

    handleEscapeKey() {
        // 关闭所有模态框和菜单
        const modals = document.querySelectorAll('.modal-overlay');
        modals.forEach(modal => {
            if (modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        });

        // 隐藏上下文菜单
        if (window.contextMenuManager) {
            window.contextMenuManager.hideContextMenu();
        }
    }

    setupFocusManagement() {
        // 设置焦点陷阱和键盘导航
        const focusableElements = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Tab') {
                this.handleTabNavigation(event, focusableElements);
            }
        });
    }

    handleTabNavigation(event, focusableSelector) {
        const modal = document.querySelector('.modal-overlay[style*="flex"]');
        if (modal) {
            const focusableElements = modal.querySelectorAll(focusableSelector);
            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];

            if (event.shiftKey) {
                if (document.activeElement === firstElement) {
                    event.preventDefault();
                    lastElement.focus();
                }
            } else {
                if (document.activeElement === lastElement) {
                    event.preventDefault();
                    firstElement.focus();
                }
            }
        }
    }

    initializeTooltips() {
        // 简单的工具提示实现
        const elementsWithTooltips = document.querySelectorAll('[title]');

        elementsWithTooltips.forEach(element => {
            const title = element.getAttribute('title');
            if (title) {
                element.removeAttribute('title');
                element.setAttribute('data-tooltip', title);

                element.addEventListener('mouseenter', (event) => {
                    this.showTooltip(event.target, title);
                });

                element.addEventListener('mouseleave', () => {
                    this.hideTooltip();
                });
            }
        });
    }

    showTooltip(element, text) {
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = text;
        tooltip.id = 'app-tooltip';

        document.body.appendChild(tooltip);

        const rect = element.getBoundingClientRect();
        tooltip.style.left = `${rect.left + rect.width / 2}px`;
        tooltip.style.top = `${rect.top - tooltip.offsetHeight - 8}px`;
        tooltip.style.transform = 'translateX(-50%)';
    }

    hideTooltip() {
        const tooltip = document.getElementById('app-tooltip');
        if (tooltip) {
            tooltip.remove();
        }
    }

    adjustResponsiveLayout() {
        // 响应式布局调整逻辑
        const sidebar = document.querySelector('.sidebar');
        const mainContent = document.querySelector('.main-content');

        if (window.innerWidth <= 768) {
            // 移动端布局调整
            if (sidebar) {
                sidebar.classList.add('mobile-hidden');
            }
        } else {
            // 桌面端布局调整
            if (sidebar) {
                sidebar.classList.remove('mobile-hidden');
            }
        }
    }

    setupPageSpecificFeatures() {
        // 页面特定功能初始化
        // 根据页面类型执行不同的初始化逻辑

        // 初始化文件树折叠功能
        this.initializeFileTree();

        // 初始化移动端侧边栏
        this.initializeMobileSidebar();

        // 初始化评论功能
        this.initializeComments();
    }

    initializeFileTree() {
        // 文件树折叠展开功能（A：点箭头展开，点文字跳转）
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;

        const STORAGE_KEY = 'planning_tree_open_dirs';

        const loadOpenSet = () => {
            try {
                const raw = localStorage.getItem(STORAGE_KEY);
                if (!raw) return new Set();
                const arr = JSON.parse(raw);
                return new Set(Array.isArray(arr) ? arr : []);
            } catch (e) {
                return new Set();
            }
        };

        const saveOpenSet = (set) => {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
            } catch (e) {
                // ignore
            }
        };

        const setChildrenOpen = (childrenEl, open) => {
            if (!childrenEl || !childrenEl.classList.contains('dir-children')) return;
            childrenEl.classList.toggle('open', open);
            // 兼容模板初始 inline style
            childrenEl.style.display = open ? '' : 'none';
        };

        const applyOpenStateFromStorage = () => {
            const openSet = loadOpenSet();
            sidebar.querySelectorAll('.dir-children[data-path]').forEach((childrenEl) => {
                const p = childrenEl.dataset.path;
                if (!p) return;
                if (openSet.has(p)) {
                    setChildrenOpen(childrenEl, true);
                }
            });
        };

        // 首次初始化：恢复展开状态
        applyOpenStateFromStorage();

        // 展开/折叠全部
        const expandAllBtn = document.getElementById('expandAllBtn');
        if (expandAllBtn) {
            expandAllBtn.addEventListener('click', () => {
                const openSet = loadOpenSet();
                sidebar.querySelectorAll('.dir-children[data-path]').forEach((childrenEl) => {
                    const p = childrenEl.dataset.path;
                    if (p) openSet.add(p);
                    setChildrenOpen(childrenEl, true);
                });
                saveOpenSet(openSet);
            });
        }

        const collapseAllBtn = document.getElementById('collapseAllBtn');
        if (collapseAllBtn) {
            collapseAllBtn.addEventListener('click', () => {
                sidebar.querySelectorAll('.dir-children[data-path]').forEach((childrenEl) => {
                    setChildrenOpen(childrenEl, false);
                });
                saveOpenSet(new Set());
            });
        }

        // 点击箭头展开/折叠
        sidebar.addEventListener('click', (e) => {
            const toggleBtn = e.target.closest('.toggle');
            const dirLink = e.target.closest('.dir-item');
            if (!toggleBtn && !dirLink) return;

            // 点目录链接：保持跳转（不拦截）
            if (dirLink && !toggleBtn) return;

            const row = toggleBtn.closest('.tree-row');
            if (!row) return;

            const children = row.nextElementSibling;
            if (!children || !children.classList.contains('dir-children')) return;

            e.preventDefault();
            e.stopPropagation();

            const nextOpen = !children.classList.contains('open');
            setChildrenOpen(children, nextOpen);

            const path = children.dataset.path;
            if (path) {
                const openSet = loadOpenSet();
                if (nextOpen) openSet.add(path);
                else openSet.delete(path);
                saveOpenSet(openSet);
            }
        });
    }

    initializeMobileSidebar() {
        // 移动端侧边栏切换（对齐 templates/index.html 的 #leftMenuBtn / .sidebar.show）
        const leftMenuBtn = document.getElementById('leftMenuBtn');
        const sidebar = document.getElementById('sidebar');
        const backdrop = document.getElementById('backdrop');

        if (leftMenuBtn && sidebar) {
            leftMenuBtn.addEventListener('click', () => {
                sidebar.classList.toggle('show');
                backdrop?.classList.toggle('show');
            });
        }

        if (backdrop && sidebar) {
            backdrop.addEventListener('click', () => {
                sidebar.classList.remove('show');
                backdrop.classList.remove('show');
            });
        }
    }

    initializeComments() {
        // 评论功能初始化
        const commentForm = document.querySelector('#commentForm');
        if (commentForm) {
            // 评论表单相关逻辑可以在这里添加
        }
    }

    // 公共工具方法
    showNotification(message, type = 'info', duration = 3000) {
        if (window.uiUtils) {
            window.uiUtils.showToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    async confirmAction(title, message, confirmText = '确定') {
        if (window.uiUtils) {
            return await window.uiUtils.showConfirmDialog(title, message, confirmText);
        } else {
            return confirm(`${title}\n\n${message}`);
        }
    }

    async promptInput(title, message, defaultValue = '') {
        if (window.uiUtils) {
            return await window.uiUtils.showPromptDialog(title, message, defaultValue);
        } else {
            return prompt(`${title}\n\n${message}`, defaultValue);
        }
    }

    // 模块间通信方法
    emit(eventName, data) {
        const event = new CustomEvent(`planning:${eventName}`, { detail: data });
        document.dispatchEvent(event);
    }

    on(eventName, callback) {
        document.addEventListener(`planning:${eventName}`, callback);
    }

    off(eventName, callback) {
        document.removeEventListener(`planning:${eventName}`, callback);
    }
}

// 创建全局应用实例
window.planningApp = new PlanningApp();

// 自动初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.planningApp.initialize();
    });
} else {
    window.planningApp.initialize();
}