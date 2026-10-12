#!/usr/bin/env python3
# coding: utf-8
# ---------------------------------------------------------------------------
# 920share cf_clearance 全自動刷新器
#   流程：呼叫 FlareSolverr 過 Cloudflare JS 盾 → 取 cf_clearance + 真實 UA
#         → 組成單行 Cookie → 寫入本機檔 和（可選）更新 GitHub Gist
#   爬蟲端 ext 的 cookie 欄位填「那個檔的 raw URL」即可全自動，過期自動刷新。
#
# 需要的環境變數（未設則用預設 / 跳過）：
#   FLARESOLVERR_URL  FlareSolverr 端點，預設 http://127.0.0.1:8191/v1
#   TARGET_URL        過盾目標，預設 https://920share.com/category/censored
#   OUTPUT_FILE       本機輸出檔，預設 ./920ck.txt
#   GIST_ID           （可選）要更新的 Gist id；設了才會推 Gist
#   GIST_TOKEN        （可選）GitHub PAT，需 gist 權限
#   GIST_FILENAME     （可選）Gist 內檔名，預設 920ck.txt
# ---------------------------------------------------------------------------
import os
import sys
import json
import urllib.request

FLARESOLVERR_URL = os.environ.get("FLARESOLVERR_URL", "http://127.0.0.1:8191/v1")
TARGET_URL = os.environ.get("TARGET_URL", "https://920share.com/category/censored")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "./920ck.txt")
GIST_ID = os.environ.get("GIST_ID", "")
GIST_TOKEN = os.environ.get("GIST_TOKEN", "")
GIST_FILENAME = os.environ.get("GIST_FILENAME", "920ck.txt")

# 爬蟲 ext 的 ua 必須與此一致；FlareSolverr 會回它實際用的 UA，一併輸出到檔尾註解
UA_HINT = "請把爬蟲 ext 的 ua 設成下方 # UA= 那一行的值"


def _post_json(url, payload, headers=None, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _patch_json(url, payload, headers, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def solve():
    """呼叫 FlareSolverr 過盾，回 (cookie_line, user_agent)。"""
    resp = _post_json(FLARESOLVERR_URL, {
        "cmd": "request.get",
        "url": TARGET_URL,
        "maxTimeout": 60000,
    })
    if resp.get("status") != "ok":
        raise RuntimeError("FlareSolverr 失敗: %s" % resp.get("message"))
    sol = resp["solution"]
    ua = sol.get("userAgent", "").strip()
    cookies = sol.get("cookies", []) or []
    # 只保留 CF 相關 cookie（cf_clearance 必要，__cf_bm 有助於穩定）
    wanted = {}
    for c in cookies:
        name = c.get("name", "")
        if name in ("cf_clearance", "__cf_bm", "cf_chl_rc_m"):
            wanted[name] = c.get("value", "")
    if "cf_clearance" not in wanted:
        raise RuntimeError("未取得 cf_clearance（可能未過盾）")
    cookie_line = "; ".join("%s=%s" % (k, v) for k, v in wanted.items())
    return cookie_line, ua


def write_local(cookie_line, ua):
    body = cookie_line + "\n# UA=" + ua + "\n"
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(body)
    print("[local] 已寫入 %s" % OUTPUT_FILE)


def push_gist(cookie_line, ua):
    if not (GIST_ID and GIST_TOKEN):
        return
    url = "https://api.github.com/gists/%s" % GIST_ID
    payload = {"files": {GIST_FILENAME: {"content": cookie_line + "\n# UA=" + ua + "\n"}}}
    headers = {
        "Authorization": "Bearer %s" % GIST_TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "ck-refresher",
        "Content-Type": "application/json",
    }
    st = _patch_json(url, payload, headers)
    print("[gist] 更新回應 HTTP %s" % st)


def main():
    cookie_line, ua = solve()
    print("[ok] cf_clearance 取得成功")
    print("     cookie=%s..." % cookie_line[:60])
    print("     UA=%s" % ua)
    write_local(cookie_line, ua)
    try:
        push_gist(cookie_line, ua)
    except Exception as e:
        print("[gist] 失敗（本機檔已更新，可忽略）：%s" % e, file=sys.stderr)


if __name__ == "__main__":
    main()
