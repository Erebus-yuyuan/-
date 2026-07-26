"""Ping 功能单元测试 - 命令注入防护验证"""


class TestPingAccess:
    """Ping 页面访问控制测试"""

    def test_ping_requires_login(self, client):
        """测试未登录被重定向"""
        resp = client.get("/ping")
        assert resp.status_code == 302

    def test_ping_logged_in(self, logged_in_client):
        """测试已登录可访问 ping 页面"""
        resp = logged_in_client.get("/ping")
        assert resp.status_code == 200


class TestPingCommandInjection:
    """命令注入防护测试"""

    VALID_IP = "127.0.0.1"
    INJECTION_PAYLOADS = [
        "127.0.0.1;id",
        "127.0.0.1|whoami",
        "127.0.0.1`id`",
        "$(cat /etc/passwd)",
        "8.8.8.8&whoami",
        "localhost$(id)",
        "127.0.0.1||id",
    ]

    def test_valid_ip_works(self, logged_in_client):
        """测试合法 IP 可以正常执行"""
        resp = logged_in_client.post("/ping", data={"ip": self.VALID_IP})
        assert resp.status_code == 200
        body = resp.data.decode()
        # 应包含 ping 输出而非错误
        assert "错误" not in body

    def test_empty_ip(self, logged_in_client):
        """测试空输入返回提示"""
        resp = logged_in_client.post("/ping", data={"ip": ""})
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "请输入" in body or "错误" in body

    def test_invalid_ip_range(self, logged_in_client):
        """测试超出范围的 IP 被拒绝"""
        resp = logged_in_client.post("/ping", data={"ip": "999.999.999.999"})
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "0-255" in body or "无效" in body

    def test_injection_payloads_blocked(self, logged_in_client):
        """测试各种命令注入 payload 都被拦截"""
        for payload in self.INJECTION_PAYLOADS:
            resp = logged_in_client.post("/ping", data={"ip": payload})
            assert resp.status_code == 200
            body = resp.data.decode()
            assert "错误" in body or "无效" in body, \
                f"Payload 未被拦截: {payload}"

    def test_valid_domain(self, logged_in_client):
        """测试合法域名正常执行（可能超时，检查不会报注入类错误）"""
        resp = logged_in_client.post("/ping", data={"ip": "example.com"})
        assert resp.status_code == 200
        body = resp.data.decode()
        # 即使 ping 不通也不应出现命令注入执行结果
        assert "uid=" not in body
        assert "root:" not in body
