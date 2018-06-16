import requests
from urllib.parse import urlencode
from requests.exceptions import RequestException
import json
from bs4 import BeautifulSoup
import re
import pymongo
from config import *
from hashlib import md5
from multiprocessing import Pool
import os

client = pymongo.MongoClient(MONGO_URL, connect=False)
db = client[MONGO_DB]


def get_page_index(offset, keyword):
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab': 3,
        'from': 'search_tab'
    }
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)
    response = requests.get(url)
    try:
        if response.status_code == 200:
            return response.text
    except RequestException as e:
        print('请求失败', url)
        return None


def get_page_detail(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36"
                      + "(KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36"}
    response = requests.get(url, headers=headers)
    try:
        if response.status_code == 200:
            return response.text
    except RequestException as e:
        print('请求失败', url)
        return Nonea


def parse_page_index(html):
    data = json.loads(html)
    if data and 'data' in data.keys():
        for item in data.get('data'):
            yield item.get('article_url')


def parse_page_detail(html, url):
    soup = BeautifulSoup(html, 'lxml')
    title = soup.select('title')[0].string

    images_pattern = re.compile('gallery: JSON.parse\("(.*)"\)', re.S)
    result = re.search(images_pattern, html)
    if result:
        data = json.loads(result.group(1).replace('\\', ''))
        if data and 'sub_images' in data.keys():
            images = [item.get('url') for item in data.get('sub_images')]
            for image in images:
                download_image(image, title)
            return {
                'title': title,
                'url': url,
                'images': images
            }
        else:
            return None


def save_to_mongodb(result):
    if db[MONGO_TABLE].insert(result):
        return True
    else:
        return False


# 下载图片
def download_image(url, title):
    print("正在下载：", title, url)
    response = requests.get(url)
    try:
        if response.status_code == 200:
            save_image(title, response.content)
    except RequestException as e:
        print('请求失败', url)
        return None


# 保存图片
def save_image(title, content):
    file_path = '{0}/{1}/'.format(os.getcwd(), title)

    if not os.path.exists(file_path):
        os.makedirs(file_path)

    with open(file_path + '/' + md5(content).hexdigest() + '.jpg', 'wb') as f:
        f.write(content)


def main(offset):
    html = get_page_index(offset, '街拍')
    for url in parse_page_index(html):
        if url is None:
            continue
        html = get_page_detail(url)
        if html:
            result = parse_page_detail(html, url)
            if result:
                save_to_mongodb(result)


if __name__ == '__main__':
    groups = [x * 20 for x in range(Group_Start, Group_End + 1)]
    pool = Pool()
    pool.map(main, groups)
