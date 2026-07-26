"""集中配置管理 - 支持环境变量覆盖"""

import os
from datetime import timedelta


class Config:
    """应用配置类，所有硬编码配置集中在此管理"""

    # ===== Flask 基础配置 =====
    # 通过环境变量 SECRET_KEY 设置，生产环境务必覆盖
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-key-insecure-change-in-production"
    )

    # ===== Session 配置 =====
    # 会话有效期：默认 2 小时
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get("SESSION_LIFETIME_HOURS", "2"))
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_SECURE", "false").lower() == "true"

    # ===== 服务器配置 =====
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5000"))
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

    # ===== 上传文件配置 =====
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
    ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    ALLOWED_MIME_TYPES = {
        'image/png', 'image/jpeg', 'image/gif',
        'image/bmp', 'image/webp', 'image/x-icon',
    }

    # ===== 登录频率限制 =====
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCKOUT_DURATION = 300  # 5 分钟

    # ===== Ping 频率限制 =====
    PING_MAX_REQUESTS = 10       # 每个 IP 最多 10 次请求
    PING_WINDOW_SECONDS = 60     # 每分钟
    PING_TIMEOUT = 30            # 每次执行超时 30 秒

    # ===== 审计日志 =====
    AUDIT_LOG_DIR = os.environ.get("AUDIT_LOG_DIR", "logs")
    AUDIT_LOG_FILE = os.environ.get("AUDIT_LOG_FILE", "audit.log")
    AUDIT_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB
    AUDIT_LOG_BACKUP_COUNT = 5

    # ===== 数据库 =====
    DB_DIR = os.environ.get("DB_DIR", "data")
    DB_FILE = os.environ.get("DB_FILE", "users.db")

    # ===== CSP 内容安全策略 =====
    CSP_POLICY = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )

    # ===== 文件魔数签名 =====
    IMAGE_SIGNATURES = {
        b'\x89PNG\r\n\x1a\n': '.png',
        b'\xff\xd8\xff': '.jpg',
        b'GIF89a': '.gif',
        b'GIF87a': '.gif',
        b'BM': '.bmp',
    }
    WEBP_SIGNATURE = b'RIFF'
    WEBP_MARKER = b'WEBP'
