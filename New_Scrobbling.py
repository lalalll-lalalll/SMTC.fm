import sys
import requests
import hashlib
import sqlite3
import os
import time
import json

# 配置常量
API_KEY = '1c979bafd82f041b34de0d152493e4f6'
API_SECRET = '3dc21d7e235f6a3db44e840254c18079'
API_URL = 'http://ws.audioscrobbler.com/2.0/'

def get_exe_directory():
    """获取 .exe 文件所在的目录"""
    if getattr(sys, 'frozen', False):  # 判断是否为打包后的 exe 文件
        # 如果是打包后的 exe 文件，获取 exe 所在目录
        return os.path.dirname(sys.executable)
    else:
        # 如果是普通 Python 脚本，获取脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))

def get_config_path(config_filename):
    """获取配置文件的完整路径"""
    exe_dir = get_exe_directory()
    config_path = os.path.join(exe_dir, config_filename)
    return config_path

# 使用函数获取配置文件路径
config_file = "config.json"  # 配置文件名
json_file_path = get_config_path(config_file)

# 检查配置文件是否存在
if os.path.exists(json_file_path):
    print(f"Config file found at: {json_file_path}")
    # 在这里读取配置文件内容
else:
    print("Config file not found!")


# 读取 JSON 文件并解析
try:
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        session_key = data.get('SESSION_KEY')  # 获取 SESSION_KEY 的值
        if session_key:
            print(f"SESSION_KEY: {session_key}")
        else:
            print("SESSION_KEY 未找到")
except FileNotFoundError:
    print(f"文件 {json_file_path} 未找到")
except json.JSONDecodeError as e:
    print(f"JSON 解析错误: {e}")

SESSION_KEY = session_key

# 获取脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
LAST_ID_FILE = os.path.join(script_dir, 'last_id.json')  # 将 JSON 文件保存在脚本目录下


class LastFmScrobbler:
    def __init__(self, api_key, api_secret, session_key):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session_key = session_key

    def generate_api_sig(self, params):
        """生成 API 签名"""
        param_string = ''.join([f"{key}{params[key]}" for key in sorted(params.keys())])
        param_string += self.api_secret
        return hashlib.md5(param_string.encode('utf-8')).hexdigest()

    def scrobble_track(self, track_info):
        """上传单首歌曲到 Last.fm"""
        params = {
            'method': 'track.scrobble',
            'api_key': self.api_key,
            'sk': self.session_key,
            'track': track_info['track'],
            'artist': track_info['artist'],
            'album': track_info.get('album', ''),
            'timestamp': track_info['timestamp']
        }

        # 添加 API 签名
        params['api_sig'] = self.generate_api_sig(params)

        try:
            response = requests.post(API_URL, data=params)
            if response.status_code == 200:
                print(f"歌曲 '{track_info['track']}' 成功上传到 Last.fm.")
            else:
                print(f"上传歌曲 '{track_info['track']}' 失败. 状态码: {response.status_code}")
                print(response.text)
        except requests.RequestException as e:
            print(f"请求失败: {e}")


class MediaDatabaseHandler:
    def __init__(self, db_path):
        self.db_path = db_path

    def get_new_tracks(self, last_id=0):
        """获取数据库中最新的歌曲记录"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, track, artist, album, timestamp FROM media_history WHERE id > ? ORDER BY id ASC",
                (last_id,)
            )
            rows = cursor.fetchall()

        return [
            {'id': row[0], 'track': row[1], 'artist': row[2], 'album': row[3], 'timestamp': row[4]}
            for row in rows
        ]


class QueueProcessor:
    def __init__(self, db_handler, scrobbler, last_id_file):
        self.db_handler = db_handler
        self.scrobbler = scrobbler
        self.last_id_file = last_id_file
        self.last_id = self.load_last_id()  # 加载上次保存的 last_id

    def load_last_id(self):
        """从文件中加载 last_id"""
        if os.path.exists(self.last_id_file):
            with open(self.last_id_file, 'r') as f:
                return json.load(f).get('last_id', 0)
        return 0

    def save_last_id(self, last_id):
        """保存 last_id 到文件"""
        with open(self.last_id_file, 'w') as f:
            json.dump({'last_id': last_id}, f)

    def process_queue(self):
        """检查新记录并上传到 Last.fm"""
        new_tracks = self.db_handler.get_new_tracks(last_id=self.last_id)
        if not new_tracks:
            print("没有发现新记录...")
            return

        print(f"发现 {len(new_tracks)} 条新记录...")
        for track in new_tracks:
            print(f"处理新记录: {track}")
            self.scrobbler.scrobble_track(track)
            self.last_id = max(self.last_id, track['id'])  # 更新最后处理的 ID

        # 保存最新的 last_id
        self.save_last_id(self.last_id)


def main(db_path):
    """主函数：初始化组件并启动队列处理器"""
    scrobbler = LastFmScrobbler(API_KEY, API_SECRET, SESSION_KEY)
    db_handler = MediaDatabaseHandler(db_path)
    queue_processor = QueueProcessor(db_handler, scrobbler, LAST_ID_FILE)

    # 处理一次队列
    queue_processor.process_queue()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python script.py <数据库路径>")
        sys.exit(1)

    db_path = sys.argv[1]
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件 '{db_path}' 不存在！")
        sys.exit(1)

    main(db_path)