import os
import time
import copy
import sqlite3
import secrets
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ===== 安全加固 1：强随机 Secret Key =====
# 通过环境变量设置，若未设置则自动生成随机密钥
app.secret_key = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)

# ===== 安全加固 5：会话安全配置 =====
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False,  # 开发环境无 HTTPS，保持 False
)

# ===== CSRF 保护辅助函数 =====
def generate_csrf_token():
    """生成并存储 CSRF token 到 session"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def validate_csrf_token():
    """验证 CSRF token"""
    token = request.form.get('_csrf_token', '')
    stored = session.pop('_csrf_token', None)
    if not stored or token != stored:
        return False
    return True

app.jinja_env.globals['csrf_token'] = generate_csrf_token

# ===== 安全加固 2：密码哈希存储 =====
# 密码不再明文存储，使用 bcrypt 算法哈希
USERS = {
    "admin": {
        "password_hash": generate_password_hash("admin123"),
        "role": "admin",
        "email": "admin@example.com",
        "phone": "13800138000",
        "balance": 99999
    },
    "alice": {
        "password_hash": generate_password_hash("alice2025"),
        "role": "user",
        "email": "alice@example.com",
        "phone": "13900139001",
        "balance": 100
    },
    # 新增用户（拼音用户名，密码也是拼音）
    "nuannuan": {
        "password_hash": generate_password_hash("nuannuan"),
        "role": "user",
        "email": "nuannuan@example.com",
        "phone": "13100000001",
        "balance": 0
    },
    "damiao": {
        "password_hash": generate_password_hash("damiao"),
        "role": "user",
        "email": "damiao@example.com",
        "phone": "13100000002",
        "balance": 0
    },
    "sinaide": {
        "password_hash": generate_password_hash("sinaide"),
        "role": "user",
        "email": "sinaide@example.com",
        "phone": "13100000003",
        "balance": 0
    },
    "weierting": {
        "password_hash": generate_password_hash("weierting"),
        "role": "user",
        "email": "weierting@example.com",
        "phone": "13100000004",
        "balance": 0
    },
    "yuyuan": {
        "password_hash": generate_password_hash("yuyuan"),
        "role": "user",
        "email": "yuyuan@example.com",
        "phone": "13100000005",
        "balance": 0
    }
}

# ===== 安全加固 3：登录频率限制 =====
# 基于 IP + 用户名 的双重限制
LOGIN_LIMIT = {
    "max_attempts": 5,           # 最大尝试次数
    "lockout_duration": 300,     # 锁定时间（秒）= 5 分钟
    "records": {}                # 记录 {"ip:username": {"count": int, "lockout_until": float}}
}


def is_login_locked(ip, username):
    """检查登录是否已被锁定"""
    key = f"{ip}:{username}"
    record = LOGIN_LIMIT["records"].get(key)
    if record and record["lockout_until"] > time.time():
        return True, int(record["lockout_until"] - time.time())
    return False, 0


def record_login_attempt(ip, username, success):
    """记录登录尝试"""
    key = f"{ip}:{username}"
    if success:
        # 登录成功：清除该记录
        LOGIN_LIMIT["records"].pop(key, None)
        return

    # 登录失败：增加计数
    now = time.time()
    record = LOGIN_LIMIT["records"].get(key)
    if record:
        record["count"] += 1
        if record["count"] >= LOGIN_LIMIT["max_attempts"]:
            record["lockout_until"] = now + LOGIN_LIMIT["lockout_duration"]
    else:
        LOGIN_LIMIT["records"][key] = {
            "count": 1,
            "lockout_until": 0
        }

    # 清理过期记录（每 10 次失败触发一次清理）
    if len(LOGIN_LIMIT["records"]) > 100:
        cleanup_time = now - LOGIN_LIMIT["lockout_duration"]
        LOGIN_LIMIT["records"] = {
            k: v for k, v in LOGIN_LIMIT["records"].items()
            if v["lockout_until"] > cleanup_time
        }


def safe_user_info(username):
    """返回不包含密码哈希的用户信息副本"""
    if username not in USERS:
        return None
    info = copy.deepcopy(USERS[username])
    info.pop("password_hash", None)
    info["username"] = username
    return info


# ===== SQLite 数据库初始化 =====
def init_db():
    """初始化 SQLite 数据库，创建 users 表并插入默认用户"""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/users.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
    """)
    # 插入默认用户（使用哈希存储密码）
    default_users = [
        ("admin", "admin123", "admin@example.com", "13800138000"),
        ("alice", "alice2025", "alice@example.com", "13900139001"),
        ("nuannuan", "nuannuan", "nuannuan@example.com", "13100000001"),
        ("damiao", "damiao", "damiao@example.com", "13100000002"),
        ("sinaide", "sinaide", "sinaide@example.com", "13100000003"),
        ("weierting", "weierting", "weierting@example.com", "13100000004"),
        ("yuyuan", "yuyuan", "yuyuan@example.com", "13100000005"),
    ]
    for u, p, e, ph in default_users:
        phash = generate_password_hash(p)
        c.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, email, phone) VALUES (?, ?, ?, ?)",
            (u, phash, e, ph)
        )
    conn.commit()
    conn.close()
    print("[init_db] 数据库初始化完成（密码已哈希存储）")


