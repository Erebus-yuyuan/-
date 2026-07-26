"""安全加固功能测试 - CSP、审计日志、Session 安全"""


class TestSecurityHeaders:
    """安全响应头测试"""

    def test_csp_header_exists(self, client):
        """测试所有响应包含 CSP 头"""
        resp = client.get("/")
        headers = resp.headers
        csp = headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "style-src 'self'" in csp
        assert "form-action 'self'" in csp

    def test_xss_protection_header(self, client):
        """测试 XSS 保护头"""
        resp = client.get("/")
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_frame_options_header(self, client):
        """测试点击劫持防护头"""
        resp = client.get("/")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_content_type_options(self, client):
        """测试 MIME 类型嗅探防护头"""
        resp = client.get("/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy(self, client):
        """测试 Referrer-Policy 头"""
        resp = client.get("/")
        assert "strict-origin" in resp.headers.get("Referrer-Policy", "")


class TestAuditLog:
    """审计日志功能测试"""

    def test_audit_log_created(self, app):
        """测试审计日志文件已创建"""
        import os
        assert os.path.exists("logs/audit.log")

    def test_login_failure_logged(self, client):
        """测试登录失败会写入审计日志"""
        import os
        before_size = os.path.getsize("logs/audit.log")
        client.post("/login", data={
            "username": "admin",
            "password": "wrong",
            "_csrf_token": "test",
        })
        after_size = os.path.getsize("logs/audit.log")
        assert after_size >= before_size


class TestConfig:
    """集中配置管理测试"""

    def test_config_imports(self):
        """测试配置模块可正常导入"""
        from config import Config
        cfg = Config()
        assert cfg.SECRET_KEY is not None
        assert cfg.PING_MAX_REQUESTS > 0
        assert "self" in cfg.CSP_POLICY
        assert cfg.PERMANENT_SESSION_LIFETIME is not None
