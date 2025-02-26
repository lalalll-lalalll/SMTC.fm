import sys
import asyncio
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
import sqlite3
import os
import time
from New_Scrobbling import LastFmScrobbler, MediaDatabaseHandler, QueueProcessor, API_KEY, API_SECRET, SESSION_KEY
import json

# 获取当前脚本所在的目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 持久化ID json文件
LAST_ID_FILE = os.path.join(script_dir, 'last_id.json')

# 定义数据库文件路径（与 .py 文件同目录）
db_path = os.path.join(script_dir, 'media_history.db')

# 连接到 SQLite 数据库（如果不存在则会自动创建）
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 创建 media_history 表
cursor.execute('''
CREATE TABLE IF NOT EXISTS media_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT,
    timestamp INTEGER NOT NULL
)
''')

# 提交更改并关闭连接
conn.commit()
conn.close()

print(f"数据库文件已创建或连接成功，位于: {db_path}")

def insert_media_info(track, artist, album, timestamp):
    """将媒体信息插入到 SQLite 数据库"""
    try:
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 插入媒体信息
        cursor.execute('''
        INSERT INTO media_history (track, artist, album, timestamp) VALUES (?, ?, ?, ?)
        ''', (track, artist, album, timestamp))

        # 提交更改
        conn.commit()
        print("媒体信息已保存到数据库。")
    except Exception as e:
        print(f"保存媒体信息到数据库时发生错误: {e}")
    finally:
        # 关闭连接
        conn.close()

class MediaWatcher:
    def __init__(self):
        self.session = None
        self.loop = None  # 保存主事件循环的引用
        self.last_media_properties = None  # 保存上一次的媒体属性，用于去重
        self.last_playback_status = None  # 保存上一次的播放状态，用于去重

    async def on_media_properties_changed(self, sender, args):
        """处理媒体属性变化的事件回调函数"""
        try:
            # 检查 sender 是否为有效的会话对象
            if not hasattr(sender, "try_get_media_properties_async"):
                print("----------")
                print("无效的 sender 对象，跳过处理。")
                print("----------")
                return

            # 获取当前播放会话的媒体属性
            media_props = await sender.try_get_media_properties_async()

            # 检查媒体属性是否有效且发生变化
            if media_props and (media_props.title, media_props.artist, media_props.album_title) != self.last_media_properties:
                self.last_media_properties = (media_props.title, media_props.artist, media_props.album_title)
                print("----------")
                print("媒体信息更新:")
                print(f"标题: {media_props.title}")  # 打印歌曲标题
                print(f"艺术家: {media_props.artist}")  # 打印艺术家名称
                print(f"专辑: {media_props.album_title}")  # 打印专辑名称
                print("----------")

                # 将媒体信息写入数据库
                insert_media_info(media_props.title, media_props.artist, media_props.album_title, int(time.time()))

                scrobbler = LastFmScrobbler(API_KEY, API_SECRET, SESSION_KEY)
                db_handler = MediaDatabaseHandler(db_path)
                queue_processor = QueueProcessor(db_handler, scrobbler, LAST_ID_FILE)
                queue_processor.process_queue()





        except Exception as e:
            print(f"获取媒体属性时发生错误: {e}")

    async def watch_for_changes(self):
        """监听系统级别的媒体播放状态变化"""
        try:
            # 获取当前的事件循环，并保存引用
            self.loop = asyncio.get_running_loop()

            # 请求全局媒体传输控制会话管理器
            session_manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()

            if session_manager:
                # 定义一个内部方法来更新当前会话
                async def update_current_session():
                    current_session = session_manager.get_current_session()
                    if current_session != self.session:
                        self.session = current_session
                        if self.session:
                            # 注册媒体属性变化事件
                            self.session.add_media_properties_changed(
                                lambda sender, args: self._schedule_coroutine(self.on_media_properties_changed(sender, args))
                            )
                        else:
                            print("当前没有活动的媒体会话。")

                # 初始更新当前会话
                await update_current_session()

                print("开始监听媒体控制属性变化...")

                # 阻止程序退出，保持监听状态
                await asyncio.Event().wait()

        except Exception as e:
            print(f"监听过程中发生错误: {e}")

    def _schedule_coroutine(self, coroutine):
        """将异步任务提交到主事件循环中"""
        if self.loop and not self.loop.is_closed():
            # 使用 run_coroutine_threadsafe 将任务提交到主事件循环
            asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        else:
            print("事件循环不可用，无法调度任务")

def cleanup():
    print("正在执行清理操作...")
    os.remove(db_path)
    os.remove(LAST_ID_FILE)

if __name__ == "__main__":

    try:   
        # 创建 MediaWatcher 实例
        media_watcher = MediaWatcher()

        # 使用 asyncio.run 启动异步任务
        asyncio.run(media_watcher.watch_for_changes())

    except KeyboardInterrupt:
        # 捕获用户中断 (Ctrl+C)
        print("\n检测到用户中断，正在退出...")

    finally:
        cleanup()
