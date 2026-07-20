# 安全漏洞检测与修复报告

**项目名称**：用户管理系统（Flask 靶场）
**报告名称**：day3漏洞报告
**检测日期**：2026-07-20

---

## 一、漏洞总览

| 编号 | 漏洞名称 | 风险等级 | 状态 |
|------|---------|---------|------|
| V-01 | SQL 注入漏洞（注册功能） | 严重 | 已修复 |
| V-02 | 数据库明文密码存储 | 严重 | 已修复 |
| V-03 | 硬编码 Secret Key | 高危 | 已修复 |
| V-04 | 跨站请求伪造（CSRF） | 高危 | 已修复 |
| V-05 | 会话安全配置缺失 | 中危 | 已修复 |
| V-06 | 异常信息泄露 | 中危 | 已修复 |
| V-07 | 输入校验不足 | 中危 | 已修复 |
| V-08 | 密码修改不同步 SQLite | 低危 | 已修复 |

---

## 二、漏洞详情与修复

---

### V-01：SQL 注入漏洞（注册功能）

**风险等级**：严重
**漏洞文件**：`app.py`（原第 228 行）
**漏洞类型**：OWASP Top 1 — 注入

**漏洞描述**：
注册路由使用 f-string 拼接 SQL 语句，攻击者可以在用户名、邮箱、手机号等字段中输入恶意 SQL 代码，操纵数据库执行未授权操作。

**原代码**：
```python
sql = f"INSERT INTO users (username, password, email, phone) VALUES ('{username}', '{password}', '{email}', '{phone}')"
c.execute(sql)
```

**攻击示例**：
在用户名输入 `admin', 'evil'), ('hacker` 即可构造恶意 INSERT 语句。

**修复方案**：
改用参数化查询（Prepared Statement），将用户输入与 SQL 语句分离。

**修复后代码**：
```python
c.execute(
    "INSERT INTO users (username, password_hash, email, phone) VALUES (?, ?, ?, ?)",
    (username, password_hash, email, phone)
)
```

---

### V-02：数据库明文密码存储

**风险等级**：严重
**漏洞文件**：`app.py`（`init_db()` 函数）
**漏洞类型**：敏感信息泄露

**漏洞描述**：
SQLite 数据库中的 `users` 表使用 `password` 字段明文存储密码。一旦数据库文件泄露，所有用户密码直接暴露。

**原代码**：
```sql
CREATE TABLE users (
    ...
    password TEXT NOT NULL,
    ...
)
INSERT INTO users ... VALUES ('admin', 'admin123', ...)
```

**修复方案**：
1. 数据库表字段名改为 `password_hash`，存储哈希后的密码
2. 插入数据时使用 `generate_password_hash()` 进行哈希处理

**修复后代码**：
```python
phash = generate_password_hash(p)
c.execute(
    "INSERT OR IGNORE INTO users (username, password_hash, email, phone) VALUES (?, ?, ?, ?)",
    (u, phash, e, ph)
)
```

---

### V-03：硬编码 Secret Key

**风险等级**：高危
**漏洞文件**：`app.py`（原第 14 行）
**漏洞类型**：密码学强度不足

**漏洞描述**：
当环境变量 `SECRET_KEY` 未设置时，使用固定的 64 位十六进制字符串作为密钥。攻击者知道密钥后可伪造 session cookie，实现任意用户身份冒充。

**原代码**：
```python
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "a9f8d7e6b5c4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9"
)
```

**修复方案**：
使用 `secrets.token_hex(32)` 在每次启动时生成 64 字符（256位）随机密钥，确保密钥不可预测。

**修复后代码**：
```python
app.secret_key = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)
```

---

### V-04：跨站请求伪造（CSRF）

**风险等级**：高危
**漏洞文件**：`app.py` + 所有模板表单
**漏洞类型**：OWASP Top 2 — 跨站请求伪造

**漏洞描述**：
登录、注册、修改密码等所有表单均无 CSRF token 保护。攻击者可构造恶意页面，诱导已登录用户提交表单，实现密码篡改等攻击。

**攻击场景**：
攻击者在论坛中发布恶意图片 `<img src="http://靶机:5000/change-password?old_password=...&new_password=hacked">`，如果用户浏览器存有 session cookie，密码将被篡改。

**修复方案**：
1. 添加 CSRF token 生成和验证函数
2. 所有 POST 表单加入隐藏字段 `_csrf_token`
3. 所有 POST 处理路由验证 CSRF token

**新增代码**：
```python
def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def validate_csrf_token():
    token = request.form.get('_csrf_token', '')
    stored = session.pop('_csrf_token', None)
    if not stored or token != stored:
        return False
    return True
```

---

### V-05：会话安全配置缺失

**风险等级**：中危
**漏洞文件**：`app.py`
**漏洞类型**：安全配置错误

**漏洞描述**：
Flask session cookie 缺少安全标志，增加了会话劫持风险：
- 未设置 `HttpOnly`：JavaScript 可通过 `document.cookie` 读取 session cookie
- 未设置 `SameSite`：浏览器可能跨站发送 cookie

