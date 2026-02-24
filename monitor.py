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
    """清理 NGA 返回数据中可能夹带的 HTML 标签"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', str(text))
    return cleantext.replace('&nbsp;', ' ').replace('&#39;', "'").strip()

def check_nga_user_posts(uid, user_name, config, pushed_posts):
    # 【核心修改】1. 域名改为 nga.178.com 匹配 Cookie。2. 增加 __output=11 调用原生 JSON API
    url = f"https://nga.178.com/nuke.php?__output=11&func=search&authorid={uid}"
    
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
            with open(f"debug_非JSON结果_UID_{uid}.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 无法解析 JSON，可能 Cookie 失效，已保存 Debug 文件。")
            return
        
        # 提取 NGA 返回的数据主体
        data = res_json.get('data', {})
        if not data or (isinstance(data, list) and len(data) == 0):
            print(f"[{time.strftime('%H:%M:%S')}] 💤 {user_name} 暂无新动态。")
            return
            
        # NGA 的 JSON 结构是个伪数组（以数字作为 Key 的字典）
        items = []
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict) and ('tid' in v or 'subject' in v):
                    items.append(v)
        elif isinstance(data, list):
            items = data

        for post in items:
            tid = post.get('tid', '')
            pid = post.get('pid', 0)
            
            # 过滤掉不需要的脏数据
            if not tid:
                continue
                
            subject = clean_html_tags(post.get('subject', '无标题'))
            content_snippet = clean_html_tags(post.get('content', ''))[:100] # 截取前100字作为摘要
            
            # 使用 tid 和 pid 联合作为绝对唯一的帖子 ID
            post_id = f"tid_{tid}_pid_{pid}"
            
            if post_id not in pushed_posts:
                pushed_posts.add(post_id)
                save_history(history_file, post_id)
                
                # 判断是发的新主帖还是回复
                if str(pid) == "0":
                    post_url = f"https://nga.178.com/read.php?tid={tid}"
                    action = "发布了新帖"
                else:
                    post_url = f"https://nga.178.com/read.php?tid={tid}&pid={pid}"
                    action = "发表了回复"
                    
                message_content = f"你关注的用户 **{user_name}** {action}：\n\n**标题：** {subject}\n\n**内容摘要：** {content_snippet}...\n\n[点击这里直达 NGA]({post_url})"
                
                send_to_wechat(sendkey, f"NGA更新: {user_name}", message_content)
                
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 网络请求发生异常: {e}")

def main():
    print("加载配置文件...")
    config = load_config("config.json")
    history_file = config['monitor_settings']['history_file']
    check_interval = config['monitor_settings']['check_interval']
    target_users = config['target_users']
    pushed_posts = load_history(history_file)
    
    print("\n--- NGA 监控脚本 (API 直连版) 已启动 ---")
    while True:
        for uid, user_name in target_users.items():
            print(f"[{time.strftime('%H:%M:%S')}] 正在检查: {user_name} (UID: {uid})...")
            check_nga_user_posts(uid, user_name, config, pushed_posts)
            time.sleep(3) 
            
        print(f"[{time.strftime('%H:%M:%S')}] 本轮检查完毕，等待 {check_interval} 秒...\n")
        time.sleep(check_interval)

if __name__ == "__main__":
    main()
