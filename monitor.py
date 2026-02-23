import requests
import time
import json
import os
from bs4 import BeautifulSoup

def load_config(config_path="config.json"):
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到配置文件 {config_path}，请检查路径。")
        exit(1)
    except json.JSONDecodeError:
        print(f"错误: 配置文件 {config_path} 格式不正确，请检查 JSON 语法。")
        exit(1)

def load_history(history_file):
    """加载已推送的历史记录"""
    if not os.path.exists(history_file):
        return set()
    with open(history_file, 'r', encoding='utf-8') as f:
        # 去除每行末尾的换行符并存入集合
        return set(line.strip() for line in f if line.strip())

def save_history(history_file, post_id):
    """将新推送的帖子ID追加到历史记录中"""
    with open(history_file, 'a', encoding='utf-8') as f:
        f.write(f"{post_id}\n")

def send_to_wechat(sendkey, title, content):
    """通过 Server酱 发送微信推送"""
    if not sendkey or sendkey.startswith("SCT_替换"):
        print("未配置有效的 Server酱 SendKey，跳过推送。")
        return

    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    data = {"title": title, "desp": content}
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print(f"[{time.strftime('%H:%M:%S')}] 成功推送到微信: {title}")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] 推送失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 推送发生异常: {e}")

def check_nga_user_posts(uid, user_name, config, pushed_posts):
    """检查特定用户的最新回复"""
    headers = {
        "User-Agent": config['nga_settings']['user_agent'],
        "Cookie": config['nga_settings']['cookie']
    }
    history_file = config['monitor_settings']['history_file']
    sendkey = config['push_service']['serverchan_sendkey']
    
    url = f"https://bbs.nga.cn/nuke.php?func=search&authorid={uid}"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'gbk'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 提取帖子列表 (注意：NGA DOM结构若有变动需调整此处)
        post_list = soup.find_all('div', class_='row')
        
        for post in post_list:
            post_link = post.find('a', class_='topic')
            if not post_link:
                continue
                
            post_url = post_link.get('href', '')
            post_title = post_link.text.strip()
            
            # 使用 URL 中的唯一标识作为去重依据
            post_id = post_url.split('&pid=')[-1] if '&pid=' in post_url else post_url
            
            if post_id and post_id not in pushed_posts:
                # 1. 加入内存集合
                pushed_posts.add(post_id)
                # 2. 写入本地文件持久化
                save_history(history_file, post_id)
                
                # 3. 构造推送内容
                full_url = f"https://bbs.nga.cn{post_url}"
                message_content = f"你关注的用户 **{user_name}** (UID: {uid}) 发布了新内容：\n\n**标题：** {post_title}\n\n[点击这里直达 NGA 帖子]({full_url})"
                
                send_to_wechat(sendkey, f"NGA更新: {user_name}", message_content)
                
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 检查 {user_name} (UID:{uid}) 时出错: {e}")

def main():
    print("加载配置文件...")
    config = load_config("config.json")
    
    history_file = config['monitor_settings']['history_file']
    check_interval = config['monitor_settings']['check_interval']
    target_users = config['target_users']
    
    print("加载历史推送记录...")
    pushed_posts = load_history(history_file)
    print(f"已加载 {len(pushed_posts)} 条历史记录。")
    
    print("\n--- NGA 监控脚本已启动 ---")
    while True:
        for uid, user_name in target_users.items():
            print(f"[{time.strftime('%H:%M:%S')}] 正在检查: {user_name} (UID: {uid})...")
            check_nga_user_posts(uid, user_name, config, pushed_posts)
            
            # 多个用户之间增加随机小延迟，避免并发请求被NGA防火墙拦截
            time.sleep(3) 
            
        print(f"[{time.strftime('%H:%M:%S')}] 这一轮检查完成，等待 {check_interval} 秒...\n")
        time.sleep(check_interval)

if __name__ == "__main__":
    main()
