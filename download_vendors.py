#!/usr/bin/env python3
"""
下载第三方 CDN 资源到本地
解决 CDN 加载慢的问题
"""
import os
import urllib.request
from pathlib import Path

# 创建目录
VENDOR_DIR = Path('static/vendor')
VENDOR_DIR.mkdir(parents=True, exist_ok=True)

# 需要下载的资源
RESOURCES = {
    # Lucide Icons
    'lucide/lucide.min.js': 'https://unpkg.com/lucide@0.263.1/dist/umd/lucide.min.js',

    # Toast UI Editor
    'toastui/toastui-editor.min.css': 'https://uicdn.toast.com/editor/latest/toastui-editor.min.css',
    'toastui/toastui-editor-all.min.js': 'https://uicdn.toast.com/editor/latest/toastui-editor-all.min.js',

    # LightGallery
    'lightgallery/lightgallery.min.css': 'https://cdnjs.cloudflare.com/ajax/libs/lightgallery/2.7.2/css/lightgallery.min.css',
    'lightgallery/lg-zoom.min.css': 'https://cdnjs.cloudflare.com/ajax/libs/lightgallery/2.7.2/css/lg-zoom.min.css',
    'lightgallery/lg-rotate.min.css': 'https://cdnjs.cloudflare.com/ajax/libs/lightgallery/2.7.2/css/lg-rotate.min.css',
    'lightgallery/lg-thumbnail.min.css': 'https://cdnjs.cloudflare.com/ajax/libs/lightgallery/2.7.2/css/lg-thumbnail.min.css',
    'lightgallery/lightgallery.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/lightgallery/2.7.2/lightgallery.min.js',
    'lightgallery/lg-zoom.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/lightgallery/2.7.2/plugins/zoom/lg-zoom.min.js',
    'lightgallery/lg-rotate.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/lightgallery/2.7.2/plugins/rotate/lg-rotate.min.js',
    'lightgallery/lg-thumbnail.min.js': 'https://cdnjs.cloudflare.com/ajax/libs/lightgallery/2.7.2/plugins/thumbnail/lg-thumbnail.min.js',

    # Chart.js
    'chartjs/chart.min.js': 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js',
}

def download_file(url, dest_path):
    """下载文件"""
    dest_path = VENDOR_DIR / dest_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists():
        print(f'[OK] Already exists: {dest_path}')
        return

    try:
        print(f'[>>] Downloading: {url}')
        urllib.request.urlretrieve(url, dest_path)
        print(f'[OK] Completed: {dest_path}')
    except Exception as e:
        print(f'[ERROR] Failed: {url} - {e}')

def main():
    print('=' * 60)
    print('下载第三方资源到本地')
    print('=' * 60)
    print()

    total = len(RESOURCES)
    for i, (dest, url) in enumerate(RESOURCES.items(), 1):
        print(f'[{i}/{total}] ', end='')
        download_file(url, dest)

    print()
    print('=' * 60)
    print('下载完成！')
    print('=' * 60)
    print()
    print('下一步：修改模板文件，将 CDN 链接替换为本地路径')
    print('例如：')
    print('  CDN:  https://unpkg.com/lucide@0.263.1/dist/umd/lucide.min.js')
    print('  本地: {{ url_for("static", filename="vendor/lucide/lucide.min.js") }}')

if __name__ == '__main__':
    main()
