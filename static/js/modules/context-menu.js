/**
 * 上下文菜单模块 - 处理右键菜单功能
 */
class ContextMenuManager {
    constructor() {
        this.contextMenuTarget = null;
        this.uploadTargetDir = '';
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        this.treeContextMenu = document.getElementById('treeContextMenu');
    }

    showContextMenu(event, target) {
        if (!this.treeContextMenu || window.innerWidth <= 900) return;

        event.preventDefault();
        event.stopPropagation();

        this.contextMenuTarget = target;

        // 设置菜单位置
        this.treeContextMenu.style.left = `${event.clientX}px`;
        this.treeContextMenu.style.top = `${event.clientY}px`;

        // 根据目标类型显示/隐藏菜单项
        const uploadDocBtn = this.treeContextMenu.querySelector('[data-action="upload-doc"]');
        const createDocBtn = this.treeContextMenu.querySelector('[data-action="create-doc"]');

        if (uploadDocBtn) {
            uploadDocBtn.style.display = target.type === 'dir' ? 'flex' : 'none';
        }

        if (createDocBtn) {
            createDocBtn.style.display = target.type === 'dir' ? 'flex' : 'none';
        }

        this.treeContextMenu.classList.add('show');

        // 刷新图标
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    hideContextMenu() {
        if (this.treeContextMenu) {
            this.treeContextMenu.classList.remove('show');
        }
        this.contextMenuTarget = null;
    }

    handleContextMenuAction(action) {
        if (!this.contextMenuTarget) return;

        const target = this.contextMenuTarget;

        switch (action) {
            case 'create-doc':
                if (target.type === 'dir') {
                    window.fileOperations?.createDocument(target.path);
                }
                break;

            case 'upload-doc':
                if (target.type === 'dir') {
                    this.uploadTargetDir = target.path;
                    const uploadInput = document.getElementById('uploadInput');
                    if (uploadInput) {
                        window.uploadManager?.setUploadTargetDir(target.path);
                        uploadInput.click();
                    }
                }
                break;

            case 'rename':
                if (target.type === 'dir') {
                    window.fileOperations?.renameDirectory(target.path, target.name);
                } else {
                    window.fileOperations?.renameDocument(target.path, target.name);
                }
                break;

            case 'delete':
                if (target.type === 'dir') {
                    window.fileOperations?.deleteDirectory(target.path, target.name);
                } else {
                    window.fileOperations?.deleteDocument(target.path, target.name);
                }
                break;

            default:
                console.warn('Unknown context menu action:', action);
        }

        this.hideContextMenu();
    }

    bindEvents() {
        // 绑定文件树节点的右键事件
        document.querySelectorAll('.dir-item, .file-row').forEach(node => {
            node.addEventListener('contextmenu', (event) => {
                const target = {
                    type: node.dataset.nodeType || (node.dataset.dirPath ? 'dir' : 'file'),
                    path: node.dataset.dirPath || node.dataset.filePath || '',
                    name: node.dataset.nodeName || node.dataset.dirName || node.dataset.fileName || ''
                };

                this.showContextMenu(event, target);
            });
        });

        // 绑定上下文菜单按钮事件
        if (this.treeContextMenu) {
            this.treeContextMenu.querySelectorAll('button').forEach(button => {
                button.addEventListener('click', (event) => {
                    event.preventDefault();
                    event.stopPropagation();

                    const action = button.dataset.action;
                    if (action) {
                        this.handleContextMenuAction(action);
                    }
                });
            });
        }

        // 点击其他地方隐藏菜单
        document.addEventListener('click', (event) => {
            if (this.treeContextMenu &&
                !this.treeContextMenu.contains(event.target) &&
                this.treeContextMenu.classList.contains('show')) {
                this.hideContextMenu();
            }
        });

        // ESC键隐藏菜单
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' &&
                this.treeContextMenu &&
                this.treeContextMenu.classList.contains('show')) {
                this.hideContextMenu();
            }
        });
    }

    // 动态添加右键菜单到新创建的节点
    addContextMenuToNode(node) {
        node.addEventListener('contextmenu', (event) => {
            const target = {
                type: node.dataset.nodeType || (node.dataset.dirPath ? 'dir' : 'file'),
                path: node.dataset.dirPath || node.dataset.filePath || '',
                name: node.dataset.nodeName || node.dataset.dirName || node.dataset.fileName || ''
            };

            this.showContextMenu(event, target);
        });
    }

    // 创建上下文菜单HTML（如果页面中不存在）
    createContextMenuHTML() {
        if (document.getElementById('treeContextMenu')) return;

        const contextMenu = document.createElement('div');
        contextMenu.id = 'treeContextMenu';
        contextMenu.className = 'context-menu';
        contextMenu.innerHTML = `
            <button data-action="create-doc">
                <i data-lucide="file-plus"></i>
                新建文档
            </button>
            <button data-action="upload-doc">
                <i data-lucide="upload"></i>
                上传文档
            </button>
            <hr>
            <button data-action="rename">
                <i data-lucide="edit-3"></i>
                重命名
            </button>
            <button data-action="delete">
                <i data-lucide="trash-2"></i>
                删除
            </button>
        `;

        document.body.appendChild(contextMenu);
        this.treeContextMenu = contextMenu;
    }
}

// 导出单例
window.contextMenuManager = new ContextMenuManager();