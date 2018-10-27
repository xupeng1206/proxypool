# -*- coding: utf-8 -*-
import requests
from pyquery import PyQuery as pq
import time
import redis
import multiprocessing
from flask import Flask

app = Flask(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

CHECK_URL = 'https://www.baidu.com'
REDIS_KEY = 'proxy_pool'
MAX_PROXT_NUM = 50
CHECK_INTERVAL = 300  # s


_db = redis.Redis(
    host='192.168.1.20',
    port=6379,
    db=1,
    decode_responses=True,
)


class CheckUtil(object):

    def __init__(self):
        global CHECK_URL
        self.url = CHECK_URL

    def check(self, proxy):
        proxies = {
            'http': proxy
        }
        print('check', proxy)
        try:
            ret = requests.get(self.url, proxies=proxies)
            return ret.status_code == 200
        except Exception as e:
            return False

    def check_event(self):
        global _db, REDIS_KEY
        all_proxy = _db.smembers(REDIS_KEY)
        for proxy in all_proxy:
            if self.check(proxy):
                print(f'check_event: {proxy} is still OK !')
            else:
                print(proxy, 'is NG ! rm ing !')
                _db.srem(REDIS_KEY, proxy)


class ProxyGet(object):

    def get_pq_doc(self, url):
        global HEADERS
        res = requests.get(url, headers=HEADERS)
        print(res.status_code, type(res.status_code))
        if res.status_code == 200:
            doc = pq(res.content)
            return doc

    def get_proxys(self):
        for x in dir(self):
            if x.startswith('proxy_'):
                for proxy in getattr(self, x)():
                    yield proxy

    def proxy_xicidaili(self):
        for page_num in range(10):
            print(page_num)
            url = f'http://www.xicidaili.com/nn/{str(page_num+1)}'
            doc = self.get_pq_doc(url)
            if doc:
                trs = doc('#ip_list tr~tr').items()
                for tr in trs:
                    ip = tr('td').eq(1).text()
                    port = tr('td').eq(2).text()
                    type = tr('td').eq(5).text()
                    yield type.lower() + '://' + ip + ':' + port

    def proxy_kuaidaili(self):
        for page_num in range(20):
            print(page_num)
            url = f'https://www.kuaidaili.com/free/inha/{str(page_num+1)}/'
            doc = self.get_pq_doc(url)
            if doc:
                trs = doc('#list tr~tr').items()
                for tr in trs:
                    ip = tr('td').eq(0).text()
                    port = tr('td').eq(1).text()
                    type = tr('td').eq(3).text()
                    yield type.lower() + '://' + ip + ':' + port
            time.sleep(1)


class ProxyAdd(object):

    def __init__(self):
        self.proxy_get = ProxyGet()
        self.check_util = CheckUtil()

    def is_enough(self):
        global _db, MAX_PROXT_NUM, REDIS_KEY
        return _db.scard(REDIS_KEY) == MAX_PROXT_NUM

    def put(self):
        global CHECK_URL, _db
        print('put')
        while not self.is_enough():
            for proxy in self.proxy_get.get_proxys():
                if self.is_enough():
                    break
                if self.check_util.check(proxy):
                    print(proxy, 'is OK! add to db !')
                    _db.sadd(REDIS_KEY, proxy)


class Run(object):

    @staticmethod
    def check():
        check_util = CheckUtil()
        while True:
            check_util.check_event()
            time.sleep(CHECK_INTERVAL)

    @staticmethod
    def add():
        proxyadd = ProxyAdd()
        while True:
            proxyadd.put()
            while proxyadd.is_enough():
                time.sleep(1)

    def main(self):
        add_process = multiprocessing.Process(target=Run.add)
        check_process = multiprocessing.Process(target=Run.check)
        add_process.start()
        check_process.start()


@app.route('/')
def hello_world():
    return _db.srandmember(REDIS_KEY, 1)[0]


if __name__ == '__main__':
    run = Run()
    run.main()
    app.run(host='0.0.0.0')
