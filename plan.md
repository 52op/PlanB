# Planning - Flask Markdown CMS 项目规划

## 项目概述

Planning 是一个基于 Flask 的轻量级 Markdown 内容管理系统，支持文档管理、博客发布、评论系统、媒体上传、主题定制等功能。

## 核心功能

### 1. 文档管理系统
- **Markdown 编辑器**：Toast UI Editor，支持所见即所得和分栏预览双模式
- **文件树导航**：支持目录/文件的创建、重命名、删除操作
- **Front Matter 元数据**：支持 YAML 格式的文章元数据（标题、日期、标签、分类等）
- **实时预览**：编辑器内置实时预览功能
- **版本控制**：基于文件系统的 Markdown 文件存储

### 2. 博客系统
- **文章列表**：支持分页、标签筛选、分类筛选、搜索
- **文章详情**：支持封面图、摘要、标签、分类、发布日期
- **存档页面**：按年月分组展示文章
- **标签云**：展示所有标签及文章数量
- **分类导航**：基于目录结构的分类系统

### 3. 评论系统
- **用户注册/登录**：支持邮箱验证
- **评论发布**：支持 Markdown 格式评论
- **评论审核**：管理员可审核/删除评论
- **评论统计**：显示评论数量和用户统计

### 4. 媒体管理
- **图片上传**：支持拖拽上传、粘贴上传
- **视频上传**：支持 mp4/webm 格式
- **存储方式**：
  - 本地存储：保存到 `static/uploads/` 目录
  - S3 兼容存储：支持 AWS S3、MinIO、阿里云 OSS 等
- **媒体库管理**：查看已上传媒体、检测未使用的媒体文件
- **自动插入**：上传后自动在编辑器中插入 Markdown 语法

### 5. 主题定制系统 ✨ 新增
- **5 种颜色主题**：蓝色（专业）、绿色（自然）、紫色（创意）、橙色（活力）、玫瑰（优雅）
- **深色/浅色模式**：支持手动切换和跟随系统设置
- **主题持久化**：用户选择的主题保存在 localStorage
- **管理员配置**：可设置默认主题和显示模式
- **CSS 变量架构**：基于 CSS Custom Properties 实现主题切换

### 6. 权限管理
- **访问控制**：
  - 开放模式：所有人可访问
  - 群组模式：仅登录用户可访问
  - 密码模式：需要全局密码
- **目录级权限**：可为不同用户/目录设置读写权限
- **角色系统**：管理员、普通用户

### 7. 搜索功能
- **全文搜索**：搜索文章标题、内容、标签
- **实时搜索**：输入时实时显示搜索结果
- **搜索结果高亮**：关键词高亮显示

### 8. 邮件通知
- **SMTP 配置**：支持自定义 SMTP 服务器
- **邮件验证**：用户注册时发送验证邮件
- **评论通知**：新评论时通知管理员

## 技术架构

### 后端技术栈
- **框架**：Flask 3.x
- **数据库**：SQLite（通过 SQLAlchemy ORM）
- **认证**：Flask-Login
- **表单验证**：WTForms
- **Markdown 解析**：Python-Markdown + PyYAML
- **S3 上传**：boto3
- **邮件发送**：smtplib
- **生产服务器**：Waitress

### 前端技术栈
- **编辑器**：Toast UI Editor 3.x
- **图标库**：Lucide Icons
- **图片预览**：LightGallery
- **图表**：Chart.js
- **样式**：原生 CSS + CSS Variables（主题系统）
- **JavaScript**：原生 ES6+，模块化架构

### 前端架构
```
static/js/
├── app.js                      # 主应用类，协调所有模块
└── modules/
    ├── ui-utils.js             # UI 工具（对话框、提示、工具提示）
    ├── editor-manager.js       # Toast UI Editor 管理
    ├── file-operations.js      # 文件/目录 CRUD 操作
    ├── front-matter-utils.js   # Front Matter 元数据处理
    ├── image-utils.js          # 图片预览和上传
    ├── context-menu.js         # 右键菜单
    ├── search-manager.js       # 搜索功能
    ├── upload-manager.js       # 文件上传管理
    └── theme-manager.js        # 主题切换管理 ✨ 新增
```

