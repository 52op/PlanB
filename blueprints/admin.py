import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import Comment, DocumentViewStat, NotificationLog, db, SystemSetting, User, DirectoryConfig, PermissionRule
from services import get_comment_stats, get_posts, get_user_stats, mailer_is_configured, send_logged_mail
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__, template_folder='templates', url_prefix='/admin')

@admin_bp.route('/images')
@login_required
def image_management():
    if current_user.role != 'admin':
        abort(403)
    return render_template('image_management.html')

@admin_bp.route('/')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        abort(403)
        
    settings = {s.key: s.value for s in SystemSetting.query.all()}
    user_query = User.query
    user_keyword = (request.args.get('user_q') or '').strip()
    user_role = (request.args.get('user_role') or 'all').strip()
    user_verified = (request.args.get('user_verified') or 'all').strip()
    if user_keyword:
        like_value = f'%{user_keyword}%'
        user_query = user_query.filter((User.username.like(like_value)) | (User.email.like(like_value)))
    if user_role != 'all':
        user_query = user_query.filter_by(role=user_role)
    if user_verified == 'yes':
        user_query = user_query.filter_by(email_verified=True)
    elif user_verified == 'no':
        user_query = user_query.filter_by(email_verified=False)
    users = user_query.all()
    dir_configs = DirectoryConfig.query.all()
    permissions = PermissionRule.query.all()
    comment_stats = get_comment_stats()
    user_stats = get_user_stats()
    site_stats = {
        'public_posts': len(get_posts(include_private=False)),
        'total_views': sum(stat.view_count for stat in DocumentViewStat.query.all()),
    }
    comment_trend = db.session.query(func.date(Comment.created_at), func.count(Comment.id)).group_by(func.date(Comment.created_at)).order_by(func.date(Comment.created_at)).limit(14).all()
    notification_trend = db.session.query(func.date(NotificationLog.created_at), func.count(NotificationLog.id)).group_by(func.date(NotificationLog.created_at)).order_by(func.date(NotificationLog.created_at)).limit(14).all()
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
    recent_comments = comment_pagination.items
    
    # 提取所有可用的目录列表供权限规则选择
    docs_dir = os.path.join(os.path.dirname(__file__), '..', SystemSetting.get('docs_dir', 'jobs') or 'jobs')
    all_dirs = []
    if os.path.exists(docs_dir):
        for root, dirs, files in os.walk(docs_dir):
            rel_path = os.path.relpath(root, docs_dir).replace('\\', '/')
            if rel_path != '.':
                all_dirs.append(rel_path + '/')
    all_dirs.sort()
    
    return render_template(
        'admin.html',
        settings=settings,
        users=users,
        dir_configs=dir_configs,
        permissions=permissions,
        all_dirs=all_dirs,
        site_stats=site_stats,
        comment_trend=comment_trend,
        notification_trend=notification_trend,
        comment_stats=comment_stats,
        user_stats=user_stats,
        recent_comments=recent_comments,
        comment_pagination=comment_pagination,
        comment_filter=comment_filter,
        comment_keyword=comment_keyword,
        user_keyword=user_keyword,
        user_role=user_role,
        user_verified=user_verified,
    )

