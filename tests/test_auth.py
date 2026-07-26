"""认证模块单元测试 - 登录、登出、注册"""


class TestLogin:
    """登录功能测试"""

    def test_login_page_loads(self, client):
        """测试登录页面可正常访问"""
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "登录" in resp.data.decode()

    def test_login_failure(self, client):
        """测试错误密码且CSRF校验失败"""
        resp = client.post("/login", data={
            "username": "admin",
            "password": "wrong-password",
            "_csrf_token": "test",
        })
        assert resp.status_code == 200
        # CSRF 校验先于密码校验执行，所以返回"表单已过期"
        assert "表单已过期" in resp.data.decode()

    def test_login_failure_no_csrf(self, client):
        """测试缺少 CSRF token 的登录请求被拒绝"""
        resp = client.post("/login", data={
            "username": "admin",
            "password": "admin123",
        })
        assert resp.status_code == 200
        assert "表单已过期" in resp.data.decode()


class TestAuthorization:
    """权限校验测试"""

    def test_index_requires_no_login(self, client):
        """测试首页未登录也可访问"""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_ping_redirects_when_not_logged_in(self, client):
        """测试未登录访问 /ping 被重定向到登录页"""
        resp = client.get("/ping")
        assert resp.status_code == 302
        assert "/login" in resp.location

    def test_admin_redirects_when_not_logged_in(self, client):
        """测试未登录访问 /admin/users 被重定向"""
        resp = client.get("/admin/users")
        assert resp.status_code == 302

    def test_logged_in_user_can_access_ping(self, logged_in_client):
        """测试已登录用户可以访问 /ping"""
        resp = logged_in_client.get("/ping")
        assert resp.status_code == 200


class TestLogout:
    """登出功能测试"""

    def test_logout_redirects(self, logged_in_client):
        """测试登出后重定向到首页"""
        resp = logged_in_client.get("/logout")
        assert resp.status_code == 302
        assert resp.location == "/"


class TestRegister:
    """注册功能测试"""

    def test_register_page_loads(self, client):
        """测试注册页面可正常访问"""
        resp = client.get("/register")
        assert resp.status_code == 200

    def test_register_short_password_rejected(self, client):
        """测试注册时短密码被拒绝"""
        resp = client.post("/register", data={
            "username": "testuser",
            "password": "123",
            "_csrf_token": "test",
        })
        assert resp.status_code == 200
        assert "密码" in resp.data.decode()
