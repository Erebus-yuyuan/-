# Flask 用户信息管理系统（安全靶场）

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
- CSRF Token 保护（所有 POST 表单）
- 密码哈希存储（bcrypt）
- 随机 Secret Key（256位）
- 会话安全配置（HttpOnly + SameSite=Lax）

## 报告文档

- [Day3 安全漏洞修复报告](day3漏洞报告.md)
- [安全漏洞修复报告 (Word)](security_report_v2.0.docx)
- [安全漏洞修复报告 (Markdown)](SECURITY_REPORT.md)
- [WAF 绕过检测报告](WAF_Bypass_Report.md)

## 项目结构

```
/opt/Class01/
├── app.py                  # Flask 主程序
├── templates/              # HTML 模板
│   ├── base.html           # 基础布局
│   ├── login.html          # 登录页
│   ├── register.html       # 注册页
│   ├── index.html          # 首页（用户信息）
│   └── change_password.html# 修改密码
├── static/css/style.css    # 样式文件
├── day3漏洞报告.md         # 安全审计报告
├── SECURITY_REPORT.md      # 安全修复报告
├── WAF_Bypass_Report.md    # WAF 绕过报告
├── hunter_search.py        # 鹰图搜索脚本
└── generate_report.py      # 报告生成工具
```

## 技术栈

- **后端**: Flask + Werkzeug
- **数据库**: SQLite（参数化查询）
- **前端**: Jinja2 模板 + CSS
- **密码加密**: bcrypt（werkzeug.security）
- **源码管理**: Git + GitHub（`git@github.com:Erebus-yuyuan/-.git`）
