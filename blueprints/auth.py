from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required, login_user, logout_user
from models import Comment, SystemSetting, User, db
from werkzeug.utils import secure_filename
import os
import uuid
from PIL import Image as PILImage, ImageOps
from services import (
    can_delete_comment,
    check_verification_send_rate_limit,
    check_permission,
    build_verification_scope_key,
    check_rate_limit,
    check_verification_rate_limit,
    clear_global_access_cookie,
    create_email_verification_code,
    format_wait_time,
    get_client_ip,
    get_safe_redirect_target,
    has_valid_global_access_cookie,
    issue_global_access_cookie,
    mailer_is_configured,
    record_login_failure,
    record_login_success,
    record_verification_send_attempt,
    record_verification_failure,
    record_verification_success,
    send_logged_mail,
    validate_registration_input,
    verify_email_code,
)
from blueprints.main import _get_site_settings

auth_bp = Blueprint('auth', __name__, template_folder='templates')


def _flash_failure_message(base_message, failure_count=0, wait_seconds=0):
    if wait_seconds > 0 and failure_count > 0:
        flash(f'{base_message}。连续失败 {failure_count} 次，请在 {format_wait_time(wait_seconds)} 后重试')
        return
    if failure_count > 0:
        flash(f'{base_message}（已失败 {failure_count} 次）')
        return
    flash(base_message)


def _can_send_verification_code(client_ip, email, purpose):
    is_allowed, wait_seconds, failure_count, blocked_scope = check_verification_send_rate_limit(client_ip, email, purpose)
    if is_allowed:
        return True

    if blocked_scope == 'email':
        flash(f'该邮箱请求验证码过于频繁，请在 {format_wait_time(wait_seconds)} 后重试')
    else:
        flash(f'当前网络环境请求验证码过于频繁，请在 {format_wait_time(wait_seconds)} 后重试')
    return False


