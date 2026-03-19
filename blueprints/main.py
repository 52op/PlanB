import os
from xml.sax.saxutils import escape

from flask import Blueprint, Response, flash, render_template, request, redirect, url_for, abort, current_app, send_from_directory
from flask_login import current_user

from models import DocumentViewStat, SystemSetting, db
from services import (
    get_adjacent_posts,
    InvalidPathError,
    check_global_access,
    check_permission,
    can_delete_comment,
    can_edit_comment,
    comments_enabled,
    create_comment,
    delete_comment,
    get_all_tags,
    get_archive_groups,
    get_comments_for_filename,
    get_default_file_for_dir,
    get_directory_articles,
    get_document_payload,
    get_docs_root,
    get_flat_files_list,
    get_markdown_files,
    get_post_by_slug,
    get_posts,
    get_public_post_tree,
    get_safe_redirect_target,
    has_valid_global_access_cookie,
    paginate_posts,
    search_posts,
    get_tag_posts,
    resolve_docs_path,
    update_comment,
)


main_bp = Blueprint('main', __name__, template_folder='templates')


def _get_blog_theme():
    """获取当前博客主题配置 - 优先从数据库读取，其次从配置文件"""
    # 优先从数据库读取
    from models import SystemSetting
    theme = SystemSetting.get('blog_theme')
    
    # 如果数据库没有，从配置文件读取
    if not theme:
        config = current_app.config.get('APP_CONFIG', {})
        theme = config.get('blog_theme', 'default')
    
    # 验证主题是否有效
    valid_themes = ['default', 'indigo', 'hexo']
    return theme if theme in valid_themes else 'default'


def _get_template_name(base_name):
    """根据主题获取模板名称"""
    theme = _get_blog_theme()
    if theme == 'hexo':
        return f"{base_name}_hexo.html"
    elif theme == 'indigo':
        return f"{base_name}_indigo.html"
    # default 主题使用原始模板名
    return f"{base_name}.html"


def _absolute_url(path_or_url):
    value = str(path_or_url or '').strip()
    if not value:
        return request.url_root.rstrip('/')
    if value.startswith('http://') or value.startswith('https://'):
        return value
    return f"{request.url_root.rstrip('/')}/{value.lstrip('/')}"


def _get_site_settings():
    blog_home_count = SystemSetting.get('blog_home_count', '12') or '12'
    try:
        blog_home_count = int(blog_home_count)
    except (TypeError, ValueError):
        blog_home_count = 12

    site_mode = (SystemSetting.get('site_mode', 'blog') or 'blog').strip() or 'blog'
    blog_enabled = (SystemSetting.get('blog_enabled', 'true') or 'true').strip().lower() != 'false'
    show_docs_entry_in_blog = (SystemSetting.get('show_docs_entry_in_blog', 'true') or 'true').strip().lower() != 'false'

    return {
        'site_name': SystemSetting.get('site_name', 'Planning') or 'Planning',
        'site_tagline': SystemSetting.get('site_tagline', '轻量 Markdown 内容站') or '轻量 Markdown 内容站',
        'home_title': SystemSetting.get('home_title', '') or '',
        'home_description': SystemSetting.get('home_description', '') or '',
        'footer_html': SystemSetting.get('footer_html', '') or '',
        'home_default_type': SystemSetting.get('home_default_type', '') or '',
        'home_default_target': SystemSetting.get('home_default_target', '') or '',
        'blog_home_count': max(blog_home_count, 0),
        'default_theme_color': SystemSetting.get('default_theme_color', 'blue') or 'blue',
        'default_theme_mode': SystemSetting.get('default_theme_mode', 'light') or 'light',
        'allow_user_theme_override': SystemSetting.get('allow_user_theme_override', 'true') or 'true',
        'site_mode': site_mode if site_mode in ('blog', 'docs') else 'blog',
        'blog_enabled': blog_enabled,
        'show_docs_entry_in_blog': show_docs_entry_in_blog,
    }


