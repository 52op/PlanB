# planB SSO 配置指南

planB 支持两种认证模式，通过 `config.yaml` 中的 `auth_mode` 字段切换：

- `standalone`（默认）：独立用户系统，自行管理账号
- `sso`：接入 GoAuth 统一认证，用户在 GoAuth 登录后自动进入 planB

---

## 配置步骤

### 1. 获取 GoAuth 公钥

```bash
curl https://auth.it0731.cn/api/public-key
```

### 2. 修改 config.yaml

打开 `data/config.yaml`（或程序目录下的 `config.yaml`），修改以下字段：

```yaml
# 认证模式
auth_mode: "sso"

# GoAuth 服务地址
sso_issuer: "https://auth.it0731.cn"

# SSO Cookie 名称（需与 GoAuth 配置的 cookie_name 一致）
sso_cookie_name: "_goauth_token"

# GoAuth RSA 公钥（PEM 格式，多行直接写 YAML 块）
sso_public_key: |
  -----BEGIN PUBLIC KEY-----
  MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...（替换为实际公钥）
  -----END PUBLIC KEY-----
```

### 3. 重启 planB

```bash
python app.py
```

重启后，访问任意需要登录的页面，会自动跳转至 GoAuth 登录页。

---

## SSO 登录流程

```
用户访问 planB 受保护页面
    ↓
Flask-Login 重定向到 /auth/sso-login
    ↓
planB 重定向到 https://auth.it0731.cn/login?redirect=<callback_url>
    ↓
用户在 GoAuth 登录
    ↓
GoAuth 重定向回 /auth/sso-callback?token=<JWT>
    ↓
planB 验证 JWT（RS256），查找或创建本地影子用户
    ↓
建立 Flask session，进入系统
```

---

## 影子用户机制

SSO 模式下，用户首次通过 GoAuth 登录时，planB 会在本地数据库自动创建一个"影子用户"：

- 邮箱、用户名来自 JWT payload
- 密码为随机值，**无法用于本地登录**
- 角色（`admin` / `regular`）**每次登录时从 GoAuth 同步**
- 本地用户 ID 稳定不变，细粒度权限（PermissionRule）正常有效

> **关于细粒度权限**：planB 后台"用户权限"页面中按路径配置的 PermissionRule，以本地 `user_id` 为键，SSO 登录不影响这些记录，可正常使用。

> **关于角色**：GoAuth 是角色的权威来源。在 planB 后台修改用户角色后，下次该用户通过 SSO 重新登录，角色会被 GoAuth 覆盖。如需在 planB 本地独立管理角色，请保持 `auth_mode: standalone`。

---

## 回退到独立模式

将 `config.yaml` 改回：

```yaml
auth_mode: "standalone"
```

重启后恢复独立登录，之前通过 SSO 创建的影子用户仍在数据库中，但无法直接使用（密码随机）。如需让这些用户能本地登录，在 planB 后台为其重置密码即可。

---

## 依赖包

SSO 模式需要以下 Python 包（已包含在 `requirements.txt`）：

```
PyJWT
cryptography
```

如缺失请运行：

```bash
pip install PyJWT cryptography
```
