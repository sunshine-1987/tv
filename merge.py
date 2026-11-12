# -*- coding: utf-8 -*-
"""
直播源汇总脚本（配合 GitHub Actions 运行）
- 读取源库.txt 中 #咪咕源 / #其他代理源 下的链接
- 逐链接拉取，兼容 m3u(#EXTINF) 与 csv(名称,url) 两种格式
- 台名归一化后宽松匹配，分类汇总到 央视 / 卫视 / 🚀少儿 / 🚀影视
- 同一频道多条链接用 # 拼接、去重保序
- 打不开的链接回填到 #失效源
"""
import requests
import time
import re
import html
from collections import defaultdict
from urllib.parse import quote

# ============ 配置 ============
MAIN_RAW_URL = "https://raw.githubusercontent.com/sunshine-1987/tv/refs/heads/main/源库.txt"
LOCAL_SRC_FILE = "源库.txt"
OUTPUT_FILE = "zb3.txt"
TIMEOUT_FETCH = 10      # 首次等待 10 秒
TIMEOUT_FAIL = 15       # 失败再等 15 秒重试
SLEEP_BETWEEN = 2       # 每个源之间间隔

# ============ 标准频道清单（输出顺序） ============
CCTV_LIST = [
    "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+",
    "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV10", "CCTV11",
    "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17",
    "CCTV老故事", "CCTV中学生",
]
KID_LIST = ["卡酷少儿", "金鹰卡通", "优漫卡通", "黑莓动画", "睛彩青少", "炫动卡通", "嘉佳卡通"]
MOVIE_LIST = ["经典香港电影", "抗战经典影片", "新片放映厅", "CHC影迷电影", "CHC动作电影", "CHC家庭影院"]

# 省级卫视固定顺序清单（依据广电总局卫星直播中心省级电视节目名单整理）
# 前 6 个按常用优先级排列，其余按地理/官方顺序补全；清单内频道按此顺序输出
WEISHI_LIST = [
    "河北卫视", "北京卫视", "湖南卫视", "浙江卫视", "天津卫视", "辽宁卫视",
    "山西卫视", "内蒙古卫视", "吉林卫视", "黑龙江卫视", "东方卫视", "江苏卫视",
    "安徽卫视", "东南卫视", "江西卫视", "山东卫视", "河南卫视", "湖北卫视",
    "广东卫视", "深圳卫视", "广西卫视", "海南卫视", "重庆卫视", "四川卫视",
    "贵州卫视", "云南卫视", "西藏卫视", "陕西卫视", "甘肃卫视", "青海卫视",
    "宁夏卫视", "新疆卫视",
]
# 卫视别名 -> 标准名（归一化后包含匹配）
WEISHI_ALIAS = [
    (("东方卫视", "上海东方"), "东方卫视"),
    (("东南卫视", "福建东南"), "东南卫视"),
    (("旅游卫视", "海南卫视"), "海南卫视"),
]

# 少儿关键词 -> 标准名（包含匹配，按优先级从上到下）
KID_RULES = [
    ("卡酷", "卡酷少儿"),
    ("金鹰", "金鹰卡通"),
    ("优漫", "优漫卡通"),
    ("黑莓", "黑莓动画"),
    ("睛彩", "睛彩青少"),
    ("炫动", "炫动卡通"),
    ("嘉佳", "嘉佳卡通"),
]
# 影视关键词 -> 标准名
MOVIE_RULES = [
    ("香港电影", "经典香港电影"),
    ("抗战", "抗战经典影片"),
    ("新片", "新片放映厅"),
    ("影迷电影", "CHC影迷电影"),
    ("动作电影", "CHC动作电影"),
    ("家庭影院", "CHC家庭影院"),
]

# 分组容器: 标准名 -> 有序链接列表
chan_map = defaultdict(list)
chan_seen = defaultdict(set)
fail_urls = []


def add_channel(std_name, url):
    """同一频道多链接去重后用 # 拼接，保序"""
    if not url or not url.startswith("http"):
        return
    if url not in chan_seen[std_name]:
        chan_seen[std_name].add(url)
        chan_map[std_name].append(url)