def _build_account_comment_items(comments):
    from services.docs import _can_access_document_metadata, _parse_markdown_file
    from services.comments import _collect_comment_descendant_ids

    status_labels = {
        'approved': '已通过',
        'pending': '待审核',
        'deleted': '已删除',
    }

    items = []
    for comment in comments or []:
        metadata = {}
        payload = _parse_markdown_file(comment.filename)
        if payload:
            metadata = payload.get('metadata') or {}

        title = str(metadata.get('title') or comment.filename).strip() or comment.filename
        can_open = bool(
            metadata and _can_access_document_metadata(comment.filename, metadata, user=current_user)
        )
        article_url = ''
        if can_open:
            if metadata.get('template') == 'post' and metadata.get('slug'):
                article_url = url_for('main.post_detail', slug=metadata['slug'])
            elif check_permission(current_user, comment.filename, 'read'):
                article_url = url_for('main.docs_doc', filename=comment.filename)

        items.append({
            'id': comment.id,
            'content': comment.content,
            'status': comment.status,
            'status_label': status_labels.get(comment.status, comment.status or '未知状态'),
            'descendant_count': len(_collect_comment_descendant_ids(comment.id)),
            'created_at': comment.created_at,
            'created_at_display': comment.created_at.strftime('%Y-%m-%d %H:%M') if comment.created_at else '',
            'article_title': title,
            'article_url': article_url,
            'can_open': bool(article_url),
            'can_delete': can_delete_comment(comment, user=current_user),
        })
    return items

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    access_mode = SystemSetting.get('access_mode', 'open')
    client_ip = get_client_ip(request)
    
    # 检测是否从文档访问被拦截跳转过来
    from_docs = request.args.get('from_docs', type=int) == 1

    # 检测是否已通过全局访问密码进入过（用于控制默认显示的 Tab）
    has_global_access = False
    if access_mode == 'password_only':
        global_pwd = SystemSetting.get('global_password', '')
        if global_pwd and has_valid_global_access_cookie():
            has_global_access = True
    
    # 用于保留表单数据
    form_data = {}
    login_mode = 'password'
    
    if request.method == 'POST':
        action_type = request.form.get('action_type')
        
        # 处理全局密码访问
        if action_type == 'global_password' and access_mode == 'password_only':
            # 检查频率限制
            is_allowed, wait_seconds, failure_count = check_rate_limit(client_ip)
            if not is_allowed:
                flash(f'尝试次数过多，请在 {format_wait_time(wait_seconds)} 后重试')
            else:
                pwd = request.form.get('password')
                if pwd == SystemSetting.get('global_password'):
                    record_login_success(client_ip)
                    target = get_safe_redirect_target(request.args.get('next'))
                    resp = redirect(target)
                    issue_global_access_cookie(resp)
                    return resp
                else:
                    wait_seconds, failure_count = record_login_failure(client_ip)
                    _flash_failure_message('全局密码错误', failure_count, wait_seconds)
            
        # 处理账号密码登录（支持用户名或邮箱）
        elif action_type == 'user_login':
            # 检查频率限制
            is_allowed, wait_seconds, failure_count = check_rate_limit(client_ip)
            if not is_allowed:
                flash(f'尝试次数过多，请在 {format_wait_time(wait_seconds)} 后重试')
                form_data['login_username'] = request.form.get('username')
            else:
                username_or_email = (request.form.get('username') or '').strip()
                password = request.form.get('password')
                
                # 尝试用户名登录
                user = User.query.filter_by(username=username_or_email).first()
                
                # 如果用户名不存在，尝试邮箱登录
                if not user:
                    user = User.query.filter_by(email=username_or_email.lower()).first()
                
                if user and user.check_password(password):
                    record_login_success(client_ip)
                    login_user(user)
                    target = get_safe_redirect_target(request.args.get('next'))
                    return redirect(target)
                else:
                    wait_seconds, failure_count = record_login_failure(client_ip)
                    _flash_failure_message('用户名/邮箱或密码错误', failure_count, wait_seconds)
                    form_data['login_username'] = username_or_email
        
        # 处理邮箱验证码登录
        elif action_type == 'email_login':
            login_mode = 'code'
            email = (request.form.get('email') or '').strip().lower()
            code = (request.form.get('verification_code') or '').strip()
            if not email or not code:
                flash('请输入邮箱和验证码')
                form_data['login_email'] = email
            else:
                verification_scope_key = build_verification_scope_key(client_ip, email, purpose='login')
                is_allowed, wait_seconds, failure_count = check_verification_rate_limit(verification_scope_key)
                if not is_allowed:
                    flash(f'验证码尝试次数过多，请在 {format_wait_time(wait_seconds)} 后重试')
                    form_data['login_email'] = email
                else:
                    user = User.query.filter_by(email=email).first()
                    if not user:
                        flash('该邮箱未注册')
                        form_data['login_email'] = email
                    elif not verify_email_code(email, code, purpose='login'):
                        wait_seconds, failure_count = record_verification_failure(verification_scope_key)
                        _flash_failure_message('验证码无效或已过期', failure_count, wait_seconds)
                        form_data['login_email'] = email
                    else:
                        record_verification_success(verification_scope_key)
                        login_user(user)
                        target = get_safe_redirect_target(request.args.get('next'))
                        return redirect(target)
        
        # 处理发送登录验证码
        elif action_type == 'send_login_code':
            login_mode = 'code'
            email = (request.form.get('email') or '').strip().lower()
            if not email:
                flash('请输入邮箱地址')
            elif not User.query.filter_by(email=email).first():
                flash('该邮箱未注册')
            elif not mailer_is_configured():
                flash('站点暂未配置邮件服务器')
            elif not _can_send_verification_code(client_ip, email, 'login'):
                pass
            else:
                try:
                    site_settings = _get_site_settings()
                    site_name = site_settings.get('site_name', 'Planning')
                    code = create_email_verification_code(email, purpose='login')
                    send_logged_mail(
                        'login_code',
                        email,
                        '登录验证码',
                        f'您的验证码是：{code}，10 分钟内有效。',
                        '登录验证码',
                        f'您正在登录 {site_name}。请使用下面的验证码完成登录：',
                        f'<div style="margin:20px 0;padding:16px 18px;border-radius:14px;background:#fff1e5;color:#9a3412;font-size:28px;font-weight:800;letter-spacing:6px;text-align:center;">{code}</div><p style="color:#64748b;line-height:1.8;">验证码 10 分钟内有效。如非本人操作，请忽略本邮件。</p>'
                    )
                    record_verification_send_attempt(client_ip, email, 'login')
                    flash('验证码已发送，请检查邮箱')
                except ValueError as exc:
                    flash(str(exc))
                except Exception:
                    flash('验证码发送失败，请检查邮件服务器配置')

        elif action_type == 'send_register_code':
            email = (request.form.get('email') or '').strip().lower()
            if not email:
                flash('请输入注册邮箱')
            elif User.query.filter_by(email=email).first():
                flash('该邮箱已被使用')
            elif not mailer_is_configured():
                flash('站点暂未配置邮件服务器，暂时无法注册')
            elif not _can_send_verification_code(client_ip, email, 'register'):
                pass
            else:
                try:
                    site_settings = _get_site_settings()
                    site_name = site_settings.get('site_name', 'Planning')
                    code = create_email_verification_code(email, purpose='register')
                    send_logged_mail(
                        'register_code',
                        email,
                        '注册验证码',
                        f'您的验证码是：{code}，10 分钟内有效。',
                        '注册验证码',
                        f'欢迎注册 {site_name} 账号。请使用下面的验证码完成邮箱验证：',
                        f'<div style="margin:20px 0;padding:16px 18px;border-radius:14px;background:#fff1e5;color:#9a3412;font-size:28px;font-weight:800;letter-spacing:6px;text-align:center;">{code}</div><p style="color:#64748b;line-height:1.8;">验证码 10 分钟内有效。如非本人操作，请忽略本邮件。</p>'
                    )
                    record_verification_send_attempt(client_ip, email, 'register')
                    flash('验证码已发送，请检查邮箱')
                except ValueError as exc:
                    flash(str(exc))
                except Exception:
                    flash('验证码发送失败，请检查邮件服务器配置')

        elif action_type == 'register_user':
            username = request.form.get('username') or ''
            email = request.form.get('email') or ''
            password = request.form.get('password') or ''
            confirm_password = request.form.get('confirm_password') or ''
            code = (request.form.get('verification_code') or '').strip()
            
            # 保存表单数据用于失败时回填
            form_data['register_username'] = username
            form_data['register_email'] = email
            
            if not username or not email or not password or not confirm_password or not code:
                flash('请完整填写注册信息')
            else:
                validation_error = None
                try:
                    username, email = validate_registration_input(username, email, password)
                except ValueError as exc:
                    validation_error = str(exc)

                if validation_error:
                    flash(validation_error)
                elif password != confirm_password:
                    flash('两次输入的密码不一致')
                elif User.query.filter_by(username=username).first():
                    flash('用户名已存在')
                elif User.query.filter_by(email=email).first():
                    flash('该邮箱已被使用')
                else:
                    verification_scope_key = build_verification_scope_key(client_ip, email, purpose='register')
                    is_allowed, wait_seconds, failure_count = check_verification_rate_limit(verification_scope_key)
                    if not is_allowed:
                        flash(f'验证码尝试次数过多，请在 {format_wait_time(wait_seconds)} 后重试')
                    elif not verify_email_code(email, code, purpose='register'):
                        wait_seconds, failure_count = record_verification_failure(verification_scope_key)
                        _flash_failure_message('验证码无效或已过期', failure_count, wait_seconds)
                    else:
                        record_verification_success(verification_scope_key)
                        user = User()
                        user.username = username
                        user.email = email
                        user.role = 'guest'
                        user.email_verified = True
                        user.set_password(password)
                        db.session.add(user)
                        db.session.commit()
                        login_user(user)
                        flash('注册成功，已自动登录')
                        target = get_safe_redirect_target(request.args.get('next'))
                        return redirect(target)
            
    # 默认 Tab：只有从文档访问被拦截时才默认显示访客访问
    default_tab = 'visitor' if from_docs else 'login'
    if request.method == 'POST':
        action = request.form.get('action_type')
        if action in {'send_register_code', 'register_user'}:
            default_tab = 'register'
        elif action in {'send_login_code', 'email_login', 'user_login'}:
            default_tab = 'login'
        elif action == 'global_password':
            default_tab = 'visitor'
        if action in {'send_login_code', 'email_login'}:
            login_mode = 'code'
        elif action == 'user_login':
            login_mode = 'password'

    # 返回链接：优先使用 next 参数，其次 referrer（排除登录页自身），兜底首页
    referrer = request.referrer or ''
    if referrer.endswith('/login'):
        referrer = ''
    back_url = get_safe_redirect_target(request.args.get('next') or referrer)

    site_settings = _get_site_settings()

    return render_template('login.html',
                           access_mode=access_mode,
                           default_tab=default_tab,
                           has_global_access=has_global_access,
                           from_docs=from_docs,
                           back_url=back_url,
                           mailer_ready=mailer_is_configured(),
                           site_settings=site_settings,
                           form_data=form_data,
                           login_mode=login_mode)

