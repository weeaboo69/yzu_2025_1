import asyncio
import numpy as np
from bleak import BleakClient, BleakScanner
import pyaudio
import wave
import threading
import os
import time
from scipy import signal
import json
import tempfile

# 設定ESP32裝置的資訊
DEVICE_NAME = "ESP32_MusicSensor_BLE"
SERVICE_UUID = "180F"
CHARACTERISTIC_UUID = "2A19"

# 音樂檔案路徑
music_files = {
    "1": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/1.wav",
    "2": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/2.wav",
    "3": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/3.wav"
}

# 全局變數
current_playing_music = None
audio_thread = None
stop_flag = False
loaded_audio_data = {}
is_connected = False
client = None

COMM_FILE = os.path.join(tempfile.gettempdir(), "songlist_controller_comm.json")
STATUS_FILE = COMM_FILE + ".status"

# 初始化狀態
controller_status = {
    "connected": False,
    "playing": None,
    "last_update": time.time()
}

def update_status():
    """更新狀態文件"""
    global controller_status
    try:
        # 更新狀態信息
        controller_status["last_update"] = time.time()
        controller_status["connected"] = is_connected
        controller_status["playing"] = current_playing_music
        
        # 添加詳細的日誌
        log_message(f"嘗試更新狀態檔案：{STATUS_FILE}")
        log_message(f"狀態內容：連接={is_connected}, 播放={current_playing_music}")
        
        # 檢查路徑是否存在
        directory = os.path.dirname(STATUS_FILE)
        if not os.path.exists(directory):
            log_message(f"創建目錄：{directory}")
            os.makedirs(directory, exist_ok=True)
        
        # 寫入檔案
        with open(STATUS_FILE, 'w') as f:
            json.dump(controller_status, f)
            f.flush()  # 確保數據寫入磁盤
            os.fsync(f.fileno())  # 強制操作系統刷新文件緩衝
        
        # 確認檔案是否成功寫入
        if os.path.exists(STATUS_FILE):
            file_size = os.path.getsize(STATUS_FILE)
            log_message(f"狀態檔案已更新，大小：{file_size} 字節")
        else:
            log_message("警告：寫入後狀態檔案仍不存在")
            
    except Exception as e:
        log_message(f"更新狀態文件失敗: {e}")
        import traceback
        log_message(traceback.format_exc())

def ensure_status_file_exists():
    if not os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'w') as f:
            json.dump({
                "connected": False,
                "playing": None,
                "last_update": time.time()
            }, f)
        print(f"已創建初始狀態文件: {STATUS_FILE}")

def check_commands():
    """檢查是否有新命令"""
    if not os.path.exists(COMM_FILE):
        return

    try:
        # 檢查文件修改時間，只處理最近10秒內的命令
        if os.path.getmtime(COMM_FILE) < time.time() - 10:
            return
            
        with open(COMM_FILE, 'r') as f:
            cmd_data = json.load(f)
            
        command = cmd_data.get("command", "")
        params = cmd_data.get("params", {})
        
        log_message(f"收到UI命令: {command}, 參數: {params}")
        
        # 處理命令
        if command == "PLAY_MUSIC":
            index = params.get("index", "1")
            loop = params.get("loop", True)
            play_music(index, loop=loop)
        elif command == "STOP_MUSIC":
            stop_audio()
        elif command == "UPDATE_CONFIG":
            update_config(params)
        
        # 處理完後，重命名文件以避免重複處理
        os.rename(COMM_FILE, COMM_FILE + ".processed")
        
        # 更新狀態
        update_status()
    except Exception as e:
        log_message(f"處理命令失敗: {e}")

def update_config(config_data):
    """更新配置"""
    global music_files, loaded_audio_data
    
    try:
        # 更新音樂檔案路徑
        if "music_files" in config_data:
            new_music_files = config_data["music_files"]
            for key, path in new_music_files.items():
                if path and path != music_files.get(key, ""):
                    log_message(f"更新音樂檔案路徑 {key}: {path}")
                    music_files[key] = path
                    
                    # 重新載入音訊檔案
                    try:
                        wf = wave.open(path, 'rb')
                        audio_data = {
                            'format': wf.getsampwidth(),
                            'channels': wf.getnchannels(),
                            'rate': wf.getframerate(),
                            'frames': wf.readframes(wf.getnframes())
                        }
                        loaded_audio_data[path] = audio_data
                        wf.close()
                        log_message(f"已重新載入音訊檔案: {path}")
                    except Exception as e:
                        log_message(f"載入音訊檔案失敗: {e}")
        
        log_message("配置已更新")
        return True
    except Exception as e:
        log_message(f"更新配置失敗: {e}")
        return False

def log_message(message):
    """記錄訊息"""
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message)

def preload_audio_files():
    """預先加載所有音效檔案到記憶體中"""
    global loaded_audio_data
    
    log_message("預加載音效檔案...")
    
    # 加載音樂檔案
    for key, file_path in music_files.items():
        try:
            wf = wave.open(file_path, 'rb')
            audio_data = {
                'format': wf.getsampwidth(),
                'channels': wf.getnchannels(),
                'rate': wf.getframerate(),
                'frames': wf.readframes(wf.getnframes())  # 讀取整個檔案
            }
            loaded_audio_data[file_path] = audio_data
            wf.close()
            log_message(f"已加載: {file_path}")
        except Exception as e:
            log_message(f"加載 {file_path} 時發生錯誤: {e}")