def normalize(name: str) -> str:
    """台名归一化：解码 HTML 实体、去空格/符号/后缀词、统一大小写"""
    if not name:
        return ""
    name = html.unescape(name)              # &#32; &#40; 等实体解码
    name = name.replace("\\_", "").replace("_", "")
    name = re.sub(r"[\s\-—（）()\[\]【】·:：|]", "", name)
    name = name.upper()
    for suf in ["高清", "HD", "频道", "直播"]:
        while name.endswith(suf):
            name = name[: -len(suf)]
    return name


def clean_display(name: str) -> str:
    """输出用台名：解码并去掉结尾 高清/HD/频道/直播 等后缀"""
    name = html.unescape(name).strip()
    for suf in ["高清", "HD", "hd", "频道", "直播"]:
        while name.endswith(suf):
            name = name[: -len(suf)].strip()
    return name


def match_cctv(norm: str):
    """从归一化名中提取 CCTV 编号，返回标准名；否则 None"""
    # 编号后不能紧跟字母/数字，避免 CCTV4K 被当成 CCTV4
    m = re.search(r"CCTV\s*-?\s*(\d{1,2}\+?)(?![0-9A-Za-z])", norm)
    if m:
        return f"CCTV{m.group(1)}"
    if "老故事" in norm:
        return "CCTV老故事"
    if "中学生" in norm:
        return "CCTV中学生"
    return None


def match_weishi(norm: str, raw_name: str):
    """卫视匹配：先别名归一到清单标准名；否则原名若在清单内用原名；清单外保留原名（排最后）"""
    for keys, std in WEISHI_ALIAS:
        if any(k in norm for k in keys):
            return std
    disp = clean_display(raw_name)
    if disp in WEISHI_LIST:
        return disp
    return disp


def classify(raw_name: str):
    """归类，返回 (分组, 标准名)；不保留返回 None。
    顺序：央视 -> 少儿 -> 影视 -> 卫视（避免“金鹰卡通卫视”被卫视抢走）"""
    if not raw_name:
        return None
    norm = normalize(raw_name)

    # 1. 央视
    cctv = match_cctv(norm)
    if cctv and cctv in CCTV_LIST:
        return ("央视", cctv)

    # 2. 少儿（优先于卫视判断）
    for kw, std in KID_RULES:
        if kw in norm:
            return ("🚀少儿", std)

    # 3. 影视
    for kw, std in MOVIE_RULES:
        if kw in norm:
            return ("🚀影视", std)

    # 4. 卫视（包含“卫视”即视为省级卫视）
    if "卫视" in norm:
        return ("卫视", match_weishi(norm, raw_name))

    return None


def encode_raw_url(url: str) -> str:
    """对含中文/特殊字符的 raw 链接路径做编码，避免 GitHub Bad request"""
    # 仅对路径部分编码，保留 scheme/host/query
    m = re.match(r"^(https?://[^/]+)(/.*)$", url)
    if not m:
        return url
    return m.group(1) + quote(m.group(2), safe="/?&=:#%")


def fetch_text(url: str):
    """拉取文本；首次 10 秒超时，失败等 15 秒重试；再失败记为失效"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    target = encode_raw_url(url)
    try:
        resp = requests.get(target, headers=headers, timeout=TIMEOUT_FETCH)
        resp.raise_for_status()
        return resp.text
    except Exception:
        time.sleep(TIMEOUT_FAIL)
        try:
            resp = requests.get(target, headers=headers, timeout=TIMEOUT_FAIL)
            resp.raise_for_status()
            return resp.text
        except Exception:
            fail_urls.append(url)
            return None


def parse_m3u(text: str):
    """解析标准 m3u：#EXTINF 最后逗号后为台名，下一 http 行为链接"""
    res = []
    name = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            m = re.search(r",([^,]+)$", line)
            name = m.group(1).strip() if m else None
        elif line.startswith("http"):
            if name:
                res.append((name, line))
            name = None
    return res