@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@auth_bp.route('/logout-global')
def logout_global():
    target = get_safe_redirect_target(request.args.get('next') or request.referrer or url_for('main.index'))
    resp = redirect(target)
    clear_global_access_cookie(resp)
    flash('已退出全局访问密码登录')
    return resp


@auth_bp.route('/account')
@login_required
def account():
    page = request.args.get('page', 1, type=int)
    query = Comment.query.filter_by(user_id=current_user.id).order_by(Comment.created_at.desc())
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    site_settings = _get_site_settings()
    account_comments = _build_account_comment_items(pagination.items)

    return render_template('account.html',
                         comments=account_comments,
                         comments_pagination=pagination,
                         site_settings=site_settings)


@auth_bp.route('/account/profile', methods=['POST'])
@login_required
def update_profile():
    nickname = (request.form.get('nickname') or '').strip()
    avatar = request.files.get('avatar')

    if nickname:
        current_user.nickname = nickname[:80]

    if avatar and avatar.filename:
        ext = os.path.splitext(secure_filename(avatar.filename))[1].lower()
        if ext not in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
            flash('头像仅支持 png/jpg/jpeg/gif/webp')
            return redirect(url_for('auth.account'))
        
        upload_dir = os.path.join(current_app.config.get('UPLOADS_DIR'), 'avatars')
        os.makedirs(upload_dir, exist_ok=True)
        
        # 删除旧头像
        if current_user.avatar_url and current_user.avatar_url.startswith('/media/'):
            old_avatar_relative = current_user.avatar_url.replace('/media/', '', 1).lstrip('/')
            old_avatar_path = os.path.join(current_app.config.get('UPLOADS_DIR'), old_avatar_relative)
            if os.path.exists(old_avatar_path):
                try:
                    os.remove(old_avatar_path)
                except Exception:
                    pass
        
        # 使用用户ID+时间戳命名
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        file_name = f'{current_user.id}-{timestamp}.jpg'
        save_path = os.path.join(upload_dir, file_name)
        
        # 处理图片：先按 EXIF 方向自动纠正，再裁剪为正方形并调整大小为 512x512
        image = PILImage.open(avatar.stream)
        image = ImageOps.exif_transpose(image).convert('RGB')
        size = min(image.size)
        left = (image.width - size) // 2
        top = (image.height - size) // 2
        image = image.crop((left, top, left + size, top + size)).resize((512, 512), PILImage.Resampling.LANCZOS)
        image.save(save_path, format='JPEG', quality=85, optimize=True)
        
        current_user.avatar_url = f'/media/avatars/{file_name}'

    db.session.commit()
    flash('个人资料已更新')
    return redirect(url_for('auth.account'))


