/**
 * UI工具模块 - 处理对话框、提示信息等UI交互
 */
class UIUtils {
    constructor() {
        this.appToast = document.getElementById('appToast');
        this.initializeDialogs();
    }

    initializeDialogs() {
        // 创建确认对话框
        if (!document.getElementById('confirmDialog')) {
            const confirmDialog = document.createElement('div');
            confirmDialog.id = 'confirmDialog';
            confirmDialog.className = 'modal-overlay';
            confirmDialog.innerHTML = `
                <div class="modal-content">
                    <h3 id="confirmTitle">确认操作</h3>
                    <p id="confirmMessage">确定要执行此操作吗？</p>
                    <div class="modal-actions">
                        <button id="confirmCancel" class="btn btn-secondary">取消</button>
                        <button id="confirmOk" class="btn btn-primary">确定</button>
                    </div>
                </div>
            `;
            document.body.appendChild(confirmDialog);
        }

        // 创建提示对话框
        if (!document.getElementById('alertDialog')) {
            const alertDialog = document.createElement('div');
            alertDialog.id = 'alertDialog';
            alertDialog.className = 'modal-overlay';
            alertDialog.innerHTML = `
                <div class="modal-content">
                    <h3 id="alertTitle">提示</h3>
                    <p id="alertMessage">操作完成</p>
                    <div class="modal-actions">
                        <button id="alertOk" class="btn btn-primary">确定</button>
                    </div>
                </div>
            `;
            document.body.appendChild(alertDialog);
        }

        // 创建输入对话框
        if (!document.getElementById('promptDialog')) {
            const promptDialog = document.createElement('div');
            promptDialog.id = 'promptDialog';
            promptDialog.className = 'modal-overlay';
            promptDialog.innerHTML = `
                <div class="modal-content">
                    <h3 id="promptTitle">输入</h3>
                    <p id="promptMessage">请输入内容：</p>
                    <input type="text" id="promptInput" class="form-control" />
                    <div class="modal-actions">
                        <button id="promptCancel" class="btn btn-secondary">取消</button>
                        <button id="promptOk" class="btn btn-primary">确定</button>
                    </div>
                </div>
            `;
            document.body.appendChild(promptDialog);
        }
    }

    showToast(message, type = 'success') {
        if (!this.appToast) return;
        this.appToast.textContent = message;
        this.appToast.className = `app-toast show ${type}`;
        window.clearTimeout(this.showToast._timer);
        this.showToast._timer = window.setTimeout(() => {
            this.appToast.className = 'app-toast';
        }, 3000);
    }

    showAlertDialog(title, message) {
        return new Promise((resolve) => {
            const dialog = document.getElementById('alertDialog');
            const titleEl = document.getElementById('alertTitle');
            const messageEl = document.getElementById('alertMessage');
            const okBtn = document.getElementById('alertOk');

            titleEl.textContent = title;
            messageEl.textContent = message;
            dialog.style.display = 'flex';

            const handleOk = () => {
                dialog.style.display = 'none';
                okBtn.removeEventListener('click', handleOk);
                resolve();
            };

            okBtn.addEventListener('click', handleOk);
        });
    }

    showConfirmDialog(title, message, confirmText = '确定') {
        return new Promise((resolve) => {
            const dialog = document.getElementById('confirmDialog');
            const titleEl = document.getElementById('confirmTitle');
            const messageEl = document.getElementById('confirmMessage');
            const okBtn = document.getElementById('confirmOk');
            const cancelBtn = document.getElementById('confirmCancel');

            titleEl.textContent = title;
            messageEl.textContent = message;
            okBtn.textContent = confirmText;
            dialog.style.display = 'flex';

            const handleOk = () => {
                dialog.style.display = 'none';
                cleanup();
                resolve(true);
            };

            const handleCancel = () => {
                dialog.style.display = 'none';
                cleanup();
                resolve(false);
            };

            const cleanup = () => {
                okBtn.removeEventListener('click', handleOk);
                cancelBtn.removeEventListener('click', handleCancel);
            };

            okBtn.addEventListener('click', handleOk);
            cancelBtn.addEventListener('click', handleCancel);
        });
    }

    showPromptDialog(title, message, defaultValue = '') {
        return new Promise((resolve) => {
            const dialog = document.getElementById('promptDialog');
            const titleEl = document.getElementById('promptTitle');
            const messageEl = document.getElementById('promptMessage');
            const inputEl = document.getElementById('promptInput');
            const okBtn = document.getElementById('promptOk');
            const cancelBtn = document.getElementById('promptCancel');

            titleEl.textContent = title;
            messageEl.textContent = message;
            inputEl.value = defaultValue;
            dialog.style.display = 'flex';
            inputEl.focus();
            inputEl.select();

            const handleOk = () => {
                const value = inputEl.value.trim();
                dialog.style.display = 'none';
                cleanup();
                resolve(value || null);
            };

            const handleCancel = () => {
                dialog.style.display = 'none';
                cleanup();
                resolve(null);
            };

            const handleKeyPress = (e) => {
                if (e.key === 'Enter') {
                    handleOk();
                } else if (e.key === 'Escape') {
                    handleCancel();
                }
            };

            const cleanup = () => {
                okBtn.removeEventListener('click', handleOk);
                cancelBtn.removeEventListener('click', handleCancel);
                inputEl.removeEventListener('keypress', handleKeyPress);
            };

            okBtn.addEventListener('click', handleOk);
            cancelBtn.addEventListener('click', handleCancel);
            inputEl.addEventListener('keypress', handleKeyPress);
        });
    }

    getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// 导出单例
window.uiUtils = new UIUtils();