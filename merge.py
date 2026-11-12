import requests
import time
import re
from collections import defaultdict
import html

# ===================== 配置区 =====================
MAIN_RAW_URL = "https://raw.githubusercontent.com/sunshine-1987/tv/refs/heads/main/源库.txt"
OUTPUT_FILE = "zb3.txt"
FAIL_FILE = "失效源.txt"
TIMEOUT_FETCH = 10
TIMEOUT_FAIL = 15

# CCTV 清单
CCTV_LIST = [
    "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+",
    "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV10", "CCTV11",
    "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17",
    "CCTV老故事", "CCTV中学生"
]

# 少儿清单（固定顺序）
KID_LIST = [
    "卡酷少儿", "金鹰卡通", "优漫卡通", "黑莓动画", "睛彩青少", "炫动卡通", "嘉佳卡通"
]

# 影视清单
MOVIE_LIST = [
    "经典香港电影", "抗战经典影片", "新片放映厅",
    "CHC影迷电影", "CHC动作电影", "CHC家庭影院"
]

# 卫视【固定顺序，按你要求优先在前】
WEISHI_LIST = [
    "河北卫视", "北京卫视", "湖南卫视", "浙江卫视", "天津卫视", "辽宁卫视",
    "山西卫视", "内蒙古卫视", "吉林卫视", "黑龙江卫视", "东方卫视", "江苏卫视",
    "安徽卫视", "东南卫视", "江西卫视", "山东卫视", "河南卫视", "湖北卫视",
    "广东卫视", "深圳卫视", "广西卫视", "海南卫视", "重庆卫视", "四川卫视",
    "贵州卫视", "云南卫视", "西藏卫视", "陕西卫视", "甘肃卫视", "青海卫视",
    "宁夏卫视", "新疆卫视"
]
# 卫视别名映射
WEISHI_ALIAS = {
    "上海东方卫视": "东方卫视",
    "东方卫视hd": "东方卫视",
    "福建东南卫视": "东南卫视",
    "东南卫视高清": "东南卫视",
    "旅游卫视": "海南卫视",
    "海南卫视hd": "海南卫视"
}

chan_map = defaultdict(set)
fail_urls = []

# ===================== 工具函数 =====================
def normalize_name(raw_name: str) -> str:
    """台名归一化：解码、去符号、清高清/HD后缀"""
    name = html.unescape(raw_name.strip())
    name = re.sub(r"[_\-，,、 ]+", "", name)
    name = re.sub(r"(高清|HD|hd|频道|直播|综合|财经|新闻|综艺|体育|电影|电视剧|科教|戏曲|社会与法|少儿)", "", name)
    name = name.strip()
    # 匹配CCTV
    cctv_match = re.search(r"CCTV\s*(\d+\+?)", name, re.IGNORECASE)
    if cctv_match:
        num = cctv_match.group(1)
        std_cctv = f"CCTV{num}"
        if std_cctv in CCTV_LIST:
            return std_cctv
    # 老故事、中学生
    if "CCTV老故事" in name:
        return "CCTV老故事"
    if "CCTV中学生" in name:
        return "CCTV中学生"
    # 少儿匹配
    for kid in KID_LIST:
        if kid in name:
            return kid
    # 影视匹配
    for movie in MOVIE_LIST:
        if movie in name:
            return movie
    # 卫视别名
    lower_n = name.lower()
    if lower_n in WEISHI_ALIAS:
        return WEISHI_ALIAS[lower_n]
    # 卫视标准名
    for ws in WEISHI_LIST:
        if ws in name:
            return ws
    return name

def fetch_text(url):
    try:
        resp = requests.get(url, timeout=TIMEOUT_FETCH)
        resp.raise_for_status()
        return resp.text
    except Exception:
        time.sleep(TIMEOUT_FAIL)
        try:
            resp = requests.get(url, timeout=TIMEOUT_FAIL)
            resp.raise_for_status()
            return resp.text
        except Exception:
            fail_urls.append(url)
            return None

def parse_m3u(text):
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

def is_keep(std_name: str) -> bool:
    if std_name in CCTV_LIST:
        return True
    if std_name in KID_LIST:
        return True
    if std_name in MOVIE_LIST:
        return True
    if std_name in WEISHI_LIST:
        return True
    return False

