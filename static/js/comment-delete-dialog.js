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
                border-bottom: 1px solid #eef2f7;
                background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            }
            .comment-delete-dialog-head h3 {
                margin: 0;
                font-size: 18px;
                color: #0f172a;
            }
            .comment-delete-dialog-head p {
                margin: 6px 0 0;
                color: #64748b;
                font-size: 13px;
                line-height: 1.6;
            }
            .comment-delete-dialog-body {
                padding: 0 20px 18px;
                color: #475569;
                line-height: 1.75;
                font-size: 14px;
            }
            .comment-delete-dialog-impact {
                margin-top: 14px;
                padding: 12px 14px;
                border-radius: 12px;
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                color: #1e40af;
                font-size: 13px;
                line-height: 1.7;
            }
            .comment-delete-dialog-impact strong {
                display: block;
                margin-bottom: 4px;
                font-size: 13px;
                color: #1d4ed8;
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
            .comment-delete-dialog-btn:hover {
                transform: translateY(-1px);
                box-shadow: 0 10px 20px rgba(15, 23, 42, 0.12);
            }
            @media (max-width: 640px) {
                .comment-delete-dialog-overlay {
                    padding: 14px;
                }
                .comment-delete-dialog {
                    border-radius: 14px;
                }
                .comment-delete-dialog-actions {
                    flex-direction: column-reverse;
                }
                .comment-delete-dialog-btn {
                    width: 100%;
                }
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
                    <p id="commentDeleteDialogSubtitle">请确认这次删除操作的影响范围。</p>
                </div>
                <div class="comment-delete-dialog-body">
                    <div id="commentDeleteDialogMessage"></div>
                    <div class="comment-delete-dialog-impact" id="commentDeleteDialogImpact"></div>
                </div>
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
        const subtitle = overlay.querySelector('#commentDeleteDialogSubtitle');
        const impact = overlay.querySelector('#commentDeleteDialogImpact');
        const treeButton = overlay.querySelector('[data-action="tree"]');
        const singleButton = overlay.querySelector('[data-action="single"]');

        const replyCount = Math.max(parseInt(options && options.replyCount, 10) || 0, 0);
        const allowTreeDelete = !!(options && options.allowTreeDelete);

        if (replyCount > 0) {
            subtitle.textContent = '这条评论下仍有关联回复，请先选择删除策略。';
            message.textContent = '删除当前评论后，你可以选择保留后续讨论上下文，或者由管理员直接删除整棵回复树。';
            impact.innerHTML = allowTreeDelete
                ? '<strong>影响范围</strong>当前评论下共有 ' + replyCount + ' 条子回复。选择“仅删除当前评论”会保留下方回复；选择“删除整个评论树”会一并移除这些子回复。'
                : '<strong>影响范围</strong>当前评论下共有 ' + replyCount + ' 条子回复。你当前只能删除自己的这条评论，下方回复会继续保留。';
            impact.style.display = 'block';
        } else {
            subtitle.textContent = '这条评论没有子回复。';
            message.textContent = '确定删除这条评论吗？';
            impact.style.display = 'none';
            impact.textContent = '';
        }

        singleButton.textContent = replyCount > 0 ? '仅删除当前评论' : '删除评论';
        treeButton.textContent = replyCount > 0 ? '删除当前评论及 ' + replyCount + ' 条回复' : '删除整个评论树';
        treeButton.style.display = allowTreeDelete && replyCount > 0 ? 'inline-flex' : 'none';

        pendingAction = options || null;
        overlay.classList.add('show');
    };
})();
