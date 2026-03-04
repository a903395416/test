import requests
import time
import json
import os
import re

def load_config(config_path="config.json"):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        exit(1)

def load_history(history_file):
    if not os.path.exists(history_file): #
        return set()
    with open(history_file, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def save_history(history_file, post_id):
    with open(history_file, 'a', encoding='utf-8') as f:
        f.write(f"{post_id}\n") #

def send_to_wechat(sendkey, title, content):
    """推送到微信 (Server酱)"""
    if not sendkey or "替换" in sendkey:
        return
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data, timeout=10)
        print(f"[{time.strftime('%H:%M:%S')}] 成功推送到微信")
    except:
        print("微信推送失败")

def send_to_feishu(webhook_url, title, content):
    """推送到飞书机器人"""
    if not webhook_url or "在这里填入" in webhook_url:
        return
    payload = {
        "msg_type": "text",
        "content": {
            "text": f"🔔 {title}\n\n{content}"
        }
    }
    try:
        requests.post(webhook_url, json=payload, timeout=10)
        print(f"[{time.strftime('%H:%M:%S')}] 成功推送到飞书")
    except:
        print("飞书推送失败")

def clean_html_tags(text):
    if not text: return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', str(text))
    return cleantext.replace('&nbsp;', ' ').replace('&#39;', "'").strip()

def check_nga_user_posts(uid, user_name, config, pushed_posts, is_first_run):
    url = f"https://nga.178.com/thread.php?authorid={uid}&searchpost=1&__output=11"
    headers = {
        "User-Agent": config['nga_settings']['user_agent'],
        "Cookie": config['nga_settings']['cookie'],
        "Referer": "https://nga.178.com/"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'gbk'
        res_json = response.json()
        data = res_json.get('data', {})
        items = []
        
        def extract_posts(node):
            if isinstance(node, dict):
                if 'tid' in node and 'pid' in node and 'content' in node:
                    try:
                        if int(node['tid']) > 10000: items.append(node)
                    except: pass
                for v in node.values(): extract_posts(v)
            elif isinstance(node, list):
                for v in node: extract_posts(v)

        extract_posts(data)
        
        for post in items:
            tid, pid, authorid = post.get('tid'), post.get('pid'), post.get('authorid')
            if str(authorid) != str(uid): continue
            
            post_id = f"tid_{tid}_pid_{pid}" #
            if post_id not in pushed_posts:
                pushed_posts.add(post_id)
                save_history(config['monitor_settings']['history_file'], post_id)
                
                content_text = clean_html_tags(post.get('content', ''))
                if not content_text: content_text = "[图片/表情/特殊格式内容]"
                
                # 构造消息内容 (移除了直达链接)
                action = "发布了新帖" if str(pid) == "0" else "发表了回复"
                msg_title = f"{user_name} {action}"
                msg_body = f"用户: {user_name}\n内容: {content_text}" # 这里显示完整内容
                
                if not is_first_run:
                    # 同时支持微信和飞书推送
                    send_to_wechat(config['push_service']['serverchan_sendkey'], msg_title, msg_body)
                    send_to_feishu(config['push_service']['feishu_webhook'], msg_title, msg_body)
                else:
                    print(f"    🤫 静默收录: {user_name} 的历史记录")
                    
    except Exception as e:
        print(f"检查出错: {e}")

def main():
    config = load_config()
    history_file = config['monitor_settings']['history_file']
    pushed_posts = load_history(history_file)
    is_first_run = len(pushed_posts) == 0
    
    print(f"已加载 {len(pushed_posts)} 条历史记录")
    print("\n--- NGA 监控脚本 (多平台推送版) 已启动 ---")
    
    while True:
        for uid, user_name in config['target_users'].items():
            print(f"[{time.strftime('%H:%M:%S')}] 检查: {user_name}...")
            check_nga_user_posts(uid, user_name, config, pushed_posts, is_first_run)
            time.sleep(5)
        is_first_run = False 
        time.sleep(config['monitor_settings']['check_interval'])

if __name__ == "__main__":
    main()
