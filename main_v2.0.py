#coding=UTF-8
import requests
import os
import json
from concurrent.futures import ThreadPoolExecutor,wait
from hyper.contrib import HTTP20Adapter


# 基础信息处理
# cookie.json为登录B站相关的header信息。header1获取API时使用(添加了HTTP2支持)，header2下载图片时使用(HTTP1)
# checkpoint.json中存储已经爬取过的应援团进度。格式：{"应援团(文件夹)名称": [应援团id号, 已爬取的信息编号]}
# unknown_msg_type_list中存储爬取中发现的未知msg_type类型的返回信息。如出现请手动issue。
# ??????         日志文件                                                                        ******目前暂未添加相关支持
# flag_chk 值说明：
# 0：正常执行
# 1：未找到checkpoint.json
# 2：checkpoint.json中存在错误，需重新生成


cookies = {}
checkpoint = {}

download_dir = ''
max_thread_get_pic = 1

flag_chk = 0
unknown_msg_type_list = []
pool_get_pic_content = ThreadPoolExecutor(max_workers=max_thread_get_pic)
list_get_pic_content = []


def init():
    global cookies, flag_chk, checkpoint, download_dir, max_thread_get_pic

    if not os.path.exists('cookies.json'):
        print("None cookie found! Check your files!")
        exit(0)
    with open('cookies.json', 'r', encoding='utf-8') as f:
        cookies = json.load(f)
        f.close()

    if os.path.exists('checkpoint.json'):
        try:
            with open('checkpoint.json', 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)
                f.close()
                flag_chk = 0
        except Exception as e:
            flag_chk = 2
            print("checkpoint.json 存在错误，即将重新生成")
            print("进度已丢失，将从头开始爬取")
            print("继续？")
            att = input("Y-继续 除Y外任意键-终止")
            if att != 'Y':
                exit(1)
    else:
        with open('checkpoint.json', 'w', encoding='utf-8') as f:
            f.close()
        flag_chk = 1

    with open('settings.json', 'r')as f:
        settings = json.load(f)
        download_dir = settings['download_base_dir']
        max_thread_get_pic = settings['thread_max']
        f.close()


def download(path_base, url, retry_times):                         # 下载模块
    path = f"{download_dir}/{path_base}/{url.split('/')[-1]}"
    if os.path.exists(path):                                       # 查重
        print(f"Current picture {path} existed, skipping...")
        return 0
    response = requests.get(url, headers=cookies['headers2'], timeout=30)
    if response.status_code != 200:                                # 有时候可能403，3次重试后退出，并保存图片链接
        if retry_times >= 3:
            print(f"{path} download failed.")
            return -1
        else:
            print(f"HTTP ERR {response.status_code}, retry is in progress.")
            list_get_pic_content.append(pool_get_pic_content.submit(download, path_base, url, retry_times+1))
            return -1
    with open(path, 'wb')as f:                                     # 写入文件
        f.write(response.content)
        print(f"{path} downloaded.")
        return 0


