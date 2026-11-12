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

# ========== 咪咕频道清单【完全照搬你PHP，顺序原样，pid一一对应】 ==========
MIGU_LIST = [
    {"name": "CCTV-1综合", "pid": "608807420", "group": "央视"},
    {"name": "CCTV-2财经", "pid": "631780532", "group": "央视"},
    {"name": "CCTV-3综艺", "pid": "624878271", "group": "央视"},
    {"name": "CCTV-4中文国际", "pid": "631780421", "group": "央视"},
    {"name": "CCTV-5体育", "pid": "641886683", "group": "央视"},
    {"name": "CCTV-5+体育赛事", "pid": "641886773", "group": "央视"},
    {"name": "CCTV-6电影", "pid": "624878396", "group": "央视"},
    {"name": "CCTV-7国防军事", "pid": "673168121", "group": "央视"},
    {"name": "CCTV-8电视剧", "pid": "624878356", "group": "央视"},
    {"name": "CCTV-9纪录", "pid": "673168140", "group": "央视"},
    {"name": "CCTV-10科教", "pid": "624878405", "group": "央视"},
    {"name": "CCTV-11戏曲", "pid": "667987558", "group": "央视"},
    {"name": "CCTV-12社会与法", "pid": "673168185", "group": "央视"},
    {"name": "CCTV-13新闻", "pid": "608807423", "group": "央视"},
    {"name": "CCTV-14少儿", "pid": "624878440", "group": "央视"},
    {"name": "CCTV-15音乐", "pid": "673168223", "group": "央视"},
    {"name": "CCTV-17农业农村", "pid": "673168256", "group": "央视"},
    {"name": "CCTV发现之旅", "pid": "624878970", "group": "央视"},
    {"name": "CCTV老故事", "pid": "884121956", "group": "央视"},
    {"name": "CCTV中学生", "pid": "708869532", "group": "央视"},
    {"name": "东方卫视", "pid": "651632648", "group": "卫视"},
    {"name": "江苏卫视", "pid": "623899368", "group": "卫视"},
    {"name": "广东卫视", "pid": "608831231", "group": "卫视"},
    {"name": "北京卫视", "pid": "630287636", "group": "卫视"},
    {"name": "辽宁卫视", "pid": "630291707", "group": "卫视"},
    {"name": "河北卫视", "pid": "962042070", "group": "卫视"},
    {"name": "江西卫视", "pid": "783847495", "group": "卫视"},
    {"name": "河南卫视", "pid": "790187291", "group": "卫视"},
    {"name": "陕西卫视", "pid": "738910838", "group": "卫视"},
    {"name": "大湾区卫视", "pid": "608917627", "group": "卫视"},
    {"name": "湖北卫视", "pid": "947472496", "group": "卫视"},
    {"name": "吉林卫视", "pid": "947472500", "group": "卫视"},
    {"name": "青海卫视", "pid": "947472506", "group": "卫视"},
    {"name": "东南卫视", "pid": "849116810", "group": "卫视"},
    {"name": "海南卫视", "pid": "947472502", "group": "卫视"},
    {"name": "海峡卫视", "pid": "849119120", "group": "卫视"},
    {"name": "中国农林卫视", "pid": "956904896", "group": "卫视"},
    {"name": "兵团卫视", "pid": "956923145", "group": "卫视"},
    {"name": "宁夏卫视", "pid": "738910535", "group": "卫视"},
    {"name": "三沙卫视", "pid": "961023778", "group": "卫视"},
    {"name": "黑龙江卫视", "pid": "738906901", "group": "卫视"},
    {"name": "优漫卡通频道", "pid": "626064703", "group": "少儿"},
    {"name": "嘉佳卡通", "pid": "614952364", "group": "少儿"},
    {"name": "经典动画大集合", "pid": "629942219", "group": "少儿"},
    {"name": "红色轮播台", "pid": "713600957", "group": "影视"},
    {"name": "新片放映厅", "pid": "619495952", "group": "影视"},
    {"name": "经典香港电影", "pid": "625703337", "group": "影视"},
    {"name": "军事迷必看大片", "pid": "617432318", "group": "影视"},
    {"name": "CHC影迷电影", "pid": "952383261", "group": "影视"},
    {"name": "CHC动作电影", "pid": "644368714", "group": "影视"},
    {"name": "CHC家庭影院", "pid": "644368373", "group": "影视"},
]
# 索引：pid → {name, group} 【优先pid匹配】
MIGU_PID_MAP = {item["pid"]: {"name": item["name"], "group": item["group"]} for item in MIGU_LIST}
# 兜底：name → group
MIGU_NAME_MAP = {item["name"]: item["group"] for item in MIGU_LIST}