def _get_docs_endpoint(filename=None, dirname=None):
    if filename is not None:
        return url_for('main.docs_doc', filename=filename)
    if dirname is not None:
        normalized_dir = (dirname or '').strip('/')
        return url_for('main.docs_dir', dirname=normalized_dir) if normalized_dir else url_for('main.docs_home')
    return url_for('main.docs_home')


def _blog_enabled(site_settings=None):
    settings = site_settings or _get_site_settings()
    return bool(settings.get('blog_enabled'))


def _abort_if_blog_disabled(site_settings=None):
    if not _blog_enabled(site_settings):
        abort(404)


def _docs_access_blocked():
    access_mode = SystemSetting.get('access_mode', 'open')
    if access_mode == 'group_only':
        return not bool(getattr(current_user, 'is_authenticated', False))
    if access_mode == 'password_only':
        global_pwd = SystemSetting.get('global_password', '')
        return bool(global_pwd and not getattr(current_user, 'is_authenticated', False) and not has_valid_global_access_cookie())
    return False


def _comment_redirect_target(default_target):
    target = get_safe_redirect_target(request.form.get('return_to') or request.referrer or default_target)
    return target if '#comments' in target else f'{target}#comments'


def _render_archive_listing(file_tree, include_private=False):
    site_settings = _get_site_settings()
    return render_template(
        _get_template_name('archive'),
        file_tree=file_tree,
        current_file=None,
        current_dir='',
        content='',
        toc='',
        config=current_app.config.get('APP_CONFIG', {}),
        can_edit=False,
        can_upload=False,
        archive_groups=get_archive_groups(include_private=include_private),
        tags=get_all_tags(include_private=include_private)[:18],
        site_settings=site_settings,
        page_meta={'title': '文章归档'},
        page_title='文章归档',
        page_description='按时间线回看所有公开发布的文章。',
        page_mode='archive',
        absolute_url=_absolute_url,
    )


def _render_blog_post(filename, file_tree=None, include_private=False):
    if file_tree is None:
        file_tree = get_public_post_tree(include_private=include_private)

    payload = get_document_payload(filename)
    if payload is None:
        abort(404)

    page_meta = payload.get('metadata') or {}
    if page_meta.get('template') != 'post':
        abort(404)

    content_html = payload.get('html') or ''
    toc_html = payload.get('toc') or ''
    current_file = payload.get('filename') or filename
    previous_post, next_post = get_adjacent_posts(current_file, include_private=include_private)

    stat = DocumentViewStat.query.get(current_file)
    if not stat:
        stat = DocumentViewStat()
        stat.filename = current_file
        stat.view_count = 0
        db.session.add(stat)
    stat.view_count = int(stat.view_count or 0) + 1
    db.session.commit()
    page_meta['view_count'] = stat.view_count

    comments = get_comments_for_filename(current_file, include_pending=_is_comment_moderator()) if comments_enabled() else []
    comment_pagination = paginate_posts(comments, page=request.args.get('comment_page', 1, type=int), per_page=12) if comments else None

    if request.headers.get('X-Forwarded-Proto') == 'https':
        host = request.host
        content_html = content_html.replace(f'http://{host}', f'https://{host}')

    return render_template(
        _get_template_name('blog_post'),
        file_tree=file_tree,
        content=content_html,
        toc=toc_html,
        current_file=current_file,
        page_meta=page_meta,
        site_settings=_get_site_settings(),
        previous_post=previous_post,
        next_post=next_post,
        comments=comment_pagination['items'] if comment_pagination else comments,
        comment_pagination=comment_pagination,
        can_delete_comment=can_delete_comment,
        comments_enabled_flag=comments_enabled(),
        tags=get_all_tags(include_private=include_private)[:18],
        archive_groups=get_archive_groups(include_private=include_private)[:8],
        page_title=page_meta.get('title') or '文章详情',
        page_description=page_meta.get('summary') or page_meta.get('category_name') or '',
        page_mode='post',
        absolute_url=_absolute_url,
    )


