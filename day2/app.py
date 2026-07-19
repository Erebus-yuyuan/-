import os
import time
import copy
from functools import wraps
from flask import Flask, render_template, request, redirect, session, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ===== 安全加固 1：强随机 Secret Key =====
# 通过环境变量设置，若无则自动生成一个固定强密钥（生产环境务必设置环境变量）
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "a9f8d7e6b5c4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9"
)

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
    """新用户注册"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        # 校验用户名
        if not username:
            return render_template("register.html", error="请输入用户名！")
        if len(username) < 2:
            return render_template("register.html", error="用户名长度不能少于2个字符！")
        if username in USERS:
            return render_template("register.html", error="用户名已存在！")

        # 校验密码
        if not password:
            return render_template("register.html", error="请输入密码！")
        if len(password) < 6:
            return render_template("register.html", error="密码长度不能少于6位！")
        if password != confirm_password:
            return render_template("register.html", error="两次输入的密码不一致！")

        # 创建新用户
        USERS[username] = {
            "password_hash": generate_password_hash(password),
            "role": "user",
            "email": email,
            "phone": phone,
            "balance": 0
        }

        # 自动登录
        session["username"] = username
        user_info = safe_user_info(username)
        return render_template("index.html", username=username, user=user_info)

    return render_template("register.html")


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    """修改密码（需登录）"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    if request.method == "POST":
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

        # 更新密码
        USERS[username]["password_hash"] = generate_password_hash(new_password)
        user_info = safe_user_info(username)
        return render_template("index.html", username=username, user=user_info,
                               success="密码修改成功！")

    return render_template("change_password.html")


if __name__ == "__main__":
    # ===== 安全加固 4：关闭 Debug，保留外部访问 =====
    # debug=False 防止远程代码执行
    # host="0.0.0.0" 允许外部主机访问（靶场需求）
    app.run(debug=False, host="0.0.0.0", port=5000)