### 后端架构
```
planning/
├── app.py                      # Flask 应用入口
├── models.py                   # 数据模型（User, Comment, SystemSetting, PermissionRule）
├── config.yaml                 # 应用配置文件
├── blueprints/                 # 路由蓝图
│   ├── main.py                 # 主路由（文档、博客）
│   ├── api.py                  # API 路由（保存、上传、媒体）
│   ├── auth.py                 # 认证路由（登录、注册）
│   └── admin.py                # 管理后台路由
├── services/                   # 业务逻辑层
│   ├── docs.py                 # 文档服务（解析、缓存、搜索）
│   ├── media.py                # 媒体服务（上传、S3）
│   ├── comments.py             # 评论服务
│   ├── mailer.py               # 邮件服务
│   ├── access.py               # 访问控制
│   ├── permissions.py          # 权限检查
│   ├── paths.py                # 路径处理
│   └── urls.py                 # URL 工具
├── templates/                  # Jinja2 模板
│   ├── index.html              # 主页面（文档/博客）
│   ├── login.html              # 登录页
│   ├── account.html            # 账户管理
│   └── admin.html              # 管理后台
└── static/                     # 静态资源
    ├── css/
    │   ├── themes.css          # 主题 CSS 变量 ✨ 新增
    │   └── modals.css          # 模态框样式
    ├── js/                     # JavaScript 模块
    ├── vendor/                 # 第三方库（本地化）
    └── uploads/                # 媒体上传目录
```

## 数据模型

### User（用户）
- `id`：主键
- `username`：用户名（唯一）
- `password_hash`：密码哈希
- `nickname`：昵称
- `avatar_url`：头像 URL
- `email`：邮箱
- `email_verified`：邮箱是否验证
- `role`：角色（admin/user）

### Comment（评论）
- `id`：主键
- `user_id`：用户 ID（外键）
- `filename`：关联的文档文件名
- `content`：评论内容（Markdown）
- `created_at`：创建时间
- `approved`：是否审核通过
- `parent_id`：父评论 ID（支持嵌套）

### SystemSetting（系统设置）
- `key`：设置键（主键）
- `value`：设置值

**主要配置项**：
- `docs_dir`：文档根目录
- `access_mode`：访问模式（open/group_only/password_only）
- `site_name`：站点名称
- `site_tagline`：站点标语
- `media_storage_type`：媒体存储类型（local/s3）
- `s3_*`：S3 配置（endpoint, bucket, access_key, secret_key, cdn_domain）
- `default_theme_color`：默认颜色主题 ✨ 新增
- `default_theme_mode`：默认显示模式 ✨ 新增
- `allow_user_theme_override`：允许用户自定义主题 ✨ 新增
- `comments_enabled`：是否启用评论
- `smtp_*`：SMTP 邮件配置

### PermissionRule（权限规则）
- `id`：主键
- `user_id`：用户 ID（外键）
- `dir_path`：目录路径
- `can_read`：可读权限
- `can_edit`：可编辑权限
- `can_upload`：可上传权限
- `can_delete`：可删除权限

## 性能优化

### 1. 文件缓存机制
- **问题**：每次请求都解析所有 Markdown 文件，导致页面加载慢（17+ 秒）
- **解决方案**：基于文件修改时间（mtime）的缓存机制
- **效果**：首次加载 10-20 秒，后续访问 <100ms（100-200 倍提升）
- **实现**：`services/docs.py` 中的 `_FILE_CACHE` 字典

### 2. CDN 资源本地化
- **问题**：外部 CDN 资源加载慢，影响页面渲染
- **解决方案**：将所有第三方库下载到 `static/vendor/` 目录
- **效果**：资源加载时间从 5-15 秒降至 <1 秒
- **资源**：Lucide Icons, Toast UI Editor, LightGallery, Chart.js

### 3. 生产服务器
- **开发模式**：Flask 内置服务器（`debug=true`）
- **生产模式**：Waitress WSGI 服务器（`debug=false`）
- **配置**：`config.yaml` 中的 `debug` 选项

## 主题系统详解 ✨

### CSS 变量架构
```css
:root {
  /* 颜色变量 */
  --color-primary: #0056b3;
  --color-primary-dark: #004494;
  --color-primary-light: #eaf4ff;
  --color-primary-medium: #d6ebff;

  /* 语义化颜色 */
  --color-background: #f4f6f9;
  --color-surface: #ffffff;
  --color-text: #1f2937;
  --color-text-muted: #6b7280;
  --color-border: #e6ebf1;
  --color-shadow: rgba(15, 79, 168, 0.08);
}

/* 深色模式 */
[data-theme="dark"] {
  --color-background: #1a1a1a;
  --color-surface: #2d2d2d;
  --color-text: #e5e5e5;
  /* ... */
}

/* 颜色主题 */
[data-theme-color="green"] {
  --color-primary: #059669;
  /* ... */
}
```

### 主题切换流程
1. 用户点击主题选择器
2. `theme-manager.js` 更新 `data-theme-color` 和 `data-theme` 属性
3. CSS 变量自动更新，页面颜色立即变化
4. 主题保存到 localStorage，下次访问自动应用

### 管理员配置
- 在 `/admin/` 后台设置默认主题
- 新用户首次访问时使用默认主题
- 用户可以覆盖默认主题（如果允许）

## API 接口

### 文档相关
- `GET /doc/<path:filename>`：查看文档
- `GET /api/get_raw`：获取文档原始内容
- `POST /api/save`：保存文档
- `POST /api/create_doc`：创建文档
- `POST /api/delete_doc`：删除文档
- `POST /api/rename_doc`：重命名文档
- `POST /api/create_dir`：创建目录
- `POST /api/delete_dir`：删除目录
- `POST /api/rename_dir`：重命名目录