def _render_homepage(file_tree, posts):
    site_settings = _get_site_settings()
    featured = posts[0] if posts else None
    recent_posts = posts[1:7] if len(posts) > 1 else []
    return render_template(
        _get_template_name('home'),
        file_tree=file_tree,
        featured_post=featured,
        posts=recent_posts,
        tags=get_all_tags()[:18],
        archive_groups=get_archive_groups()[:6],
        site_settings=site_settings,
        page_meta={
            'title': site_settings['home_title'] or site_settings['site_name'],
            'summary': site_settings['home_description'] or site_settings['site_tagline'],
            'cover': featured.get('cover') if featured else '',
        },
        page_title=site_settings['home_title'] or site_settings['site_name'],
        page_description=site_settings['home_description'] or site_settings['site_tagline'],
        absolute_url=_absolute_url,
    )


def _render_document(filename, file_tree=None, docs_endpoint='main.docs_doc'):
    if file_tree is None:
        file_tree = get_markdown_files()

    flat_files = get_flat_files_list(file_tree)
    if filename not in flat_files:
        abort(404)

    payload = get_document_payload(filename)
    if payload is None:
        abort(404)

    content_html = payload.get('html') or ''
    toc_html = payload.get('toc') or ''
    page_meta = payload.get('metadata') or {}
    current_file = payload.get('filename') or filename
    current_dir = os.path.dirname(current_file).replace('\\', '/')
    can_edit = check_permission(current_user, current_dir, 'edit')
    can_upload = check_permission(current_user, current_dir, 'upload')
    previous_post, next_post = get_adjacent_posts(current_file, include_private=bool(getattr(current_user, 'is_authenticated', False))) if page_meta.get('template') == 'post' else (None, None)

    if page_meta.get('template') == 'post':
        stat = DocumentViewStat.query.get(current_file)
        if not stat:
            stat = DocumentViewStat()
            stat.filename = current_file
            stat.view_count = 0
            db.session.add(stat)
        stat.view_count = int(stat.view_count or 0) + 1
        db.session.commit()
        page_meta['view_count'] = stat.view_count
    comments = get_comments_for_filename(current_file, include_pending=_is_comment_moderator()) if page_meta.get('template') == 'post' and comments_enabled() else []
    comment_pagination = paginate_posts(comments, page=request.args.get('comment_page', 1, type=int), per_page=12) if comments else None

    if request.headers.get('X-Forwarded-Proto') == 'https':
        host = request.host
        content_html = content_html.replace(f'http://{host}', f'https://{host}')

    return render_template(
        'index.html',
        file_tree=file_tree,
        current_file=current_file,
        current_dir=current_dir,
        content=content_html,
        toc=toc_html,
        config=current_app.config.get('APP_CONFIG', {}),
        can_edit=can_edit,
        can_upload=can_upload,
        previous_post=previous_post,
        next_post=next_post,
        comments=comment_pagination['items'] if comment_pagination else comments,
        comment_pagination=comment_pagination,
        can_delete_comment=can_delete_comment,
        page_meta=page_meta,
        site_settings=_get_site_settings(),
        page_mode='doc',
        absolute_url=_absolute_url,
        comments_enabled_flag=comments_enabled(),
        docs_endpoint=docs_endpoint,
    )


