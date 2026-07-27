# Flask 用户信息管理系统（安全靶场）

> 版本：Day9 - 全面安全加固 + 工程化改进

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
- **修改密码**（CSRF Token 防护 + 原密码校验 + 密码复杂度校验 + 频率限制）
- **动态页面加载**
  - /page 路由，从 pages/ 目录加载页面内容
  - 支持 .html 后缀自动补全
  - 帮助中心页面（/page?name=help）
- **管理员用户管理**
  - /admin/users 页面，仅 admin 角色可访问
  - 按用户名模糊搜索
  - 列表展示所有用户信息
  - 权限校验：普通用户不可见
- **Ping 网络诊断**（/ping）
  - 需要登录访问
  - 支持 IP 地址和域名格式
  - 严格白名单校验，防止命令注入
  - 黑色控制台风格输出结果
- **欢迎页**（/welcome）
  - GET 方式，支持 URL 参数 name 定制欢迎语
  - 不传参数时默认显示"亲爱的用户"
- **用户反馈**（/feedback）
  - GET 显示反馈表单（姓名 + 留言内容）
  - POST 提交后展示反馈结果
- **面包屑导航**
  - 用户管理 -> 查看详情 -> 返回上一页（而非直接回首页）
- CSRF Token 保护（所有 POST 表单）
- 密码哈希存储（bcrypt）
- 集中配置管理（config.py，支持环境变量覆盖）
- 会话安全配置（HttpOnly + SameSite=Lax + 2 小时自动过期）
- 内容安全策略（CSP）头（阻止 XSS 和资源注入）
- 操作审计日志（登录、密码修改、Ping、管理员操作等敏感操作全记录）
- Ping 频率限制（每个 IP 每分钟最多 10 次）
- 余额精度修复（避免浮点数显示 `xxx.0` 问题）

## 权限体系

- **RBAC 装饰器**: `require_login` / `require_role("admin")`
- 普通用户只能查看和操作自己的资料
- 管理员可以查看所有用户资料、访问用户管理页面
- 管理员可在导航栏和首页看到"用户管理"入口
- 所有资金操作绑定当前会话用户

## 报告文档

- [Day3 安全漏洞修复报告](reports/day3漏洞报告.md)
- [Day4 文件上传漏洞修复报告](reports/day4-文件上传漏洞修复报告.md)
- [Day5 越权业务逻辑漏洞修复报告](reports/day5-越权业务逻辑漏洞修复报告.docx)
- [Day6 文件包含漏洞修复报告](reports/day6-文件包含漏洞修复报告.docx)
- [Day7 CSRF漏洞修复报告](reports/day7-CSRF漏洞修复报告.docx)
- [Day8 SSTI漏洞修复报告](reports/day8-ssti漏洞修复报告.docx)
- [Day9 命令执行漏洞修复报告](reports/day9-命令执行漏洞修复报告.docx)

## 项目结构

```
/opt/Class01/
├── app.py                  # Flask 主程序
├── config.py               # 集中配置管理（环境变量覆盖）
├── requirements.txt        # Python 依赖清单
├── Dockerfile              # Docker 容器化部署
├── .dockerignore           # Docker 构建忽略
├── tests/                  # 单元测试
│   ├── __init__.py
│   ├── conftest.py         # 共享测试夹具
│   ├── test_auth.py        # 认证模块测试（8 个用例）
│   ├── test_ping.py        # Ping 模块测试（7 个用例）
│   └── test_security.py    # 安全加固测试（7 个用例）
├── logs/                   # 审计日志目录
├── pages/                  # 动态页面目录
│   └── help.html           # 帮助中心页面
├── reports/                # 安全修复报告
│   ├── day3漏洞报告.md
│   ├── day4-文件上传漏洞修复报告.md
│   ├── day5-越权业务逻辑漏洞修复报告.docx
│   ├── day6-文件包含漏洞修复报告.docx
│   ├── day7-CSRF漏洞修复报告.docx
│   ├── day8-ssti漏洞修复报告.docx
│   ├── day9-命令执行漏洞修复报告.docx
│   ├── SECURITY_REPORT.md
│   ├── WAF_Bypass_Report.md
│   ├── security_report_v2.0.docx
│   └── generate_report.py  # 报告生成工具
├── templates/              # HTML 模板
│   ├── base.html           # 基础布局（导航栏含头像）
│   ├── login.html          # 登录页
│   ├── register.html       # 注册页
│   ├── index.html          # 首页（用户信息+头像）
│   ├── upload.html         # 头像上传页
│   ├── profile.html        # 个人中心（含充值、修改密码功能）
│   ├── change_password.html# 修改密码（旧版，不再使用）
│   ├── ping.html           # Ping 网络诊断页
│   ├── admin_users.html    # 管理员用户管理页
│   └── error.html          # 错误提示页
├── static/
│   └── css/style.css       # 样式文件（含头像样式）
├── uploads/                # 用户上传文件目录（static外）
├── data/
│   └── users.db            # SQLite 用户数据库
├── hunter_search.py        # 鹰图搜索脚本
```

