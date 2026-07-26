"""共享测试夹具"""

import pytest
from app import app as flask_app


@pytest.fixture
def app():
    """提供 Flask 测试应用实例"""
    flask_app.config.update({
        "TESTING": True,
    })
    yield flask_app


@pytest.fixture
def client(app):
    """提供 Flask 测试客户端"""
    return app.test_client()


@pytest.fixture
def logged_in_client(client):
    """提供一个已登录 admin 的测试客户端"""
    with client.session_transaction() as sess:
        sess["username"] = "admin"
        sess["role"] = "admin"
    yield client