### 媒体相关
- `POST /api/media_upload`：上传媒体文件
- `GET /api/media_list`：获取媒体列表
- `POST /api/media_delete`：删除媒体文件
- `GET /media/<path:filename>`：访问媒体文件

### 博客相关
- `GET /posts`：文章列表
- `GET /tags`：标签列表
- `GET /tag/<tag>`：按标签筛选
- `GET /category/<path:category>`：按分类筛选
- `GET /archive`：存档页面
- `GET /search`：搜索

### 评论相关
- `POST /api/comment`：发表评论
- `GET /api/comments/<filename>`：获取评论列表
- `POST /api/comment/delete`：删除评论
- `POST /api/comment/approve`：审核评论

### 认证相关
- `GET /login`：登录页面
- `POST /login`：登录处理
- `GET /logout`：登出
- `POST /register`：注册
- `POST /verify_email`：邮箱验证

### 管理相关
- `GET /admin/`：管理后台首页
- `POST /admin/settings`：更新系统设置
- `POST /admin/user/add`：添加用户
- `POST /admin/user/delete`：删除用户
- `POST /admin/permission/set`：设置权限

## 配置说明

### config.yaml
```yaml
port: 5002                    # 服务端口
debug: false                  # 调试模式（false 使用 Waitress）
database: planning.db         # SQLite 数据库文件
secret_key: your-secret-key   # Flask 密钥
force_https: false            # 是否强制 HTTPS
```

### SystemSetting 配置项
详见"数据模型"章节的 SystemSetting 部分。

## 部署指南

### 开发环境
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
python app.py
```

### 生产环境
1. 修改 `config.yaml`：`debug: false`
2. 设置环境变量：`PLANNING_ADMIN_INITIAL_PASSWORD`
3. 运行：`python app.py`（自动使用 Waitress）

详细部署说明见 [docs/DEPLOY.md](docs/DEPLOY.md)

## 文档索引

- [docs/architecture.md](docs/architecture.md) - 架构详细说明
- [docs/THEME_SYSTEM_COMPLETE.md](docs/THEME_SYSTEM_COMPLETE.md) - 主题系统实施文档
- [docs/SLOW_PAGE_FIX.md](docs/SLOW_PAGE_FIX.md) - 页面加载慢问题修复
- [docs/CDN_OPTIMIZATION_REPORT.md](docs/CDN_OPTIMIZATION_REPORT.md) - CDN 本地化报告
- [docs/PERFORMANCE.md](docs/PERFORMANCE.md) - 性能优化总结
- [docs/DEPLOY.md](docs/DEPLOY.md) - 部署指南

## 依赖清单

### Python 依赖（requirements.txt）
```
Flask>=3.0.0
Flask-Login>=0.6.3
SQLAlchemy>=2.0.0
Markdown>=3.5.0
PyYAML>=6.0.1
boto3>=1.34.0
waitress>=3.0.0
bleach>=6.1.0
WTForms>=3.1.0
```

### 前端依赖（CDN/本地）
- Toast UI Editor 3.x
- Lucide Icons 0.263.1
- LightGallery 2.x
- Chart.js 4.x

## 未来规划

### 短期计划
- [ ] 其他模板页面的主题适配（login.html, account.html 等）
- [ ] 主题预加载脚本，避免页面闪烁
- [ ] 主题预览功能
- [ ] 移动端响应式优化

### 中期计划
- [ ] 自定义主题编辑器
- [ ] 主题导出/导入功能
- [ ] 多语言支持（i18n）
- [ ] 文章草稿功能
- [ ] 定时发布功能

### 长期计划
- [ ] 插件系统
- [ ] API 文档（Swagger/OpenAPI）
- [ ] 数据库迁移工具
- [ ] 全文搜索引擎（Elasticsearch）
- [ ] 静态站点生成器

## 更新日志

### 2026-03-17
- 🧩 登录页/账户页站点信息（站点名称/副标题/首页标题等）与后台设置保持一致
- 🧹 编辑器保存后不再触发浏览器原生“重新加载此网站？”离开提醒（移除 reload 行为）
- 🎛️ 通知日志页(/admin/notifications) 复用统一后台布局样式（admin.html）
- 📝 整理项目文档到 docs 目录

### 2026-03-17（早期）
- ⚡ 实施文件缓存机制，解决页面加载慢问题
- ⚡ CDN 资源本地化，提升资源加载速度
- 🔧 添加 Waitress 生产服务器支持

### 2026-03-16
- 🎉 项目初始化
- ✨ 实现 Toast UI Editor 集成
- ✨ 实现媒体上传功能（本地 + S3）
- ✨ 实现评论系统
- ✨ 实现权限管理系统

---

**注意**：本文档会随着项目功能的增加和改动持续更新。