def parse_csv(text: str):
    """解析 csv：台名,链接（跳过 #genre# 等分组标题）"""
    res = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line and not line.startswith("http"):
            sp = line.split(",", 1)
            if len(sp) == 2:
                n, u = sp[0].strip(), sp[1].strip()
                if n and u.startswith("http"):
                    res.append((n, u))
    return res


def parse_source(text: str):
    """同一链接两种格式都尝试，合并结果"""
    items = parse_m3u(text)
    items += parse_csv(text)
    return items


def main():
    # 1. 下载源库
    src_text = fetch_text(MAIN_RAW_URL)
    if src_text is None:
        print("源库.txt 拉取失败！")
        return

    section = None
    migu_urls, other_urls, rest_lines, old_fail = [], [], [], []
    for l in src_text.splitlines():
        ll = l.strip()
        if ll == "#咪咕源":
            section = "migu"; rest_lines.append(l); continue
        if ll == "#其他代理源":
            section = "other"; rest_lines.append(l); continue
        if ll == "#失效源":
            section = "fail"; rest_lines.append(l); continue

        if section in ("migu", "other"):
            if ll.startswith("http"):
                (migu_urls if section == "migu" else other_urls).append(ll)
            else:
                rest_lines.append(l)
        elif section == "fail":
            if ll.startswith("http"):
                old_fail.append(ll)
            rest_lines.append(l)
        else:
            rest_lines.append(l)

    print(f"咪咕源 {len(migu_urls)} 条，代理源 {len(other_urls)} 条，历史失效 {len(old_fail)} 条")

    # 2. 遍历所有链接，逐个解析（咪咕 / 代理统一走双格式解析）
    for group, urls in (("咪咕", migu_urls), ("代理", other_urls)):
        for u in urls:
            print(f"[{group}] 拉取: {u}")
            txt = fetch_text(u)
            if not txt:
                print(f"  -> 无法访问，记入失效源")
                continue
            items = parse_source(txt)
            print(f"  -> 解析到 {len(items)} 条频道")
            for name, url in items:
                hit = classify(name)
                if hit:
                    g, std = hit
                    add_channel(std, url)
            time.sleep(SLEEP_BETWEEN)

    # 3. 生成 zb3.txt
    out = []
    out.append("央视,#genre#")
    for c in CCTV_LIST:
        if c in chan_map:
            out.append(f"{c},{'#'.join(chan_map[c])}")

    out.append("")
    out.append("卫视,#genre#")
    weishi_all = [k for k in chan_map if classify(k) and classify(k)[0] == "卫视"]
    # 清单内按 WEISHI_LIST 顺序，清单外按名称排序排最后
    weishi_ordered = [w for w in WEISHI_LIST if w in chan_map]
    weishi_extra = sorted([w for w in weishi_all if w not in WEISHI_LIST])
    for w in weishi_ordered + weishi_extra:
        out.append(f"{w},{'#'.join(chan_map[w])}")

    out.append("")
    out.append("🚀少儿,#genre#")
    for c in KID_LIST:
        if c in chan_map:
            out.append(f"{c},{'#'.join(chan_map[c])}")

    out.append("")
    out.append("🚀影视,#genre#")
    for c in MOVIE_LIST:
        if c in chan_map:
            out.append(f"{c},{'#'.join(chan_map[c])}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"已生成 {OUTPUT_FILE}，共 {sum(len(v) for v in chan_map.values())} 条链接")

    # 4. 回填失效源（历史失效 + 本次新失效，去重保序）
    merged_fail = list(dict.fromkeys(old_fail + fail_urls))
    new_src = []
    in_fail = False
    for l in rest_lines:
        if l.strip() == "#失效源":
            in_fail = True
            new_src.append(l)
            for fu in merged_fail:
                new_src.append(fu)
            continue
        if in_fail:
            continue  # 旧失效行已被收集进 old_fail，不再重复写
        new_src.append(l)
    with open(LOCAL_SRC_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(new_src) + "\n")
    print(f"已更新 {LOCAL_SRC_FILE}，失效链接 {len(merged_fail)} 条")


if __name__ == "__main__":
    main()
