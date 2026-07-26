import os
import re
import uuid
import time
import copy
import sqlite3
import secrets
from functools import wraps
from urllib.parse import unquote
from flask import Flask, render_template, render_template_string, request, redirect, session, send_from_directory, abort
import subprocess, platform
import bleach


ALLOWED_HTML_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr',
    'div', 'span',
    'ul', 'ol', 'li',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'strong', 'b', 'em', 'i', 'u', 's',
    'a', 'img',
    'pre', 'code', 'tt',
    'blockquote',
    'section', 'header', 'footer',
    'dl', 'dt', 'dd',
    'abbr', 'cite',
]


ALLOWED_HTML_ATTRS = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'abbr': ['title'],
    '*': ['id', 'class'],
}


ALLOWED_HTML_PROTOCOLS = ['http', 'https', 'mailto']


def sanitize_html(content):
    """安全过滤HTML内容，仅保留安全的标签、属性和协议"""
    if not content:
        return ""
    return bleach.clean(
        content,
        tags=ALLOWED_HTML_TAGS,
        attributes=ALLOWED_HTML_ATTRS,
        protocols=ALLOWED_HTML_PROTOCOLS,
        strip=True,
        strip_comments=True
    )


from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge

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
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 最大上传文件 16MB
)

app.jinja_env.filters['sanitize'] = sanitize_html

# ===== 上传文件存储目录（存放于 static 之外，防止直接静态访问） =====
UPLOAD_DIR = os.path.join(app.root_path, "uploads")

# ===== 扩展名白名单（仅允许图片格式） =====
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

# ===== MIME 类型白名单（辅助校验） =====
ALLOWED_MIME_TYPES = {
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/bmp',
    'image/webp',
    'image/x-icon',
}

# ===== 文件魔数签名（用于文件内容真实性校验） =====
IMAGE_SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': '.png',
    b'\xff\xd8\xff': '.jpg',
    b'GIF89a': '.gif',
    b'GIF87a': '.gif',
    b'BM': '.bmp',
}

# WebP 特殊处理：前 4 字节 RIFF，偏移 8 处 WEBP
WEBP_SIGNATURE = b'RIFF'
WEBP_MARKER = b'WEBP'


def sanitize_filename(filename):
    """安全清洗文件名，防护列表：
       - 路径遍历（../ 等）
       - 空字节截断（\x00） + URL编码空字节（%00）
       - 换行符/回车符绕过（\x0a / \x0d，CVE-2017-15715）
       - NTFS 文件流绕过（::$DATA）
       - 大小写绕过（.PhP → .php）
       - 空格/点绕过（尾随空格和点）
       - 双扩展名绕过（.php.jpg → 拒绝）
       - .htaccess / .user.ini 配置文件上传
       - 危险字符注入"""
    # 先做 URL 解码，防止 %00、%0a、%0d 等编码绕过
    filename = unquote(filename)
    # 统一路径分隔符并提取纯文件名
    filename = filename.replace("\\", "/")
    filename = os.path.basename(filename)
    # 移除空字节（包括 URL 解码后的 %00）
    filename = filename.replace("\x00", "")
    # 【CVE-2017-15715】移除换行符和回车符（Apache 解析绕过）
    filename = filename.replace("\n", "").replace("\r", "")
    # 移除 NTFS 文件流标记
    if '::$' in filename.upper():
        filename = filename.split('::$')[0]
    # 替换危险字符，但保留点（后面单独处理扩展名）
    filename = re.sub(r'[^\w.\-()\[\] ]', '_', filename)
    # 确保文件名不为空
    if not filename or filename.strip() == '':
        filename = "unnamed"
    # 【白名单第一步】拒绝上传 .htaccess / .user.ini 等配置文件
    lowered = filename.lower()
    if lowered in ('.htaccess', '.user.ini', '.htpasswd') or \
       lowered.startswith('.ht') or lowered.startswith('.user.'):
        return None
    # 剥离文件名，获取纯扩展名（取最后一个点后的内容）
    name_part, ext = os.path.splitext(filename)
    ext = ext.lower()
    # 规范化扩展名：将 .jpeg 统一为 .jpg
    if ext == '.jpeg':
        ext = '.jpg'
    filename = name_part + ext
    # 限制文件名长度
    if len(filename) > 200:
        name_part, ext = os.path.splitext(filename)
        filename = name_part[:196] + ext
    return filename


