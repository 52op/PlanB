import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, current_app
from flask_login import login_required, current_user
from models import Comment, DocumentViewStat, NotificationLog, PasswordAccessRule, db, SystemSetting, User, PermissionRule, BackupConfig
from services import (
    annotate_comment_descendant_counts,
    clear_comment_approval_token,
    get_comment_descendant_ids,
    get_comment_stats,
    get_docs_root,
    get_posts,
    get_rate_limit_backend_status,
    get_user_stats,
    mailer_is_configured,
    normalize_password_access_target,
    preview_cover_source,
    resolve_docs_path,
    send_logged_mail,
    update_all_image_references,
)
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__, template_folder='templates', url_prefix='/admin')

DELETED_USER_USERNAME = '__deleted_user__'
DELETED_USER_NICKNAME = '已注销用户'

SECURITY_SETTING_DEFAULTS = {
    'security_rate_limit_backend': 'database',
    'security_redis_url': '',
    'security_redis_key_prefix': 'planning:rate-limit',
    'security_login_rate_limit_enabled': 'true',
    'security_verification_rate_limit_enabled': 'true',
    'security_verification_send_rate_limit_enabled': 'true',
    'security_rate_limit_level1_attempts': '3',
    'security_rate_limit_level1_seconds': '30',
    'security_rate_limit_level2_attempts': '5',
    'security_rate_limit_level2_seconds': '300',
    'security_rate_limit_level3_attempts': '10',
    'security_rate_limit_level3_seconds': '1800',
    'security_send_rate_limit_level1_attempts': '5',
    'security_send_rate_limit_level1_seconds': '600',
    'security_send_rate_limit_level2_attempts': '10',
    'security_send_rate_limit_level2_seconds': '3600',
    'security_send_rate_limit_level3_attempts': '20',
    'security_send_rate_limit_level3_seconds': '86400',
    'security_rate_limit_record_ttl_seconds': '7200',
    # IP 访问控制
    'security_ip_whitelist_enabled': 'false',
    'security_ip_whitelist': '',
    'security_ip_blacklist_enabled': 'false',
    'security_ip_blacklist': '',
    'security_shared_secret_enabled': 'false',
    'security_shared_secret': '',
    'security_shared_secret_header': 'X-Internal-Secret',
}

COVER_SETTING_DEFAULTS = {
    'random_cover_api': '',
    'random_cover_source_type': 'url',
    'random_cover_local_dir': 'covers',
    'random_cover_pexels_api_key': '',
    'random_cover_pexels_default_query': 'nature',
    'random_cover_pexels_orientation': 'landscape',
    'random_cover_pexels_per_page': '6',
    'random_cover_pexels_cache_hours': '24',
}


def _get_settings_map():
    return {s.key: s.value for s in SystemSetting.query.all()}


def _get_or_404(model, object_id):
    instance = db.session.get(model, object_id)
    if instance is None:
        abort(404)
    return instance


def _is_protected_system_user(user):
    if not user:
        return False
    return user.username in {'admin', DELETED_USER_USERNAME}


def _get_access_mode_label(access_mode):
    labels = {
        'open': '完全开放模式',
        'group_only': '需登录访问模式',
        'password_only': '固定密码访问模式',
    }
    return labels.get(access_mode, access_mode or '未设置')


def _list_doc_directories(include_root=False):
    docs_dir = get_docs_root()
    all_dirs = ['/'] if include_root else []
    if os.path.exists(docs_dir):
        for root, dirs, files in os.walk(docs_dir):
            del files
            rel_path = os.path.relpath(root, docs_dir).replace('\\', '/')
            if rel_path != '.':
                all_dirs.append(rel_path + '/')
    all_dirs = sorted(dict.fromkeys(all_dirs))
    return all_dirs


def _list_doc_files():
    docs_dir = get_docs_root()
    all_files = []
    if os.path.exists(docs_dir):
        for root, dirs, files in os.walk(docs_dir):
            dirs.sort()
            files.sort()
            rel_dir = os.path.relpath(root, docs_dir).replace('\\', '/')
            if rel_dir == '.':
                rel_dir = ''
            for filename in files:
                if not filename.lower().endswith('.md'):
                    continue
                relative_path = os.path.join(rel_dir, filename).replace('\\', '/') if rel_dir else filename
                all_files.append(relative_path)
    return sorted(dict.fromkeys(all_files))


def _get_security_settings():
    settings = _get_settings_map()
    for key, default_value in SECURITY_SETTING_DEFAULTS.items():
        settings.setdefault(key, default_value)
    return settings


def _get_admin_stats_context():
    comment_stats = get_comment_stats()
    user_stats = get_user_stats()
    site_stats = {
        'public_posts': len(get_posts(include_private=False)),
        'total_views': sum(stat.view_count for stat in DocumentViewStat.query.all()),
    }
    comment_trend = db.session.query(func.date(Comment.created_at), func.count(Comment.id)).group_by(func.date(Comment.created_at)).order_by(func.date(Comment.created_at)).limit(14).all()
    notification_trend = db.session.query(func.date(NotificationLog.created_at), func.count(NotificationLog.id)).group_by(func.date(NotificationLog.created_at)).order_by(func.date(NotificationLog.created_at)).limit(14).all()
    return {
        'site_stats': site_stats,
        'comment_stats': comment_stats,
        'user_stats': user_stats,
        'comment_trend': comment_trend,
        'notification_trend': notification_trend,
    }


def _get_admin_base_context():
    settings = _get_settings_map()
    for key, default_value in COVER_SETTING_DEFAULTS.items():
        settings.setdefault(key, default_value)

    comment_filter = (request.args.get('comment_status') or 'all').strip()
    comment_keyword = (request.args.get('comment_q') or '').strip()
    comment_query = Comment.query.order_by(Comment.created_at.desc())
    if comment_filter != 'all':
        comment_query = comment_query.filter_by(status=comment_filter)
    if comment_keyword:
        like_value = f'%{comment_keyword}%'
        comment_query = comment_query.filter(Comment.content.like(like_value))
    comment_page = request.args.get('comment_page', 1, type=int)
    comment_pagination = comment_query.paginate(page=comment_page, per_page=20, error_out=False)

    all_dirs = _list_doc_directories(include_root=False)
    access_mode = settings.get('access_mode', 'open')

    return {
        'settings': settings,
        'all_dirs': all_dirs,
        'access_mode_label': _get_access_mode_label(access_mode),
        'has_global_password': bool(str(settings.get('global_password') or '').strip()),
        'password_rule_count': PasswordAccessRule.query.count(),
        'user_permission_count': PermissionRule.query.count(),
        'recent_comments': _annotate_comment_descendant_counts(comment_pagination.items),
        'comment_pagination': comment_pagination,
        'comment_filter': comment_filter,
        'comment_keyword': comment_keyword,
    }


def _get_admin_access_context():
    settings = _get_settings_map()
    access_mode = settings.get('access_mode', 'open')
    users = (
        User.query
        .filter(User.role != 'admin', User.username != DELETED_USER_USERNAME)
        .order_by(User.role.asc(), User.username.asc())
        .all()
    )
    permissions = (
        PermissionRule.query
        .join(User, PermissionRule.user_id == User.id)
        .order_by(User.username.asc(), PermissionRule.dir_path.asc())
        .all()
    )
    password_rules = (
        PasswordAccessRule.query
        .order_by(PasswordAccessRule.target_type.asc(), PasswordAccessRule.target_path.asc(), PasswordAccessRule.id.asc())
        .all()
    )
    return {
        'settings': settings,
        'access_mode': access_mode,
        'access_mode_label': _get_access_mode_label(access_mode),
        'has_global_password': bool(str(settings.get('global_password') or '').strip()),
        'users': users,
        'permissions': permissions,
        'password_rules': password_rules,
        'all_dirs': _list_doc_directories(include_root=True),
        'all_files': _list_doc_files(),
        'user_permission_count': len(permissions),
        'password_rule_count': len(password_rules),
    }


def _save_user_permission_from_form():
    user_id = (request.form.get('user_id') or '').strip()
    dir_path = (request.form.get('dir_path') or '').strip()

    if not user_id or not dir_path:
        raise ValueError('规则参数不全')

    target_user = db.session.get(User, int(user_id))
    if not target_user or target_user.role == 'admin' or _is_protected_system_user(target_user):
        raise ValueError('只能为普通用户配置权限规则')

    p = PermissionRule.query.filter_by(user_id=target_user.id, dir_path=dir_path).first()
    if not p:
        p = PermissionRule()
        p.user_id = target_user.id
        p.dir_path = dir_path
        db.session.add(p)

    p.can_read = 'can_read' in request.form
    p.can_edit = 'can_edit' in request.form
    p.can_upload = 'can_upload' in request.form
    p.can_delete = 'can_delete' in request.form
    p.can_manage = 'can_manage' in request.form
    db.session.commit()


def _save_password_rule_from_form():
    target_type = (request.form.get('target_type') or 'dir').strip().lower()
    raw_target_path = ''
    if target_type == 'file':
        raw_target_path = request.form.get('file_path') or request.form.get('target_path') or ''
    else:
        raw_target_path = request.form.get('dir_path') or request.form.get('target_path') or ''

    normalized_type, normalized_path = normalize_password_access_target(target_type, raw_target_path)
    if normalized_type == 'dir':
        _, _, absolute_path = resolve_docs_path(normalized_path, allow_directory=True)
        if not os.path.isdir(absolute_path):
            raise ValueError('目标目录不存在')
    else:
        _, _, absolute_path = resolve_docs_path(normalized_path)
        if not os.path.isfile(absolute_path):
            raise ValueError('目标文档不存在')

    existing_rule = PasswordAccessRule.query.filter_by(
        target_type=normalized_type,
        target_path=normalized_path,
    ).first()
    if existing_rule:
        raise ValueError('该访问密码规则已存在')

    rule = PasswordAccessRule()
    rule.target_type = normalized_type
    rule.target_path = normalized_path
    db.session.add(rule)
    db.session.commit()