**修复方案**：
配置 Flask 的 session cookie 安全选项：
```python
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,    # 禁止 JS 读取 cookie
    SESSION_COOKIE_SAMESITE='Lax',   # 限制跨站发送
    SESSION_COOKIE_SECURE=False,     # 开发环境无 HTTPS
)
```

---

### V-06：异常信息泄露

**风险等级**：中危
**漏洞文件**：`app.py`（注册路由）
**漏洞类型**：信息泄露

**漏洞描述**：
注册失败时将数据库原始异常信息直接返回给用户，攻击者可利用这些信息推断数据库结构。

**原代码**：
```python
except Exception as e:
    return render_template("register.html", error=f"注册失败（{str(e)}）")
```

**修复后代码**：
```python
except sqlite3.IntegrityError:
    return render_template("register.html", error="用户名已存在！")
except Exception:
    return render_template("register.html", error="注册失败，请稍后重试！")
```

---

### V-07：输入校验不足

**风险等级**：中危
**漏洞文件**：`app.py`（注册路由）
**漏洞类型**：输入验证

**漏洞描述**：
注册功能检查了用户名和密码非空，但存在以下不足：
1. 未限制用户名长度（可插入超长字符串）
2. 未检查用户名是否已存在（插入重复用户名时触发 IntegrityError，错误提示不友好）
3. 密码最小长度校验过于宽松

**修复方案**：
添加用户名长度限制（2-32 字符）、密码最小长度校验（6位）、用户名重复前置检查。

---

### V-08：密码修改不同步 SQLite

**风险等级**：低危
**漏洞文件**：`app.py`（修改密码路由）
**漏洞类型**：数据一致性

**漏洞描述**：
修改密码仅更新了内存中的 `USERS` 字典，未同步更新 SQLite 数据库。重新初始化数据库后修改的密码会丢失。

**修复方案**：
修改密码时同步更新 SQLite 数据库：
```python
c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
conn.commit()
```

---

## 三、安全加固清单

### 3.1 代码变更统计

| 文件 | 修改类型 | 行数变化 |
|------|---------|---------|
| `app.py` | 修改 | +42 / -32 |
| `templates/login.html` | 修改 | +1 |
| `templates/register.html` | 修改 | +1 |
| `templates/change_password.html` | 修改 | +1 |

### 3.2 应用的安全机制

| 安全机制 | 对应漏洞 | 防护效果 |
|---------|---------|---------|
| 参数化查询 | V-01 SQL 注入 | 防止恶意 SQL 语句执行 |
| bcrypt 密码哈希 | V-02 明文密码 | 即使数据库泄露也无法还原密码 |
| 256位随机 Secret Key | V-03 密钥硬编码 | session 签名不可预测 |
| CSRF Token | V-04 CSRF | 跨站请求无法提交表单 |
| HttpOnly + SameSite | V-05 会话安全 | 防止 XSS 窃取 cookie |
| 通用错误提示 | V-06 信息泄露 | 不暴露内部实现细节 |
| 输入长度/格式校验 | V-07 输入校验 | 限制恶意输入 |
| 数据库同步更新 | V-08 数据一致性 | 修改密码持久化到数据库 |
| 登录频率限制 | — | 5 次失败锁定 5 分钟 |
| 调试模式关闭 | — | 防止远程代码执行 |

---

## 四、修复前后对比

### SQL 注入攻击测试

| 测试项 | 修复前 | 修复后 |
|-------|--------|--------|
| 正常注册 | 成功 | 通过 |
| 用户名含 SQL 注入代码 | 注入成功 | 参数化查询拦截 |
| 超长用户名（200 字符） | 插入成功 | 长度校验拒绝 |
| 短密码（3 位） | 注册成功 | 至少 6 位要求 |

### CSRF 攻击测试

| 测试项 | 修复前 | 修复后 |
|-------|--------|--------|
| 直接 POST 无 token | 正常执行 | 拒绝（显示"表单已过期"） |
| 正常带 token 提交 | — | 正常执行 |
| token 重复使用 | — | 一次性使用即失效 |

### 数据安全

| 测试项 | 修复前 | 修复后 |
|-------|--------|--------|
| 数据库密码存储 | 明文 admin123 | 哈希值（如 `$2b$12$...`） |
| Secret Key 可预测性 | 固定字符串 | 每次启动随机生成 |
| 密码修改持久化 | 仅内存更新 | 同步写入 SQLite |

---

## 五、安全建议（后续可改进）

1. **启用 HTTPS**：生产环境应配置 SSL/TLS 证书，防止密码在传输中被截获
2. **添加 reCAPTCHA**：注册和登录页增加验证码，防止自动化攻击
3. **密码复杂度策略**：要求包含大小写字母、数字、特殊字符
4. **账户锁定通知**：登录被锁定时发送邮件或短信通知用户
5. **定期密钥轮换**：建议每 90 天更换一次 `SECRET_KEY`
6. **数据库访问控制**：限制 SQLite 数据库文件的文件系统权限
7. **日志审计**：记录所有敏感操作（登录、注册、改密）到日志文件

---

*审计日期：2026年7月20日*