def get_clean_extension(filename):
    """提取并规范化文件扩展名（小写，去尾随空格/点）"""
    _, ext = os.path.splitext(filename)
    ext = ext.lower().strip().rstrip('.')
    if not ext:
        return ''
    if ext == 'jpeg':
        ext = 'jpg'
    # splitext 返回的 ext 已包含前置点（如 .png），无需额外加点
    return ext


def validate_image_content(file_stream):
    """通过魔数（Magic Number）检测文件内容是否属于图片类型。
    返回检测到的扩展名（含点），无法识别则返回空字符串"""
    # 读取文件前 12 字节足够检测所有支持的格式
    header = file_stream.read(12)
    file_stream.seek(0)  # 重置指针

    for sig, ext in IMAGE_SIGNATURES.items():
        if header.startswith(sig):
            return ext

    # 特殊检测：WebP（RIFF + WEBP）
    if header[:4] == WEBP_SIGNATURE and header[8:12] == WEBP_MARKER:
        return '.webp'

    return ''


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

def sync_session_avatar(username):
    """将用户的头像 URL 同步到 session 中，返回 avatar_url 或空字符串"""
    if username and username in USERS:
        avatar = USERS[username].get("avatar", "")
        if avatar:
            session["avatar_url"] = f"/uploads/{avatar}"
            return session["avatar_url"]
    session.pop("avatar_url", None)
    return ""


app.jinja_env.globals['csrf_token'] = generate_csrf_token


# ===== 基于角色的访问控制（RBAC）装饰器 =====
def require_login(f):
    """要求用户已登录的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("username"):
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def require_role(required_role):
    """角色校验装饰器，要求当前用户具备指定角色"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            username = session.get("username")
            if not username:
                return redirect("/login")
            user_role = USERS.get(username, {}).get("role")
            if user_role != required_role:
                return render_template("error.html", error="无权限访问，需要管理员身份")
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.context_processor
def inject_user_id():
    """向所有模板注入当前登录用户的 user_id 和 role"""
    username = session.get("username")
    user_id = None
    user_role = None
    if username and username in USERS:
        user_id = USERS[username].get("id")
        user_role = USERS[username].get("role")
    return dict(current_user_id=user_id, current_user_role=user_role)

