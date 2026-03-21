# Planning

一个基于 Flask 的 Markdown 文档与博客一体化内容管理系统。

项目同时支持：

- 文档中心：目录树浏览、Markdown 编辑、WYSIWYG 编辑、Front Matter、图片上传、目录权限控制
- 博客系统：文章列表、分类、标签、归档、评论、RSS、Sitemap、SEO 结构化数据、多套主题
- 分享能力：文档或目录分享、有效期、密码、可编辑权限、二维码访问
- 管理后台：基础设置、安全设置、图片管理、用户管理、评论管理、博客文章管理
- 单文件打包：支持打包为 Windows 单文件 `exe`

---

## 主要特性

- Markdown 文档系统
- 博客与文档双模式站点
- 文档 Front Matter 管理
- 博客 5 套主题
  - Default
  - Indigo
  - Hexo
  - Astro
  - Vercel
- 图片上传与媒体库管理
- 站点 Logo 上传、媒体库选择、引用追踪
- 文档与目录分享
- 评论系统与最新评论
- 邮件验证码注册/登录/邮箱变更
- 后台安全限流
- SEO 支持
  - `robots.txt`
  - `sitemap.xml`
  - `rss.xml`
  - Open Graph / Twitter Meta
  - JSON-LD 结构化数据

---

## 技术栈

- Python 3.12
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF
- Markdown
- Pillow
- Waitress
- SQLite

可选能力：

- boto3：对象存储
- redis：限流后端

---

## 目录结构

```text
planning/
  app.py
  models.py
  runtime_paths.py
  blueprints/
  services/
  static/
  templates/
  requirements.txt
  planning.spec
  build_onefile.bat
  data/
    config.yaml
    app.db
    jobs/
    uploads/
    covers/
```

说明：

- `static/` 和 `templates/` 属于程序资源
- `data/` 属于运行时数据
- 当前版本运行时配置、数据库、上传文件、文档目录、封面目录都走 `data/`

---

## 运行时数据目录

程序启动后会自动创建 `data/` 目录。

默认结构：

```text
data/
  config.yaml
  app.db
  jobs/
  uploads/
    avatars/
    logo/
    2026/03/...
  covers/
```

含义：

- `data/config.yaml`：运行时配置文件
- `data/app.db`：SQLite 数据库
- `data/jobs`：文档根目录
- `data/uploads`：上传图片、头像、Logo
- `data/covers`：本地随机封面目录

说明：

- 当前版本默认不再使用项目根目录下旧的 `config.yaml`
- 如果你看到仓库根目录还存在旧 `config.yaml`，它通常只是历史文件，不是当前运行主配置

---

## 快速开始

### 1. 创建虚拟环境

```powershell
python -m venv venv
venv\Scripts\activate
```

Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动项目

Windows:

```powershell
python app.py
```

或直接使用项目自带脚本：

```powershell
start.bat
```

Linux:

```bash
python app.py
```

---

## 首次启动说明

首次启动时，程序会自动：

- 创建 `data/` 目录
- 创建 `data/config.yaml`
- 创建 `data/app.db`
- 初始化系统设置
- 创建默认 `admin` 账号

如果数据库里还没有 `admin` 用户，程序会：

- 自动创建 `admin`
- 自动生成一条初始密码
- 把密码打印到控制台

请在首次登录后尽快修改密码。

---

## 管理员密码重置

为了防止首次密码没记住，或者管理员忘记密码，可以使用 `.changepassword` 机制。

使用方法：

1. 在程序运行文件同目录创建一个名为 `.changepassword` 的空文件
2. 重新启动程序
3. 程序会自动重置 `admin` 密码并把新密码打印到控制台
4. 处理完成后，`.changepassword` 会自动删除

规则：

- 如果 `admin` 不存在，会先创建 `admin`，再打印新密码
- 如果 `admin` 已存在，只会重置密码

注意：

- 这个机制依赖控制台输出
- 因此当前单文件打包版本默认保留控制台窗口

---

## 配置文件

当前运行配置文件位置：

```text
data/config.yaml
```

一个典型示例：

```yaml
port: 5000
debug: false
database_path: ''
secret_key: 'replace-with-your-own-secret'
timezone: Asia/Shanghai
force_https_for_external_urls: true
```

说明：

- `debug`
  - 源码模式首次运行默认 `true`
  - 单文件打包版首次运行默认 `false`
- `database_path`
  - 留空时默认使用 `data/app.db`
- `secret_key`
  - 生产环境建议自行替换为稳定值