def _require_admin_role():
    if current_user.role != 'admin':
        abort(403)


def _normalize_optional_email(value):
    normalized = (value or '').strip().lower()
    return normalized or None


def _normalize_user_role(value, default='regular'):
    role = (value or '').strip()
    return role if role in {'admin', 'regular', 'guest'} else default


def _create_user_record(username, password, role='regular', email=None):
    normalized_username = (username or '').strip()
    normalized_email = _normalize_optional_email(email)
    normalized_role = _normalize_user_role(role)

    if not normalized_username or not password:
        raise ValueError('用户名和密码不能为空')
    if User.query.filter_by(username=normalized_username).first():
        raise ValueError('用户名已存在')
    if normalized_email and User.query.filter_by(email=normalized_email).first():
        raise ValueError('邮箱已被使用')

    user = User()
    user.username = normalized_username
    user.email = normalized_email
    user.role = normalized_role
    user.can_comment = True
    user.set_password(password)

    db.session.add(user)
    db.session.commit()
    return user


def _get_or_create_deleted_user():
    deleted_user = User.query.filter_by(username=DELETED_USER_USERNAME).first()
    if deleted_user:
        if deleted_user.nickname != DELETED_USER_NICKNAME:
            deleted_user.nickname = DELETED_USER_NICKNAME
            db.session.commit()
        return deleted_user

    deleted_user = User()
    deleted_user.username = DELETED_USER_USERNAME
    deleted_user.nickname = DELETED_USER_NICKNAME
    deleted_user.role = 'guest'
    deleted_user.can_comment = False
    deleted_user.email_verified = False
    deleted_user.set_password(os.urandom(24).hex())
    db.session.add(deleted_user)
    db.session.commit()
    return deleted_user


def _update_user_record(user, username=None, nickname=None, email=None, role=None, new_password=None):
    if user is None:
        raise ValueError('用户不存在')

    if username is not None:
        normalized_username = username.strip()
        if not normalized_username:
            raise ValueError('用户名不能为空')
        existing_user = User.query.filter(User.username == normalized_username, User.id != user.id).first()
        if existing_user:
            raise ValueError('用户名已存在')
        user.username = normalized_username

    if nickname is not None:
        user.nickname = nickname.strip() or None

    if email is not None:
        normalized_email = _normalize_optional_email(email)
        if normalized_email:
            existing_email = User.query.filter(User.email == normalized_email, User.id != user.id).first()
            if existing_email:
                raise ValueError('邮箱已被使用')
        if user.email != normalized_email:
            user.email_verified = False
        user.email = normalized_email

    if role is not None and user.username != 'admin':
        user.role = _normalize_user_role(role, default=user.role or 'regular')

    if new_password:
        user.set_password(new_password)

    db.session.commit()
    return user


def _delete_user_record(user):
    if user is None:
        raise ValueError('用户不存在')
    if _is_protected_system_user(user):
        raise ValueError('不能删除系统保留账号')

    deleted_user = _get_or_create_deleted_user()
    (
        Comment.query
        .filter_by(user_id=user.id)
        .update({'user_id': deleted_user.id}, synchronize_session=False)
    )
    PermissionRule.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()


def _send_comment_status_mail(comment, approved):
    if not (
        comment
        and comment.user
        and comment.user.email
        and comment.user.email_verified
        and mailer_is_configured()
    ):
        return

    try:
        if approved:
            send_logged_mail(
                'comment_approved',
                comment.user.email,
                '你的评论已通过审核',
                f'你在 {comment.filename} 下的评论已通过审核。',
                '评论审核通过',
                f'你在文章 <strong>{comment.filename}</strong> 下的评论已通过审核。',
                f'<div style="margin-top:16px;padding:16px 18px;border-radius:14px;background:#f0fdf4;color:#166534;line-height:1.8;">{comment.content}</div>',
                action_url=request.url_root.rstrip('/') + url_for('main.docs_doc', filename=comment.filename),
                action_label='查看文章',
                cooldown_seconds=30,
            )
            return

        if comment.status == 'deleted':
            return

        send_logged_mail(
            'comment_rejected',
            comment.user.email,
            '你的评论未通过审核',
            f'你在 {comment.filename} 下的评论未通过审核。',
            '评论未通过审核',
            f'你在文章 <strong>{comment.filename}</strong> 下的评论未通过审核。',
            f'<div style="margin-top:16px;padding:16px 18px;border-radius:14px;background:#fff1f2;color:#9f1239;line-height:1.8;">{comment.content}</div>',
            action_url=request.url_root.rstrip('/') + url_for('main.docs_doc', filename=comment.filename),
            action_label='返回文章',
            cooldown_seconds=30,
        )
    except Exception:
        current_app.logger.exception('发送评论状态邮件失败: comment_id=%s approved=%s target_email=%s', getattr(comment, 'id', None), approved, getattr(getattr(comment, 'user', None), 'email', None))


def _approve_comment_record(comment):
    if comment is None:
        raise ValueError('评论不存在')
    comment.status = 'approved'
    clear_comment_approval_token(comment)
    db.session.commit()
    _send_comment_status_mail(comment, approved=True)
    return comment


def _delete_comment_record(comment):
    if comment is None:
        raise ValueError('评论不存在')
    _send_comment_status_mail(comment, approved=False)
    comment.status = 'deleted'
    clear_comment_approval_token(comment)
    db.session.commit()
    return comment


def _delete_comment_tree_record(comment):
    if comment is None:
        raise ValueError('评论不存在')

    _send_comment_status_mail(comment, approved=False)
    target_ids = get_comment_descendant_ids(comment)
    target_ids.append(comment.id)
    target_ids = list(dict.fromkeys(target_ids))
    (
        Comment.query
        .filter(Comment.id.in_(target_ids))
        .update({'status': 'deleted', 'approval_token': None, 'approval_token_expires_at': None}, synchronize_session=False)
    )
    db.session.commit()
    return len(target_ids)


def _restore_comment_record(comment):
    if comment is None:
        raise ValueError('评论不存在')
    comment.status = 'approved'
    clear_comment_approval_token(comment)
    db.session.commit()
    return comment

def _annotate_comment_descendant_counts(comments):
    return annotate_comment_descendant_counts(comments)


def _hard_delete_comment_record(comment):
    if comment is None:
        raise ValueError('评论不存在')
    if comment.status != 'deleted':
        raise ValueError('请先将评论标记为已删除，再执行彻底删除')

    target_ids = get_comment_descendant_ids(comment)
    target_ids.append(comment.id)
    target_ids = list(dict.fromkeys(target_ids))

    deleted_count = (
        Comment.query
        .filter(Comment.id.in_(target_ids))
        .delete(synchronize_session=False)
    )
    db.session.commit()
    return deleted_count

@admin_bp.route('/images')
@login_required
def image_management():
    _require_admin_role()
    return render_template('image_management.html')

@admin_bp.route('/')
@login_required
def admin_dashboard():
    _require_admin_role()
    return render_template('admin_dashboard.html', **_get_admin_stats_context())


@admin_bp.route('/base')
@login_required
def admin_base():
    _require_admin_role()
    return render_template('admin_base.html', **_get_admin_base_context())


@admin_bp.route('/access')
@login_required
def admin_access():
    _require_admin_role()
    return render_template('admin_access.html', **_get_admin_access_context())


@admin_bp.route('/cover-preview', methods=['POST'])
@login_required
def admin_cover_preview():
    _require_admin_role()

    settings = {
        'random_cover_source_type': (request.form.get('random_cover_source_type') or '').strip(),
        'random_cover_api': (request.form.get('random_cover_api') or '').strip(),
        'random_cover_local_dir': (request.form.get('random_cover_local_dir') or '').strip(),
        'random_cover_pexels_api_key': (request.form.get('random_cover_pexels_api_key') or '').strip(),
        'random_cover_pexels_default_query': (request.form.get('random_cover_pexels_default_query') or '').strip(),
        'random_cover_pexels_orientation': (request.form.get('random_cover_pexels_orientation') or '').strip(),
        'random_cover_pexels_per_page': (request.form.get('random_cover_pexels_per_page') or '').strip(),
        'random_cover_pexels_cache_hours': (request.form.get('random_cover_pexels_cache_hours') or '').strip(),
    }
    sample_query = (request.form.get('sample_query') or '').strip()
    result = preview_cover_source(settings, sample_query=sample_query)
    return jsonify({
        'success': True,
        'preview': result,
    })


@admin_bp.route('/security')
@login_required
def admin_security():
    _require_admin_role()
    return render_template(
        'admin_security.html',
        security_settings=_get_security_settings(),
        rate_limit_status=get_rate_limit_backend_status(),
    )


