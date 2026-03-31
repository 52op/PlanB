# PlanB

PlanB 是一个基于 Flask 的 Markdown 文档中心与博客一体化系统。

它最初只是一个“展示工作计划”的小项目，后来一路长歪：

- 先是加上了文档目录浏览和 Markdown 编辑
- 然后又补上了 Front Matter、图片上传、权限控制
- 再后来又把文档一键发布成博客文章、加上分享、评论、SEO

最后它就变成了一个偏轻量、偏实用的“文档中心 + 博客系统 + 分享能力”的综合体。

也正因为它不是最初那个 A 计划的样子，而是一路演化出来的 B 计划产物，所以它叫 **PlanB**。

如果你喜欢 Trilium 这类“文档整理 + 内容发布”的方向，但又希望它更简单、更直接、更适合个人或小团队自托管，那么 PlanB 可能会比较对味。

---

## 它现在能做什么

PlanB 目前同时覆盖三类使用场景：

- 文档中心
  - Markdown 文档浏览
  - 目录树导航
  - 在线正文编辑
  - Front Matter 头部管理
  - 文档上传、重命名、删除
- 博客系统
  - 文档一键切换为博客文章
  - 分类、标签、归档
  - RSS、Sitemap、SEO 元数据
  - 多套博客主题
- 访问与协作
  - 用户目录权限规则
  - 固定密码访问模式
  - 固定密码白名单访问规则
  - 文档/目录分享链接
  - 可选密码、有效期、可编辑分享

它的定位不是“大而全 CMS”，而是一个更偏内容管理与发布的轻量系统。

---

## 主要特性

- Markdown 文档中心
- 博客与文档双模式站点
- Front Matter 可视化管理
- 博客文章管理工作台
- 文档与目录分享
- 评论系统
- 图片上传与媒体库
- 用户、访客、管理员权限体系
- 固定密码访问模式
- 固定密码白名单只读访问
- 目录级权限控制
- 细粒度管理权限
  - 允许读取
  - 允许编辑
  - 允许上传
  - 允许删除
  - 允许管理
- 博客 5 套主题
  - Default
  - Indigo
  - Hexo
  - Astro
  - Vercel
- SEO 支持
  - `robots.txt`
  - `sitemap.xml`
  - `rss.xml`
  - Open Graph / Twitter Meta
  - JSON-LD 结构化数据
- Windows 单文件打包

---

## 适合什么场景

- 个人知识库，同时想顺手把部分内容公开成博客
- 团队内部文档站，同时保留临时外部访问能力
- 用 Markdown 管理内容，但不想拆成“文档系统”和“博客系统”两套工具
- 想要一个比传统 CMS 更轻、更接近文件系统管理习惯的内容站

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

- `boto3`：对象存储
- `redis`：限流后端

---

## 项目结构

