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
        input("按回车键退出...")
        exit(1)

def load_history(history_file):
    if not os.path.exists(history_file):
        return set()
    with open(history_file, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def save_history(history_file, post_id):
    with open(history_file, 'a', encoding='utf-8') as f:
        f.write(f"{post_id}\n")

def send_to_wechat(sendkey, title, content):
    if not sendkey or "替换" in sendkey:
        print("未配置有效的 Server酱 SendKey，跳过推送。")
        return
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data, timeout=10)
        print(f"[{time.strftime('%H:%M:%S')}] 成功推送到微信: {title}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 微信推送失败: {e}")

def clean_html_tags(text):
    if not text:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', str(text))
    return cleantext.replace('&nbsp;', ' ').replace('&#39;', "'").strip()

def check_nga_user_posts(uid, user_name, config, pushed_posts, is_first_run):
    url = f"https://nga.178.com/thread.php?authorid={uid}&searchpost=1&__output=11"
    
    headers = {
        "User-Agent": config['nga_settings']['user_agent'],
        "Cookie": config['nga_settings']['cookie'],
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://nga.178.com/"
    }
    
    history_file = config['monitor_settings']['history_file']
    sendkey = config['push_service']['serverchan_sendkey']
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'gbk'
        
        try:
            res_json = response.json()
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ API返回异常，可能是 Cookie 失效。")
            return
        
        data = res_json.get('data', {})
        items = []
        
        # 【最终真理】不瞎找，也不死板。只提取 NGA 返回的以 "0", "1", "2" 等纯数字作为 Key 的字典
        # 这样既能拿到所有历史发言，又能完美避开所有系统级的广告参数！
        if isinstance(data, dict):
            for k, post in data.items():
                if str(k).isdigit() and isinstance(post, dict):
                    if 'tid' in post and 'pid' in post:
                        items.append(post)
        elif isinstance(data, list):
            for post in data:
                if isinstance(post, dict) and 'tid' in post and 'pid' in post:
                    items.append(post)
        
        if not items:
            print(f"[{time.strftime('%H:%M:%S')}] 💤 {user_name} 暂无新动态。")
            return
            
        new_post_count = 0
        for post in items:
            tid = post.get('tid', '')
            pid = post.get('pid', 0)
            
            if not tid:
                continue
                
            raw_subject = post.get('subject', '')
            raw_content = post.get('content', '')
            
            subject = clean_html_tags(raw_subject) if raw_subject else "未命名回复贴"
            content_text = clean_html_tags(raw_content)
            if not content_text:
                content_text = "[图片/表情/特殊格式内容]"
                
            content_snippet = content_text[:100]
            
            post_id = f"tid_{tid}_pid_{pid}"
            
            if post_id not in pushed_posts:
                pushed_posts.add(post_id)
                save_history(history_file, post_id)
                new_post_count += 1
                
                if str(pid) == "0":
                    post_url = f"https://nga.178.com/read.php?tid={tid}"
                    action = "发布了新帖"
                else:
                    post_url = f"https://nga.178.com/read.php?tid={tid}&pid={pid}"
                    action = "发表了回复"
                    
                message_content = f"你关注的用户 **{user_name}** {action}：\n\n**相关