@admin_bp.route('/security/settings', methods=['POST'])
@login_required
def update_security_settings():
    _require_admin_role()

    checkbox_keys = {
        'security_login_rate_limit_enabled',
        'security_verification_rate_limit_enabled',
        'security_verification_send_rate_limit_enabled',
        'security_ip_whitelist_enabled',
        'security_ip_blacklist_enabled',
        'security_shared_secret_enabled',
    }

    for key in SECURITY_SETTING_DEFAULTS:
        if key in checkbox_keys:
            SystemSetting.set(key, 'true' if request.form.get(key) else 'false')
        else:
            SystemSetting.set(key, (request.form.get(key) or '').strip())

    flash('安全设置已更新')
    return redirect(url_for('admin.admin_security'))


@admin_bp.route('/security/test-nginx', methods=['POST'])
@login_required
def test_nginx_config():
    """测试 Nginx 配置是否正确传递共享密钥"""
    _require_admin_role()
    
    try:
        data = request.get_json()
        header_name = data.get('header_name', 'X-Internal-Secret')
        expected_value = data.get('expected_value', '')
        
        # 检查请求头中是否包含共享密钥
        actual_value = request.headers.get(header_name, '')
        
        if not expected_value:
            return jsonify({
                'success': False,
                'message': '未设置共享密钥，无法测试。'
            })
        
        if actual_value == expected_value:
            return jsonify({
                'success': True,
                'message': f'Nginx 正确传递了请求头 {header_name}，值匹配成功。'
            })
        elif actual_value:
            return jsonify({
                'success': False,
                'message': f'Nginx 传递了请求头 {header_name}，但值不匹配。期望: {expected_value[:10]}..., 实际: {actual_value[:10]}...'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Nginx 未传递请求头 {header_name}。请检查 Nginx 配置中是否添加了 proxy_set_header {header_name} "your-secret"。'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'测试失败: {str(e)}'
        })


@admin_bp.route('/settings', methods=['POST'])
@login_required
def update_settings():
    _require_admin_role()

    # 循环处理所有可能的设置项，如果表单中存在该值，则更新
    settings_to_update = [
        'docs_dir', 'access_mode', 'global_password', 'home_default_type',
        'home_default_target', 'media_storage_type', 'media_max_size_mb',
        's3_endpoint', 's3_bucket', 's3_access_key', 's3_secret_key',
        's3_cdn_domain', 's3_path_prefix', 's3_path_style', 'site_name',
        'site_logo', 'site_tagline', 'home_title', 'home_description', 'footer_html', 'blog_home_count',
        'random_cover_api', 'random_cover_source_type', 'random_cover_local_dir',
        'random_cover_pexels_api_key', 'random_cover_pexels_default_query',
        'random_cover_pexels_orientation', 'random_cover_pexels_per_page',
        'random_cover_pexels_cache_hours',
        'comments_enabled', 'comments_require_approval', 'smtp_host', 'smtp_port',
        'smtp_username', 'smtp_password', 'smtp_use_ssl', 'smtp_sender',
        'default_theme_color', 'default_theme_mode', 'site_mode', 'blog_theme',
        'allow_user_theme_override', 'blog_enabled', 'show_docs_entry_in_blog'
    ]

    for key in settings_to_update:
        if key in request.form:
            value = request.form.get(key)
            # 特殊处理 home_default_target
            if key == 'home_default_type':
                home_type = value
                if home_type == 'dir':
                    target = (request.form.get('home_default_dir') or '').strip()
                    if target == '/': target = ''
                    SystemSetting.set('home_default_target', target)
                elif home_type == 'file':
                    target = (request.form.get('home_default_file') or '').strip()
                    SystemSetting.set('home_default_target', target)
                else:
                    SystemSetting.set('home_default_target', '')
                SystemSetting.set(key, value)

            # 特殊处理 s3_secret_key，为空则不更新
            elif key == 's3_secret_key':
                if value:
                    SystemSetting.set(key, value)
            elif key == 'smtp_password':
                if value:
                    SystemSetting.set(key, value)
            elif key == 'global_password':
                if value or request.form.get('access_mode') != 'password_only':
                    SystemSetting.set(key, value)
            # 特殊处理 checkbox
            elif key in ['s3_path_style', 'smtp_use_ssl', 'comments_enabled', 'comments_require_approval', 'allow_user_theme_override', 'blog_enabled', 'show_docs_entry_in_blog']:
                SystemSetting.set(key, 'true' if request.form.get(key) else 'false')
            # 跳过已经处理过的 target
            elif key not in ['home_default_target']:
                SystemSetting.set(key, value)

    update_all_image_references()
    flash('系统设置已更新')
    return redirect(url_for('admin.admin_base'))

@admin_bp.route('/user/add', methods=['POST'])
@login_required
def admin_add_user():
    _require_admin_role()
    try:
        _create_user_record(
            username=request.form.get('username'),
            password=request.form.get('password'),
            role=request.form.get('role'),
        )
        flash('添加用户成功')
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    _require_admin_role()
    user = _get_or_404(User, user_id)
    try:
        _delete_user_record(user)
        flash('删除用户成功')
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/user/update/<int:user_id>', methods=['POST'])
@login_required
def admin_update_user(user_id):
    _require_admin_role()
    user = _get_or_404(User, user_id)
    if _is_protected_system_user(user):
        flash('系统保留账号不支持在此修改')
        return redirect(url_for('admin.admin_users'))
    try:
        _update_user_record(
            user,
            role=request.form.get('role'),
            new_password=request.form.get('new_password'),
        )
        flash('用户资料已更新')
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/permission/add', methods=['POST'])
@login_required
def admin_add_permission():
    _require_admin_role()
    try:
        _save_user_permission_from_form()
        flash("权限规则已更新")
    except (ValueError, TypeError):
        flash("规则参数不全")
    return redirect(url_for('admin.admin_access'))

@admin_bp.route('/permission/delete/<int:rule_id>', methods=['POST'])
@login_required
def admin_delete_permission(rule_id):
    _require_admin_role()
    p = db.session.get(PermissionRule, rule_id)
    if p:
        db.session.delete(p)
        db.session.commit()
        flash("权限规则已删除")
    return redirect(url_for('admin.admin_access'))


@admin_bp.route('/access/user-rules', methods=['POST'])
@login_required
def admin_access_save_user_rule():
    _require_admin_role()
    try:
        _save_user_permission_from_form()
        flash('用户目录权限规则已更新')
    except ValueError as exc:
        flash(str(exc))
    except (TypeError, OSError):
        flash('用户目录权限规则保存失败')
    return redirect(url_for('admin.admin_access'))


@admin_bp.route('/access/user-rules/<int:rule_id>/delete', methods=['POST'])
@login_required
def admin_access_delete_user_rule(rule_id):
    _require_admin_role()
    rule = db.session.get(PermissionRule, rule_id)
    if rule:
        db.session.delete(rule)
        db.session.commit()
        flash('用户目录权限规则已删除')
    return redirect(url_for('admin.admin_access'))


@admin_bp.route('/access/password-rules', methods=['POST'])
@login_required
def admin_access_add_password_rule():
    _require_admin_role()
    try:
        _save_password_rule_from_form()
        flash('访问密码权限规则已添加')
    except ValueError as exc:
        flash(str(exc))
    except (TypeError, OSError):
        flash('访问密码权限规则保存失败')
    return redirect(url_for('admin.admin_access'))


@admin_bp.route('/access/password-rules/<int:rule_id>/delete', methods=['POST'])
@login_required
def admin_access_delete_password_rule(rule_id):
    _require_admin_role()
    rule = db.session.get(PasswordAccessRule, rule_id)
    if rule:
        db.session.delete(rule)
        db.session.commit()
        flash('访问密码权限规则已删除')
    return redirect(url_for('admin.admin_access'))


@admin_bp.route('/comment/approve/<int:comment_id>', methods=['POST'])
@login_required
def admin_approve_comment(comment_id):
    _require_admin_role()
    comment = db.session.get(Comment, comment_id)
    if comment:
        _approve_comment_record(comment)
        flash('评论已通过审核')
    return redirect(url_for('admin.admin_base'))


@admin_bp.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
def admin_delete_comment(comment_id):
    _require_admin_role()
    comment = db.session.get(Comment, comment_id)
    if comment:
        delete_mode = (request.form.get('delete_mode') or 'single').strip().lower()
        if delete_mode == 'tree':
            deleted_count = _delete_comment_tree_record(comment)
            flash(f'评论树已删除（共标记 {deleted_count} 条记录）')
        else:
            _delete_comment_record(comment)
            flash('评论已删除')
    return redirect(url_for('admin.admin_base'))


@admin_bp.route('/comment/restore/<int:comment_id>', methods=['POST'])
@login_required
def admin_restore_comment(comment_id):
    _require_admin_role()
    comment = db.session.get(Comment, comment_id)
    if comment:
        _restore_comment_record(comment)
        flash('评论已恢复')
    return redirect(url_for('admin.admin_base'))


@admin_bp.route('/comment/hard-delete/<int:comment_id>', methods=['POST'])
@login_required
def admin_hard_delete_comment(comment_id):
    _require_admin_role()
    comment = db.session.get(Comment, comment_id)
    if comment:
        try:
            deleted_count = _hard_delete_comment_record(comment)
            flash(f'评论已彻底删除（共移除 {deleted_count} 条记录）')
        except ValueError as exc:
            flash(str(exc))
    return redirect(url_for('admin.admin_base'))


