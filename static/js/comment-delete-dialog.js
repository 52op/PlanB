(function () {
    if (window.openCommentDeleteDialog) {
        return;
    }

    let pendingAction = null;

    function ensureStyles() {
        if (document.getElementById('commentDeleteDialogStyles')) {
            return;
        }
        const style = document.createElement('style');
        style.id = 'commentDeleteDialogStyles';
        style.textContent = `
            .comment-delete-dialog-overlay {
                position: fixed;
                inset: 0;
                display: none;
                align-items: center;
                justify-content: center;
                padding: 20px;
                background: rgba(15, 23, 42, 0.45);
                backdrop-filter: blur(4px);
                z-index: 2200;
            }
            .comment-delete-dialog-overlay.show {
                display: flex;
            }
            .comment-delete-dialog {
                width: min(480px, 100%);
                background: #fff;
                border-radius: 16px;
                box-shadow: 0 20px 48px rgba(15, 23, 42, 0.24);
                overflow: hidden;
            }
            .comment-delete-dialog-head {
                padding: 18px 20px 12px;
            }
            .comment-delete-dialog-head h3 {
                margin: 0;
                font-size: 18px;
                color: #0f172a;
            }
            .comment-delete-dialog-body {
                padding: 0 20px 18px;
                color: #475569;
                line-height: 1.75;
                font-size: 14px;
            }
            .comment-delete-dialog-actions {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                justify-content: flex-end;
                padding: 16px 20px 20px;
                border-top: 1px solid #e2e8f0;
                background: #f8fafc;
            }
            .comment-delete-dialog-btn {
                border: none;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
            }
            .comment-delete-dialog-btn.cancel {
                background: #e2e8f0;
                color: #334155;
            }
            .comment-delete-dialog-btn.single {
                background: #2563eb;
                color: #fff;
            }
            .comment-delete-dialog-btn.tree {
                background: #b91c1c;
                color: #fff;
            }
        `;
        document.head.appendChild(style);
    }

    function closeDialog() {
        const overlay = document.getElementById('commentDeleteDialogOverlay');
        if (overlay) {
            overlay.classList.remove('show');
        }
        pendingAction = null;
    }

    function ensureDialog() {
        ensureStyles();
        let overlay = document.getElementById('commentDeleteDialogOverlay');
        if (overlay) {
            return overlay;
        }

        overlay = document.createElement('div');
        overlay.id = 'commentDeleteDialogOverlay';
        overlay.className = 'comment-delete-dialog-overlay';
        overlay.innerHTML = `
            <div class="comment-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="commentDeleteDialogTitle">
                <div class="comment-delete-dialog-head">
                    <h3 id="commentDeleteDialogTitle">删除评论</h3>
                </div>
                <div class="comment-delete-dialog-body" id="commentDeleteDialogMessage"></div>
                <div class="comment-delete-dialog-actions">
                    <button type="button" class="comment-delete-dialog-btn cancel" data-action="cancel">取消</button>
                    <button type="button" class="comment-delete-dialog-btn single" data-action="single">仅删除当前评论</button>
                    <button type="button" class="comment-delete-dialog-btn tree" data-action="tree">删除整个评论树</button>
                </div>
            </div>
        `;

        overlay.addEventListener('click', function (event) {
            if (event.target === overlay) {
                closeDialog();
            }
        });

        overlay.querySelector('[data-action="cancel"]').addEventListener('click', function () {
            closeDialog();
        });

        overlay.querySelector('[data-action="single"]').addEventListener('click', function () {
            const action = pendingAction;
            closeDialog();
            if (action && typeof action.onSingle === 'function') {
                action.onSingle();
            }
        });

        overlay.querySelector('[data-action="tree"]').addEventListener('click', function () {
            const action = pendingAction;
            closeDialog();
            if (action && typeof action.onTree === 'function') {
                action.onTree();
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                closeDialog();
            }
        });

        document.body.appendChild(overlay);
        return overlay;
    }

    window.openCommentDeleteDialog = function (options) {
        const overlay = ensureDialog();
        const message = overlay.querySelector('#commentDeleteDialogMessage');
        const treeButton = overlay.querySelector('[data-action="tree"]');
        const singleButton = overlay.querySelector('[data-action="single"]');

        const replyCount = Math.max(parseInt(options && options.replyCount, 10) || 0, 0);
        const allowTreeDelete = !!(options && options.allowTreeDelete);

        message.textContent = replyCount > 0
            ? '这条评论下还有 ' + replyCount + ' 条回复。你可以只删除当前评论并保留讨论上下文，或者删除整棵评论树。'
            : '确定删除这条评论吗？';

        singleButton.textContent = replyCount > 0 ? '仅删除当前评论' : '删除评论';
        treeButton.style.display = allowTreeDelete && replyCount > 0 ? 'inline-flex' : 'none';

        pendingAction = options || null;
        overlay.classList.add('show');
    };
})();
