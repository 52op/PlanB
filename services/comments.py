from datetime import datetime, timedelta
import re
import secrets

import bleach
import markdown
from flask_login import current_user

from models import Comment, EmailVerificationCode, SystemSetting, User, db
from .mailer import mailer_is_configured, notification_allowed, record_notification, render_mail_layout, send_logged_mail


EMAIL_RE = re.compile(r'^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$', re.I)
PASSWORD_RE = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{8,}$')
COMMENT_ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union({'p', 'br', 'pre', 'code', 'blockquote', 'ul', 'ol', 'li', 'strong', 'em', 'a'})
COMMENT_ALLOWED_ATTRIBUTES = {'a': ['href', 'title', 'rel', 'target']}


def _render_comment_content(text):
    html = markdown.markdown(text or '', extensions=['fenced_code'])
    return bleach.clean(html, tags=COMMENT_ALLOWED_TAGS, attributes=COMMENT_ALLOWED_ATTRIBUTES, strip=True)


MENTION_RE = re.compile(r'@([A-Za-z0-9_\-\u4e00-\u9fff]+)')


def create_email_verification_code(email, purpose='register'):
    latest = EmailVerificationCode.query.filter_by(email=email, purpose=purpose).order_by(EmailVerificationCode.created_at.desc()).first()
    if latest and latest.created_at and latest.created_at > datetime.utcnow() - timedelta(seconds=60):
        seconds_left = 60 - int((datetime.utcnow() - latest.created_at).total_seconds())
        raise ValueError(f'请 {seconds_left} 秒后再发送验证码')
    EmailVerificationCode.query.filter_by(email=email, purpose=purpose).delete()
    code = f'{secrets.randbelow(1000000):06d}'
    record = EmailVerificationCode()
    record.email = email
    record.code = code
    record.purpose = purpose
    record.expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.session.add(record)
    db.session.commit()
    return code


def verify_email_code(email, code, purpose='register'):
    record = EmailVerificationCode.query.filter_by(email=email, purpose=purpose, code=code).first()
    if not record:
        return False
    if record.expires_at < datetime.utcnow():
        db.session.delete(record)
        db.session.commit()
        return False
    db.session.delete(record)
    db.session.commit()
    return True


def comments_enabled():
    return (SystemSetting.get('comments_enabled', 'true') or 'true').lower() == 'true'


def comments_require_approval():
    return (SystemSetting.get('comments_require_approval', 'true') or 'true').lower() == 'true'


def _collect_comment_descendant_ids(comment_id):
    descendant_ids = []
    children = Comment.query.filter_by(parent_id=comment_id).all()
    for child in children:
        descendant_ids.extend(_collect_comment_descendant_ids(child.id))
        descendant_ids.append(child.id)
    return descendant_ids


def get_comments_for_filename(filename, include_pending=False):
    comments = Comment.query.filter_by(filename=filename).order_by(Comment.created_at.asc()).all()
    comment_map = {comment.id: comment for comment in comments}

    for comment in comments:
        comment._children = []
        comment.visible_replies = []
        comment.visible_descendant_count = 0
        comment.descendant_count = 0
        comment.rendered_content = ''

    for comment in comments:
        if comment.parent_id and comment.parent_id in comment_map:
            comment_map[comment.parent_id]._children.append(comment)

    placeholder_html = '<p><em>该评论已删除，回复内容已保留。</em></p>'

    def build_visible_tree(comment):
        visible_children = []
        visible_descendant_count = 0

        for child in getattr(comment, '_children', []):
            if build_visible_tree(child):
                visible_children.append(child)
                visible_descendant_count += 1 + int(getattr(child, 'visible_descendant_count', 0) or 0)

        comment.visible_replies = visible_children
        comment.visible_descendant_count = visible_descendant_count
        comment.descendant_count = len(_collect_comment_descendant_ids(comment.id))

        status = str(comment.status or '').strip().lower()
        if status == 'approved':
            comment.rendered_content = _render_comment_content(comment.content)
            return True
        if status == 'pending':
            if include_pending:
                comment.rendered_content = _render_comment_content(comment.content)
                return True
            return False
        if status == 'deleted' and visible_children:
            comment.rendered_content = placeholder_html
            return True
        return False

    top_level = []
    for comment in comments:
        if comment.parent_id and comment.parent_id in comment_map:
            continue
        if build_visible_tree(comment):
            top_level.append(comment)

    for comment in comments:
        if hasattr(comment, '_children'):
            delattr(comment, '_children')

    return top_level