# ========== 【其他代理源】 旧白名单逻辑 ==========
CCTV_LIST = [
    "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+",
    "CCTV6", "CCTV7", "CCTV8", "CCTV9", "CCTV10", "CCTV11",
    "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17",
    "CCTV老故事", "CCTV中学生"
]
KID_LIST = [
    "卡酷少儿", "金鹰卡通", "优漫卡通", "黑莓动画", "睛彩青少", "炫动卡通", "嘉佳卡通", "经典动画大集合"
]
MOVIE_LIST = [
    "经典香港电影", "抗战经典影片", "新片放映厅",
    "CHC影迷电影", "CHC动作电影", "CHC家庭影院", "红色轮播台", "军事迷必看大片"
]
WEISHI_LIST = [
    "河北卫视", "北京卫视", "湖南卫视", "浙江卫视", "天津卫视", "辽宁卫视",
    "山西卫视", "内蒙古卫视", "吉林卫视", "黑龙江卫视", "东方卫视", "江苏卫视",
    "安徽卫视", "东南卫视", "江西卫视", "山东卫视", "河南卫视", "湖北卫视",
    "广东卫视", "深圳卫视", "广西卫视", "海南卫视", "重庆卫视", "四川卫视",
    "贵州卫视", "云南卫视", "西藏卫视", "陕西卫视", "甘肃卫视", "青海卫视",
    "宁夏卫视", "新疆卫视"
]
WEISHI_ALIAS = {
    "上海东方卫视": "东方卫视",
    "东方卫视hd": "东方卫视",
    "福建东南卫视": "东南卫视",
    "东南卫视高清": "东南卫视",
    "旅游卫视": "海南卫视",
    "海南卫视hd": "海南卫视"
}

# 分组存储
group_data = {
    "央视": defaultdict(set),
    "卫视": defaultdict(set),
    "少儿": defaultdict(set),
    "影视": defaultdict(set),
}
fail_urls = []

# ===================== 工具函数 =====================
def normalize_name(raw_name: str) -> str:
    name = html.unescape(raw_name.strip())
    name = re.sub(r"[_\-，,、 ]+", "", name)
    name = re.sub(r"(高清|HD|hd|频道|直播|综合|财经|新闻|综艺|体育|电视剧|科教|戏曲|社会与法|少儿)", "", name)
    name = name.strip()
    return name

def extract_pid(url: str):
    """从咪咕播放链接提取pid数字"""
    m = re.search(r"pid[:=](\d+)", url)
    if m:
        return m.group(1)
    return None

def match_migu(raw_name: str, url: str):
    """咪咕源匹配：优先pid匹配，pid命中直接拿标准name+group；pid找不到再名字兜底"""
    pid = extract_pid(url)
    if pid and pid in MIGU_PID_MAP:
        info = MIGU_PID_MAP[pid]
        return info["name"], info["group"]
    raw = raw_name.strip()
    if raw in MIGU_NAME_MAP:
        return raw, MIGU_NAME_MAP[raw]
    n1 = normalize_name(raw)
    for std_name, g in MIGU_NAME_MAP.items():
        n2 = normalize_name(std_name)
        if n1 == n2:
            return std_name, g
    return None, None

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