- `timezone`
  - 默认 `Asia/Shanghai`

---

## 主要页面

前台：

- `/`
  - 根据站点模式跳到博客首页或文档首页
- `/blog`
  - 博客首页
- `/posts`
  - 文章列表
- `/category/`
  - 分类页
- `/archive`
  - 归档页
- `/tags`
  - 标签页
- `/post/<slug>`
  - 文章详情页
- `/docs`
  - 文档首页
- `/docs/doc/<path:filename>`
  - 文档详情
- `/share/<token>`
  - 分享页

后台与账户：

- `/login`
- `/account`
- `/admin/`
  - 数据看板
- `/admin/base`
  - 基础设置
- `/admin/security`
  - 安全设置
- `/admin/images`
  - 图片管理
- `/admin/users`
  - 用户管理
- `/manage-posts`
  - 博客文章管理

SEO 与订阅：

- `/rss.xml`
- `/robots.txt`
- `/sitemap.xml`

---

## 图片与媒体

上传图片统一通过 `/media/...` 路由访问。

目录规则：

- 普通文档图片：`data/uploads/YYYY/MM/...`
- 用户头像：`data/uploads/avatars/...`
- 站点 Logo：`data/uploads/logo/...`

说明：

- 图片管理会追踪图片是否正在被引用
- 站点 Logo 也会被计入引用状态
- Logo 图片会显示 `Logo` 用途标记，避免误删

---

## 文档与博客关系

文档通过 Front Matter 控制是否作为博客文章展示。

常见字段：

- `title`
- `date`
- `updated`
- `summary`
- `cover`
- `template`
  - `post` 表示博客文章
  - `doc` 表示普通文档
- `public`
- `draft`
- `slug`
- `tags`

说明：

- `template=post` 的文档可以进入博客流
- 是否公开、是否显示在博客、详情权限等逻辑均由头部信息控制

---

## 分享功能

支持对文档或目录创建分享链接，并可配置：

- 是否加密
- 是否允许编辑
- 有效期限

分享页支持：

- 二维码访问
- Markdown 内容展示
- 图片预览
- 有权限时在线编辑

---

## 后台能力

目前后台主要包括：

- 数据看板
- 基础设置
- 安全设置
- 图片管理
- 用户管理
- 评论管理
- 博客文章管理
- 通知日志

---

## 安全相关

项目已包含以下基础安全能力：

- 登录限流
- 验证码发送限流
- 验证码校验限流
- 数据库存储型限流
- Redis 可选限流后端
- Session Cookie 安全选项

---

## 单文件打包

当前项目已适配单文件打包。

已提供文件：

- `[planning.spec](./planning.spec)`
- `[build_onefile.bat](./build_onefile.bat)`

Windows 下打包：

```powershell
build_onefile.bat
```

打包完成后生成：

```text
dist/planning.exe
```

特点：

- 首次运行自动创建 `dist/data/`
- 首次运行自动生成 `dist/data/config.yaml`
- 首次运行自动生成 `dist/data/app.db`
- 支持 `.changepassword` 重置管理员密码

说明：

- 当前打包方案默认保留控制台窗口
- 这样可以看到首次管理员密码和重置密码输出

---

## Linux 部署建议

如果部署到 Linux 服务器，更推荐源码运行，而不是打包成 Linux 二进制。

推荐方式：

- `venv`
- `pip install -r requirements.txt`
- `python app.py`
- 生产环境使用 `waitress`
- 由 `systemd` 托管
- `nginx` 做反向代理

不优先推荐 Linux 单文件二进制的原因：

- 排错不如源码直观
- 兼容性不如源码稳定
- 服务端长期维护成本更高

---

## 开发说明

### 安装依赖

```bash
pip install -r requirements.txt
```

### 常用命令

启动：

```bash
python app.py
```

语法检查：

```bash
python -m py_compile app.py models.py
```

打包：

```bash
build_onefile.bat
```

---

## 注意事项

- 当前运行主配置是 `data/config.yaml`
- 单文件打包版同样使用外部 `data/` 目录保存数据
- 如果你清空 `data/`，程序会按首次启动逻辑重新初始化
- 如果忘记 `admin` 密码，优先使用 `.changepassword`
- 生产环境务必替换 `secret_key`

---

## 后续建议

后续如果继续演进，比较值得做的方向有：

- 完整 Linux `systemd + nginx` 部署文档
- Docker 部署方案
- 自动备份 `data/` 目录
- 日志输出与轮转
- 数据库从 SQLite 迁移到 MySQL/PostgreSQL 的可选方案