@app.route("/")
def index():
    """首页路由，从session获取当前登录用户名"""
    username = session.get("username")
    user_info = None
    if username and username in USERS:
        user_info = safe_user_info(username)
    return render_template("index.html", username=username, user=user_info)


@app.route("/login", methods=["GET", "POST"])
def login():
    """登录路由，支持GET和POST"""
    if request.method == "POST":
        # CSRF 校验
        if not validate_csrf_token():
            return render_template("login.html", error="表单已过期，请重新提交！")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        client_ip = request.remote_addr or "unknown"

        # 检查是否被锁定
        locked, remaining = is_login_locked(client_ip, username)
        if locked:
            return render_template(
                "login.html",
                error=f"登录已被锁定，请在 {remaining} 秒后重试！"
            )

        # 验证用户名和密码
        user = USERS.get(username)
        if user and check_password_hash(user["password_hash"], password):
            # 验证成功
            record_login_attempt(client_ip, username, success=True)
            session["username"] = username
            user_info = safe_user_info(username)
            return render_template("index.html", username=username, user=user_info)
        else:
            # 验证失败
            record_login_attempt(client_ip, username, success=False)
            return render_template("login.html", error="用户名或密码错误！")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """登出路由，清除session后重定向到首页"""
    session.clear()
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """新用户注册（使用参数化查询防止 SQL 注入）"""
    if request.method == "POST":
        # CSRF 校验
        if not validate_csrf_token():
            return render_template("register.html", error="表单已过期，请重新提交！")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        # 输入校验
        if not username or not password:
            return render_template("register.html", error="用户名和密码不能为空！")
        if len(username) < 2 or len(username) > 32:
            return render_template("register.html", error="用户名长度应为2-32个字符！")
        if len(password) < 6:
            return render_template("register.html", error="密码长度不能少于6位！")

        # 检查用户名是否已存在
        if username in USERS:
            return render_template("register.html", error="用户名已存在！")

        # 使用参数化查询防止 SQL 注入
        conn = sqlite3.connect("data/users.db")
        c = conn.cursor()
        password_hash = generate_password_hash(password)
        try:
            c.execute(
                "INSERT INTO users (username, password_hash, email, phone) VALUES (?, ?, ?, ?)",
                (username, password_hash, email, phone)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="用户名已存在！")
        except Exception:
            conn.close()
            return render_template("register.html", error="注册失败，请稍后重试！")

        # 同步添加到 USERS 字典
        USERS[username] = {
            "password_hash": password_hash,
            "role": "user",
            "email": email,
            "phone": phone,
            "balance": 0
        }
        conn.close()
        return render_template("login.html", success="注册成功，请登录！")

    return render_template("register.html")


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    """修改密码（需登录）"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    if request.method == "POST":
        # CSRF 校验
        if not validate_csrf_token():
            return render_template("change_password.html", error="表单已过期，请重新提交！")

        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        user = USERS.get(username)

        # 校验旧密码
        if not check_password_hash(user["password_hash"], old_password):
            return render_template("change_password.html", error="原密码错误！")

        # 校验新密码
        if not new_password:
            return render_template("change_password.html", error="请输入新密码！")
        if len(new_password) < 6:
            return render_template("change_password.html", error="新密码长度不能少于6位！")
        if new_password == old_password:
            return render_template("change_password.html", error="新密码不能与原密码相同！")
        if new_password != confirm_password:
            return render_template("change_password.html", error="两次输入的密码不一致！")

        # 更新密码（同时更新 SQLite 和 USERS 字典）
        password_hash = generate_password_hash(new_password)
        USERS[username]["password_hash"] = password_hash

        # 同步更新 SQLite 数据库
        try:
            conn = sqlite3.connect("data/users.db")
            c = conn.cursor()
            c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, username))
            conn.commit()
            conn.close()
        except Exception:
            pass  # SQLite 更新失败不阻塞功能

        user_info = safe_user_info(username)
        return render_template("index.html", username=username, user=user_info,
                               success="密码修改成功！")

    return render_template("change_password.html")


if __name__ == "__main__":
    # ===== 初始化数据库 =====
    init_db()
    # ===== 安全加固 4：关闭 Debug，保留外部访问 =====
    # debug=False 防止远程代码执行
    # host="0.0.0.0" 允许外部主机访问（靶场需求）
    app.run(debug=False, host="0.0.0.0", port=5000)
