# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx[http2]",
# ]
#
# [[tool.uv.index]]
# url = "https://pypi.tuna.tsinghua.edu.cn/simple"
# default = true
# ///

import httpx

import sys
import random
import time

from utils import load_config


class ZhenBaiMeng:
    def __init__(self, cookies: str):
        self.cookies = cookies
        self.url = "https://masiro.me/admin/dailySignIn"

    def sign(self, session: httpx.Client):
        res = session.get(self.url).json()
        if res["code"] == 1:
            msg = res["msg"]
        elif res["code"] == -1:
            msg = res["msg"]
        else:
            msg = f"签到失败，信息为：{res}"
        return msg

    def main(self):
        msg_all = ""
        cookie = {
            item.split("=", 1)[0]: item.split("=", 1)[1]
            for item in self.cookies.split("; ")
        }

        session = httpx.Client()

        session.cookies.update(cookie)
        session.headers.update(
            {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
                "referer": "https://masiro.me/admin",
                "accept": "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,image/apng,*/*;"
                "q=0.8,application/signed-exchange;v=b3;q=0.9",
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )

        msg = self.sign(session)
        msg_all += msg + "\n\n"
        return msg_all


if __name__ == "__main__":
    cfg = load_config()
    debug = cfg.get("debug", False)
    cfg = cfg.get("zhenbaimeng", [])
    if not debug:
        sleep_time = random.randint(0, 60 * 5)
        print(f"sleep {sleep_time}s")
        time.sleep(sleep_time)
    result = ZhenBaiMeng(cfg["cookie"]).main()
    print("真白萌", result)
