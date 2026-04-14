import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from models import Comment, DocumentViewStat, NotificationLog, PasswordAccessRule, db, SystemSetting, User, PermissionRule
from services import (
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
        'recent_comments': comment_pagination.items,
        'comment_pagination': comment_pagination,
        'comment_filter': comment_filter,
        'comment_keyword': comment_keyword,
    }


def _get_admin_access_context():
    settings = _get_settings_map()
    access_mode = settings.get('access_mode', 'open')
    users = (
        User.query
        .filter(User.role != 'admin')
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

    target_user = User.query.get(int(user_id))
    if not target_user or target_user.role == 'admin':
        raise ValueError('只能为非管理员用户配置权限规则')

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
    if user.username == 'admin':
        raise ValueError('不能删除 admin 账号')

    Comment.query.filter_by(user_id=user.id).delete()
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
        pass


def _approve_comment_record(comment):
    if comment is None:
        raise ValueError('评论不存在')
    comment.status = 'approved'
    db.session.commit()
    _send_comment_status_mail(comment, approved=True)
    return comment


def _delete_comment_record(comment):
    if comment is None:
        raise ValueError('评论不存在')
    _send_comment_status_mail(comment, approved=False)
    comment.status = 'deleted'
    db.session.commit()
    return comment

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
    }

    for key in SECURITY_SETTING_DEFAULTS:
        if key in checkbox_keys:
            SystemSetting.set(key, 'true' if request.form.get(key) else 'false')
        else:
            SystemSetting.set(key, (request.form.get(key) or '').strip())

    flash('安全设置已更新')
    return redirect(url_for('admin.admin_security'))

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
    user = User.query.get_or_404(user_id)
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
    user = User.query.get_or_404(user_id)
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
    p = PermissionRule.query.get(rule_id)
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
    rule = PermissionRule.query.get(rule_id)
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
    rule = PasswordAccessRule.query.get(rule_id)
    if rule:
        db.session.delete(rule)
        db.session.commit()
        flash('访问密码权限规则已删除')
    return redirect(url_for('admin.admin_access'))


@admin_bp.route('/comment/approve/<int:comment_id>', methods=['POST'])
@login_required
def admin_approve_comment(comment_id):
    _require_admin_role()
    comment = Comment.query.get(comment_id)
    if comment:
        _approve_comment_record(comment)
        flash('评论已通过审核')
    return redirect(url_for('admin.admin_base'))


@admin_bp.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
def admin_delete_comment(comment_id):
    _require_admin_role()
    comment = Comment.query.get(comment_id)
    if comment:
        _delete_comment_record(comment)
        flash('评论已删除')
    return redirect(url_for('admin.admin_base'))


@admin_bp.route('/user/verify/<int:user_id>', methods=['POST'])
@login_required
def admin_verify_user_email(user_id):
    _require_admin_role()
    user = User.query.get(user_id)
    if user:
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
    user = User.query.get_or_404(user_id)
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
    
    query = User.query
    
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
    
    user = User.query.get_or_404(user_id)
    comments = Comment.query.filter_by(user_id=user.id).order_by(Comment.created_at.desc()).all()
    
    return render_template('admin_user_detail_page.html', user=user, comments=comments)


@admin_bp.route('/users/<int:user_id>/update', methods=['POST'])
@login_required
def admin_update_user_info(user_id):
    _require_admin_role()
    user = User.query.get_or_404(user_id)
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
    user = User.query.get_or_404(user_id)
    user.email_verified = True
    db.session.commit()
    
    flash('用户邮箱已标记为已验证')
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user_page(user_id):
    _require_admin_role()
    user = User.query.get_or_404(user_id)
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
    user = User.query.get_or_404(user_id)
    user.can_comment = 'can_comment' in request.form
    db.session.commit()
    
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/comments/<int:comment_id>/approve', methods=['POST'])
@login_required
def admin_approve_comment_page(comment_id):
    _require_admin_role()
    comment = Comment.query.get_or_404(comment_id)
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
    comment = Comment.query.get_or_404(comment_id)
    _delete_comment_record(comment)
    flash('评论已删除')
    user_id = request.form.get('user_id')
    if user_id:
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    return redirect(url_for('admin.admin_base'))