@admin_bp.route('/settings', methods=['POST'])
@login_required
def update_settings():
    if current_user.role != 'admin':
        abort(403)

    # 循环处理所有可能的设置项，如果表单中存在该值，则更新
    settings_to_update = [
        'docs_dir', 'access_mode', 'global_password', 'home_default_type',
        'home_default_target', 'media_storage_type', 'media_max_size_mb',
        's3_endpoint', 's3_bucket', 's3_access_key', 's3_secret_key',
        's3_cdn_domain', 's3_path_prefix', 's3_path_style', 'site_name',
        'site_logo', 'site_tagline', 'home_title', 'home_description', 'footer_html', 'blog_home_count',
        'comments_enabled', 'comments_require_approval', 'smtp_host', 'smtp_port',
        'smtp_username', 'smtp_password', 'smtp_use_ssl', 'smtp_sender',
        'default_theme_color', 'default_theme_mode', 'site_mode', 'blog_theme'
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

    flash('系统设置已更新')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/user/add', methods=['POST'])
@login_required
def admin_add_user():
    if current_user.role != 'admin': abort(403)
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    
    if User.query.filter_by(username=username).first():
        flash("用户名已存在")
        return redirect(url_for('admin.admin_dashboard'))
        
    u = User()
    u.username = username
    u.role = role
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    flash("添加用户成功")
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin': abort(403)
    u = User.query.get(user_id)
    if u and u.username != 'admin':
        db.session.delete(u)
        db.session.commit()
        flash("删除用户成功")
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/user/update/<int:user_id>', methods=['POST'])
@login_required
def admin_update_user(user_id):
    if current_user.role != 'admin': abort(403)
    u = User.query.get(user_id)
    if u:
        new_pwd = request.form.get('new_password')
        new_role = request.form.get('role')
        
        if new_pwd:
            u.set_password(new_pwd)
            
        if new_role and new_role in ['admin', 'regular', 'guest']:
            if u.username != 'admin':
                u.role = new_role
                
        db.session.commit()
        flash("用户资料已更新")
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/permission/add', methods=['POST'])
@login_required
def admin_add_permission():
    if current_user.role != 'admin': abort(403)
    user_id = request.form.get('user_id')
    dir_path = request.form.get('dir_path')
    
    if not user_id or not dir_path:
        flash("规则参数不全")
        return redirect(url_for('admin.admin_dashboard'))
    
    # 查找是否已有同用户和同路径的规则则覆盖
    p = PermissionRule.query.filter_by(user_id=user_id, dir_path=dir_path).first()
    if not p:
        p = PermissionRule()
        p.user_id = user_id
        p.dir_path = dir_path
        db.session.add(p)
        
    p.can_read = 'can_read' in request.form
    p.can_edit = 'can_edit' in request.form
    p.can_upload = 'can_upload' in request.form
    p.can_delete = 'can_delete' in request.form
    db.session.commit()
    flash("权限规则已更新")
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/permission/delete/<int:rule_id>', methods=['POST'])
@login_required
def admin_delete_permission(rule_id):
    if current_user.role != 'admin': abort(403)
    p = PermissionRule.query.get(rule_id)
    if p:
        db.session.delete(p)
        db.session.commit()
        flash("权限规则已删除")
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/comment/approve/<int:comment_id>', methods=['POST'])
@login_required
def admin_approve_comment(comment_id):
    if current_user.role != 'admin':
        abort(403)
    comment = Comment.query.get(comment_id)
    if comment:
        comment.status = 'approved'
        db.session.commit()
        if comment.user and comment.user.email and comment.user.email_verified and mailer_is_configured():
            try:
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
            except Exception:
                pass
        flash('评论已通过审核')
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/comment/delete/<int:comment_id>', methods=['POST'])
@login_required
def admin_delete_comment(comment_id):
    if current_user.role != 'admin':
        abort(403)
    comment = Comment.query.get(comment_id)
    if comment:
        if comment.user and comment.user.email and comment.user.email_verified and mailer_is_configured() and comment.status != 'deleted':
            try:
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
        comment.status = 'deleted'
        db.session.commit()
        flash('评论已删除')
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/user/verify/<int:user_id>', methods=['POST'])
@login_required
def admin_verify_user_email(user_id):
    if current_user.role != 'admin':
        abort(403)
    user = User.query.get(user_id)
    if user:
        user.email_verified = True
        db.session.commit()
        flash('用户邮箱已标记为已验证')
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/user/<int:user_id>')
@login_required
def admin_user_detail(user_id):
    if current_user.role != 'admin':
        abort(403)
    user = User.query.get_or_404(user_id)
    comments = Comment.query.filter_by(user_id=user.id).order_by(Comment.created_at.desc()).all()
    return render_template('admin_user_detail.html', user=user, comments=comments)


@admin_bp.route('/user/detail-update/<int:user_id>', methods=['POST'])
@login_required
def admin_update_user_detail(user_id):
    if current_user.role != 'admin':
        abort(403)
    user = User.query.get_or_404(user_id)

    username = (request.form.get('username') or '').strip()
    nickname = (request.form.get('nickname') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    role = (request.form.get('role') or '').strip()

    if not username:
        flash('用户名不能为空')
        return redirect(url_for('admin.admin_user_detail', user_id=user_id))

    existing_user = User.query.filter(User.username == username, User.id != user.id).first()
    if existing_user:
        flash('用户名已存在')
        return redirect(url_for('admin.admin_user_detail', user_id=user_id))

    if email:
        existing_email = User.query.filter(User.email == email, User.id != user.id).first()
        if existing_email:
            flash('邮箱已被使用')
            return redirect(url_for('admin.admin_user_detail', user_id=user_id))

    user.username = username
    user.nickname = nickname or None
    user.email = email or None
    if role in ['admin', 'regular', 'guest'] and user.username != 'admin':
        user.role = role

    db.session.commit()
    flash('用户资料已更新')
    return redirect(url_for('admin.admin_user_detail', user_id=user_id))


@admin_bp.route('/notifications')
@login_required
def notification_logs():
    if current_user.role != 'admin':
        abort(403)
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
    if current_user.role != 'admin':
        abort(403)
    
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
    if current_user.role != 'admin':
        abort(403)
    
    username = (request.form.get('username') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password')
    role = request.form.get('role') or 'regular'
    
    if not username or not password:
        flash('用户名和密码不能为空')
        return redirect(url_for('admin.admin_users'))
    
    if User.query.filter_by(username=username).first():
        flash('用户名已存在')
        return redirect(url_for('admin.admin_users'))
    
    if email and User.query.filter_by(email=email).first():
        flash('邮箱已被使用')
        return redirect(url_for('admin.admin_users'))
    
    user = User()
    user.username = username
    user.email = email or None
    user.role = role if role in ['admin', 'regular', 'guest'] else 'regular'
    user.set_password(password)
    user.can_comment = True
    
    db.session.add(user)
    db.session.commit()
    
    flash('用户添加成功')
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/users/<int:user_id>')
@login_required
def admin_user_detail_page(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    comments = Comment.query.filter_by(user_id=user.id).order_by(Comment.created_at.desc()).all()
    
    return render_template('admin_user_detail_page.html', user=user, comments=comments)


@admin_bp.route('/users/<int:user_id>/update', methods=['POST'])
@login_required
def admin_update_user_info(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    
    username = (request.form.get('username') or '').strip()
    nickname = (request.form.get('nickname') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    role = (request.form.get('role') or '').strip()
    new_password = request.form.get('new_password')
    
    if not username:
        flash('用户名不能为空')
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    
    # 检查用户名是否被占用
    existing_user = User.query.filter(User.username == username, User.id != user.id).first()
    if existing_user:
        flash('用户名已存在')
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    
    # 检查邮箱是否被占用
    if email:
        existing_email = User.query.filter(User.email == email, User.id != user.id).first()
        if existing_email:
            flash('邮箱已被使用')
            return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    
    # 更新用户信息
    old_email = user.email
    user.username = username
    user.nickname = nickname or None
    user.email = email or None
    
    # 如果邮箱变更，标记为未验证
    if old_email != user.email:
        user.email_verified = False
    
    # 更新角色（admin 账号除外）
    if role in ['admin', 'regular', 'guest'] and user.username != 'admin':
        user.role = role
    
    # 更新密码
    if new_password:
        user.set_password(new_password)
    
    db.session.commit()
    flash('用户信息已更新')
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/verify-email', methods=['POST'])
@login_required
def admin_verify_user_email_page(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    user.email_verified = True
    db.session.commit()
    
    flash('用户邮箱已标记为已验证')
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user_page(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    
    if user.username == 'admin':
        flash('不能删除 admin 账号')
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    
    # 删除用户的所有评论
    Comment.query.filter_by(user_id=user.id).delete()
    
    # 删除用户的权限规则
    PermissionRule.query.filter_by(user_id=user.id).delete()
    
    # 删除用户
    db.session.delete(user)
    db.session.commit()
    
    flash('用户已删除')
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/users/<int:user_id>/toggle-comment', methods=['POST'])
@login_required
def admin_toggle_comment_permission(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    user.can_comment = 'can_comment' in request.form
    db.session.commit()
    
    return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))


@admin_bp.route('/comments/<int:comment_id>/approve', methods=['POST'])
@login_required
def admin_approve_comment_page(comment_id):
    if current_user.role != 'admin':
        abort(403)
    
    comment = Comment.query.get_or_404(comment_id)
    comment.status = 'approved'
    db.session.commit()
    
    # 发送通知邮件
    if comment.user and comment.user.email and comment.user.email_verified and mailer_is_configured():
        try:
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
        except Exception:
            pass
    
    flash('评论已通过审核')
    user_id = request.form.get('user_id')
    if user_id:
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def admin_delete_comment_page(comment_id):
    if current_user.role != 'admin':
        abort(403)
    
    comment = Comment.query.get_or_404(comment_id)
    
    # 发送通知邮件
    if comment.user and comment.user.email and comment.user.email_verified and mailer_is_configured() and comment.status != 'deleted':
        try:
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
    
    comment.status = 'deleted'
    db.session.commit()
    
    flash('评论已删除')
    user_id = request.form.get('user_id')
    if user_id:
        return redirect(url_for('admin.admin_user_detail_page', user_id=user_id))
    return redirect(url_for('admin.admin_dashboard'))
