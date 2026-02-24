import requests
import time
import json
import os
from bs4 import BeautifulSoup

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

def check_nga_user_posts(uid, user_name, config, pushed_posts):
    headers = {
        "User-Agent": config['nga_settings']['user_agent'],
        "Cookie": config['nga_settings']['cookie']
    }
    history_file = config['monitor_settings']['history_file']
    sendkey = config['push_service']['serverchan_sendkey']
    
    # NGA 搜索接口
    url = f"https://bbs.nga.cn/nuke.php?func=search&authorid={uid}"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'gbk'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尝试查找帖子。NGA的搜索结果通常在 class 为 row1, row2 的 div 中，或者 table 中
        post_list = soup.find_all('div', class_='row') 
        
        if not post_list:
            # 【关键诊断代码】如果没找到帖子，把网页源码存下来！
            debug_file = f"debug_页面返回结果_UID_{uid}.html"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ 未找到 {user_name} 的任何发言。")
            print(f"可能原因：1.没发过言 2.Cookie失效被要求登录 3.触发验证码 4.NGA网页结构变了。")
            print(f"👉 诊断：已将网页保存为【{debug_file}】，请双击在浏览器中打开看看 NGA 到底提示了什么！")
            return

        for post in post_list:
            post_link = post.find('a', class_='topic')
            if not post_link:
                continue
                
            post_url = post_link.get('href', '')
            post_title = post_link.text.strip()
            post_id = post_url.split('&pid=')[-1] if '&pid=' in post_url else post_url
            
            if post_id and post_id not in pushed_posts:
                pushed_posts.add(post_id)
                save_history(history_file, post_id)
                full_url = f"https://bbs.nga.cn{post_url}"
                message_content = f"你关注的用户 **{user_name}** 发布了新内容：\n\n**标题：** {post_title}\n\n[点击这里直达 NGA 帖子]({full_url})"
                send_to_wechat(sendkey, f"NGA更新: {user_name}", message_content)
                
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 检查 {user_name} 时发生网络错误: {e}")

def main():
    print("加载配置文件...")
    config = load_config("config.json")
    history_file = config['monitor_settings']['history_file']
    check_interval = config['monitor_settings']['check_interval']
    target_users = config['target_users']
    pushed_posts = load_history(history_file)
    
    print("\n--- NGA 监控脚本已启动 ---")
    while True:
        for uid, user_name in target_users.items():
            print(f"[{time.strftime('%H:%M:%S')}] 正在检查: {user_name} (UID: {uid})...")
            check_nga_user_posts(uid, user_name, config, pushed_posts)
            time.sleep(3) 
            
        print(f"[{time.strftime('%H:%M:%S')}] 检查完毕，等待 {check_interval} 秒...\n")
        time.sleep(check_interval)

if __name__ == "__main__":
    main()