@admin_bp.route('/user/verify/<int:user_id>', methods=['POST'])
@login_required
def admin_verify_user_email(user_id):
    _require_admin_role()
    user = db.session.get(User, user_id)
    if user:
        if _is_protected_system_user(user):
            flash('系统保留账号不支持此操作')
            return redirect(url_for('admin.admin_users'))
        user.email_verified = True
        db.session.commit()
        flash('用户邮箱已标记为已验证')
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/user/<int:user_id>')
@login_required
def admin_user_detail(user_id):
    _require_admin_role()
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/user/detail-update/<int:user_id>', methods=['POST'])
@login_required
def admin_update_user_detail(user_id):
    _require_admin_role()
    user = _get_or_404(User, user_id)
    if _is_protected_system_user(user):
        flash('系统保留账号不支持在此修改')
        return redirect(url_for('admin.admin_users'))
    try:
        _update_user_record(
            user,
            username=request.form.get('username') or '',
            nickname=request.form.get('nickname') or '',
            email=request.form.get('email') or '',
            role=request.form.get('role'),
        )
        flash('用户资料已更新')
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/notifications')
@login_required
def notification_logs():
    _require_admin_role()
    page = request.args.get('page', 1, type=int)
    event_type = (request.args.get('event_type') or 'all').strip()
    keyword = (request.args.get('q') or '').strip()
    query = NotificationLog.query.order_by(NotificationLog.created_at.desc())
    if event_type != 'all':
        query = query.filter_by(event_type=event_type)
    if keyword:
        like_value = f'%{keyword}%'
        query = query.filter(NotificationLog.target.like(like_value))
    logs = query.paginate(page=page, per_page=30, error_out=False)
    return render_template('notification_logs.html', logs=logs, event_type=event_type, keyword=keyword)


@admin_bp.route('/users')
@login_required
def admin_users():
    _require_admin_role()
    
    page = request.args.get('page', 1, type=int)
    keyword = (request.args.get('q') or '').strip()
    role_filter = (request.args.get('role') or 'all').strip()
    verified_filter = (request.args.get('verified') or 'all').strip()
    can_comment_filter = (request.args.get('can_comment') or 'all').strip()
    
    query = User.query.filter(User.username != DELETED_USER_USERNAME)
    
    if keyword:
        like_value = f'%{keyword}%'
        query = query.filter((User.username.like(like_value)) | (User.email.like(like_value)))
    
    if role_filter != 'all':
        query = query.filter_by(role=role_filter)
    
    if verified_filter == 'yes':
        query = query.filter_by(email_verified=True)
    elif verified_filter == 'no':
        query = query.filter_by(email_verified=False)
    
    if can_comment_filter == 'yes':
        query = query.filter_by(can_comment=True)
    elif can_comment_filter == 'no':
        query = query.filter_by(can_comment=False)
    
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    users = pagination.items
    
    # 为每个用户添加评论数统计
    for user in users:
        user.comment_count = Comment.query.filter_by(user_id=user.id).count()
    
    return render_template(
        'admin_users.html',
        users=users,
        pagination=pagination,
        keyword=keyword,
        role_filter=role_filter,
        verified_filter=verified_filter,
        can_comment_filter=can_comment_filter
    )


@admin_bp.route('/users/add', methods=['POST'])
@login_required
def admin_add_user_page():
    _require_admin_role()
    try:
        _create_user_record(
            username=request.form.get('username'),
            password=request.form.get('password'),
            role=request.form.get('role') or 'regular',
            email=request.form.get('email'),
        )
        flash('用户添加成功')
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/users/<int:user_id>')
@login_required
def admin_user_detail_page(user_id):
    _require_admin_role()
    
    user = _get_or_404(User, user_id)
    if user.username == DELETED_USER_USERNAME:
        abort(404)
    comments = Comment.query.filter_by(user_id=user.id).order_by(Comment.created_at.desc()).all()
    _annotate_comment_descendant_counts(comments)
    
    return render_template('admin_user_detail_page.html', user=user, comments=comments)


@admin_bp.route('/users/<int:user_id>/update', methods=['POST'])
@login_required
def admin_update_user_info(user_id):
    _require_admin_role()
    user = _get_or_404(User, user_id)
    if _is_protected_system_user(user):
        flash('系统保留账号不支持在此修改')
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    try:
        _update_user_record(
            user,
            username=request.form.get('username') or '',
            nickname=request.form.get('nickname') or '',
            email=request.form.get('email'),
            role=request.form.get('role'),
            new_password=request.form.get('new_password'),
        )
        flash('用户信息已更新')
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/verify-email', methods=['POST'])
@login_required
def admin_verify_user_email_page(user_id):
    _require_admin_role()
    user = _get_or_404(User, user_id)
    if _is_protected_system_user(user):
        flash('系统保留账号不支持此操作')
        return redirect(url_for('admin.admin_users'))
    user.email_verified = True
    db.session.commit()
    
    flash('用户邮箱已标记为已验证')
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user_page(user_id):
    _require_admin_role()
    user = _get_or_404(User, user_id)
    try:
        _delete_user_record(user)
        flash('用户已删除')
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/users/<int:user_id>/toggle-comment', methods=['POST'])
@login_required
def admin_toggle_comment_permission(user_id):
    _require_admin_role()
    user = _get_or_404(User, user_id)
    if _is_protected_system_user(user):
        flash('系统保留账号不支持此操作')
        return redirect(url_for('admin.admin_users'))
    user.can_comment = 'can_comment' in request.form
    db.session.commit()
    
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/comments/<int:comment_id>/approve', methods=['POST'])
@login_required
def admin_approve_comment_page(comment_id):
    _require_admin_role()
    comment = _get_or_404(Comment, comment_id)
    _approve_comment_record(comment)
    flash('评论已通过审核')
    user_id = request.form.get('user_id')
    if user_id:
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    return redirect(url_for('admin.admin_base'))


