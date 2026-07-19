#!/usr/bin/env python3
"""
鹰图 Hunter (https://hunter.qianxin.com/) API 搜索脚本

默认每次只搜索 10 条数据（节约配额），除非使用者明确指定 --page-size 参数。

使用方法：
    python3 hunter_search.py -q "搜索语法"
    python3 hunter_search.py -q 'body="调试信息" && body="admin"' --page 2
    python3 hunter_search.py -q 'body="login"' --page-size 20 --is-web 1

首次使用需要安装依赖：
    pip3 install requests
"""

import argparse
import base64
import json
import sys
from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("❌ 缺少 requests 库，请执行: pip3 install requests")
    sys.exit(1)

# ============================================================
# 🔑 API 配置
# ============================================================
API_KEY = "1ae0183221bf7a4243904ed5636f59a7ee7521220554b1c9134f3bb0ae0606e8"
API_URL = "https://hunter.qianxin.com/openApi/search"

# ============================================================
# ⚠️ 硬性默认值：每次只搜 10 条，节约配额
#    使用者可通过 --page-size 明确改写，但脚本默认绝不超过 10
# ============================================================
# 鹰图 API 硬性要求：page_size 最小为 10，否则返回 400
DEFAULT_PAGE_SIZE = 10
MIN_PAGE_SIZE = 10


def build_params(
    search_query: str,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    start_time: str = "",
    end_time: str = "",
    is_web: str = "",
    status_code: str = "",
) -> dict:
    """构建 API 请求参数"""
    # 如果未提供起止时间，默认搜索最近 7 天（确保不超过 30 天限制）
    if not start_time:
        start_time = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not end_time:
        end_time = datetime.now().strftime("%Y-%m-%d")

    # 搜索语法必须进行 URL-safe Base64 编码
    encoded_query = base64.urlsafe_b64encode(search_query.encode("utf-8")).decode("utf-8")

    params = {
        "api-key": API_KEY,
        "search": encoded_query,
        "page": page,
        "page_size": page_size,
        "start_time": start_time,
        "end_time": end_time,
    }
    if is_web:
        params["is_web"] = is_web
    if status_code:
        params["status_code"] = status_code
    return params


def search(
    search_query: str,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    start_time: str = "",
    end_time: str = "",
    is_web: str = "",
    status_code: str = "",
    raw: bool = False,
):
    """执行搜索并打印结果"""

    # 鹰图 API 要求 page_size 最小为 10
    if page_size < MIN_PAGE_SIZE:
        print(f"⚠️ 鹰图 API 要求 page_size 最小为 {MIN_PAGE_SIZE}，已自动调整为 {MIN_PAGE_SIZE}")
        page_size = MIN_PAGE_SIZE

    params = build_params(search_query, page, page_size, start_time, end_time, is_web, status_code)

    print(f"\n🔍 正在搜索: {search_query}")
    print(f"📄 页码: {page}  |  每页条数: {page_size}")
    print(f"📅 时间范围: {params['start_time']} ~ {params['end_time']}")
    print(f"{'─' * 60}")

    try:
        resp = requests.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return
    except json.JSONDecodeError:
        print(f"❌ 响应不是有效 JSON: {resp.text[:500]}")
        return

    code = data.get("code")
    if code != 200:
        msg = data.get("message") or data.get("msg") or "未知错误"
        print(f"❌ API 返回错误 (code={code}): {msg}")
        if raw:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    result_data = data.get("data", {})
    total_count = result_data.get("total", 0)
    time_cost = result_data.get("time", 0)
    arr = result_data.get("arr", [])
    rest_quota = result_data.get("rest_quota", "")
    consume_quota = result_data.get("consume_quota", "")

    if not arr:
        print("📭 未找到匹配结果")
        # 仍然显示配额信息
        if rest_quota:
            print(f"📊 {consume_quota}  |  {rest_quota}")
        return

    # ----- 统计摘要 -----
    print(f"\n📊 总计匹配: {total_count} 条  |  本次返回: {len(arr)} 条  |  耗时: {time_cost}ms")
    if consume_quota:
        print(f"💰 {consume_quota}  |  {rest_quota}")

    # ----- 逐条展示 -----
    print()
    for idx, item in enumerate(arr, 1):
        ip = item.get("ip", "N/A")
        port = item.get("port", "N/A")
        protocol = item.get("protocol", "")
        domain = item.get("domain", "") or item.get("host", "")
        title = (item.get("web_title", "") or item.get("title", "") or "").strip()
        url = item.get("url", "")
        status = item.get("status_code", "")
        province = item.get("province", "")
        city = item.get("city", "")
        is_web = item.get("is_web", "")
        base_protocol = item.get("base_protocol", "")

        print(f"  ┌─ [{idx:03d}] {'─' * 50}")
        print(f"  │  🌐 URL:     {url or f'{protocol}://{ip}:{port}'}")
        if domain:
            print(f"  │  📌 域名:    {domain}")
        print(f"  │  📍 IP:      {ip}:{port}")
        if status:
            print(f"  │  📡 状态码:  {status}")
        if protocol:
            print(f"  │  🔗 协议:    {protocol} ({base_protocol})")
        if title:
            print(f"  │  📋 标题:    {title[:100]}")
        if province or city:
            print(f"  │  🗺️  位置:    {province} {city}".strip())
        if is_web:
            print(f"  │  🌍 Web:     {is_web}")
        print(f"  └─{'─' * 55}\n")

    # ----- 分页提示 -----
    total_pages = (total_count + page_size - 1) // page_size
    if page < total_pages:
        print(f"💡 还有更多结果 (第 {page}/{total_pages} 页，共 {total_count} 条)，加 --page {page + 1} 查看下一页")
    print(f"{'=' * 60}")

    # raw 模式打印完整 JSON
    if raw:
        print("\n📦 完整 JSON 响应:")
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(
        description="鹰图 Hunter API 搜索工具 — 默认每次只返回 10 条数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s -q 'body="调试信息" && body="admin"'
  %(prog)s -q 'body="login"' --page 2
  %(prog)s -q 'ip=118.232.125.154'
  %(prog)s -q 'domain=example.com' --is-web 1
  %(prog)s -q 'title="登录"' --start 2025-01-01 --end 2025-12-31
  %(prog)s -q 'port=8080' --page-size 50 --status-code 200
  %(prog)s -q 'icp="粤ICP备"' --page-size 20 --raw
        """,
    )

    parser.add_argument("-q", "--query", required=True, help="搜索语法（必填）")
    parser.add_argument("--page", type=int, default=1, help="页码，默认 1")
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"每页条数，默认 {DEFAULT_PAGE_SIZE}（鹰图 API 最低要求 {MIN_PAGE_SIZE}）",
    )
    parser.add_argument("--start", dest="start_time", default="", help="开始日期，格式 YYYY-MM-DD，默认 7 天前")
    parser.add_argument("--end", dest="end_time", default="", help="结束日期，格式 YYYY-MM-DD，默认今天")
    parser.add_argument("--is-web", type=str, default="", help='是否仅搜索 Web 资产：1 或 0')
    parser.add_argument("--status-code", type=str, default="", help="筛选 HTTP 状态码，如 200")
    parser.add_argument("--raw", action="store_true", help="同时打印完整 JSON 响应")

    args = parser.parse_args()

    search(
        search_query=args.query,
        page=args.page,
        page_size=args.page_size,
        start_time=args.start_time,
        end_time=args.end_time,
        is_web=args.is_web,
        status_code=args.status_code,
        raw=args.raw,
    )


if __name__ == "__main__":
    main()
