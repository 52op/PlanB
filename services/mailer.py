import smtplib
from email.message import EmailMessage

from models import NotificationLog, SystemSetting, db


def mailer_is_configured():
    return bool(SystemSetting.get('smtp_host') and SystemSetting.get('smtp_sender'))


def render_mail_layout(title, intro, body_html, action_url='', action_label=''):
    # 获取站点信息
    site_name = SystemSetting.get('site_name', 'Planning') or 'Planning'
    site_tagline = SystemSetting.get('site_tagline', '轻量 Markdown 内容站') or '轻量 Markdown 内容站'
    
    action_html = ''
    if action_url and action_label:
        action_html = f'<p style="margin-top:16px;"><a href="{action_url}" style="display:inline-block;padding:10px 16px;border-radius:12px;background:#b85c38;color:#fff;text-decoration:none;">{action_label}</a></p>'
    
    footer_html = f'''
        <div style="margin-top:32px;padding-top:20px;border-top:1px solid #eadfce;">
            <p style="margin:0;color:#94a3b8;font-size:13px;line-height:1.6;">
                此邮件由 <strong style="color:#64748b;">{site_name}</strong> 自动发送<br>
                {site_tagline}
            </p>
        </div>
    '''
    
    return f'''<div style="font-family:Segoe UI,PingFang SC,sans-serif;background:#f8f5ef;padding:24px;">
        <div style="max-width:620px;margin:0 auto;background:#fffdf9;border:1px solid #eadfce;border-radius:18px;padding:28px;">
            <h2 style="margin:0 0 12px;color:#b85c38;">{title}</h2>
            <p style="color:#64748b;line-height:1.8;">{intro}</p>
            {body_html}
            {action_html}
            {footer_html}
        </div>
    </div>'''


def notification_allowed(event_type, target, cooldown_seconds=60):
    latest = NotificationLog.query.filter_by(event_type=event_type, target=target).order_by(NotificationLog.created_at.desc()).first()
    if latest and latest.created_at:
        from datetime import datetime, timedelta
        if latest.created_at > datetime.utcnow() - timedelta(seconds=cooldown_seconds):
            return False
    return True


def record_notification(event_type, target):
    log = NotificationLog()
    log.event_type = event_type
    log.target = target
    db.session.add(log)
    db.session.commit()


def send_logged_mail(event_type, recipient, subject, plain_text, title, intro, body_html, action_url='', action_label='', cooldown_seconds=60):
    if not notification_allowed(event_type, recipient, cooldown_seconds=cooldown_seconds):
        return False
    send_mail(
        subject,
        recipient,
        plain_text,
        html_content=render_mail_layout(title, intro, body_html, action_url=action_url, action_label=action_label),
    )
    record_notification(event_type, recipient)
    return True


def send_mail(subject, recipient, content, html_content=None):
    host = (SystemSetting.get('smtp_host') or '').strip()
    sender = (SystemSetting.get('smtp_sender') or '').strip()
    port = int(SystemSetting.get('smtp_port', '465') or '465')
    username = (SystemSetting.get('smtp_username') or '').strip()
    password = SystemSetting.get('smtp_password') or ''
    use_ssl = (SystemSetting.get('smtp_use_ssl', 'true') or 'true').lower() == 'true'

    if not host or not sender:
        raise RuntimeError('邮件服务器未配置完整')

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = recipient
    message.set_content(content)
    if html_content:
        message.add_alternative(html_content, subtype='html')

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=20) as server:
            if username:
                server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if username:
                server.login(username, password)
            server.send_message(message)
