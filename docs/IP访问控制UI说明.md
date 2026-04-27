# IP 访问控制 UI 说明

## 概述

IP 访问控制功能已完成 UI 集成，现在可以通过管理后台的安全设置页面 (`/admin/security`) 进行配置。

## 功能特性

### 1. IP 白名单
- 启用后，只允许白名单中的 IP 访问系统
- 支持多种 IP 格式：
  - 单个 IP: `192.168.1.100`
  - CIDR 网段: `192.168.1.0/24`
  - IP 范围: `192.168.1.100-192.168.1.200`
- 支持注释行（以 `#` 开头）

### 2. IP 黑名单
- 启用后，黑名单中的 IP 将被拒绝访问
- 黑名单优先级高于白名单
- 支持与白名单相同的 IP 格式

### 3. 共享密钥验证
- 要求请求头包含正确的共享密钥
- 适用于内部服务调用场景
- 可自定义请求头名称（默认: `X-Internal-Secret`）

### 4. 当前请求 IP 显示
- 实时显示当前访问者的 IP 地址
- 帮助管理员正确配置白名单

### 5. Nginx 配置指南
- 动态显示 Nginx 反向代理配置示例
- 当启用任何 IP 控制功能时自动显示
- 共享密钥配置会动态更新到示例中

### 6. 紧急恢复机制
- 提供数据库直接修改方法
- 防止配置错误导致无法访问系统

## 使用说明

### 配置步骤

1. 访问 `/admin/security` 页面
2. 滚动到"IP 访问控制"部分
3. 根据需要启用相应功能：
   - 启用 IP 白名单并填写允许的 IP 列表
   - 启用 IP 黑名单并填写禁止的 IP 列表
   - 启用共享密钥验证并设置密钥
4. 查看"当前请求 IP"确认自己的 IP 地址
5. 点击"保存安全设置"

### Nginx 配置

如果使用 Nginx 反向代理，需要添加以下配置：

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    # 如果启用了共享密钥，添加以下行
    proxy_set_header X-Internal-Secret "your-secret-here";
}
```

### 紧急恢复

如果配置错误导致无法访问系统，可以使用命令行参数禁用 IP 访问控制：

```bash
python app.py --disable-ip-control
```

该命令会自动禁用所有 IP 访问控制（白名单、黑名单、共享密钥验证），让你能够重新访问系统并修正配置。

**旧方法（不推荐）：** 也可以直接修改数据库：

```sql
UPDATE system_settings 
SET value = 'false' 
WHERE key IN (
    'security_ip_whitelist_enabled',
    'security_ip_blacklist_enabled',
    'security_shared_secret_enabled'
);
```

## 技术实现

### 前端
- 位置: `templates/admin_security.html`
- 使用 Jinja2 模板渲染
- JavaScript 动态控制 Nginx 配置显示
- 响应式布局，支持移动端

### 后端
- 中间件: `services/ip_access_control.py`
- 路由处理: `blueprints/admin.py`
- 配置存储: `SystemSetting` 模型

### 配置键
- `security_ip_whitelist_enabled`: 白名单开关
- `security_ip_whitelist`: 白名单 IP 列表
- `security_ip_blacklist_enabled`: 黑名单开关
- `security_ip_blacklist`: 黑名单 IP 列表
- `security_shared_secret_enabled`: 共享密钥开关
- `security_shared_secret`: 共享密钥值
- `security_shared_secret_header`: 共享密钥请求头名称

## 测试建议

1. 先在黑名单模式下测试，确保配置正确
2. 启用白名单前，确认当前 IP 已添加到白名单
3. 使用无痕模式或其他设备测试访问控制是否生效
4. 测试共享密钥时，使用 curl 或 Postman 验证请求头

## 注意事项

1. 白名单和黑名单可以同时启用，黑名单优先级更高
2. 共享密钥验证独立于 IP 控制，可单独使用
3. 静态文件 (`/static/`) 不受 IP 访问控制影响
4. 配置错误可能导致自己无法访问系统，请谨慎操作
5. 建议在测试环境先验证配置，再应用到生产环境
