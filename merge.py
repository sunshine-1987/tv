import requests
import time
import re
from collections import defaultdict

# 配置
MAIN_RAW_URL = "https://raw.githubusercontent.com/sunshine-1987/tv/refs/heads/main/源库.txt"
LOCAL_SRC_FILE = "源库.txt"
OUTPUT_FILE = "zb3.txt"
TIMEOUT_FETCH = 10
TIMEOUT_FAIL = 15

# 白名单频道，只保留这些台
CCTV_LIST = [
    "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+",
    "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV10", "CCTV11",
    "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17",
    "CCTV老故事", "CCTV中学生"
]
KID_LIST = ["优漫卡通", "卡酷少儿", "嘉佳卡通"]
MOVIE_LIST = [
    "经典香港电影", "抗战经典影片", "新片放映厅",
    "CHC影迷电影", "CHC动作电影", "CHC家庭影院"
]
# 卫视正则：匹配 【XX卫视】
REG_PROV = re.compile(r".+卫视$")

# 分组容器: key=频道名, value=链接集合
chan_map = defaultdict(set)
fail_urls = []

def fetch_text(url):
    """拉取源内容，超时判断"""
    try:
        resp = requests.get(url, timeout=TIMEOUT_FETCH)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        time.sleep(TIMEOUT_FAIL)
        try:
            resp = requests.get(url, timeout=TIMEOUT_FAIL)
            resp.raise_for_status()
            return resp.text
        except Exception:
            fail_urls.append(url)
            return None

def parse_m3u(text):
    """解析m3u格式，提取 台名,url"""
    res = []
    name = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            m = re.search(r",([^,]+)$", line)
            if m:
                name = m.group(1).strip()
        elif line.startswith("http"):
            if name:
                res.append((name, line))
                name = None
    return res

def parse_csv(text):
    """解析 名称,url 格式"""
    res = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "#" in line:
            continue
        if "," in line and line.startswith("http") is False:
            sp = line.split(",", 1)
            if len(sp) == 2:
                n, u = sp[0].strip(), sp[1].strip()
                if n and u.startswith("http"):
                    res.append((n, u))
    return res

def is_keep(name: str) -> bool:
    """判断是否在保留清单内"""
    if name in CCTV_LIST:
        return True
    if name in KID_LIST:
        return True
    if name in MOVIE_LIST:
        return True
    if REG_PROV.match(name):
        return True
    return False

def main():
    # 1. 下载源库.txt
    src_text = fetch_text(MAIN_RAW_URL)
    if src_text is None:
        print("源库.txt 拉取失败！")
        return
    lines = src_text.splitlines()
    section = None
    migu_urls = []
    other_urls = []
    rest_lines = []
    for l in lines:
        ll = l.strip()
        if ll == "#咪咕源":
            section = "migu"
            rest_lines.append(l)
            continue
        if ll == "#其他代理源":
            section = "other"
            rest_lines.append(l)
            continue
        if ll == "#失效源":
            section = "fail"
            rest_lines.append(l)
            continue
        if section == "migu":
            if ll.startswith("http"):
                migu_urls.append(ll)
            else:
                rest_lines.append(l)
        elif section == "other":
            if ll.startswith("http"):
                other_urls.append(ll)
            else:
                rest_lines.append(l)
        else:
            rest_lines.append(l)

    # 2. 遍历咪咕源
    for u in migu_urls:
        print(f"正在拉取咪咕源: {u}")
        txt = fetch_text(u)
        if not txt:
            continue
        items = parse_m3u(txt)
        for name, url in items:
            if is_keep(name):
                chan_map[name].add(url)
        time.sleep(2)

    # 3. 遍历其他代理源
    for u in other_urls:
        print(f"正在拉取代理源: {u}")
        txt = fetch_text(u)
        if not txt:
            continue
        items = parse_m3u(txt) + parse_csv(txt)
        for name, url in items:
            if is_keep(name):
                chan_map[name].add(url)
        time.sleep(2)

    # 4. 生成 zb3.txt
    out_lines = []
    out_lines.append("央视,#genre#")
    for c in CCTV_LIST:
        if c in chan_map:
            links = "#".join(chan_map[c])
            out_lines.append(f"{c},{links}")

    out_lines.append("")
    out_lines.append("卫视,#genre#")
    weishi = sorted([k for k in chan_map if REG_PROV.match(k)])
    for w in weishi:
        links = "#".join(chan_map[w])
        out_lines.append(f"{w},{links}")

    out_lines.append("")
    out_lines.append("🚀少儿,#genre#")
    for c in KID_LIST:
        if c in chan_map:
            links = "#".join(chan_map[c])
            out_lines.append(f"{c},{links}")

    out_lines.append("")
    out_lines.append("🚀影视,#genre#")
    for c in MOVIE_LIST:
        if c in chan_map:
            links = "#".join(chan_map[c])
            out_lines.append(f"{c},{links}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print(f"已生成 {OUTPUT_FILE}")

    # 5. 回填失效源到 #失效源 下方
    new_src = []
    in_fail = False
    for l in rest_lines:
        if l.strip() == "#失效源":
            in_fail = True
            new_src.append(l)
            for fu in fail_urls:
                new_src.append(fu)
            continue
        if in_fail:
            continue
        new_src.append(l)
    with open(LOCAL_SRC_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(new_src))
    print(f"已更新 {LOCAL_SRC_FILE}，失效链接 {len(fail_urls)} 条")

if __name__ == "__main__":
    main()