def can_delete_comment(comment, user=None):
    actor = user or current_user
    if not getattr(actor, 'is_authenticated', False):
        return False
    if getattr(actor, 'role', '') == 'admin':
        return True
    return getattr(comment, 'user_id', None) == getattr(actor, 'id', None)


def can_edit_comment(comment, user=None):
    return can_delete_comment(comment, user=user)


def create_comment(filename, content, user=None, parent_id=None, article_url=''):
    import secrets
    from flask import url_for
    
    author = user or current_user
    if not getattr(author, 'is_authenticated', False):
        raise PermissionError('请先登录后再发表评论')
    if not getattr(author, 'email_verified', False):
        raise PermissionError('请先完成邮箱验证后再发表评论')
    if not getattr(author, 'can_comment', True):
        raise PermissionError('你的评论权限已被管理员禁用')
    text = (content or '').strip()
    if not text:
        raise ValueError('评论内容不能为空')

    comment = Comment()
    comment.filename = filename
    comment.user_id = author.id
    comment.content = text
    
    # 生成审核令牌
    comment.approval_token = secrets.token_urlsafe(32)
    
    if parent_id:
        comment.parent_id = int(parent_id)
    if getattr(author, 'role', '') == 'admin':
        comment.status = 'approved'
    elif getattr(author, 'role', '') == 'guest' and comments_require_approval():
        comment.status = 'pending'
    else:
        comment.status = 'approved' if not comments_require_approval() else 'pending'
    db.session.add(comment)
    db.session.commit()

    # 发送管理员通知（仅当评论需要审核时）
    if comment.status == 'pending' and mailer_is_configured():
        # 获取所有已验证邮箱的管理员
        admins = User.query.filter_by(role='admin', email_verified=True).filter(User.email.isnot(None)).all()
        
        for admin in admins:
            if not admin.email:
                continue
            
            try:
                # 生成审核链接
                approval_url = url_for('main.approve_comment', token=comment.approval_token, _external=True)
                
                # 获取文章标题（从 filename 提取）
                article_title = filename.replace('.md', '').replace('/', ' / ')
                
                send_logged_mail(
                    'comment_admin_notification',
                    admin.email,
                    '新评论待审核',
                    f'{author.username} 在 {article_title} 发表了新评论：{text[:100]}',
                    '新评论待审核',
                    f'用户 <strong>{author.username}</strong> 在文章 <strong>{article_title}</strong> 发表了新评论。',
                    f'<div style="margin-top:16px;padding:16px 18px;border-radius:14px;background:#f0f9ff;color:#0c4a6e;line-height:1.8;"><strong>评论内容：</strong><br>{text}</div>',
                    action_url=approval_url,
                    action_label='审核通过',
                    cooldown_seconds=10,
                )
            except Exception:
                pass

    # 发送回复通知
    if comment.parent_id:
        parent_comment = Comment.query.get(comment.parent_id)
        if parent_comment and parent_comment.user and parent_comment.user.email and parent_comment.user.email_verified and mailer_is_configured() and notification_allowed('comment_reply', parent_comment.user.email, cooldown_seconds=30):
            try:
                send_logged_mail(
                    'comment_reply',
                    parent_comment.user.email,
                    '你收到了一条评论回复',
                    f'{author.username} 回复了你在 {filename} 下的评论：{text}',
                    '你收到了一条评论回复',
                    f'用户 <strong>{author.username}</strong> 回复了你在文章 <strong>{filename}</strong> 下的评论。',
                    f'<div style="margin-top:16px;padding:16px 18px;border-radius:14px;background:#fff7ed;color:#7c2d12;line-height:1.8;">{text}</div>',
                    action_url=article_url,
                    action_label='查看文章',
                    cooldown_seconds=30,
                )
            except Exception:
                pass

    # 发送提及通知
    mentioned_names = {name for name in MENTION_RE.findall(text) if name}
    if mentioned_names and mailer_is_configured():
        users = User.query.filter(User.username.in_(list(mentioned_names))).all()
        for mentioned_user in users:
            if mentioned_user.id == author.id:
                continue
            if not mentioned_user.email or not mentioned_user.email_verified:
                continue
            try:
                send_logged_mail(
                    'comment_mention',
                    mentioned_user.email,
                    '你在评论中被提及了',
                    f'{author.username} 在 {filename} 的评论中提到了你：{text}',
                    '你在评论中被提及了',
                    f'用户 <strong>{author.username}</strong> 在文章 <strong>{filename}</strong> 的评论中提到了你。',
                    f'<div style="margin-top:16px;padding:16px 18px;border-radius:14px;background:#fff7ed;color:#7c2d12;line-height:1.8;">{text}</div>',
                    action_url=article_url,
                    action_label='查看文章',
                    cooldown_seconds=30,
                )
            except Exception:
                pass
    return comment