@admin_bp.route('/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def admin_delete_comment_page(comment_id):
    _require_admin_role()
    comment = _get_or_404(Comment, comment_id)
    delete_mode = (request.form.get('delete_mode') or 'single').strip().lower()
    if delete_mode == 'tree':
        deleted_count = _delete_comment_tree_record(comment)
        flash(f'评论树已删除（共标记 {deleted_count} 条记录）')
    else:
        _delete_comment_record(comment)
        flash('评论已删除')
    user_id = request.form.get('user_id')
    if user_id:
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    return redirect(url_for('admin.admin_base'))


@admin_bp.route('/comments/<int:comment_id>/restore', methods=['POST'])
@login_required
def admin_restore_comment_page(comment_id):
    _require_admin_role()
    comment = _get_or_404(Comment, comment_id)
    _restore_comment_record(comment)
    flash('评论已恢复')
    user_id = request.form.get('user_id')
    if user_id:
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    return redirect(url_for('admin.admin_base'))


@admin_bp.route('/comments/<int:comment_id>/hard-delete', methods=['POST'])
@login_required
def admin_hard_delete_comment_page(comment_id):
    _require_admin_role()
    comment = _get_or_404(Comment, comment_id)
    user_id = request.form.get('user_id')
    try:
        deleted_count = _hard_delete_comment_record(comment)
        flash(f'评论已彻底删除（共移除 {deleted_count} 条记录）')
    except ValueError as exc:
        flash(str(exc))
    if user_id:
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    return redirect(url_for('admin.admin_base'))


# ============================================================================
# 备份管理路由
# ============================================================================

@admin_bp.route('/backup/config')
@login_required
def admin_backup_config():
    """备份配置页面"""
    _require_admin_role()
    
    from models import BackupConfig
    
    # 获取当前配置
    config = BackupConfig.query.first()
    
    return render_template('admin_backup_config.html', config=config)


@admin_bp.route('/backup/config', methods=['POST'])
@login_required
def admin_backup_config_save():
    """保存备份配置"""
    _require_admin_role()
    
    from services.backup_config import BackupConfigManager
    from models import BackupConfig
    
    try:
        # 获取或创建配置
        config = BackupConfig.query.first()
        if not config:
            config = BackupConfig()
            db.session.add(config)
        
        # 基本配置
        storage_types = request.form.getlist('storage_types')
        if not storage_types:
            flash('请至少选择一个存储方式')
            return redirect(url_for('admin.admin_backup_config'))
        
        # 将存储类型列表转换为JSON字符串存储
        import json
        config.storage_type = json.dumps(storage_types)
        config.enabled = request.form.get('auto_backup_enabled') == 'on'
        
        # 解析备份计划
        schedule_type = request.form.get('backup_schedule_type', 'daily')
        
        if schedule_type == 'hourly':
            # 每N小时
            interval = int(request.form.get('hourly_interval', 1))
            if interval == 1:
                cron_expr = '0 * * * *'  # 每小时
            else:
                cron_expr = f'0 */{interval} * * *'  # 每N小时
            config.schedule_type = 'hourly'
            config.schedule_value = cron_expr
            config.schedule_metadata = None
            
        elif schedule_type == 'daily_interval':
            # 每N天（需要存储间隔信息）
            days = int(request.form.get('daily_interval_days', 1))
            hour = int(request.form.get('daily_interval_hour', 2))
            # 使用每天的cron，但在调度器中检查间隔
            cron_expr = f'0 {hour} * * *'
            config.schedule_type = 'daily_interval'
            config.schedule_value = cron_expr
            # 存储间隔信息到metadata
            config.schedule_metadata = json.dumps({'interval': days, 'last_run': None})
            
        elif schedule_type == 'daily':
            # 每天的第N个小时
            hour = int(request.form.get('daily_hour', 2))
            cron_expr = f'0 {hour} * * *'
            config.schedule_type = 'daily'
            config.schedule_value = cron_expr
            config.schedule_metadata = None
            
        elif schedule_type == 'weekly_interval':
            # 每N周（需要存储间隔信息）
            weeks = int(request.form.get('weekly_interval_weeks', 1))
            day = int(request.form.get('weekly_interval_day', 0))
            hour = int(request.form.get('weekly_interval_hour', 2))
            # 使用每周的cron，但在调度器中检查间隔
            cron_expr = f'0 {hour} * * {day}'
            config.schedule_type = 'weekly_interval'
            config.schedule_value = cron_expr
            # 存储间隔信息到metadata
            config.schedule_metadata = json.dumps({'interval': weeks, 'last_run': None})
            
        elif schedule_type == 'weekly':
            # 每周的第N天
            day = int(request.form.get('weekly_day', 0))
            hour = int(request.form.get('weekly_hour', 2))
            cron_expr = f'0 {hour} * * {day}'
            config.schedule_type = 'weekly'
            config.schedule_value = cron_expr
            config.schedule_metadata = None
            
        elif schedule_type == 'monthly':
            # 每月的第N天
            day = int(request.form.get('monthly_day', 1))
            hour = int(request.form.get('monthly_hour', 2))
            cron_expr = f'0 {hour} {day} * *'
            config.schedule_type = 'monthly'
            config.schedule_value = cron_expr
            config.schedule_metadata = None
            
        elif schedule_type == 'custom':
            # 自定义 cron 表达式
            cron_expr = request.form.get('custom_cron', '0 2 * * *').strip()
            if not cron_expr:
                flash('自定义 Cron 表达式不能为空')
                return redirect(url_for('admin.admin_backup_config'))
            config.schedule_type = 'cron'
            config.schedule_value = cron_expr
            config.schedule_metadata = None
        else:
            # 默认每天凌晨2点
            config.schedule_type = 'daily'
            config.schedule_value = '0 2 * * *'
            config.schedule_metadata = None
        
        config.backup_mode = request.form.get('backup_mode', 'full')
        config.retention_count = int(request.form.get('retention_count', 10))
        
        # 加密配置
        config.encryption_enabled = request.form.get('encryption_enabled') == 'on'
        encryption_password = request.form.get('encryption_password')
        if encryption_password:
            # 使用应用密钥加密存储密码
            from cryptography.fernet import Fernet
            import base64
            import hashlib
            
            # 从Flask secret_key派生加密密钥
            key_material = hashlib.sha256(current_app.secret_key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(key_material)
            fernet = Fernet(fernet_key)
            
            # 加密密码并存储
            encrypted_password = fernet.encrypt(encryption_password.encode())
            config.encryption_key_hash = encrypted_password.decode('utf-8')  # 重用这个字段存储加密后的密码
        
        # 通知配置
        config.notification_enabled = request.form.get('notification_enabled') == 'on'
        config.notification_email = request.form.get('notification_email')
        
        # 根据存储类型保存相应配置（无论是否勾选都保存，方便用户预先配置）
        # FTP 配置
        config.ftp_host = request.form.get('ftp_host')
        config.ftp_port = int(request.form.get('ftp_port', 21))
        config.ftp_username = request.form.get('ftp_username')
        config.ftp_password = request.form.get('ftp_password')
        config.ftp_path = request.form.get('ftp_directory', '/')
        
        # Email 配置
        config.email_recipient = request.form.get('email_recipient')
        
        # S3 配置
        config.s3_bucket = request.form.get('s3_bucket')
        config.s3_access_key = request.form.get('s3_access_key')
        config.s3_secret_key = request.form.get('s3_secret_key')
        config.s3_region = request.form.get('s3_region', 'us-east-1')
        config.s3_endpoint = request.form.get('s3_endpoint')
        config.s3_path_prefix = 'backups/'  # 固定使用 backups/ 作为路径前缀
        
        db.session.commit()
        
        # 从数据库重新读取配置，生成详细的保存摘要
        config = BackupConfig.query.first()
        
        # 解析存储类型
        storage_types = json.loads(config.storage_type) if config.storage_type else []
        storage_names = {
            'ftp': 'FTP服务器',
            'email': '邮件附件',
            's3': 'S3存储'
        }
        storage_list = '、'.join([storage_names.get(t, t) for t in storage_types])
        
        # 解析调度计划
        def parse_cron_to_chinese(cron_expr):
            """将cron表达式转换为中文描述"""
            if not cron_expr:
                return '未设置'
            
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                return cron_expr
            
            minute, hour, day, month, weekday = parts
            
            # 常见模式
            if cron_expr == '0 * * * *':
                return '每小时整点'
            if cron_expr.startswith('0 */'):
                interval = cron_expr.split()[1].split('/')[1]
                return f'每{interval}小时'
            if day == '*' and month == '*' and weekday == '*':
                return f'每天{hour}:{minute.zfill(2)}'
            if day == '*' and month == '*' and weekday != '*':
                week_names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
                return f'每{week_names[int(weekday)]}{hour}:{minute.zfill(2)}'
            if month == '*' and weekday == '*':
                return f'每月{day}号{hour}:{minute.zfill(2)}'
            
            return cron_expr
        
        schedule_desc = parse_cron_to_chinese(config.schedule_value)
        
        # 构建详细消息
        summary_parts = []
        summary_parts.append(f"✓ 备份配置已保存")
        summary_parts.append(f"")
        summary_parts.append(f"【存储方式】{storage_list}")
        summary_parts.append(f"【自动备份】{'已启用' if config.enabled else '已禁用'}")
        if config.enabled:
            summary_parts.append(f"【备份计划】{schedule_desc}")
        summary_parts.append(f"【备份模式】{'完整备份' if config.backup_mode == 'full' else '增量备份'}")
        summary_parts.append(f"【保留数量】{config.retention_count}个")
        summary_parts.append(f"【备份加密】{'已启用' if config.encryption_enabled else '未启用'}")
        summary_parts.append(f"【邮件通知】{'已启用' if config.notification_enabled else '未启用'}")
        if config.notification_enabled and config.notification_email:
            summary_parts.append(f"【通知邮箱】{config.notification_email}")
        
        flash('\n'.join(summary_parts))
        
        # 更新调度器配置
        try:
            scheduler = current_app.config.get('BACKUP_SCHEDULER')
            if scheduler:
                scheduler.update_schedule(config)
                print(f"[Admin] 已更新调度器配置: {config.schedule_type} - {config.schedule_value}")
            else:
                print("[Admin] 警告：调度器未初始化")
        except Exception as scheduler_error:
            print(f"[Admin] 更新调度器失败: {str(scheduler_error)}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        db.session.rollback()
        flash(f'保存配置失败: {str(e)}')
    
    return redirect(url_for('admin.admin_backup_config'))


@admin_bp.route('/backup/config/test', methods=['POST'])
@login_required
def admin_backup_config_test():
    """测试备份配置 - 执行完整备份流程测试"""
    _require_admin_role()
    
    from services.backup_config import BackupConfigManager
    from services.backup_engine import BackupEngine
    from services.backup_notification import NotificationService
    from models import BackupConfig
    from flask import jsonify
    
    try:
        # 从表单数据创建临时配置对象用于测试
        storage_types = request.form.getlist('storage_types')
        
        if not storage_types:
            return jsonify({'success': False, 'message': '请至少选择一个存储方式'}), 400
        
        # 创建临时配置对象（不保存到数据库）
        import json
        temp_config = BackupConfig()
        temp_config.storage_type = json.dumps(storage_types)
        temp_config.enabled = True
        
        # 解析备份计划
        backup_schedule = request.form.get('backup_schedule', '0 2 * * *')
        if backup_schedule == '0 * * * *':
            temp_config.schedule_type = 'hourly'
            temp_config.schedule_value = backup_schedule
        elif backup_schedule == '0 2 * * *':
            temp_config.schedule_type = 'daily'
            temp_config.schedule_value = backup_schedule
        elif backup_schedule == '0 2 * * 0':
            temp_config.schedule_type = 'weekly'
            temp_config.schedule_value = backup_schedule
        else:
            temp_config.schedule_type = 'cron'
            temp_config.schedule_value = backup_schedule
        
        temp_config.backup_mode = request.form.get('backup_mode', 'full')
        temp_config.retention_count = int(request.form.get('retention_count', 10))
        
        # 加密配置
        temp_config.encryption_enabled = request.form.get('encryption_enabled') == 'on'
        encryption_password = request.form.get('encryption_password')
        if temp_config.encryption_enabled:
            if encryption_password:
                # 用户在测试时输入了新密码
                from cryptography.fernet import Fernet
                import base64
                import hashlib
                
                # 从Flask secret_key派生加密密钥
                key_material = hashlib.sha256(current_app.secret_key.encode()).digest()
                fernet_key = base64.urlsafe_b64encode(key_material)
                fernet = Fernet(fernet_key)
                
                # 加密密码并存储
                encrypted_password = fernet.encrypt(encryption_password.encode())
                temp_config.encryption_key_hash = encrypted_password.decode('utf-8')
                temp_config._test_encryption_password = encryption_password
            else:
                # 用户没有输入密码，尝试从数据库读取已保存的加密密码
                saved_config = BackupConfig.query.first()
                if saved_config and saved_config.encryption_key_hash:
                    try:
                        from cryptography.fernet import Fernet
                        import base64
                        import hashlib
                        
                        # 从Flask secret_key派生加密密钥
                        key_material = hashlib.sha256(current_app.secret_key.encode()).digest()
                        fernet_key = base64.urlsafe_b64encode(key_material)
                        fernet = Fernet(fernet_key)
                        
                        # 解密已保存的密码
                        decrypted_password = fernet.decrypt(saved_config.encryption_key_hash.encode()).decode('utf-8')
                        temp_config.encryption_key_hash = saved_config.encryption_key_hash
                        temp_config._test_encryption_password = decrypted_password
                    except Exception as e:
                        return jsonify({'success': False, 'message': f'无法读取已保存的加密密码，请重新输入密码: {str(e)}'}), 400
                else:
                    return jsonify({'success': False, 'message': '启用加密时必须提供加密密码'}), 400
        else:
            temp_config.encryption_key_hash = None
            temp_config._test_encryption_password = None
        
        # 通知配置
        temp_config.notification_enabled = request.form.get('notification_enabled') == 'on'
        temp_config.notification_email = request.form.get('notification_email')
        
        # 设置所有存储方式的配置（无论是否勾选）
        temp_config.ftp_host = request.form.get('ftp_host')
        temp_config.ftp_port = int(request.form.get('ftp_port', 21))
        temp_config.ftp_username = request.form.get('ftp_username')
        temp_config.ftp_password = request.form.get('ftp_password')
        temp_config.ftp_path = request.form.get('ftp_directory', '/')
        
        temp_config.email_recipient = request.form.get('email_recipient')
        
        temp_config.s3_bucket = request.form.get('s3_bucket')
        temp_config.s3_region = request.form.get('s3_region', 'us-east-1')
        temp_config.s3_access_key = request.form.get('s3_access_key')
        temp_config.s3_secret_key = request.form.get('s3_secret_key')
        temp_config.s3_endpoint = request.form.get('s3_endpoint')
        temp_config.s3_path_prefix = 'backups/'
        
        # 验证已勾选的存储方式配置是否完整
        validation_errors = []
        if 'ftp' in storage_types and not temp_config.ftp_host:
            validation_errors.append('FTP: 请填写主机地址')
        if 'email' in storage_types and not temp_config.email_recipient:
            validation_errors.append('邮件: 请填写接收邮箱')
        if 's3' in storage_types and not temp_config.s3_bucket:
            validation_errors.append('S3: 请填写存储桶名称')
        
        if validation_errors:
            return jsonify({'success': False, 'message': '配置不完整:\n' + '\n'.join(validation_errors)}), 400
        
        # 验证配置
        is_valid, error_msg = BackupConfigManager.validate_config(temp_config)
        if not is_valid:
            return jsonify({'success': False, 'message': f'配置验证失败: {error_msg}'}), 400
        
        # 临时保存配置到数据库（用于备份引擎）
        original_config = BackupConfig.query.first()
        original_config_data = None
        
        if original_config:
            # 备份原始配置
            original_config_data = {
                'enabled': original_config.enabled,
                'storage_type': original_config.storage_type,
                'schedule_type': original_config.schedule_type,
                'schedule_value': original_config.schedule_value,
                'retention_count': original_config.retention_count,
                'backup_mode': original_config.backup_mode,
                'encryption_enabled': original_config.encryption_enabled,
                'encryption_key_hash': original_config.encryption_key_hash,
                'ftp_host': original_config.ftp_host,
                'ftp_port': original_config.ftp_port,
                'ftp_username': original_config.ftp_username,
                'ftp_password': original_config.ftp_password,
                'ftp_path': original_config.ftp_path,
                'email_recipient': original_config.email_recipient,
                's3_endpoint': original_config.s3_endpoint,
                's3_bucket': original_config.s3_bucket,
                's3_access_key': original_config.s3_access_key,
                's3_secret_key': original_config.s3_secret_key,
                's3_path_prefix': original_config.s3_path_prefix,
                's3_region': original_config.s3_region,
                'notification_enabled': original_config.notification_enabled,
                'notification_email': original_config.notification_email,
            }
            
            # 临时替换为测试配置
            original_config.enabled = temp_config.enabled
            original_config.storage_type = temp_config.storage_type
            original_config.schedule_type = temp_config.schedule_type
            original_config.schedule_value = temp_config.schedule_value
            original_config.retention_count = temp_config.retention_count
            original_config.backup_mode = temp_config.backup_mode
            original_config.encryption_enabled = temp_config.encryption_enabled
            original_config.encryption_key_hash = temp_config.encryption_key_hash
            # 临时存储测试密码
            if hasattr(temp_config, '_test_encryption_password'):
                original_config._test_encryption_password = temp_config._test_encryption_password
            original_config.ftp_host = temp_config.ftp_host
            original_config.ftp_port = temp_config.ftp_port
            original_config.ftp_username = temp_config.ftp_username
            original_config.ftp_password = temp_config.ftp_password
            original_config.ftp_path = temp_config.ftp_path
            original_config.email_recipient = temp_config.email_recipient
            original_config.s3_endpoint = temp_config.s3_endpoint
            original_config.s3_bucket = temp_config.s3_bucket
            original_config.s3_access_key = temp_config.s3_access_key
            original_config.s3_secret_key = temp_config.s3_secret_key
            original_config.s3_path_prefix = temp_config.s3_path_prefix
            original_config.s3_region = temp_config.s3_region
            original_config.notification_enabled = temp_config.notification_enabled
            original_config.notification_email = temp_config.notification_email
            db.session.commit()
        else:
            # 创建新配置
            db.session.add(temp_config)
            db.session.commit()
        
        try:
            # 执行完整备份流程测试
            engine = BackupEngine(app=current_app)
            backup_job = engine.execute_backup(trigger_type='manual')
            
            # 如果启用了通知，发送测试通知
            if temp_config.notification_enabled and temp_config.notification_email:
                try:
                    notification_service = NotificationService()
                    notification_service.send_backup_success_notification(backup_job, temp_config)
                except Exception as notif_error:
                    # 通知失败不影响备份测试结果
                    print(f"警告: 发送测试通知失败: {str(notif_error)}")
            
            # 构建成功消息
            file_size_mb = backup_job.file_size_bytes / (1024 * 1024) if backup_job.file_size_bytes else 0
            
            # 构建存储方式列表
            storage_names = {
                'ftp': 'FTP',
                'email': '邮件',
                's3': 'S3'
            }
            storage_list = ', '.join([storage_names.get(st, st.upper()) for st in storage_types])
            
            message_parts = [
                f"✓ 备份测试成功完成",
                f"",
                f"备份文件: {backup_job.filename}",
                f"文件大小: {file_size_mb:.2f} MB",
                f"存储方式: {storage_list}",
                f"备份模式: {'完整备份' if backup_job.backup_mode == 'full' else '增量备份'}",
            ]
            
            if backup_job.is_encrypted:
                message_parts.append(f"加密状态: 已加密 (AES-256)")
            
            message_parts.extend([
                f"",
                f"备份内容统计:",
                f"- 数据库: {backup_job.db_size_bytes / (1024 * 1024):.2f} MB",
                f"- 上传文件: {backup_job.uploads_count} 个文件, {backup_job.uploads_size_bytes / (1024 * 1024):.2f} MB",
                f"- 文档文件: {backup_job.docs_count} 个文件, {backup_job.docs_size_bytes / (1024 * 1024):.2f} MB",
            ])
            
            if temp_config.notification_enabled and temp_config.notification_email:
                message_parts.extend([
                    f"",
                    f"✓ 测试通知已发送到: {temp_config.notification_email}"
                ])
            
            message_parts.extend([
                f"",
                f"执行时长: {backup_job.duration_seconds} 秒",
                f"",
                f"所有配置项均已测试通过，可以正常使用。"
            ])
            
            success_message = "\n".join(message_parts)
            
            return jsonify({'success': True, 'message': success_message})
            
        finally:
            # 恢复原始配置
            if original_config_data:
                original_config.enabled = original_config_data['enabled']
                original_config.storage_type = original_config_data['storage_type']
                original_config.schedule_type = original_config_data['schedule_type']
                original_config.schedule_value = original_config_data['schedule_value']
                original_config.retention_count = original_config_data['retention_count']
                original_config.backup_mode = original_config_data['backup_mode']
                original_config.encryption_enabled = original_config_data['encryption_enabled']
                original_config.encryption_key_hash = original_config_data['encryption_key_hash']
                # 清理测试密码
                if hasattr(original_config, '_test_encryption_password'):
                    delattr(original_config, '_test_encryption_password')
                original_config.ftp_host = original_config_data['ftp_host']
                original_config.ftp_port = original_config_data['ftp_port']
                original_config.ftp_username = original_config_data['ftp_username']
                original_config.ftp_password = original_config_data['ftp_password']
                original_config.ftp_path = original_config_data['ftp_path']
                original_config.email_recipient = original_config_data['email_recipient']
                original_config.s3_endpoint = original_config_data['s3_endpoint']
                original_config.s3_bucket = original_config_data['s3_bucket']
                original_config.s3_access_key = original_config_data['s3_access_key']
                original_config.s3_secret_key = original_config_data['s3_secret_key']
                original_config.s3_path_prefix = original_config_data['s3_path_prefix']
                original_config.s3_region = original_config_data['s3_region']
                original_config.notification_enabled = original_config_data['notification_enabled']
                original_config.notification_email = original_config_data['notification_email']
                db.session.commit()
            elif original_config is None:
                # 删除测试创建的配置
                db.session.delete(temp_config)
                db.session.commit()
        
    except Exception as e:
        # 确保恢复原始配置
        if 'original_config_data' in locals() and original_config_data:
            try:
                original_config.enabled = original_config_data['enabled']
                original_config.storage_type = original_config_data['storage_type']
                original_config.schedule_type = original_config_data['schedule_type']
                original_config.schedule_value = original_config_data['schedule_value']
                original_config.retention_count = original_config_data['retention_count']
                original_config.backup_mode = original_config_data['backup_mode']
                original_config.encryption_enabled = original_config_data['encryption_enabled']
                original_config.encryption_key_hash = original_config_data['encryption_key_hash']
                # 清理测试密码
                if hasattr(original_config, '_test_encryption_password'):
                    delattr(original_config, '_test_encryption_password')
                original_config.ftp_host = original_config_data['ftp_host']
                original_config.ftp_port = original_config_data['ftp_port']
                original_config.ftp_username = original_config_data['ftp_username']
                original_config.ftp_password = original_config_data['ftp_password']
                original_config.ftp_path = original_config_data['ftp_path']
                original_config.email_recipient = original_config_data['email_recipient']
                original_config.s3_endpoint = original_config_data['s3_endpoint']
                original_config.s3_bucket = original_config_data['s3_bucket']
                original_config.s3_access_key = original_config_data['s3_access_key']
                original_config.s3_secret_key = original_config_data['s3_secret_key']
                original_config.s3_path_prefix = original_config_data['s3_path_prefix']
                original_config.s3_region = original_config_data['s3_region']
                original_config.notification_enabled = original_config_data['notification_enabled']
                original_config.notification_email = original_config_data['notification_email']
                db.session.commit()
            except:
                pass
        
        return jsonify({'success': False, 'message': f'测试失败: {str(e)}'}), 500



@admin_bp.route('/backup/config/export')
@login_required
def admin_backup_config_export():
    """导出备份配置"""
    _require_admin_role()
    
    from services.backup_config import BackupConfigManager
    import json
    from flask import Response
    
    try:
        manager = BackupConfigManager()
        config_data = manager.export_config()
        
        return Response(
            json.dumps(config_data, indent=2, ensure_ascii=False),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment;filename=backup_config.json'}
        )
    except Exception as e:
        flash(f'导出配置失败: {str(e)}')
        return redirect(url_for('admin.admin_backup_config'))


@admin_bp.route('/backup/config/import', methods=['POST'])
@login_required
def admin_backup_config_import():
    """导入备份配置"""
    _require_admin_role()
    
    from services.backup_config import BackupConfigManager
    import json
    
    try:
        if 'config_file' not in request.files:
            flash('请选择配置文件')
            return redirect(url_for('admin.admin_backup_config'))
        
        file = request.files['config_file']
        if file.filename == '':
            flash('请选择配置文件')
            return redirect(url_for('admin.admin_backup_config'))
        
        config_data = json.load(file)
        
        manager = BackupConfigManager()
        manager.import_config(config_data)
        
        flash('配置导入成功')
    except Exception as e:
        flash(f'导入配置失败: {str(e)}')
    
    return redirect(url_for('admin.admin_backup_config'))


@admin_bp.route('/backup/config/decrypt-password', methods=['POST'])
@login_required
def admin_backup_decrypt_password():
    """
    解密备份加密密码
    需要验证管理员密码
    """
    _require_admin_role()
    
    try:
        # 获取管理员密码
        admin_password = request.form.get('admin_password', '').strip()
        if not admin_password:
            return jsonify({'success': False, 'message': '请输入管理员密码'}), 400
        
        # 验证管理员密码
        from werkzeug.security import check_password_hash
        if not check_password_hash(current_user.password_hash, admin_password):
            return jsonify({'success': False, 'message': '管理员密码错误'}), 403
        
        # 获取备份配置
        config = BackupConfig.query.first()
        if not config or not config.encryption_key_hash:
            return jsonify({'success': False, 'message': '未配置加密密码'}), 404
        
        # 解密密码
        from cryptography.fernet import Fernet
        import base64
        import hashlib
        
        # 从Flask secret_key派生加密密钥
        key_material = hashlib.sha256(current_app.secret_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_material)
        fernet = Fernet(fernet_key)
        
        # 解密
        decrypted_password = fernet.decrypt(config.encryption_key_hash.encode()).decode('utf-8')
        
        return jsonify({
            'success': True,
            'password': decrypted_password
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'解密失败: {str(e)}'}), 500


@admin_bp.route('/backup/history')
@login_required
def admin_backup_history():
    """备份历史页面"""
    _require_admin_role()
    
    from models import BackupJob
    
    # 获取筛选参数
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 构建查询
    query = BackupJob.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    # 分页
    pagination = query.order_by(BackupJob.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template(
        'admin_backup_history.html',
        jobs=pagination.items,
        pagination=pagination,
        status_filter=status_filter
    )


@admin_bp.route('/backup/trigger', methods=['POST'])
@login_required
def admin_backup_trigger():
    """手动触发备份"""
    _require_admin_role()
    
    from services.backup_engine import BackupEngine
    
    try:
        # 直接使用备份引擎执行手动备份
        engine = BackupEngine(app=current_app)
        backup_job = engine.execute_backup(trigger_type='manual')
        
        flash(f'备份任务已完成，任务ID: {backup_job.id}')
    except Exception as e:
        flash(f'触发备份失败: {str(e)}')
    
    return redirect(url_for('admin.admin_backup_history'))


@admin_bp.route('/backup/create-local', methods=['POST'])
@login_required
def admin_backup_create_local():
    """生成本地备份（不上传到远程）"""
    _require_admin_role()
    
    from services.backup_engine import BackupEngine
    from runtime_paths import get_data_subdir
    import os
    import shutil
    
    try:
        # 创建本地备份目录
        local_backup_dir = get_data_subdir('backups')
        os.makedirs(local_backup_dir, exist_ok=True)
        
        # 临时修改配置，禁用远程上传
        from models import BackupConfig
        config = BackupConfig.query.first()
        
        if not config:
            flash('请先配置备份参数')
            return redirect(url_for('admin.admin_backup_config'))
        
        # 备份原始配置
        original_storage_type = config.storage_type
        
        # 临时设置为本地存储（通过设置一个特殊标记）
        config._local_backup_mode = True
        
        try:
            # 执行备份
            engine = BackupEngine(app=current_app)
            
            # 收集文件
            files = engine._collect_files('full', None)
            
            # 创建归档到本地目录
            archive_path, file_size, file_hash = engine._create_archive(files, local_backup_dir)
            
            # 如果启用了加密，加密文件
            if config.encryption_enabled and config.encryption_key_hash:
                try:
                    from cryptography.fernet import Fernet
                    import base64
                    import hashlib
                    
                    # 解密密码
                    key_material = hashlib.sha256(current_app.secret_key.encode()).digest()
                    fernet_key = base64.urlsafe_b64encode(key_material)
                    fernet = Fernet(fernet_key)
                    encryption_password = fernet.decrypt(config.encryption_key_hash.encode()).decode('utf-8')
                    
                    # 加密归档
                    archive_path = engine._encrypt_archive(archive_path, encryption_password)
                    file_size = os.path.getsize(archive_path)
                    file_hash = engine._calculate_file_hash(archive_path)
                except Exception as e:
                    flash(f'警告: 加密失败，已生成未加密备份: {str(e)}')
            
            # 创建备份任务记录
            from models import BackupJob
            from datetime import datetime
            
            backup_job = BackupJob(
                trigger_type='manual',
                status='success',
                backup_mode='full',
                filename=os.path.basename(archive_path),
                file_size_bytes=file_size,
                file_hash=file_hash,
                storage_type='local',
                storage_path=archive_path,
                is_encrypted=config.encryption_enabled,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
            
            # 统计信息
            db_files = [f for f in files if f['file_type'] == 'database']
            upload_files = [f for f in files if f['file_type'] == 'upload']
            doc_files = [f for f in files if f['file_type'] == 'document']
            
            backup_job.db_size_bytes = sum(f['size'] for f in db_files)
            backup_job.uploads_count = len(upload_files)
            backup_job.uploads_size_bytes = sum(f['size'] for f in upload_files)
            backup_job.docs_count = len(doc_files)
            backup_job.docs_size_bytes = sum(f['size'] for f in doc_files)
            
            db.session.add(backup_job)
            db.session.commit()
            
            flash(f'本地备份已生成: {os.path.basename(archive_path)} ({file_size / 1024 / 1024:.2f} MB)')
        finally:
            # 恢复原始配置
            if hasattr(config, '_local_backup_mode'):
                delattr(config, '_local_backup_mode')
        
    except Exception as e:
        flash(f'生成本地备份失败: {str(e)}')
    
    return redirect(url_for('admin.admin_backup_restore'))


@admin_bp.route('/backup/download/<int:job_id>')
@login_required
def admin_backup_download(job_id):
    """下载备份文件"""
    _require_admin_role()
    
    from models import BackupJob
    from flask import send_file
    import os
    
    job = BackupJob.query.get_or_404(job_id)
    
    if job.status != 'success':
        flash('只能下载成功的备份文件')
        return redirect(url_for('admin.admin_backup_history'))
    
    # 这里需要从存储适配器下载文件
    # 简化实现：假设文件在本地临时目录
    flash('备份文件下载功能需要从远程存储下载，请使用恢复功能')
    return redirect(url_for('admin.admin_backup_history'))


@admin_bp.route('/backup/restore')
@login_required
def admin_backup_restore():
    """备份恢复页面"""
    _require_admin_role()
    
    from services.backup_restorer import BackupRestorer
    from datetime import datetime
    
    try:
        restorer = BackupRestorer()
        backups = restorer.list_available_backups()
        
        # 获取筛选参数
        source_filter = request.args.get('source', '')
        start_date_str = request.args.get('start_date', '')
        end_date_str = request.args.get('end_date', '')
        
        # 应用筛选
        if source_filter:
            backups = [b for b in backups if b.get('source') == source_filter]
        
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                backups = [b for b in backups if b.get('created_at') and b['created_at'] >= start_date]
            except ValueError:
                pass
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                # 结束日期包含当天的23:59:59
                from datetime import timedelta
                end_date = end_date + timedelta(days=1) - timedelta(seconds=1)
                backups = [b for b in backups if b.get('created_at') and b['created_at'] <= end_date]
            except ValueError:
                pass
        
        return render_template('admin_backup_restore.html', backups=backups)
    except Exception as e:
        flash(f'获取备份列表失败: {str(e)}')
        return render_template('admin_backup_restore.html', backups=[])


@admin_bp.route('/backup/restore/scan', methods=['POST'])
@login_required
def admin_backup_scan_remote():
    """扫描远程存储中的备份文件"""
    _require_admin_role()
    
    from services.backup_restorer import BackupRestorer
    
    try:
        restorer = BackupRestorer()
        found_count, new_count, message = restorer.scan_remote_backups()
        flash(message)
    except Exception as e:
        flash(f'扫描失败: {str(e)}')
    
    return redirect(url_for('admin.admin_backup_restore'))


@admin_bp.route('/backup/restore/<int:job_id>/metadata')
@login_required
def admin_backup_restore_metadata(job_id):
    """获取备份元数据"""
    _require_admin_role()
    
    from services.backup_restorer import BackupRestorer
    from flask import jsonify
    
    try:
        restorer = BackupRestorer()
        metadata = restorer.get_backup_metadata(job_id)
        
        return jsonify({'success': True, 'metadata': metadata})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@admin_bp.route('/backup/restore/<int:job_id>', methods=['POST'])
@login_required
def admin_backup_restore_execute(job_id):
    """执行备份恢复"""
    _require_admin_role()
    
    from services.backup_restorer import BackupRestorer
    
    try:
        restore_type = request.form.get('restore_type', 'all')
        decryption_password = request.form.get('decryption_password')
        
        # 将restore_type映射到restore_options字典
        restore_options = {
            'restore_database': restore_type in ('all', 'database'),
            'restore_uploads': restore_type in ('all', 'uploads'),
            'restore_documents': restore_type in ('all', 'documents'),
            'decryption_password': decryption_password
        }
        
        restorer = BackupRestorer()
        success, message = restorer.restore_backup(
            backup_job_id=job_id,
            restore_options=restore_options
        )
        
        if success:
            flash(f'恢复成功: {message}')
        else:
            flash(f'恢复失败: {message}')
    except Exception as e:
        flash(f'恢复操作失败: {str(e)}')
    
    return redirect(url_for('admin.admin_backup_restore'))


@admin_bp.route('/backup/restore/orphaned', methods=['POST'])
@login_required
def admin_backup_restore_orphaned():
    """恢复孤立文件（无数据库记录的备份文件）"""
    _require_admin_role()
    
    from services.backup_restorer import BackupRestorer
    
    try:
        filename = request.form.get('filename')
        restore_type = request.form.get('restore_type', 'all')
        decryption_password = request.form.get('decryption_password')
        
        if not filename:
            flash('缺少文件名参数')
            return redirect(url_for('admin.admin_backup_restore'))
        
        # 为孤立文件创建临时的 BackupJob 记录
        restorer = BackupRestorer()
        backup_job = restorer.create_orphaned_backup_job(filename)
        
        # 将restore_type映射到restore_options字典
        restore_options = {
            'restore_database': restore_type in ('all', 'database'),
            'restore_uploads': restore_type in ('all', 'uploads'),
            'restore_documents': restore_type in ('all', 'documents'),
            'decryption_password': decryption_password
        }
        
        # 执行恢复
        success, message = restorer.restore_backup(
            backup_job_id=backup_job.id,
            restore_options=restore_options
        )
        
        if success:
            flash(f'恢复成功: {message}')
        else:
            flash(f'恢复失败: {message}')
    except Exception as e:
        flash(f'恢复操作失败: {str(e)}')
    
    return redirect(url_for('admin.admin_backup_restore'))


@admin_bp.route('/backup/records/cleanup', methods=['POST'])
@login_required
def admin_backup_cleanup_records():
    """清理无效的备份记录"""
    _require_admin_role()
    
    from services.backup_restorer import BackupRestorer
    
    try:
        restorer = BackupRestorer()
        count, message = restorer.cleanup_invalid_records()
        flash(message)
    except Exception as e:
        flash(f'清理失败: {str(e)}')
    
    return redirect(url_for('admin.admin_backup_history'))


@admin_bp.route('/backup/records/<int:job_id>/delete', methods=['POST'])
@login_required
def admin_backup_delete_record(job_id):
    """删除备份记录"""
    _require_admin_role()
    
    from services.backup_restorer import BackupRestorer
    
    try:
        delete_file = request.form.get('delete_file') == 'true'
        
        restorer = BackupRestorer()
        success, message = restorer.delete_backup_record(job_id, delete_file=delete_file)
        
        flash(message)
    except Exception as e:
        flash(f'删除失败: {str(e)}')
    
    return redirect(url_for('admin.admin_backup_history'))


@admin_bp.route('/backup/upload', methods=['POST'])
@login_required
def admin_backup_upload():
    """上传备份文件到本地"""
    _require_admin_role()
    
    import os
    from werkzeug.utils import secure_filename
    from runtime_paths import get_data_subdir
    
    try:
        # 检查是否有文件上传
        if 'backup_file' not in request.files:
            flash('请选择要上传的备份文件')
            return redirect(url_for('admin.admin_backup_restore'))
        
        file = request.files['backup_file']
        
        if file.filename == '':
            flash('请选择要上传的备份文件')
            return redirect(url_for('admin.admin_backup_restore'))
        
        # 验证文件扩展名
        filename = secure_filename(file.filename)
        if not (filename.endswith('.tar.gz') or filename.endswith('.tar.gz.enc')):
            flash('不支持的文件格式，请上传 .tar.gz 或 .tar.gz.enc 文件')
            return redirect(url_for('admin.admin_backup_restore'))
        
        # 保存上传的文件到本地备份目录
        local_backup_dir = get_data_subdir('backups')
        os.makedirs(local_backup_dir, exist_ok=True)
        
        upload_path = os.path.join(local_backup_dir, filename)
        
        # 如果文件已存在，添加时间戳
        if os.path.exists(upload_path):
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            name_parts = filename.rsplit('.', 2)  # 分割 name.tar.gz 或 name.tar.gz.enc
            if len(name_parts) >= 2:
                if filename.endswith('.enc'):
                    # name.tar.gz.enc -> name_timestamp.tar.gz.enc
                    filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}.{name_parts[2]}"
                else:
                    # name.tar.gz -> name_timestamp.tar.gz
                    filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
            upload_path = os.path.join(local_backup_dir, filename)
        
        file.save(upload_path)
        
        # 检测是否加密
        is_encrypted = filename.endswith('.enc')
        
        # 创建备份任务记录
        from models import BackupJob, BackupConfig
        from datetime import datetime
        
        config = BackupConfig.query.first()
        
        backup_job = BackupJob(
            trigger_type='manual',
            status='success',
            backup_mode='full',
            storage_type='local',
            is_encrypted=is_encrypted,
            filename=filename,
            file_size_bytes=os.path.getsize(upload_path),
            storage_path=upload_path,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.session.add(backup_job)
        db.session.commit()
        
        flash(f'备份文件已上传到本地: {filename} ({backup_job.file_size_bytes / 1024 / 1024:.2f} MB)')
        return redirect(url_for('admin.admin_backup_restore'))
        
    except Exception as e:
        flash(f'上传备份文件失败: {str(e)}')
        return redirect(url_for('admin.admin_backup_restore'))


# ============================================================================
# 备份存储监控路由
# ============================================================================

@admin_bp.route('/backup/storage')
@login_required
def admin_backup_storage():
    """备份存储监控页面"""
    _require_admin_role()
    
    from services.backup_storage_monitor import BackupStorageMonitor
    
    # 获取存储统计信息
    stats = BackupStorageMonitor.get_storage_stats()
    
    # 获取存储趋势数据（最近30天）
    trend_data = BackupStorageMonitor.get_storage_trend(days=30)
    
    # 获取按类型统计的数据
    storage_by_type = BackupStorageMonitor.get_storage_by_type()
    
    # 检查备份数量警告
    warning_active, warning_message = BackupStorageMonitor.check_storage_warning()
    
    return render_template(
        'admin_backup_storage.html',
        stats=stats,
        trend_data=trend_data,
        storage_by_type=storage_by_type,
        warning_active=warning_active,
        warning_message=warning_message
    )


# 注意：存储警告阈值现在自动计算（保留数量的80%），不再需要手动配置
# 以下路由已废弃，保留以防需要恢复
# @admin_bp.route('/backup/storage/threshold', methods=['POST'])
# @login_required
# def admin_backup_storage_threshold():
#     """更新存储空间警告阈值（已废弃）"""
#     pass
