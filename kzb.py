# -*- coding: utf-8 -*-
# @Author  : Doubebly
# @Time    : 2025/3/23 21:55
import base64
import sys
import time
import json
import requests
import re
import os


def natural_sort_key(s):
    """自然排序辅助函数"""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r'(\d+)', s)
    ]


def liveContent():
    a = ['#EXTM3U']
    try:
        base_url = "https://kzb29rda.com/prod-api/iptv/getIptvList?liveType=0&deviceType=1"
        response = requests.get(base_url, timeout=15)
        response.raise_for_status()
        data = response.json()

        sorted_list = sorted(
            data.get('list', []),
            key=lambda x: natural_sort_key(x.get("play_source_name", ""))
        )

        channels = []
        for item in sorted_list:
            name = item["play_source_name"]
            url = item["play_source_url"]
            extinf = (
                f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" '
                f'tvg-logo="https://logo.doube.eu.org/{name}.png" group-title="",{name}'
            )
            channels.append(extinf)
            channels.append(url)
        a += channels

    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {e}")
        a.append('# 错误：无法获取频道列表')
    except KeyError as e:
        print(f"数据解析错误，缺少字段: {e}")
        a.append('# 错误：数据格式异常')
    except json.JSONDecodeError:
        print("响应内容不是有效的JSON")
        a.append('# 错误：无效的API响应')
    return '\n'.join(a)


def b64encode(data):
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')


def b64decode(data):
    return base64.b64decode(data.encode('utf-8')).decode('utf-8')


def main():
    # 确保 output 文件夹存在
    os.makedirs("output", exist_ok=True)
    result = liveContent()
    output_m3u_path = "output/live.m3u"
    output_txt_path = "output/live.txt"

    with open(output_m3u_path, 'w', encoding='utf-8') as f:
        f.write(result)
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        f.write(result)


if __name__ == '__main__':
    main()