```text
planb/
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

- `static/` 和 `templates/` 是程序资源
- `data/` 是运行时数据目录
- 当前运行时配置、数据库、上传文件、文档目录、封面目录都集中在 `data/`

---

## 一个需要说明的命名细节

仓库名现在叫 **PlanB**，但项目内部仍保留了一部分早期命名：

- 目录名可能还是 `planning/`
- 打包文件目前仍是 `planning.spec`
- Windows 单文件构建产物默认仍是 `planning.exe`
- 部分日志前缀、内部事件名、默认配置值里仍保留 `planning`

这不影响功能，但确实属于“历史命名尚未完全切换”的状态。  
当前 README 会以 **PlanB** 作为对外名称来描述项目。

---

## 运行时数据目录

程序首次启动后会自动创建 `data/`。

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

- `data/config.yaml`：运行时配置
- `data/app.db`：SQLite 数据库
- `data/jobs/`：默认文档根目录
- `data/uploads/`：上传图片、头像、Logo
- `data/covers/`：本地随机封面目录

说明：

- 当前版本主配置文件是 `data/config.yaml`
- 仓库根目录如果还有旧 `config.yaml`，通常只是历史遗留，不是当前主配置

---

## 快速开始

### 1. 创建虚拟环境

Windows:

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

或者：

```powershell
start.bat
```

Linux:

```bash
python app.py
```

---

## 首次启动时会发生什么

首次启动时，程序会自动：

- 创建 `data/`
- 创建 `data/config.yaml`
- 创建 `data/app.db`
- 初始化系统设置
- 创建默认 `admin` 账号

如果数据库里还没有 `admin` 用户，程序会：

- 自动创建 `admin`
- 自动生成初始密码
- 把密码打印到控制台

请在首次登录后尽快修改管理员密码。

---

## 管理员密码重置

项目支持 `.changepassword` 机制，用于忘记管理员密码时快速重置。

使用方式：

1. 在程序运行目录创建一个空文件 `.changepassword`
2. 重启程序
3. 程序会自动重置 `admin` 密码并输出新密码
4. 处理完成后，`.changepassword` 会自动删除

规则：

- 如果 `admin` 不存在，会先创建再重置
- 如果 `admin` 已存在，则直接重置

说明：

- 该机制依赖控制台输出
- 因此当前单文件打包版本默认保留控制台窗口

---

## 配置文件

当前主配置文件位置：

```text
data/config.yaml
```

示例：

```yaml
port: 5000
debug: false
database_path: ''
secret_key: 'replace-with-your-own-secret'
timezone: Asia/Shanghai
cookie_secure: false
force_https_for_external_urls: true
```

主要说明：

- `debug`
  - 源码运行首次默认 `true`
  - 单文件打包首次默认 `false`
- `database_path`
  - 留空时默认使用 `data/app.db`
- `secret_key`
  - 生产环境建议替换为稳定随机值
- `timezone`
  - 默认 `Asia/Shanghai`
- `cookie_secure`
  - 本地或局域网 HTTP 访问通常应为 `false`
  - 正式 HTTPS 环境建议设为 `true`

局域网访问建议：

- 本地 / 局域网 HTTP：`cookie_secure: false`
- 正式 HTTPS：`cookie_secure: true`

---

## 核心内容模型

PlanB 的核心思路其实很简单：

- 所有内容首先都是 Markdown 文档
- 文档是否进入博客流，由 Front Matter 决定
- 博客文章并不是另一套独立内容模型，而是“带有特定头部信息的文档”

常见 Front Matter 字段：

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

- `template=post` 的文档会进入博客流
- `public` 控制是否公开访问
- `draft` 可用于草稿控制

---

## 访问控制与权限

当前权限体系包含两层：

### 1. 系统访问模式

- `open`
  - 完全开放
- `group_only`
  - 需要登录访问
- `password_only`
  - 固定密码访问

### 2. 用户目录权限规则

后台可为非管理员用户配置目录级权限：

- 允许读取
- 允许编辑
- 允许上传
- 允许删除
- 允许管理

其中：

- `编辑` 主要用于正文编辑
- `管理` 主要用于头部信息、公开状态、博客文章管理等元数据操作

也就是说，一个普通用户可以被允许“改正文”，但不能改“是否公开”“是否进入博客”“Front Matter 头部”等管理项。

### 固定密码访问白名单

在 `password_only` 模式下，还可以通过“访问密码权限规则”为已输入固定密码的访问者追加只读白名单访问能力。

这适合把整站作为文档中心时，临时开放部分目录或文档给外部查看。

---

## 分享能力

PlanB 支持把文档或目录生成分享链接，并可配置：

- 是否需要密码
- 是否允许编辑
- 有效期限

分享页支持：

- Markdown 展示
- 图片预览
- 二维码访问
- 在有权限时在线编辑

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
  - 文档详情页
- `/share/<token>`
  - 分享页

后台与账户：

- `/login`
- `/account`
- `/admin/`
  - 数据看板
- `/admin/base`
  - 基础设置
- `/admin/access`
  - 访问管理
- `/admin/security`
  - 安全设置
- `/admin/images`
  - 图片管理
- `/admin/users`
  - 用户管理
- `/manage-posts`
  - 博客文章管理工作台

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

- 图片管理会追踪图片是否仍被引用
- 站点 Logo 也会进入引用统计
- Logo 会显示用途标记，避免误删

---

## 后台能力

当前后台主要包括：

- 数据看板
- 基础设置
- 访问管理
- 安全设置
- 图片管理
- 用户管理
- 评论管理
- 博客文章管理
- 通知日志

---

## 安全相关

项目目前已包含这些基础安全能力：

- 登录限流
- 验证码发送限流
- 验证码校验限流
- 数据库存储型限流
- Redis 可选限流后端
- Session Cookie 安全选项

---

## 单文件打包

项目当前已适配 Windows 单文件打包。

现有文件：

- [`planning.spec`](./planning.spec)
- [`build_onefile.bat`](./build_onefile.bat)

Windows 下打包：

```powershell
build_onefile.bat
```

当前默认生成：

```text
dist/planning.exe
```

说明：

- 这里目前仍保留旧的 `planning` 打包名
- 如果后续正式统一品牌名，可以再把它改成 `PlanB.exe`

---

## Linux 部署建议

如果部署到 Linux，更推荐源码运行，而不是打包成二进制。

推荐方式：

- `venv`
- `pip install -r requirements.txt`
- `python app.py`
- 生产环境使用 `waitress`
- 由 `systemd` 托管
- `nginx` 反向代理

不优先推荐 Linux 单文件二进制的原因：

- 排错不如源码直观
- 兼容性不如源码稳定
- 长期维护成本更高

---

## 开发常用命令

安装依赖：

```bash
pip install -r requirements.txt
```

启动项目：

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
- 如果清空 `data/`，程序会按首次启动逻辑重新初始化
- 如果忘记 `admin` 密码，优先使用 `.changepassword`
- 生产环境请务必替换 `secret_key`

---

## 我建议后续可以顺手统一的命名点

如果你后面想把 **PlanB** 这个名字彻底统一，我建议优先改这几处：

1. `planning.spec` 改成 `planb.spec`
2. 打包产物从 `planning.exe` 改成 `PlanB.exe`
3. 启动日志里的 `[planning]` 前缀改成 `[planb]`
4. 默认站点名从 `Planning` 改成 `PlanB`
5. Redis 默认前缀 `planning:rate-limit` 改成 `planb:rate-limit`

这些都不是功能性必须修改，但它们会让项目在对外发布时更完整、更统一 。
