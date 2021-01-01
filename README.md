# SECOND RECONSTRUCTION & TEST FIN @2021-1-1 23:46

----
> 第二次重构完成
----

## 主要功能：下载B站应援团里的图片

## 主要依赖库：
```python
import requests                                            # 请求用
import json                                                # 解析用
import os                                                  # 创建文件夹，文件查重用
from concurrent.futures import ThreadPoolExecutor,wait     # 线程池
from hyper.contrib import HTTP20Adapter                    # 添加了HTTP/2支持
```

## 简介：
+ 每次请求200条信息并从中获取msg_type==2的信息中的图片链接并加入线程池下载。
+ 需在settings.json中设置基地址（下载时在那个目录下建立文件夹）和下载图片时的最大线程数。
+ 按应援团名称命名文件夹
+ 可以从上次爬取到的位置继续下载（checkpoint.json）
+ 需要自己添加cookies.json，下文会介绍格式及用途


## 使用方法：
主程序：new_main.py

header：cookies.json

记录点信息：checkpoint.json

在cookie里面写好header：header1填进入应援团（https://messages.bilibili.com/）时候的header，header2换掉python默认的user-agent就行

示例（下面的user-agent和cookie记得自己填，:path项留给程序填，所有的字符串必须用双引号）：
```json
{
  "headers1": {
    ":authority": "api.vc.bilibili.com",
    ":method": "GET",
    ":path": "",
    ":scheme": "https",
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "zh-CN,zh;q=0.9",
    "cookie": "",
    "origin": "https://message.bilibili.com",
    "referer": "https://message.bilibili.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4343.0 Safari/537.36"
  },
  "headers2": {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4343.0 Safari/537.36"
  }
}
```
下载参数（checkpoint.json）首次启动由程序根据你的应援团列表自动生成（总之不管他就完事了）
首次启动会提示没有settings.json并自动生成，然后用文本编辑器填写下列信息即可。
```json
{
  "download_base_dir": "",    # 此处填写下载基地址的绝对路径
  "thread_max": 10            # 此处填写下载图片时的线程数
}
```