def proxy_group_rule(raw_name: str):
    """代理源旧规则"""
    name = normalize_name(raw_name)
    cctv_match = re.search(r"CCTV\s*(\d+\+?)", name, re.IGNORECASE)
    if cctv_match:
        num = cctv_match.group(1)
        std_cctv = f"CCTV{num}"
        if std_cctv in CCTV_LIST:
            return std_cctv, "央视"
    if "CCTV老故事" in name:
        return "CCTV老故事", "央视"
    if "CCTV中学生" in name:
        return "CCTV中学生", "央视"
    for movie in MOVIE_LIST:
        if movie in name:
            return movie, "影视"
    for kid in KID_LIST:
        if kid in name:
            return kid, "少儿"
    lower_n = name.lower()
    if lower_n in WEISHI_ALIAS:
        return WEISHI_ALIAS[lower_n], "卫视"
    for ws in WEISHI_LIST:
        if ws in name:
            return ws, "卫视"
    return None, None

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

    # 处理咪咕源
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
            std_name, g = match_migu(raw_name, url)
            pid = extract_pid(url)
            print(f"原始台名:{raw_name} | pid={pid} → 标准:{std_name},分组:{g}")
            if std_name and g:
                group_data[g][std_name].add(url)
        time.sleep(2)

    # 处理代理源
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
            std_name, g = proxy_group_rule(raw_name)
            print(f"原始台名:{raw_name} → 标准:{std_name},分组:{g}")
            if std_name and g:
                group_data[g][std_name].add(url)
        time.sleep(2)

    # ---------------------- 生成输出 ----------------------
    out_lines = []

    # 央视：按清单顺序
    out_lines.append("央视,#genre#")
    for item in MIGU_LIST:
        if item["group"] == "央视" and item["name"] in group_data["央视"]:
            links = "#".join(group_data["央视"][item["name"]])
            out_lines.append(f"{item['name']},{links}")
    extra_cctv = [k for k in group_data["央视"] if k not in MIGU_NAME_MAP]
    for name in sorted(extra_cctv):
        links = "#".join(group_data["央视"][name])
        out_lines.append(f"{name},{links}")

    out_lines.append("")
    # 卫视：严格PHP原始顺序
    out_lines.append("卫视,#genre#")
    for item in MIGU_LIST:
        if item["group"] == "卫视" and item["name"] in group_data["卫视"]:
            links = "#".join(group_data["卫视"][item["name"]])
            out_lines.append(f"{item['name']},{links}")
    extra_weishi = [k for k in group_data["卫视"] if k not in MIGU_NAME_MAP]
    for name in sorted(extra_weishi):
        links = "#".join(group_data["卫视"][name])
        out_lines.append(f"{name},{links}")

    out_lines.append("")
    # 少儿：清单顺序
    out_lines.append("🚀少儿,#genre#")
    for item in MIGU_LIST:
        if item["group"] == "少儿" and item["name"] in group_data["少儿"]:
            links = "#".join(group_data["少儿"][item["name"]])
            out_lines.append(f"{item['name']},{links}")
    extra_kid = [k for k in group_data["少儿"] if k not in MIGU_NAME_MAP]
    for name in sorted(extra_kid):
        links = "#".join(group_data["少儿"][name])
        out_lines.append(f"{name},{links}")

    out_lines.append("")
    # 影视：清单顺序
    out_lines.append("🚀影视,#genre#")
    for item in MIGU_LIST:
        if item["group"] == "影视" and item["name"] in group_data["影视"]:
            links = "#".join(group_data["影视"][item["name"]])
            out_lines.append(f"{item['name']},{links}")
    extra_movie = [k for k in group_data["影视"] if k not in MIGU_NAME_MAP]
    for name in sorted(extra_movie):
        links = "#".join(group_data["影视"][name])
        out_lines.append(f"{name},{links}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print(f"\n✅ 已生成 {OUTPUT_FILE}")

    with open(FAIL_FILE, "w", encoding="utf-8") as f:
        f.write("#失效源\n")
        f.write("\n".join(fail_urls))
    print(f"✅ 已生成 {FAIL_FILE}，本次失效链接数量：{len(fail_urls)}")

if __name__ == "__main__":
    main()
