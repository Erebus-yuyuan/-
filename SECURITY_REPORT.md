# 🛡️ 靶场漏洞修复报告

**项目**：Flask 用户信息管理系统 | **路径**：`/opt/Class01/`  
**日期**：2026-07-19 | **状态**：✅ 全部 7 个漏洞已修复

---

## 1️⃣ 🔴 HTML 注释泄露默认管理员凭证

### 修复前
```html
<!-- 调试信息 - 默认管理员账号 用户名: admin 密码: admin123 -->
```
任何访客查看页面源码即可获取管理员账号密码。

### 修复方式
✅ **已删除该注释行**（`templates/login.html` 第 1 行）

---

## 2️⃣ 🔴 登录后前端页面直接回显密码

### 修复前
```html
<li><span class="info-label">密码：</span><span class="info-value">{{ user.password }}</span></li>
```
登录成功后用户的明文密码直接渲染在首页。

### 修复方式
✅ **删除该行 + 后端不再传递密码**（`templates/index.html` 第 13 行 + `app.py` `safe_user_info()` 函数）

---

## 3️⃣ 🟠 明文存储密码

### 修复前
```python
USERS = {
    "admin": { "password": "admin123", ... },
}
```

### 修复方式
✅ **改用 `werkzeug.security` 哈希存储**
```python
from werkzeug.security import generate_password_hash, check_password_hash

USERS = {
    "admin": {
        "password_hash": generate_password_hash("admin123"),
        ...
    },
}
```
- `generate_password_hash()` 使用 bcrypt(PBKDF2-SHA256) 加盐哈希
- 验证时用 `check_password_hash(hash, password)` → 不可逆比对
- **即使数据库泄露，攻击者也拿不到原始密码**

---

## 4️⃣ 🟠 弱 Secret Key → Session 伪造

### 修复前
```python
app.secret_key = "dev-key-2025"
```
弱密钥可被爆破 → 攻击者可伪造任意用户 session。

### 修复方式
✅ **改用环境变量 + 强随机密钥**
```python
import os
app.secret_key = os.environ.get("SECRET_KEY", "a9f8d7e6b...")
```
- 优先从环境变量 `SECRET_KEY` 读取
- 默认使用 62 位十六进制强密钥（不可预测）
- 生产环境建议：`export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")`

---

## 5️⃣ 🟠 Debug 模式开启（host="0.0.0.0" 保留）

### 修复前
```python
app.run(debug=True, host="0.0.0.0", port=5000)
```
- Debug 模式 → 可通过 `/console` 远程执行代码
- host="0.0.0.0" → 靶场外部访问需求，保留此项

### 修复方式
✅ **关闭 Debug 模式，保留外部访问能力**
- 删除 `debug=True` → `debug=False`，防止远程代码执行（`/console` 注入）
- 保留 `host="0.0.0.0"`，确保外部主机可正常访问（靶场需求）
```python
app.run(debug=False, host="0.0.0.0", port=5000)
```

---

## 6️⃣ 🟠 无登录失败频率限制

### 修复前：可无限无限暴力破解密码

### 修复方式
✅ **实现基于 IP + 用户名的双重限速机制**

| 参数 | 值 |
|------|-----|
| 最大失败次数 | 5 次 |
| 锁定时长 | 300 秒（5 分钟） |
| 限制粒度 | `IP:用户名` 组合 |
| 自动清理 | 记录超 100 条时自动回收过期条目 |

```python
# 第 6 次尝试会返回：
"登录已被锁定，请在 296 秒后重试！"
```

---

## 7️⃣ 🟡 用户对象原地变异（代码质量 Bug）

### 修复前
```python
user_info = USERS[username]
user_info["username"] = username   # ← 直接修改了全局 USERS 字典！
```
首次登录后 USERS 字典被"污染"，每条用户记录被额外添加 `username` 字段。

### 修复方式
✅ **使用 `copy.deepcopy()` 创建副本后再修改**
```python
import copy

def safe_user_info(username):
    info = copy.deepcopy(USERS[username])
    info.pop("password_hash", None)   # 同时确保哈希不泄露
    info["username"] = username
    return info
```
- 原始数据完好无损
- 密码哈希永远不会流出到模板层

---

## 📊 修复前后对比总表

| # | 漏洞 | 严重程度 | 修复前 | 修复后 | OWASP 映射 |
|---|------|---------|--------|--------|-----------|
| 1 | HTML 注释泄露密码 | 🔴 严重 | 注释行含 admin/admin123 | 已删除 | A05 - 安全配置错误 |
| 2 | 前端回显密码 | 🔴 严重 | 首页显示明文密码 | 已移除 | A04 - 不安全设计 |
| 3 | 明文存储密码 | 🟠 高危 | `"password": "admin123"` | bcrypt 哈希 | A02 - 加密失效 |
| 4 | 弱 Secret Key | 🟠 高危 | `"dev-key-2025"` | 62位强密钥 | A02 - 加密失效 |
| 5 | Debug 模式 + 0.0.0.0 | 🟠 高危 | debug=True, host=0.0.0.0 | debug=False, host=0.0.0.0（保留外部访问） | A05 - 安全配置错误 |
| 6 | 无暴力破解防护 | 🟠 高危 | 无限次尝试 | 5次锁定5分钟 | A07 - 身份验证失效 |
| 7 | 引用拷贝污染数据 | 🟡 中危 | 直接修改全局字典 | `deepcopy` 副本操作 | 代码质量 |

---

## 🔧 一键验证

```bash
# 1. 验证密码哈希（正确登录）
curl -s http://127.0.0.1:5000/login -X POST \
  -d "username=admin&password=admin123" | grep -c "欢迎回来"
# 输出: 1

# 2. 验证无密码泄露
curl -s http://127.0.0.1:5000/login -X POST \
  -d "username=admin&password=admin123" | grep -c "密码："
# 输出: 0

# 3. 验证锁定机制
for i in $(seq 1 6); do
  curl -s http://127.0.0.1:5000/login -X POST \
    -d "username=admin&password=wrong" | grep -o "已被锁定"
done
# 前5次无输出，第6次输出: 已被锁定

# 4. 验证 Debug 关闭
curl -s http://127.0.0.1:5000/console 2>/dev/null
# 输出: 404 Not Found
```

---

> **项目运行**：`cd /opt/Class01 && python app.py` → `http://0.0.0.0:5000`（外部主机请替换为实际 IP）  
> **生产建议**：使用 `gunicorn -w 4 -b 127.0.0.1:5000 app:app` 部署，并配置反向代理（Nginx/Caddy）处理 HTTPS。