## 技术栈

- **后端**: Flask + Werkzeug
- **数据库**: SQLite（参数化查询）
- **前端**: Jinja2 模板 + CSS
- **密码加密**: bcrypt（werkzeug.security）
- **HTML净化**: bleach（XSS防护）
- **源码管理**: Git + GitHub（`git@github.com:Erebus-yuyuan/-.git`）

## 安全修复历史

### Day6 - 文件包含漏洞修复
- **LFI-001 任意文件读取**：递归移除路径遍历序列 + os.path.realpath 规范化 + pages/ 目录白名单检查
- **XSS-001 内容未经转义渲染**：以 bleach HTML 净化器替换 | safe 过滤器，仅保留安全标签与属性
- **INF-001 数据库文件泄露**：LFI 防护间接保护数据库文件

### Day7 - CSRF漏洞修复
- **CSRF-001 /change-password 无 CSRF 防护**：添加 validate_csrf_token() 校验及表单 hidden 字段
- **IDOR-001 越权修改他人密码**：从 session 获取用户名，移除表单 username 字段
- **AUTH-001 无需原密码即可修改**：增加原密码 check_password_hash 校验
- **SESSION-001 修改密码后会话未失效**：成功后 session.clear() 强制重新登录
- **RATE-001 密码修改无频率限制**：复用 LOGIN_LIMIT 机制限制尝试次数
- **PWEAK-001 弱密码策略**：长度 8 位 + 大小写字母/数字/特殊字符至少三类

### Day8 - SSTI漏洞修复
- **SSTI-001 /welcome 路由注入漏洞**：将 render_template_string(f"...{name}...") 改为 render_template_string("...{{ name }}...", name=name)，阻止通过 URL 参数注入 Jinja2 模板代码
- **SSTI-002 /feedback POST 路由注入漏洞**：同时修复 name 和 message 两个注入点，将 f-string 拼接改为模板变量传递
- **新增 /welcome 欢迎页**：支持 URL 参数 name 自定义欢迎语
- **新增 /feedback 反馈页**：支持 GET 表单展示和 POST 结果展示

### Day9 - 命令执行漏洞修复 + 全面安全加固

**命令执行漏洞修复**
- **CMD-001 Ping 功能命令注入**：移除 f-string 命令拼接 + shell=True，改用参数列表方式调用 subprocess.check_output()
- **CMD-002 用户输入无校验**：增加 IP 地址正则白名单校验和域名格式校验，IP 每段范围 0-255 检查
- **新增 /ping Ping 网络诊断功能**：需登录访问，蓝底白字风格控制台输出页面

**安全加固增强**
- **SEC-001 内容安全策略（CSP）**：全局添加 Content-Security-Policy 头，形成 XSS 纵深防御
- **SEC-002 Session 过期机制**：添加 PERMANENT_SESSION_LIFETIME = 2 小时，防止会话长期有效
- **SEC-003 操作审计日志**：记录登录成功/失败、退出、密码修改、Ping 执行、管理员搜索、头像上传、充值等敏感操作
- **SEC-004 Ping 频率限制**：每个 IP 每分钟最多 10 次请求，防止滥用和内网探测
- **SEC-005 余额浮点数精度修复**：使用 2 位小数舍入，避免显示 `xxx.0` 形式的浮点数

**工程化改进**
- **DEV-001 集中配置管理**：创建 config.py，所有硬编码配置集中管理，支持环境变量覆盖（SECRET_KEY、DB_DIR、SESSION_LIFETIME_HOURS 等）
- **DEV-002 依赖锁定**：创建 requirements.txt，明确版本区间
- **DEV-003 Docker 容器化**：创建 Dockerfile + .dockerignore，支持一行命令容器化部署
- **DEV-004 单元测试**：创建 tests/ 测试目录，共 25 个测试用例覆盖认证、Ping 命令注入防护、安全头验证、审计日志、配置检查
- **DEV-005 生产级运行**：支持 gunicorn 多 worker 生产部署