def change_playback_speed(audio_data, speed):
    """改變音訊資料的播放速度"""
    if speed == 1.0:
        return audio_data  # 速度不變，直接返回原始資料
        
    # 將位元組資料轉換為 numpy 陣列
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    
    # 使用 resample 函數來改變速度
    # 速度增加，樣本數減少；速度減少，樣本數增加
    new_length = int(len(audio_array) / speed)
    new_audio = signal.resample(audio_array, new_length)
    
    # 將處理後的資料轉回位元組格式
    return new_audio.astype(np.int16).tobytes()

def play_audio_loop(file_path, initial_speed=1.0):
    """使用預加載的資料循環播放音訊，支援速度控制"""
    global stop_flag, current_playing_music
    
    if file_path not in loaded_audio_data:
        log_message(f"錯誤: 找不到預加載的音效檔案 {file_path}")
        return
    
    playback_speed = initial_speed
    audio_data = loaded_audio_data[file_path]
    p = pyaudio.PyAudio()
    
    # 取得原始資料
    original_frames = audio_data['frames']
    original_rate = audio_data['rate']
    
    stop_flag = False
    
    # 循環播放
    while not stop_flag:
        # 根據當前速度計算新的播放率
        adjusted_rate = int(original_rate * playback_speed)
        
        # 開啟新的音訊流，使用調整後的播放率
        stream = p.open(format=p.get_format_from_width(audio_data['format']),
                       channels=audio_data['channels'],
                       rate=adjusted_rate,
                       output=True)
                       
        log_message(f"播放速度已設定為: {playback_speed}, 調整後播放率: {adjusted_rate}")
        
        # 分段播放整個檔案
        chunk = 256
        for i in range(0, len(original_frames), chunk * audio_data['format'] * audio_data['channels']):
            if stop_flag:
                break
                
            chunk_data = original_frames[i:i + chunk * audio_data['format'] * audio_data['channels']]
            if len(chunk_data) > 0:
                # 這裡直接使用原始數據，因為已經通過調整採樣率來改變播放速度
                stream.write(chunk_data)
        
        # 關閉流，準備下一次迭代
        stream.stop_stream()
        stream.close()
    
    # 清理資源
    p.terminate()
    log_message("音訊播放停止")

def play_audio_once(file_path, speed=1.0):
    """使用預加載的資料播放音訊一次，支援即時速度控制"""
    global stop_flag
    
    if file_path not in loaded_audio_data:
        log_message(f"錯誤: 找不到預加載的音效檔案 {file_path}")
        return
    
    # 提前檢查停止標誌
    if stop_flag:
        log_message("播放被停止標誌阻止")
        return
    
    audio_data = loaded_audio_data[file_path]
    p = pyaudio.PyAudio()
    
    # 取得原始資料
    original_format = audio_data['format']
    original_channels = audio_data['channels']
    original_rate = audio_data['rate']
    frames = audio_data['frames']
    
    # 調整播放速率根據速度參數
    adjusted_rate = int(original_rate * speed)
    
    # 開啟音訊流，使用調整後的播放率
    stream = p.open(format=p.get_format_from_width(original_format),
                   channels=original_channels,
                   rate=adjusted_rate,  # 使用調整後的播放率
                   output=True)
    
    log_message(f"單次播放速度設定為: {speed}, 調整後播放率: {adjusted_rate}")
    
    # 使用適中的塊大小
    chunk = 128
    
    try:
        # 分段播放整個檔案
        for i in range(0, len(frames), chunk * original_format * original_channels):
            # 檢查停止標誌
            if stop_flag:
                log_message("播放被中途停止")
                break
                
            # 獲取當前塊的數據
            chunk_data = frames[i:i + chunk * original_format * original_channels]
            if len(chunk_data) == 0:
                break
            
            # 播放音頻塊
            stream.write(chunk_data)
    except Exception as e:
        log_message(f"播放音訊時出錯: {e}")
    finally:
        # 釋放資源
        try:
            stream.stop_stream()
            stream.close()
        except:
            pass
        try:
            p.terminate()
        except:
            pass
        log_message("單次音訊播放完成")

def stop_audio():
    """停止正在播放的音訊"""
    global stop_flag, audio_thread,current_playing_music
    
    if audio_thread and audio_thread.is_alive():
        stop_flag = True
        audio_thread.join(timeout=1.0)  # 等待線程結束，最多1秒
        log_message("已停止音訊播放")
    
    stop_flag = False
    audio_thread = None
    current_playing_music = None
    
    update_status()

