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
        
        def extract_posts(node):
            if isinstance(node, dict):
                # 【终极补丁】：强制要求必须包含 'content' 字段！
                # 这样就能把那些伪装成帖子的“元数据”和“系统广告”彻底挡在门外。
                if 'tid' in node and 'pid' in node and 'content' in node:
                    items.append(node)
                else:
                    for v in node.values():
                        extract_posts(v)
            elif isinstance(node, list):
                for v in node:
                    extract_posts(v)

        extract_posts(data)
        
        if not items:
            print(f"[{time.strftime('%H:%M:%S')}] 💤 {user_name} 暂无新动态。")
            return
            
        new_post_count = 0
        for post in items:
            tid = post.get('tid', '')
            pid = post.get('pid', 0)
            authorid = post.get('authorid', '')
            
            if str(authorid) != str(uid):
                continue
                
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
                    
                message_content = f"你关注的用户 **{user_name}** {action}：\n\n**相关标题：** {subject}\n\n**具体内容：** {content_snippet}...\n\n[点击这里直达 NGA]({post_url})"
                
                if is_first_run:
                    print(f"    🤫 静默收录: {content_text[:20].replace(chr(10), ' ')}...")
                else:
                    send_to_wechat(sendkey, f"NGA更新: {user_name}", message_content)
                    
        if new_post_count > 0 and not is_first_run:
            print(f"[{time.strftime('%H:%M:%S')}] 🔔 {user_name} 有 {new_post_count} 条新动态，已推送到微信！")
        elif new_post_count == 0:
            print(f"[{time.strftime('%H:%M:%S')}] 💤 {user_name} 暂无新动态。")
                
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 网络请求发生异常: {e}")

def main():
    print("加载配置文件...")
    config = load_config("config.json")
    history_file = config['monitor_settings']['history_file']
    check_interval = config['monitor_settings']['check_interval']
    target_users = config['target_users']
    pushed_posts = load_history(history_file)
    
    is_first_run = len(pushed_posts) == 0
    
    print(f"已加载 {len(pushed_posts)} 条历史记录。")
    if is_first_run:
        print("\n⚠️ 首次运行：为了防止 Server酱 额度耗尽，第一轮检查将只把最新的帖子写入本地，**不会推送到微信**。")
        
    print("\n--- NGA 监控脚本 (究极无敌防弹版) 已启动 ---")
    
    while True:
        for uid, user_name in target_users.items():
            print(f"[{time.strftime('%H:%M:%S')}] 正在检查: {user_name} (UID: {uid})...")
            check_nga_user_posts(uid, user_name, config, pushed_posts, is_first_run)
            time.sleep(5) 
            
        is_first_run = False 
            
        print(f"[{time.strftime('%H:%M:%S')}] 本轮检查完毕，等待 {check_interval} 秒...\n")
        time.sleep(check_interval)

if __name__ == "__main__":
    main()