def _is_comment_moderator():
    return bool(getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', '') == 'admin')


def _render_blog_listing(title, posts, file_tree, category_path='', empty_message='', include_private=False):
    site_settings = _get_site_settings()
    normalized_category = (category_path or '').replace('\\', '/').strip('/')
    category_name = os.path.basename(normalized_category) if normalized_category else ''
    category_name = category_name.replace('-', ' ').replace('_', ' ').strip()

    if not posts and empty_message:
        posts = []

    post_url_map = {}
    for post in get_posts(include_private=include_private):
        filename = (post.get('filename') or '').strip()
        if filename:
            post_url_map[filename] = post.get('url') or url_for('main.post_detail', slug=post.get('slug'))

    page = request.args.get('page', 1, type=int)
    pagination = paginate_posts(posts, page=page, per_page=12)
    endpoint = request.endpoint or 'main.posts'
    pagination_base_args = dict(request.view_args or {})
    extra_args = {}
    if endpoint == 'main.search' and request.args.get('q'):
        extra_args['q'] = request.args.get('q')
    pagination['prev_url'] = url_for(endpoint, **pagination_base_args, **extra_args, page=pagination['prev_page']) if pagination['has_prev'] else ''
    pagination['next_url'] = url_for(endpoint, **pagination_base_args, **extra_args, page=pagination['next_page']) if pagination['has_next'] else ''

    return render_template(
        _get_template_name('blog_list'),
        file_tree=file_tree,
        current_file=None,
        current_dir=normalized_category,
        content='',
        toc='',
        config=current_app.config.get('APP_CONFIG', {}),
        can_edit=False,
        can_upload=False,
        posts=pagination['items'],
        category_path=normalized_category,
        category_name=category_name,
        page_title=title,
        site_settings=site_settings,
        empty_message=empty_message,
        tags=get_all_tags(include_private=include_private)[:18],
        archive_groups=get_archive_groups(include_private=include_private)[:8],
        page_meta={'title': title},
        page_description=empty_message if not posts else '公开发布的文章列表。',
        page_mode='posts',
        search_query='',
        absolute_url=_absolute_url,
        pagination=pagination,
        post_url_map=post_url_map,
    )


@main_bp.route('/')
def index():
    site_settings = _get_site_settings()
    
    # 只有当站点模式是文档模式时，才检查访问控制
    if site_settings['site_mode'] == 'docs':
        docs_locked = _docs_access_blocked()
        if docs_locked:
            access_redirect = check_global_access()
            if access_redirect:
                return access_redirect
    
    docs_root = get_docs_root()
    file_tree = get_markdown_files()
    home_type = site_settings['home_default_type']
    home_target = site_settings['home_default_target']
    blog_home_count = site_settings['blog_home_count'] or 12

    # 文档模式：显示文档首页
    if site_settings['site_mode'] == 'docs':
        default_file = get_default_file_for_dir(docs_root, '')
        if default_file:
            return _render_document(default_file, file_tree=file_tree)
        return docs_dir('')

    # 博客模式：显示博客首页
    if not _blog_enabled(site_settings):
        return redirect(url_for('main.docs_home'))

    if home_type == 'dir':
        try:
            _, home_dir, abs_dir = resolve_docs_path(home_target, allow_directory=True)
        except InvalidPathError:
            home_dir = ''
            abs_dir = None

        if abs_dir and os.path.isdir(abs_dir):
            posts = get_directory_articles(home_dir)
            if posts:
                title = '最新文章' if not home_dir else f'分类：{os.path.basename(home_dir)}'
                return _render_blog_listing(title, posts, get_public_post_tree(), category_path=home_dir)

    posts = get_posts(limit=blog_home_count)
    if posts:
        return _render_homepage(get_public_post_tree(), posts)

    return redirect(url_for('main.docs_home'))


@main_bp.route('/docs')
def docs_home():
    access_redirect = check_global_access()
    if access_redirect:
        return access_redirect

    docs_root = get_docs_root()
    file_tree = get_markdown_files()
    default_file = get_default_file_for_dir(docs_root, '')
    if default_file:
        return _render_document(default_file, file_tree=file_tree)
    return docs_dir('')


@main_bp.route('/posts')
def posts():
    site_settings = _get_site_settings()
    _abort_if_blog_disabled(site_settings)
    include_private = bool(getattr(current_user, 'is_authenticated', False))
    file_tree = get_public_post_tree(include_private=include_private)
    return _render_blog_listing(
        '全部文章',
        get_posts(include_private=include_private),
        file_tree,
        empty_message='当前还没有已发布的文章。',
        include_private=include_private,
    )


@main_bp.route('/tags/<tag_name>')
def tag(tag_name):
    site_settings = _get_site_settings()
    _abort_if_blog_disabled(site_settings)
    include_private = bool(getattr(current_user, 'is_authenticated', False))
    file_tree = get_public_post_tree(include_private=include_private)
    return _render_blog_listing(
        f'标签：{tag_name}',
        get_tag_posts(tag_name, include_private=include_private),
        file_tree,
        empty_message='当前标签下还没有已发布的文章。',
        include_private=include_private,
    )


@main_bp.route('/archive')
def archive():
    site_settings = _get_site_settings()
    _abort_if_blog_disabled(site_settings)
    include_private = bool(getattr(current_user, 'is_authenticated', False))
    file_tree = get_public_post_tree(include_private=include_private)
    return _render_archive_listing(file_tree, include_private=include_private)


@main_bp.route('/tags')
def tags_page():
    site_settings = _get_site_settings()
    _abort_if_blog_disabled(site_settings)
    include_private = bool(getattr(current_user, 'is_authenticated', False))
    file_tree = get_public_post_tree(include_private=include_private)
    all_tags = get_all_tags(include_private=include_private)
    
    return render_template(
        _get_template_name('tags'),
        file_tree=file_tree,
        tags=all_tags,
        site_settings=site_settings,
        page_title='标签',
        page_description='浏览所有标签',
        page_meta={'title': '标签'},
        archive_groups=get_archive_groups(include_private=include_private)[:8],
        absolute_url=_absolute_url,
    )


@main_bp.route('/category/', defaults={'dirname': ''})
@main_bp.route('/category/<path:dirname>')
def category(dirname):
    site_settings = _get_site_settings()
    _abort_if_blog_disabled(site_settings)
    include_private = bool(getattr(current_user, 'is_authenticated', False))
    file_tree = get_public_post_tree(include_private=include_private)
    try:
        _, dirname, target_dir = resolve_docs_path(dirname, allow_directory=True)
    except InvalidPathError:
        abort(404)

    if not os.path.isdir(target_dir):
        abort(404)

    category_title = '全部分类文章' if not dirname else f'分类：{os.path.basename(dirname)}'
    return _render_blog_listing(
        category_title,
        get_posts(category_path=dirname, include_private=include_private),
        file_tree,
        category_path=dirname,
        empty_message='当前分类下还没有已发布的文章。',
        include_private=include_private,
    )


@main_bp.route('/post/<slug>')
def post_detail(slug):
    site_settings = _get_site_settings()
    _abort_if_blog_disabled(site_settings)
    include_private = bool(getattr(current_user, 'is_authenticated', False))
    payload = get_post_by_slug(slug, include_private=include_private)
    if payload is None:
        abort(404)
    return _render_blog_post(payload['filename'], file_tree=get_public_post_tree(include_private=include_private), include_private=include_private)


@main_bp.route('/search')
def search():
    site_settings = _get_site_settings()
    _abort_if_blog_disabled(site_settings)
    include_private = bool(getattr(current_user, 'is_authenticated', False))
    query = (request.args.get('q') or '').strip()
    file_tree = get_public_post_tree(include_private=include_private)
    results = search_posts(query, include_private=include_private) if query else []
    post_url_map = {}
    for post in get_posts(include_private=include_private):
        filename = (post.get('filename') or '').strip()
        if filename:
            post_url_map[filename] = post.get('url') or url_for('main.post_detail', slug=post.get('slug'))
    pagination = paginate_posts(results, page=request.args.get('page', 1, type=int), per_page=12)
    pagination['prev_url'] = url_for('main.search', q=query, page=pagination['prev_page']) if pagination['has_prev'] else ''
    pagination['next_url'] = url_for('main.search', q=query, page=pagination['next_page']) if pagination['has_next'] else ''
    return render_template(
        _get_template_name('blog_list'),
        file_tree=file_tree,
        current_file=None,
        current_dir='',
        content='',
        toc='',
        config=current_app.config.get('APP_CONFIG', {}),
        can_edit=False,
        can_upload=False,
        posts=pagination['items'],
        category_path='',
        category_name='',
        page_title='搜索文章',
        site_settings=_get_site_settings(),
        empty_message=f'没有搜索到与“{query}”匹配的公开文章。' if query else '输入关键词后即可搜索公开文章。',
        tags=get_all_tags(include_private=include_private)[:18],
        archive_groups=get_archive_groups(include_private=include_private)[:8],
        page_meta={'title': '搜索文章'},
        page_description='搜索公开发布的文章内容。',
        page_mode='posts',
        search_query=query,
        absolute_url=_absolute_url,
        pagination=pagination,
        post_url_map=post_url_map,
    )


@main_bp.route('/rss.xml')
def rss_feed():
    site_settings = _get_site_settings()
    _abort_if_blog_disabled(site_settings)
    posts = get_posts(limit=30, include_private=False)
    channel_link = _absolute_url(url_for('main.posts'))

    items = []
    for post in posts:
        item_link = _absolute_url(post.get('url'))
        items.append(
            f"<item><title>{escape(post.get('title', 'Untitled'))}</title>"
            f"<link>{escape(item_link)}</link>"
            f"<guid>{escape(item_link)}</guid>"
            f"<description>{escape(post.get('summary', ''))}</description>"
            f"<category>{escape(post.get('category_name', ''))}</category>"
            f"<pubDate>{escape(post.get('updated') or post.get('date') or '')}</pubDate></item>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f'<title>{escape(site_settings["site_name"])}</title>'
        f'<link>{escape(channel_link)}</link>'
        f'<description>{escape(site_settings["site_tagline"])}</description>'
        f'{"".join(items)}'
        '</channel></rss>'
    )
    return Response(xml, mimetype='application/rss+xml')


@main_bp.route('/sitemap.xml')
def sitemap():
    site_settings = _get_site_settings()
    urls = {
        _absolute_url(url_for('main.index')),
        _absolute_url(url_for('main.docs_home')),
    }
    if _blog_enabled(site_settings):
        urls.update({
            _absolute_url(url_for('main.posts')),
            _absolute_url(url_for('main.archive')),
            _absolute_url(url_for('main.search')),
            _absolute_url(url_for('main.rss_feed')),
        })
        for post in get_posts(include_private=False):
            urls.add(_absolute_url(post.get('url')))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for item in sorted(urls):
        xml.append(f'<url><loc>{escape(item)}</loc></url>')
    xml.append('</urlset>')
    return Response(''.join(xml), mimetype='application/xml')


@main_bp.route('/docs/doc/<path:filename>')
def docs_doc(filename):
    access_redirect = check_global_access()
    if access_redirect:
        return access_redirect

    return _render_document(filename, docs_endpoint='main.docs_doc')


@main_bp.route('/doc/<path:filename>')
def doc(filename):
    access_redirect = check_global_access()
    if access_redirect:
        return access_redirect

    return redirect(_get_docs_endpoint(filename=filename))


@main_bp.route('/comment/<path:filename>', methods=['POST'])
def post_comment(filename):
    # 评论功能不受访问控制限制（博客文章的评论是公开的）
    if not comments_enabled():
        flash('评论功能当前未开启')
        return redirect(_comment_redirect_target(_get_docs_endpoint(filename=filename)))
    try:
        article_path = get_safe_redirect_target(request.form.get('return_to') or request.referrer or _get_docs_endpoint(filename=filename))
        article_url = request.url_root.rstrip('/') + article_path
        create_comment(filename, request.form.get('content', ''), parent_id=request.form.get('parent_id'), article_url=article_url)
        flash('评论已提交' + ('，等待审核' if getattr(current_user, 'role', '') == 'guest' else ''))
    except (PermissionError, ValueError) as exc:
        flash(str(exc))
    return redirect(_comment_redirect_target(_get_docs_endpoint(filename=filename)))


@main_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
def remove_comment(comment_id):
    # 评论功能不受访问控制限制（博客文章的评论是公开的）
    from models import Comment

    comment = Comment.query.get(comment_id)
    if not comment:
        abort(404)
    try:
        delete_comment(comment)
        flash('评论已删除')
    except PermissionError as exc:
        flash(str(exc))
    return redirect(_comment_redirect_target(_get_docs_endpoint(filename=comment.filename)))


@main_bp.route('/comment/<int:comment_id>/edit', methods=['POST'])
def edit_comment(comment_id):
    # 评论功能不受访问控制限制（博客文章的评论是公开的）
    from models import Comment

    comment = Comment.query.get(comment_id)
    if not comment:
        abort(404)
    try:
        update_comment(comment, request.form.get('content', ''))
        flash('评论已更新' + ('，等待重新审核' if getattr(current_user, 'role', '') != 'admin' else ''))
    except (PermissionError, ValueError) as exc:
        flash(str(exc))
    return redirect(_comment_redirect_target(_get_docs_endpoint(filename=comment.filename)))


@main_bp.route('/comment/approve/<token>')
def approve_comment(token):
    """通过审核令牌批准评论"""
    from models import Comment
    
    if not token:
        abort(404)
    
    comment = Comment.query.filter_by(approval_token=token).first()
    if not comment:
        abort(404)
    
    # 检查评论状态
    if comment.status == 'approved':
        flash('该评论已经审核通过')
    elif comment.status == 'deleted':
        flash('该评论已被删除')
    else:
        # 审核通过
        comment.status = 'approved'
        db.session.commit()
        flash('评论已审核通过')
    
    # 重定向到文章页面
    site_settings = _get_site_settings()
    if _blog_enabled(site_settings):
        # 尝试获取文章的 slug
        payload = get_document_payload(comment.filename)
        if payload and payload.get('metadata', {}).get('slug'):
            return redirect(url_for('main.post_detail', slug=payload['metadata']['slug']) + '#comments')
    
    # 如果无法获取 slug，重定向到文档页面
    return redirect(_get_docs_endpoint(filename=comment.filename) + '#comments')


@main_bp.route('/docs/dir/', defaults={'dirname': ''})
@main_bp.route('/docs/dir/<path:dirname>')
def docs_dir(dirname):
    access_redirect = check_global_access()
    if access_redirect:
        return access_redirect

    file_tree = get_markdown_files()
    docs_root = get_docs_root()
    try:
        _, dirname, target_dir = resolve_docs_path(dirname, allow_directory=True)
    except InvalidPathError:
        abort(404)

    if not os.path.isdir(target_dir):
        abort(404)

    default_file = get_default_file_for_dir(docs_root, dirname)
    if default_file:
        return redirect(_get_docs_endpoint(filename=default_file))

    can_upload = check_permission(current_user, dirname, 'upload')
    site_settings = _get_site_settings()
    content_html = '<h3>您选中了目录【{0}】</h3><p>如果您拥有权限，可以通过右上角的菜单向此目录上传 .md 文件。</p>'.format(dirname or '/')
    return render_template(
        'index.html',
        file_tree=file_tree,
        current_file=None,
        current_dir=dirname,
        content=content_html,
        toc='',
        config=current_app.config.get('APP_CONFIG', {}),
        can_edit=False,
        can_upload=can_upload,
        page_meta={'title': dirname or site_settings['site_name']},
        site_settings=site_settings,
        page_mode='directory',
        docs_endpoint='main.docs_doc',
    )


@main_bp.route('/dir/', defaults={'dirname': ''})
@main_bp.route('/dir/<path:dirname>')
def dir_view(dirname):
    access_redirect = check_global_access()
    if access_redirect:
        return access_redirect

    return redirect(_get_docs_endpoint(dirname=dirname))


@main_bp.route('/media/<path:filename>')
def media_file(filename):
    return send_from_directory(os.path.join(current_app.root_path, 'static', 'uploads'), filename)