def play_music(index, loop=True, speed=1.0): 
    """開始播放音樂"""
    global audio_thread, current_playing_music, stop_flag
    
    # 確保前一個音訊真的停止了
    if audio_thread and audio_thread.is_alive():
        stop_flag = True
        audio_thread.join(timeout=0.1)  # 等待最多 0.1 秒
        audio_thread = None
    
    # 重置停止標誌
    stop_flag = False
    
    # 獲取音樂檔案路徑
    if index not in music_files:
        log_message(f"找不到音樂 {index}")
        return False
    
    file_path = music_files[index]
    
    # 更新目前播放的音樂記錄
    current_playing_music = index
    
    if loop:
        # 啟動新的播放線程
        audio_thread = threading.Thread(
            target=play_audio_loop, 
            args=(file_path, speed)
        )
        audio_thread.daemon = True
        audio_thread.start()
        log_message(f"開始循環播放: {file_path}, 速度: {speed}")
    else:
        # 單次播放
        audio_thread = threading.Thread(
            target=play_audio_once, 
            args=(file_path, speed)
        )
        audio_thread.daemon = True
        audio_thread.start()
        log_message(f"開始單次播放: {file_path}, 速度: {speed}")
    update_status()
    return True

# 處理來自ESP32的資料
def process_data(data):
    command = data.decode('utf-8')
    log_message(f"歌單控制器: 收到命令 {command}")
    
    # 根據命令選擇並播放對應的音樂
    if command == "PLAY_MUSIC_1":
        log_message("開始播放音樂1")
        play_music("1", loop=True)
    elif command == "STOP_MUSIC_1":
        log_message("停止播放音樂1")
        stop_audio()
    
    elif command == "PLAY_MUSIC_2":
        log_message("開始播放音樂2")
        play_music("2", loop=True)
    elif command == "STOP_MUSIC_2":
        log_message("停止播放音樂2")
        stop_audio()
    
    elif command == "PLAY_MUSIC_3":
        log_message("開始播放音樂3")
        play_music("3", loop=True)
    elif command == "STOP_MUSIC_3":
        log_message("停止播放音樂3")
        stop_audio()

# 回調函數，處理來自裝置的通知
def notification_handler(_, data):
    process_data(data)

# 連接到ESP32
async def connect_to_device():
    global client, is_connected
    
    log_message(f"搜尋歌單控制器 {DEVICE_NAME}...")
    
    # 搜尋裝置
    device = await BleakScanner.find_device_by_name(DEVICE_NAME)
    
    if device is None:
        log_message(f"找不到裝置 {DEVICE_NAME}")
        return False
    
    # 連接裝置
    client = BleakClient(device)
    try:
        await client.connect()
        log_message(f"已連接到 {DEVICE_NAME}")
        
        # 更新連接狀態
        is_connected = True
        
        # 訂閱通知
        await client.start_notify(CHARACTERISTIC_UUID, notification_handler)
        
        return True
    except Exception as e:
        log_message(f"連接到 {DEVICE_NAME} 失敗: {e}")
        is_connected = False
        return False

# 初始化並啟動藍牙服務
async def start_bluetooth_service():
    # 加載音頻文件
    preload_audio_files()
    
    # 連接到歌單控制器
    success = await connect_to_device()
    if not success:
        log_message("無法連接到歌單控制器，將每5秒重試一次...")
    
    # 保持連接並處理資料
    reconnect_attempt = 0
    try:
        while True:
            if not is_connected:
                reconnect_attempt += 1
                log_message(f"嘗試重新連接 (第 {reconnect_attempt} 次)...")
                success = await connect_to_device()
                if success:
                    reconnect_attempt = 0
                else:
                    # 等待5秒後再嘗試
                    await asyncio.sleep(5)
            
            # 小延遲，讓其他任務有機會執行
            await asyncio.sleep(0.1)
    except Exception as e:
        log_message(f"藍牙服務發生錯誤: {e}")
        # 斷開連接
        if client and client.is_connected:
            try:
                await client.disconnect()
            except:
                pass
        is_connected = False

# 主函數
def main():
    log_message("啟動歌單控制器專用程式...")
    ensure_status_file_exists()

    # 在新線程中啟動藍牙服務
    def run_async_loop():
        asyncio.run(start_bluetooth_service())
    
    # 啟動後端線程
    backend_thread = threading.Thread(target=run_async_loop)
    backend_thread.daemon = True
    backend_thread.start()
    
    # 更新初始狀態
    update_status()
    
    # 顯示檔案路徑
    log_message(f"命令檔案路徑: {COMM_FILE}")
    log_message(f"狀態檔案路徑: {STATUS_FILE}")
    
    # 主循環，檢查命令並更新狀態
    heartbeat_counter = 0
    try:
        while True:
            check_commands()
            update_status()
            
            # 每隔10秒打印一次心跳信息，確認程式仍在運行
            heartbeat_counter += 1
            if heartbeat_counter >= 20:  # 20 * 0.5 = 10秒
                log_message("歌單控制器仍在運行中...")
                heartbeat_counter = 0
                
            time.sleep(0.5)
    except KeyboardInterrupt:
        log_message("程式結束")
    except Exception as e:
        log_message(f"主循環發生異常: {e}")
        import traceback
        log_message(traceback.format_exc())

if __name__ == "__main__":
    main()
    ensure_status_file_exists