# ===================== 主逻辑 =====================
def main():
    print(f"开始拉取源库：{MAIN_RAW_URL}")
    src_text = fetch_text(MAIN_RAW_URL)
    if src_text is None:
        print("源库.txt 拉取失败！")
        return
    lines = src_text.splitlines()
    print(f"源库一共读取 {len(lines)} 行")

    section = None
    migu_urls = []
    other_urls = []

    for l in lines:
        ll = l.strip()
        if ll == "#咪咕源":
            section = "migu"
            print("✅ 进入 #咪咕源 分区")
            continue
        if ll == "#其他代理源":
            section = "other"
            print("✅ 进入 #其他代理源 分区")
            continue
        if ll == "#失效源":
            section = "fail"
            print("✅ 进入 #失效源 分区，此分区链接不再抓取")
            continue

        if section == "migu":
            if ll.startswith("http"):
                migu_urls.append(ll)
                print(f"👉 读到咪咕源地址：{ll}")
        elif section == "other":
            if ll.startswith("http"):
                other_urls.append(ll)
                print(f"👉 读到代理源地址：{ll}")

    print(f"\n==== 汇总读取结果 ====")
    print(f"咪咕源数量：{len(migu_urls)}，列表：{migu_urls}")
    print(f"代理源数量：{len(other_urls)}，列表：{other_urls}")

    # 遍历咪咕源
    for u in migu_urls:
        print(f"\n【咪咕源】正在拉取: {u}")
        txt = fetch_text(u)
        if not txt:
            print(f"❌ {u} 获取内容失败")
            continue
        print(f"✅ 成功拿到源内容，行数：{len(txt.splitlines())}")
        items = parse_m3u(txt) + parse_csv(txt)
        print(f"解析提取频道数量：{len(items)}")
        for raw_name, url in items:
            std = normalize_name(raw_name)
            print(f"原始台名:{raw_name} → 标准:{std}")
            if is_keep(std):
                chan_map[std].add(url)
        time.sleep(2)

    # 遍历代理源
    for u in other_urls:
        print(f"\n【代理源】正在拉取: {u}")
        txt = fetch_text(u)
        if not txt:
            print(f"❌ {u} 获取内容失败")
            continue
        print(f"✅ 成功拿到源内容，行数：{len(txt.splitlines())}")
        items = parse_m3u(txt) + parse_csv(txt)
        print(f"解析提取频道数量：{len(items)}")
        for raw_name, url in items:
            std = normalize_name(raw_name)
            print(f"原始台名:{raw_name} → 标准:{std}")
            if is_keep(std):
                chan_map[std].add(url)
        time.sleep(2)

    print(f"\n✅ 全部源处理完成，一共收集到频道：{len(chan_map)}")

    # 生成 zb3.txt
    out_lines = []
    out_lines.append("央视,#genre#")
    for c in CCTV_LIST:
        if c in chan_map:
            links = "#".join(chan_map[c])
            out_lines.append(f"{c},{links}")

    out_lines.append("")
    out_lines.append("卫视,#genre#")
    # 先输出清单内顺序
    for ws in WEISHI_LIST:
        if ws in chan_map:
            links = "#".join(chan_map[ws])
            out_lines.append(f"{ws},{links}")
    # 清单外的卫视（兜底）
    outer_weishi = sorted(k for k in chan_map if k not in WEISHI_LIST and k not in CCTV_LIST and k not in KID_LIST and k not in MOVIE_LIST)
    for ow in outer_weishi:
        links = "#".join(chan_map[ow])
        out_lines.append(f"{ow},{links}")

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
    print(f"\n✅ 已生成 {OUTPUT_FILE}")

    # 失效链接单独写入失效源.txt，**不再修改源库.txt**
    with open(FAIL_FILE, "w", encoding="utf-8") as f:
        f.write("#失效源\n")
        f.write("\n".join(fail_urls))
    print(f"✅ 已生成 {FAIL_FILE}，本次失效链接数量：{len(fail_urls)}")

if __name__ == "__main__":
    main()
