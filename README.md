# Flask 用户信息管理系统（安全靶场）

> 版本：越权业务逻辑漏洞

一个基于 Flask 的 Web 安全靶场项目，包含完整的用户管理功能，用于 Web 安全教学与漏洞复现。

## 快速启动

```bash
cd /opt/Class01/ && python3 app.py
```

服务启动后访问 `http://192.168.248.129:5000`

## 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |
| alice | alice2025 | 普通用户 |
| nuannuan | nuannuan | 普通用户 |
| damiao | damiao | 普通用户 |
| sinaide | sinaide | 普通用户 |
| weierting | weierting | 普通用户 |
| yuyuan | yuyuan | 普通用户 |

## 功能列表

- 用户登录（带频率限制：5 次失败锁定 5 分钟）
- 用户注册（带 CSRF 防护、参数化查询）
- 修改密码（需校验旧密码、同步更新数据库）
- 用户信息展示（用户名、邮箱、手机、角色、余额）
- **个人中心**（独立页面，需登录，含权限校验）
- **账户充值**（仅限本人，金额必须为正数，CSRF 防护）
- **用户头像上传（7 层安全加固）**
  - 扩展名白名单（仅允许图片格式）
  - MIME 类型白名单
  - 文件魔数校验（PNG/JPEG/GIF/BMP/WebP）
  - 路径遍历防护
  - 条件竞争防护（原子重命名）
  - CVE-2017-15715 换行符绕过防护
  - 全局安全响应头（XSS/点击劫持防护）
- **头像展示**
  - 导航栏右上角圆形头像
  - 首页用户信息区大头像
  - 重启后头像持久化（SQLite）
- CSRF Token 保护（所有 POST 表单）
- 密码哈希存储（bcrypt）
- 随机 Secret Key（256位）
- 会话安全配置（HttpOnly + SameSite=Lax）

## 权限体系

- **RBAC 装饰器**: `require_login` / `require_role("admin")`
- 普通用户只能查看和操作自己的资料
- 管理员可以查看所有用户资料
- 所有资金操作绑定当前会话用户

## 报告文档

- [Day3 安全漏洞修复报告](day3漏洞报告.md)
- [Day4 文件上传漏洞修复报告](day4-文件上传漏洞修复报告.md)
- [Day5 越权业务逻辑漏洞修复报告](day5-越权业务逻辑漏洞修复报告.docx)

## 项目结构

```
/opt/Class01/
├── app.py                  # Flask 主程序
├── templates/              # HTML 模板
│   ├── base.html           # 基础布局（导航栏含头像）
│   ├── login.html          # 登录页
│   ├── register.html       # 注册页
│   ├── index.html          # 首页（用户信息+头像）
│   ├── upload.html         # 头像上传页
│   ├── profile.html        # 个人中心（含充值功能）
│   ├── change_password.html# 修改密码
│   └── error.html          # 错误提示页
├── static/
│   └── css/style.css       # 样式文件（含头像样式）
├── uploads/                # 用户上传文件目录（static外）
├── data/
│   └── users.db            # SQLite 用户数据库
├── day5-越权业务逻辑漏洞修复报告.docx
├── day4-文件上传漏洞修复报告.md
├── day3漏洞报告.md
├── hunter_search.py        # 鹰图搜索脚本
└── generate_report.py      # 报告生成工具
```

## 技术栈

- **后端**: Flask + Werkzeug
- **数据库**: SQLite（参数化查询）
- **前端**: Jinja2 模板 + CSS
- **密码加密**: bcrypt（werkzeug.security）
- **源码管理**: Git + GitHub（`git@github.com:Erebus-yuyuan/-.git`）