# ===== 安全加固 2：密码哈希存储 =====
# 密码不再明文存储，使用 bcrypt 算法哈希
USERS = {
    "admin": {
        "id": 1,
        "password_hash": generate_password_hash("admin123"),
        "role": "admin",
        "email": "admin@example.com",
        "phone": "13800138000",
        "balance": 99999,
        "avatar": ""
    },
    "alice": {
        "id": 2,
        "password_hash": generate_password_hash("alice2025"),
        "role": "user",
        "email": "alice@example.com",
        "phone": "13900139001",
        "balance": 100,
        "avatar": ""
    },
    # 新增用户（拼音用户名，密码也是拼音）
    "nuannuan": {
        "id": 3,
        "password_hash": generate_password_hash("nuannuan"),
        "role": "user",
        "email": "nuannuan@example.com",
        "phone": "13100000001",
        "balance": 0,
        "avatar": ""
    },
    "damiao": {
        "id": 4,
        "password_hash": generate_password_hash("damiao"),
        "role": "user",
        "email": "damiao@example.com",
        "phone": "13100000002",
        "balance": 0,
        "avatar": ""
    },
    "sinaide": {
        "id": 5,
        "password_hash": generate_password_hash("sinaide"),
        "role": "user",
        "email": "sinaide@example.com",
        "phone": "13100000003",
        "balance": 0,
        "avatar": ""
    },
    "weierting": {
        "id": 6,
        "password_hash": generate_password_hash("weierting"),
        "role": "user",
        "email": "weierting@example.com",
        "phone": "13100000004",
        "balance": 0,
        "avatar": ""
    },
    "yuyuan": {
        "id": 7,
        "password_hash": generate_password_hash("yuyuan"),
        "role": "user",
        "email": "yuyuan@example.com",
        "phone": "13100000005",
        "balance": 0,
        "avatar": ""
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
            phone TEXT,
            avatar TEXT DEFAULT ''
        )
    """)
    # 兼容旧表：如果 avatar 列不存在则添加
    try:
        c.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # 列已存在
    # 兼容旧表：如果 balance 列不存在则添加
    try:
        c.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # 列已存在
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

    # 从数据库加载已保存的头像信息到 USERS 字典（重启后恢复）
    c.execute("SELECT username, avatar FROM users WHERE avatar IS NOT NULL AND avatar != ''")
    for row in c.fetchall():
        u, a = row
        if u in USERS:
            USERS[u]["avatar"] = a

    # 从数据库加载余额信息到 USERS 字典（重启后恢复）
    c.execute("SELECT username, balance FROM users WHERE balance IS NOT NULL")
    for row in c.fetchall():
        u, b = row
        if u in USERS:
            USERS[u]["balance"] = b

    # 将 USERS 字典中的余额同步回数据库（确保 DB 与代码定义一致）
    for username, info in USERS.items():
        c.execute("UPDATE users SET balance = ? WHERE username = ? AND (balance IS NULL OR balance != ?)",
                  (info["balance"], username, info["balance"]))
    conn.commit()

    conn.close()

    # 迁移旧文件：将 static/uploads/ 下的已有文件复制到新目录
    old_upload_dir = os.path.join(app.root_path, "static", "uploads")
    if os.path.exists(old_upload_dir):
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        for fname in os.listdir(old_upload_dir):
            old_path = os.path.join(old_upload_dir, fname)
            new_path = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(old_path) and not os.path.exists(new_path):
                try:
                    with open(old_path, 'rb') as src, open(new_path, 'wb') as dst:
                        dst.write(src.read())
                except Exception:
                    pass

    print("[init_db] 数据库初始化完成（密码已哈希存储）")


@app.route("/")
def index():
    """首页路由，从session获取当前登录用户名"""
    username = session.get("username")
    user_info = None
    if username and username in USERS:
        sync_session_avatar(username)
        user_info = safe_user_info(username)
    return render_template("index.html", username=username, user=user_info)


@app.route("/page")
def dynamic_page():
    """动态页面加载路由 - 从 pages/ 目录读取文件并显示在首页上"""
    name = request.args.get("name", "")
    page_content = None

    # 【安全修复】URL解码后移除路径遍历序列
    name = unquote(name)
    # 递归移除所有路径遍历序列，防止双写绕过
    while ".." in name or "./" in name or "\\" in name or name.startswith("/"):
        name = name.replace("..", "").replace("./", "").replace("\\", "")
        name = name.lstrip("/")

    if not name:
        page_content = "页面不存在"
        username = session.get("username")
        user_info = None
        if username and username in USERS:
            sync_session_avatar(username)
            user_info = safe_user_info(username)
        return render_template("index.html", username=username, user=user_info, page_content=page_content)

    # 【安全修复】获取 pages 目录的绝对路径
    pages_dir = os.path.join(app.root_path, "pages")

    # 尝试直接读取文件
    file_path = os.path.join(pages_dir, name)
    real_path = os.path.realpath(file_path)
    real_pages_dir = os.path.realpath(pages_dir)

    # 【安全修复】检查文件是否在 pages/ 目录内
    if real_path.startswith(real_pages_dir + os.sep) and os.path.isfile(real_path):
        with open(real_path, "r", encoding="utf-8") as f:
            page_content = f.read()
    else:
        # 尝试加上 .html 后缀
        file_path_html = file_path + ".html"
        real_path_html = os.path.realpath(file_path_html)
        if real_path_html.startswith(real_pages_dir + os.sep) and os.path.isfile(real_path_html):
            with open(real_path_html, "r", encoding="utf-8") as f:
                page_content = f.read()
        else:
            page_content = "页面不存在"

    username = session.get("username")
    user_info = None
    if username and username in USERS:
        sync_session_avatar(username)
        user_info = safe_user_info(username)
    return render_template("index.html", username=username, user=user_info, page_content=page_content)


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
            sync_session_avatar(username)
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


@app.route("/welcome")
def welcome():
    """欢迎页路由 - 使用render_template_string以拼接方式渲染"""
    name = request.args.get("name", "")
    if not name:
        name = "亲爱的用户"
    return render_template_string("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>欢迎页</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">用户管理系统</div>
        <div class="nav-menu">
            <a href="/" class="nav-link">首页</a>
            <a href="/welcome" class="nav-link">欢迎页</a>
            <a href="/feedback" class="nav-link">反馈</a>
            {% if session.get('username') %}
                <span class="nav-welcome">欢迎，{{ session['username'] }}</span>
                <a href="/logout" class="nav-link">退出</a>
            {% else %}
                <a href="/login" class="nav-link">登录</a>
            {% endif %}
        </div>
    </nav>
    <main class="container">
        <div class="card">
            <h1>欢迎你，{{ name }}！</h1>
        </div>
    </main>
</body>
</html>
""", name=name)


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    """反馈路由 - GET显示表单，POST使用render_template_string以拼接方式渲染结果"""
    if request.method == "POST":
        name = request.form.get("name", "")
        message = request.form.get("message", "")
        if not name:
            name = "匿名用户"
        if not message:
            message = "（无留言内容）"
        return render_template_string("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>反馈结果</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">用户管理系统</div>
        <div class="nav-menu">
            <a href="/" class="nav-link">首页</a>
            <a href="/welcome" class="nav-link">欢迎页</a>
            <a href="/feedback" class="nav-link">反馈</a>
            {% if session.get('username') %}
                <span class="nav-welcome">欢迎，{{ session['username'] }}</span>
                <a href="/logout" class="nav-link">退出</a>
            {% else %}
                <a href="/login" class="nav-link">登录</a>
            {% endif %}
        </div>
    </nav>
    <main class="container">
        <div class="card">
            <h2>{{ name }} 的反馈：</h2>
            <p>{{ message }}</p>
            <div class="action-bar">
                <a href="/feedback" class="btn btn-primary">继续反馈</a>
            </div>
        </div>
    </main>
</body>
</html>
""", name=name, message=message)

    return render_template_string("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>反馈</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">用户管理系统</div>
        <div class="nav-menu">
            <a href="/" class="nav-link">首页</a>
            <a href="/welcome" class="nav-link">欢迎页</a>
            <a href="/feedback" class="nav-link">反馈</a>
            {% if session.get('username') %}
                <span class="nav-welcome">欢迎，{{ session['username'] }}</span>
                <a href="/logout" class="nav-link">退出</a>
            {% else %}
                <a href="/login" class="nav-link">登录</a>
            {% endif %}
        </div>
    </nav>
    <main class="container">
        <div class="card">
            <h2 class="card-title">用户反馈</h2>
            <form method="POST" action="/feedback" class="login-form">
                <div class="form-group">
                    <label for="name">姓名</label>
                    <input type="text" id="name" name="name" class="form-input" placeholder="请输入您的姓名">
                </div>
                <div class="form-group">
                    <label for="message">留言</label>
                    <textarea id="message" name="message" class="form-input" rows="5" placeholder="请输入您的留言内容"></textarea>
                </div>
                <button type="submit" class="btn btn-primary">提交反馈</button>
            </form>
        </div>
    </main>
</body>
</html>
""")


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
        max_id = max(u.get("id", 0) for u in USERS.values())
        USERS[username] = {
            "id": max_id + 1,
            "password_hash": password_hash,
            "role": "user",
            "email": email,
            "phone": phone,
            "balance": 0,
            "avatar": ""
        }
        conn.close()
        return render_template("login.html", success="注册成功，请登录！")

    return render_template("register.html")


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    """修改密码（需登录）
    修复：仅允许修改当前登录用户密码，需验证原密码，含频率限制和密码复杂度校验。"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    # GET 请求时直接重定向到个人中心
    if request.method == "GET":
        current_user_id = USERS.get(username, {}).get("id")
        return redirect(f"/profile?user_id={current_user_id}")

    # CSRF Token 校验（修复 CSRF 漏洞）
    if not validate_csrf_token():
        current_user_id = USERS.get(username, {}).get("id")
        return redirect(f"/profile?user_id={current_user_id}")

    # 频率限制检查（修复无频率限制漏洞）
    client_ip = request.remote_addr or "unknown"
    locked, remaining = is_login_locked(client_ip, username + "_pwd")
    if locked:
        current_user_id = USERS.get(username, {}).get("id")
        return redirect(f"/profile?user_id={current_user_id}")

    # 从 session 获取当前用户名，不从表单接收（修复越权漏洞）
    target_username = username
    new_password = request.form.get("new_password", "")
    old_password = request.form.get("old_password", "")
    confirm_password = request.form.get("confirm_password", "")

    user = USERS.get(target_username)

    # 校验原密码（修复无需原密码漏洞）
    if not check_password_hash(user["password_hash"], old_password):
        record_login_attempt(client_ip, username + "_pwd", success=False)
        current_user_id = USERS.get(username, {}).get("id")
        return redirect(f"/profile?user_id={current_user_id}")

    # 校验新密码
    if not new_password:
        record_login_attempt(client_ip, username + "_pwd", success=False)
        current_user_id = USERS.get(username, {}).get("id")
        return redirect(f"/profile?user_id={current_user_id}")

    # 修复弱密码策略漏洞：长度提升至8位，要求包含大小写字母、数字、特殊字符中至少三类
    if len(new_password) < 8:
        record_login_attempt(client_ip, username + "_pwd", success=False)
        current_user_id = USERS.get(username, {}).get("id")
        return redirect(f"/profile?user_id={current_user_id}")

    strength = 0
    if re.search(r'[a-z]', new_password):
        strength += 1
    if re.search(r'[A-Z]', new_password):
        strength += 1
    if re.search(r'[0-9]', new_password):
        strength += 1
    if re.search(r'[^a-zA-Z0-9]', new_password):
        strength += 1

    if strength < 3:
        record_login_attempt(client_ip, username + "_pwd", success=False)
        current_user_id = USERS.get(username, {}).get("id")
        return redirect(f"/profile?user_id={current_user_id}")

    # 修复新密码与旧密码相同漏洞
    if new_password == old_password:
        record_login_attempt(client_ip, username + "_pwd", success=False)
        current_user_id = USERS.get(username, {}).get("id")
        return redirect(f"/profile?user_id={current_user_id}")

    # 修复确认密码服务端未验证漏洞
    if new_password != confirm_password:
        record_login_attempt(client_ip, username + "_pwd", success=False)
        current_user_id = USERS.get(username, {}).get("id")
        return redirect(f"/profile?user_id={current_user_id}")

    # 记录成功尝试
    record_login_attempt(client_ip, username + "_pwd", success=True)

    # 更新密码（同时更新 SQLite 和 USERS 字典）
    password_hash = generate_password_hash(new_password)
    USERS[target_username]["password_hash"] = password_hash

    # 同步更新 SQLite 数据库
    try:
        conn = sqlite3.connect("data/users.db")
        c = conn.cursor()
        c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (password_hash, target_username))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[change_password] SQLite 同步失败: {e}")

    # 修复会话未失效漏洞：清空会话强制重新登录
    session.clear()
    return redirect("/login")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    """用户头像上传路由（需登录）"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    if request.method == "POST":
        # CSRF 校验
        if not validate_csrf_token():
            return render_template("upload.html", error="表单已过期，请重新提交！")

        # 获取上传文件
        file = request.files.get("file")
        if not file or file.filename == "":
            return render_template("upload.html", error="请选择要上传的文件！")

        # 获取用户提交的原始文件名
        raw_filename = file.filename

        # ==================== 【安全检测层 1：文件名清洗】 ====================
        safe_name = sanitize_filename(raw_filename)
        if safe_name is None:
            return render_template("upload.html",
                                   error="禁止上传系统配置文件（.htaccess、.user.ini 等）！")

        # ==================== 【安全检测层 2：扩展名白名单】 ====================
        ext = get_clean_extension(safe_name)
        if ext not in ALLOWED_EXTENSIONS:
            return render_template(
                "upload.html",
                error=f"不允许上传 {ext} 格式。仅支持：{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # ==================== 【安全检测层 3：MIME 类型辅助校验】 ====================
        mime = file.content_type or ''
        if mime and mime not in ALLOWED_MIME_TYPES:
            return render_template("upload.html",
                                   error=f"文件类型（{mime}）不被允许，请上传图片文件。")

        # ==================== 【安全检测层 4：文件内容魔数校验】 ====================
        detected_ext = validate_image_content(file.stream)
        if not detected_ext:
            return render_template("upload.html",
                                   error="文件内容不是有效的图片格式，请上传真实图片文件。")
        # 魔数检测的扩展名必须与白名单扩展名匹配
        if detected_ext != ext:
            return render_template("upload.html",
                                   error=f"文件扩展名（{ext}）与实际内容（{detected_ext}）不匹配！")

        # ==================== 【安全隔离：用户名前缀防覆盖】 ====================
        filename = f"{username}_{safe_name}"
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # 【条件竞争防护】先保存到临时文件，再原子重命名为目标文件名
        # 防止攻击者在文件写入完成前发起并发访问
        tmp_name = f".tmp_{uuid.uuid4().hex}_{filename}"
        tmp_path = os.path.join(UPLOAD_DIR, tmp_name)
        file.save(tmp_path)
        filepath = os.path.join(UPLOAD_DIR, filename)
        os.rename(tmp_path, filepath)

        # 将头像关联到当前用户（更新内存字典和 SQLite）
        USERS[username]["avatar"] = filename
        session["avatar_url"] = f"/uploads/{filename}"
        try:
            conn = sqlite3.connect("data/users.db")
            c = conn.cursor()
            c.execute("UPDATE users SET avatar = ? WHERE username = ?", (filename, username))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[upload] SQLite 同步头像失败: {e}")

        file_url = f"/uploads/{filename}"
        return render_template("upload.html", success="文件上传成功！", file_url=file_url)

    return render_template("upload.html")


@app.route("/profile")
def profile():
    """个人中心路由（需登录，普通用户只能查看自己的资料）"""
    # 检查登录态（VULN-001 修复）
    current_username = session.get("username")
    if not current_username:
        return redirect("/login")

    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return redirect("/")

    # 根据 user_id 查找用户
    target_user = None
    target_username = None
    for username, info in USERS.items():
        if info.get("id") == user_id:
            target_user = safe_user_info(username)
            target_username = username
            break

    if target_user is None:
        return render_template("profile.html", error="用户不存在", user=None)

    # 权限校验：普通用户只能查看自己的资料（VULN-005 修复）
    current_user_id = USERS[current_username].get("id")
    user_role = USERS[current_username].get("role")
    if user_role != "admin" and current_user_id != user_id:
        return render_template("profile.html", error="无权限查看其他用户资料", user=None)

    redirect_url = request.args.get("redirect", "")
    return render_template("profile.html", user=target_user, error=None, redirect_url=redirect_url)


@app.route("/admin/users")
@require_role("admin")
def admin_users():
    """管理员用户管理 - 搜索并查看所有用户"""
    keyword = request.args.get("keyword", "").strip()

    user_list = []
    for username, info in USERS.items():
        # 如果有关键字，按用户名模糊搜索（大小写不敏感）
        if keyword and keyword.lower() not in username.lower():
            continue
        user_info = safe_user_info(username)
        user_list.append(user_info)

    # 按用户 ID 排序
    user_list.sort(key=lambda u: u.get("id", 0))

    return render_template("admin_users.html", users=user_list, keyword=keyword)


@app.route("/recharge", methods=["POST"])
def recharge():
    """充值路由（需登录，仅限本人充值，必须为正数）"""
    # CSRF 校验（VULN-004 修复）
    if not validate_csrf_token():
        current_username = session.get("username")
        if current_username and current_username in USERS:
            return render_template("profile.html", error="表单已过期，请重新提交！",
                                   user=safe_user_info(current_username))
        return redirect("/")

    # 检查登录态（VULN-002 修复）
    current_username = session.get("username")
    if not current_username:
        return redirect("/login")

    amount = request.form.get("amount", type=float, default=0)

    # 充值金额必须为正数（VULN-003 修复）
    if amount <= 0:
        return render_template("profile.html", error="充值金额必须大于零",
                               user=safe_user_info(current_username))

    # 只允许给当前登录用户充值（VULN-002 修复）
    USERS[current_username]["balance"] += amount

    # 同步更新 SQLite 数据库
    try:
        conn = sqlite3.connect("data/users.db")
        c = conn.cursor()
        c.execute("UPDATE users SET balance = ? WHERE username = ?",
                  (USERS[current_username]["balance"], current_username))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[recharge] SQLite 同步失败: {e}")

    current_user_id = USERS[current_username].get("id")
    return redirect(f"/profile?user_id={current_user_id}")


@app.after_request
def add_security_headers(response):
    """【安全修复】为所有响应添加安全头"""
    # 禁用 MIME 类型嗅探
    response.headers["X-Content-Type-Options"] = "nosniff"
    # 防止点击劫持
    response.headers["X-Frame-Options"] = "DENY"
    # 启用 XSS 过滤器（老旧浏览器兼容）
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # 禁止浏览器自动检测和引用不安全的资源
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.before_request
def block_static_uploads_direct_access():
    """【安全修复】拦截对 /static/uploads/ 的直接静态文件访问。
    所有已上传文件必须通过 /uploads/<filename> 专用路由访问，
    该路由会进行 Content-Type 安全控制。"""
    if request.path.startswith('/static/uploads/'):
        abort(404)


@app.route("/uploads/<filename>")
def serve_upload(filename):
    """【安全修复】通过专用路由安全地提供上传文件。
     - 二次路径清洗防遍历（含 %00 URL 路径截断防护）
     - 禁用 MIME嗅探
     - 非图片文件强制 octet-stream 下载"""
    # 【%00 路径截断防护】URL 路径中的 %00 会被浏览/some中间件解码，
    # 但 Flask 收到时可能是已解码的 \x00 或未解码的 %00
    # 先做一次 URL 解码清洗
    filename = unquote(filename)
    # 防止路径遍历：重新清洗文件名
    safe_name = sanitize_filename(filename)
    if safe_name is None:
        abort(404)
    filepath = os.path.join(UPLOAD_DIR, safe_name)

    # 安全检查：确保文件在 UPLOAD_DIR 内（二次确认）
    real_path = os.path.realpath(filepath)
    if not real_path.startswith(os.path.realpath(UPLOAD_DIR) + os.sep) and \
       not real_path == os.path.realpath(UPLOAD_DIR):
        abort(404)

    if not os.path.exists(real_path):
        abort(404)

    # 使用 send_from_directory 安全地发送文件
    response = send_from_directory(UPLOAD_DIR, safe_name)

    # 非图片类型文件强制以 application/octet-stream 下载（防止 HTML/SVG XSS）
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'

    return response


@app.errorhandler(413)
def request_entity_too_large(error):
    """【安全修复】处理上传文件过大错误（RequestEntityTooLarge）"""
    return render_template("upload.html", error="文件过大！上传文件大小不能超过 16MB。"), 413


@app.route("/ping", methods=["GET", "POST"])
def ping():
    """Ping 网络诊断功能，需要登录才能访问"""
    username = session.get("username")
    if not username:
        return redirect("/login")

    result = ""
    if request.method == "POST":
        ip = request.form.get("ip", "").strip()

        # 【安全加固】白名单校验：仅允许合法 IP 地址或域名
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'

        if not ip:
            result = "错误：请输入 IP 地址或域名"
        elif re.match(ip_pattern, ip):
            parts = ip.split('.')
            if not all(0 <= int(p) <= 255 for p in parts):
                result = "错误：IP 地址格式不正确（每段应为 0-255）"
            else:
                try:
                    result = subprocess.check_output(
                        ["ping", "-c", "3", ip],
                        timeout=30,
                        stderr=subprocess.STDOUT
                    ).decode("utf-8", errors="replace")
                except subprocess.CalledProcessError as e:
                    result = e.output.decode("utf-8", errors="replace")
                except subprocess.TimeoutExpired:
                    result = "错误：执行超时（30秒）"
                except Exception as e:
                    result = f"错误：执行出错：{e}"
        elif re.match(domain_pattern, ip):
            try:
                result = subprocess.check_output(
                    ["ping", "-c", "3", ip],
                    timeout=30,
                    stderr=subprocess.STDOUT
                ).decode("utf-8", errors="replace")
            except subprocess.CalledProcessError as e:
                result = e.output.decode("utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                result = "错误：执行超时（30秒）"
            except Exception as e:
                result = f"错误：执行出错：{e}"
        else:
            result = "错误：无效的 IP 地址或域名格式"

    return render_template("ping.html", result=result)


if __name__ == "__main__":
    # ===== 初始化数据库 =====
    init_db()
    # ===== 安全加固 4：关闭 Debug，保留外部访问 =====
    # debug=False 防止远程代码执行
    # host="0.0.0.0" 允许外部主机访问（靶场需求）
    app.run(debug=False, host="0.0.0.0", port=5000)