@auth_bp.route('/account/password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password') or ''
    new_password = request.form.get('new_password') or ''
    confirm_password = request.form.get('confirm_password') or ''

    if not current_user.check_password(current_password):
        flash('当前密码不正确')
        return redirect(url_for('auth.account'))

    try:
        validate_registration_input(current_user.username, current_user.email or 'user@example.com', new_password)
    except ValueError as exc:
        flash(str(exc).replace('邮箱格式不正确', '新密码不符合要求'))
        return redirect(url_for('auth.account'))

    if new_password != confirm_password:
        flash('两次输入的新密码不一致')
        return redirect(url_for('auth.account'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('密码已更新')
    return redirect(url_for('auth.account'))


@auth_bp.route('/account/send-verification', methods=['POST'])
@login_required
def send_account_verification():
    client_ip = get_client_ip(request)
    if not current_user.email:
        flash('当前账号未绑定邮箱')
        return redirect(url_for('auth.account'))
    if current_user.email_verified:
        flash('当前邮箱已验证')
        return redirect(url_for('auth.account'))
    if not mailer_is_configured():
        flash('站点暂未配置邮件服务器')
        return redirect(url_for('auth.account'))
    if not _can_send_verification_code(client_ip, current_user.email, 'account_verify'):
        return redirect(url_for('auth.account'))
    try:
        code = create_email_verification_code(current_user.email, purpose='account_verify')
        send_logged_mail(
            'account_verify',
            current_user.email,
            '邮箱验证',
            f'您的邮箱验证码是：{code}，10 分钟内有效。',
            '邮箱验证',
            '请使用下面的验证码完成邮箱验证：',
            f'<div style="margin:20px 0;padding:16px 18px;border-radius:14px;background:#fff1e5;color:#9a3412;font-size:28px;font-weight:800;letter-spacing:6px;text-align:center;">{code}</div><p style="color:#64748b;line-height:1.8;">验证码 10 分钟内有效。</p>'
        )
        record_verification_send_attempt(client_ip, current_user.email, 'account_verify')
        flash('验证邮件已发送，请检查邮箱')
    except ValueError as exc:
        flash(str(exc))
    except Exception:
        flash('验证邮件发送失败，请检查邮件配置')
    return redirect(url_for('auth.account'))


@auth_bp.route('/account/verify-email', methods=['POST'])
@login_required
def verify_account_email():
    code = (request.form.get('verification_code') or '').strip()
    if not current_user.email:
        flash('当前账号未绑定邮箱')
    elif not code:
        flash('请输入验证码')
    else:
        client_ip = get_client_ip(request)
        verification_scope_key = build_verification_scope_key(client_ip, current_user.email, purpose='account_verify')
        is_allowed, wait_seconds, failure_count = check_verification_rate_limit(verification_scope_key)
        if not is_allowed:
            flash(f'验证码尝试次数过多，请在 {format_wait_time(wait_seconds)} 后重试')
        elif verify_email_code(current_user.email, code, purpose='account_verify'):
            record_verification_success(verification_scope_key)
            current_user.email_verified = True
            db.session.commit()
            flash('邮箱验证成功')
        else:
            wait_seconds, failure_count = record_verification_failure(verification_scope_key)
            _flash_failure_message('验证码无效或已过期', failure_count, wait_seconds)
    return redirect(url_for('auth.account'))


@auth_bp.route('/account/send-email-change', methods=['POST'])
@login_required
def send_email_change_code():
    client_ip = get_client_ip(request)
    new_email = (request.form.get('new_email') or '').strip().lower()
    if not new_email:
        flash('请输入新的邮箱地址')
        return redirect(url_for('auth.account'))
    try:
        _, new_email = validate_registration_input(current_user.username, new_email, 'Password1')
    except ValueError:
        flash('新邮箱格式不正确')
        return redirect(url_for('auth.account'))
    if User.query.filter(User.email == new_email, User.id != current_user.id).first():
        flash('该邮箱已被使用')
        return redirect(url_for('auth.account'))
    if not mailer_is_configured():
        flash('站点暂未配置邮件服务器')
        return redirect(url_for('auth.account'))
    if not _can_send_verification_code(client_ip, new_email, 'change_email'):
        return redirect(url_for('auth.account'))
    try:
        code = create_email_verification_code(new_email, purpose='change_email')
        send_logged_mail(
            'change_email_code',
            new_email,
            '修改邮箱验证码',
            f'您的邮箱修改验证码是：{code}，10 分钟内有效。',
            '邮箱修改验证码',
            '请使用下面的验证码完成邮箱变更：',
            f'<div style="margin:20px 0;padding:16px 18px;border-radius:14px;background:#fff1e5;color:#9a3412;font-size:28px;font-weight:800;letter-spacing:6px;text-align:center;">{code}</div><p style="color:#64748b;line-height:1.8;">验证码 10 分钟内有效。</p>'
        )
        record_verification_send_attempt(client_ip, new_email, 'change_email')
        flash('邮箱修改验证码已发送')
    except ValueError as exc:
        flash(str(exc))
    except Exception:
        flash('验证码发送失败，请检查邮件配置')
    return redirect(url_for('auth.account'))


@auth_bp.route('/account/change-email', methods=['POST'])
@login_required
def change_email():
    new_email = (request.form.get('new_email') or '').strip().lower()
    code = (request.form.get('verification_code') or '').strip()
    if not new_email or not code:
        flash('请填写新邮箱和验证码')
        return redirect(url_for('auth.account'))
    try:
        _, new_email = validate_registration_input(current_user.username, new_email, 'Password1')
    except ValueError:
        flash('新邮箱格式不正确')
        return redirect(url_for('auth.account'))
    if User.query.filter(User.email == new_email, User.id != current_user.id).first():
        flash('该邮箱已被使用')
        return redirect(url_for('auth.account'))
    client_ip = get_client_ip(request)
    verification_scope_key = build_verification_scope_key(client_ip, new_email, purpose='change_email')
    is_allowed, wait_seconds, failure_count = check_verification_rate_limit(verification_scope_key)
    if not is_allowed:
        flash(f'验证码尝试次数过多，请在 {format_wait_time(wait_seconds)} 后重试')
        return redirect(url_for('auth.account'))
    if not verify_email_code(new_email, code, purpose='change_email'):
        wait_seconds, failure_count = record_verification_failure(verification_scope_key)
        _flash_failure_message('验证码无效或已过期', failure_count, wait_seconds)
        return redirect(url_for('auth.account'))
    record_verification_success(verification_scope_key)
    current_user.email = new_email
    current_user.email_verified = True
    db.session.commit()
    flash('邮箱已更新并验证成功')
    return redirect(url_for('auth.account'))