def delete_comment(comment, user=None, delete_mode='single'):
    actor = user or current_user
    if not can_delete_comment(comment, user=actor):
        raise PermissionError('无权删除该评论')

    normalized_mode = str(delete_mode or 'single').strip().lower()
    if normalized_mode not in {'single', 'tree'}:
        raise ValueError('评论删除模式无效')
    if normalized_mode == 'tree' and getattr(actor, 'role', '') != 'admin':
        raise PermissionError('只有管理员可以删除整棵评论树')

    if normalized_mode == 'tree':
        target_ids = _collect_comment_descendant_ids(comment.id)
        target_ids.append(comment.id)
        target_ids = list(dict.fromkeys(target_ids))
        (
            Comment.query
            .filter(Comment.id.in_(target_ids))
            .update({'status': 'deleted'}, synchronize_session=False)
        )
    else:
        comment.status = 'deleted'
    db.session.commit()


def update_comment(comment, content, user=None):
    if not can_edit_comment(comment, user=user):
        raise PermissionError('无权编辑该评论')
    text = (content or '').strip()
    if not text:
        raise ValueError('评论内容不能为空')
    actor = user or current_user
    comment.content = text
    if getattr(actor, 'role', '') == 'admin':
        comment.status = 'approved'
    elif comments_require_approval():
        comment.status = 'pending'
    else:
        comment.status = 'approved'
    db.session.commit()
    return comment


def get_comment_stats():
    return {
        'total_comments': Comment.query.filter(Comment.status != 'deleted').count(),
        'pending_comments': Comment.query.filter_by(status='pending').count(),
        'approved_comments': Comment.query.filter_by(status='approved').count(),
        'deleted_comments': Comment.query.filter_by(status='deleted').count(),
    }


def get_recent_comment_entries(limit=5, include_private=False):
    from .docs import get_posts

    try:
        max_items = max(int(limit or 0), 0)
    except (TypeError, ValueError):
        max_items = 5
    if max_items <= 0:
        return []

    post_map = {}
    for post in get_posts(include_private=include_private):
        filename = str(post.get('filename') or '').strip()
        if not filename:
            continue
        post_map[filename] = {
            'title': str(post.get('title') or '未命名文章').strip() or '未命名文章',
            'url': str(post.get('url') or '').strip(),
        }

    if not post_map:
        return []

    sample_size = max(max_items * 6, 24)
    recent_comments = (
        Comment.query
        .filter_by(status='approved')
        .order_by(Comment.created_at.desc())
        .limit(sample_size)
        .all()
    )

    entries = []
    for comment in recent_comments:
        post_info = post_map.get(comment.filename)
        if not post_info:
            continue
        author = getattr(comment, 'user', None)
        author_name = ''
        if author:
            author_name = str(getattr(author, 'nickname', '') or getattr(author, 'username', '') or '').strip()
        if not author_name:
            author_name = '匿名'
        excerpt = re.sub(r'\s+', ' ', str(comment.content or '')).strip()
        excerpt = re.sub(r'[`#>*_\-\[\]\(\)!]+', '', excerpt).strip()
        if len(excerpt) > 72:
            excerpt = f"{excerpt[:69].rstrip()}..."
        entries.append({
            'id': comment.id,
            'author_name': author_name,
            'excerpt': excerpt or '这条评论还没有可显示的内容。',
            'created_at': comment.created_at,
            'url': f"{post_info['url']}#comments" if post_info.get('url') else '',
            'post_title': post_info.get('title') or '未命名文章',
            'is_reply': bool(comment.parent_id),
        })
        if len(entries) >= max_items:
            break

    return entries


def get_user_stats():
    return {
        'total_users': User.query.count(),
        'verified_users': User.query.filter_by(email_verified=True).count(),
        'guest_users': User.query.filter_by(role='guest').count(),
    }


def validate_registration_input(username, email, password):
    username = (username or '').strip()
    email = (email or '').strip().lower()
    if len(username) < 3:
        raise ValueError('用户名至少 3 个字符')
    if not EMAIL_RE.match(email):
        raise ValueError('邮箱格式不正确')
    if not PASSWORD_RE.match(password or ''):
        raise ValueError('密码至少 8 位，且必须同时包含字母和数字')
    return username, email