def get_pic_ind(gp_name, gp_id, seq_start, seq_end):
    # 抓取消息的API如下，文字前方带"$"符号的为使用时需替换的变量。需使用HTTP2。每次获取200条信息。
    # f'https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs?sender_device_id=1&talker_id= $应援团编号 &session_type=2&size= $获取消息条数 &end_seqno= $获取消息最右端+1 &begin_seqno= $获取消息区间最左端-1 &build=0&mobi_app=web'
    # messages信息的路径为{}['data']['messages']
    # 目前已知的nsg_type：
    # 1：文字+常规表情信息
    # 2：图片（我的目标）。但仍然混有部分自定义表情。
    # 5：系统消息？撤回消息？（目前观察到的信息为xxx撤回了信息）
    # 6：自定义表情
    # 7：分享up主的视频链接
    # 306：欢迎xx入群
    fin = 0
    while fin == 0:
        if seq_start + 200 >= seq_end:
            end_seqno = seq_end
            fin = 1
        else:
            end_seqno = seq_start + 200

        print(f"Getting messages from group:{gp_name} ranged from seqno {seq_start} to {end_seqno}")

        url = f'https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs?sender_device_id=1&talker_id={gp_id}&session_type=2&size={200}&end_seqno={end_seqno}&begin_seqno={seq_start - 1}&build=0&mobi_app=web'
        cookies['headers1'][':path'] = f'/svr_sync/v1/svr_sync/fetch_session_msgs?sender_device_id=1&talker_id={gp_id}&session_type=2&size={200}&end_seqno={end_seqno}&begin_seqno={seq_start - 1}&build=0&mobi_app=web'

        session_get_pic_url = requests.session()
        session_get_pic_url.mount("https://api.vc.bilibili.com/", HTTP20Adapter())
        r = session_get_pic_url.get(url, headers=cookies['headers1'])

        if r.status_code != 200 or json.loads(r.text)['code'] != 0:
            print("Getting messages error. Please check your environment.")
            exit(0)

        base = json.loads(r.text)['data']
        if base.get('messages'):
            messages = json.loads(r.text)['data']['messages']
        else:
            seq_start += 200
            continue

        for msg in messages:
            if msg['msg_type'] == 2:
                pic_url = json.loads(msg['content'])['url']
                # download(gp_name, pic_url, 0)
                list_get_pic_content.append(pool_get_pic_content.submit(download, gp_name, pic_url, 0))
            elif msg['msg_type'] != 1 and msg['msg_type'] != 2 and msg['msg_type'] != 5 and msg['msg_type'] != 6 and msg['msg_type'] != 7 and msg['msg_type'] != 306:
                unknown_msg_type_list.append(msg)
        seq_start += 200


def get_group_status():
    # 获取用户列表中所有应援团信息的API。需使用HTTP2。
    # API:https://api.vc.bilibili.com/session_svr/v1/session_svr/get_sessions?session_type=3&group_fold=1&unfollow_fold=0&sort_rule=2&build=0&mobi_app=web
    # json中包含session的list的路径：{}['data']['session_list']
    # API后面带的参数本次未使用所以没有研究
    # 编写这段代码的人列表里只有个位数的应援团，所以在有大量应援团的情况下可能会出bug

    target_url = f"https://api.vc.bilibili.com/session_svr/v1/session_svr/get_sessions?session_type=3&group_fold=1&unfollow_fold=0&sort_rule=2&build=0&mobi_app=web"
    cookies['headers1'][':path'] = f"/session_svr/v1/session_svr/get_sessions?session_type=3&group_fold=1&unfollow_fold=0&sort_rule=2&build=0&mobi_app=web"

    sessions = requests.session()
    sessions.mount("https://api.vc.bilibili.com/", HTTP20Adapter())
    r = sessions.get(target_url, headers=cookies['headers1'], timeout=30)

    if r.status_code != 200 or json.loads(r.text)['code'] != 0:
        print("Getting sessions error. Please check your environment.")
        exit(0)

    session_list = json.loads(r.content.decode('utf-8'))['data']['session_list']

    for element in session_list:
        end_seqno = element['last_msg']['msg_seqno']
        group_id = element['talker_id']
        group_name = element['group_name']

        if not os.path.exists(download_dir + group_name):
            os.mkdir(group_name)

        if flag_chk != 0:
            start_seqno = 0
        else:
            start_seqno = checkpoint[group_name][1]

        checkpoint[str(group_name)] = [group_id, end_seqno]
        print(f"Get session from group:{group_name}.")
        get_pic_ind(group_name, group_id, start_seqno, end_seqno)

    print("Get sessions complete.")


if __name__ == '__main__':
    init()
    get_group_status()
    wait(list_get_pic_content)
    with open('checkpoint.json', 'w') as f:
        json.dump(checkpoint, f)
        f.close()
    if len(unknown_msg_type_list) > 0:
        print("Warning: Unknown message type found. Please send generated file 'unknown_msg_list' to author. Thank you.")
        with open("unknown_msg_list.txt", 'w') as f:
            for msg in unknown_msg_type_list:
                f.write(str(msg)+"\n")
            f.close()
