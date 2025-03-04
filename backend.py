import asyncio
import numpy as np
from bleak import BleakClient, BleakScanner
import pyaudio
import cv2
import time
import wave
import threading
import os
import pyaudio
import numpy as np
from scipy import signal

current_audio_thread = None
stop_current_audio_flag = False
current_playing_music = None  # 目前正在播放的音樂編號
current_playback_speed = 1.0
audio_stream = None  # 用於儲存音訊流的全局變數
loaded_audio_data = {}
wheel_audio_file = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/wheel_sound.wav"  # 請替換為實際的 wheel 音檔路徑

current_playback_speed = 1.0  # 預設播放速度
music_files = {
    "1": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/1.wav",
    "2": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/2.wav",
    "3": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/3.wav"
}
rdp_audio_file = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP.wav"

# 設定ESP32裝置的UUID
ESP32_DEVICES = [
    #"ESP32_HornBLE",           # 喇叭控制器
    "ESP32_Wheelspeed2_BLE",   # 輪子速度控制器
    #"ESP32_RDP_BLE",           # 輪子觸發控制器
    #"ESP32_MusicSensor_BLE"    # 歌單控制器
]

# 特性UUID (需要與ESP32端匹配)
SERVICE_UUID = "180F"
CHARACTERISTIC_UUID = "2A19"

# 儲存所有設備的資料
device_data = {uuid: {} for uuid in ESP32_DEVICES}
# 連接狀態字典 - 新增
device_connection_status = {uuid: False for uuid in ESP32_DEVICES}
# 訊息記錄列表 - 新增
message_log = []
# UI 更新回調函數 - 新增
ui_update_callback = None

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

def set_ui_update_callback(callback):
    """設置UI更新回調函數"""
    global ui_update_callback
    ui_update_callback = callback

def log_message(message):
    """記錄訊息並呼叫UI更新回調"""
    global message_log
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message)
    message_log.append(formatted_message)
    # 限制訊息記錄數量
    if len(message_log) > 100:
        message_log = message_log[-100:]
    # 呼叫UI更新回調
    if ui_update_callback:
        ui_update_callback(formatted_message)

def preload_audio_files():
    """預先加載所有音效檔案到記憶體中"""
    global loaded_audio_data
    
    print("預加載音效檔案...")
    
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
            print(f"已加載: {file_path}")
        except Exception as e:
            print(f"加載 {file_path} 時發生錯誤: {e}")
    
    # 加載 RDP 音效
    try:
        wf = wave.open(rdp_audio_file, 'rb')
        audio_data = {
            'format': wf.getsampwidth(),
            'channels': wf.getnchannels(),
            'rate': wf.getframerate(),
            'frames': wf.readframes(wf.getnframes())
        }
        loaded_audio_data[rdp_audio_file] = audio_data
        wf.close()
        print(f"已加載: {rdp_audio_file}")
    except Exception as e:
        print(f"加載 {rdp_audio_file} 時發生錯誤: {e}")
        
    # 加載 Wheel 音效
    try:
        wf = wave.open(wheel_audio_file, 'rb')
        audio_data = {
            'format': wf.getsampwidth(),
            'channels': wf.getnchannels(),
            'rate': wf.getframerate(),
            'frames': wf.readframes(wf.getnframes())
        }
        loaded_audio_data[wheel_audio_file] = audio_data
        wf.close()
        print(f"已加載: {wheel_audio_file}")
    except Exception as e:
        print(f"加載 {wheel_audio_file} 時發生錯誤: {e}")

def play_audio_loop(file_path, initial_speed=1.0):
    """使用預加載的資料循環播放音訊，支援速度控制"""
    global stop_current_audio_flag, current_playback_speed
    
    if file_path not in loaded_audio_data:
        print(f"錯誤: 找不到預加載的音效檔案 {file_path}")
        return
    
    current_playback_speed = initial_speed
    audio_data = loaded_audio_data[file_path]
    p = pyaudio.PyAudio()
    
    # 取得原始資料
    original_frames = audio_data['frames']
    original_rate = audio_data['rate']
    
    stop_current_audio_flag = False
    last_speed = current_playback_speed
    
    # 循環播放
    while not stop_current_audio_flag:
        # 根據當前速度計算新的播放率
        adjusted_rate = int(original_rate * current_playback_speed)
        
        # 開啟新的音訊流，使用調整後的播放率
        stream = p.open(format=p.get_format_from_width(audio_data['format']),
                       channels=audio_data['channels'],
                       rate=adjusted_rate,
                       output=True)
                       
        print(f"播放速度已設定為: {current_playback_speed}, 調整後播放率: {adjusted_rate}")
        
        # 分段播放整個檔案
        chunk = 512  # 較小的資料塊大小以減少延遲
        for i in range(0, len(original_frames), chunk * audio_data['format'] * audio_data['channels']):
            if stop_current_audio_flag or last_speed != current_playback_speed:
                break  # 如果需要停止或速度改變，跳出內循環
                
            chunk_data = original_frames[i:i + chunk * audio_data['format'] * audio_data['channels']]
            if len(chunk_data) > 0:
                stream.write(chunk_data)
        
        # 關閉流，準備下一次迭代
        stream.stop_stream()
        stream.close()
        
        # 更新上次速度
        last_speed = current_playback_speed
    
    # 清理資源
    p.terminate()
    print("音訊播放停止")

def play_audio_once(file_path):
    """使用預加載的資料播放音訊一次"""
    global stop_current_audio_flag
    
    if file_path not in loaded_audio_data:
        log_message(f"錯誤: 找不到預加載的音效檔案 {file_path}")
        return
    
    audio_data = loaded_audio_data[file_path]
    p = pyaudio.PyAudio()
    
    # 開啟音訊流
    stream = p.open(format=p.get_format_from_width(audio_data['format']),
                    channels=audio_data['channels'],
                    rate=audio_data['rate'],
                    output=True)
    
    # 設定較小的資料塊大小以減少延遲
    chunk = 512
    
    # 將二進制資料轉換為可讀取的位置
    frames = audio_data['frames']
    
    stop_current_audio_flag = False
    
    # 分段播放整個檔案
    for i in range(0, len(frames), chunk * audio_data['format'] * audio_data['channels']):
        if stop_current_audio_flag:
            break
        chunk_data = frames[i:i + chunk * audio_data['format'] * audio_data['channels']]
        if len(chunk_data) > 0:
            stream.write(chunk_data)
    
    # 關閉資源
    stream.stop_stream()
    stream.close()
    p.terminate()
    log_message("單次音訊播放完成")

def stop_current_audio():
    """停止目前正在播放的音訊並重置播放速度"""
    global current_audio_thread, stop_current_audio_flag, current_playback_speed
    
    if current_audio_thread and current_audio_thread.is_alive():
        stop_current_audio_flag = True
        current_audio_thread.join(timeout=1.0)  # 等待線程結束，最多1秒
        print("已停止先前的音訊播放")
    
    stop_current_audio_flag = False
    
    # 重置播放速度回預設值 1.0
    current_playback_speed = 1.0
    print("播放速度已重置為 1.0")

def play_music(file_path, loop=True, speed=1.0):
    """開始播放指定的音樂檔案"""
    global current_audio_thread, current_playback_speed
    
    # 先停止當前播放
    stop_current_audio()
    
    # 設定初始速度
    current_playback_speed = speed
    
    if loop:
        # 啟動新的播放線程
        current_audio_thread = threading.Thread(target=play_audio_loop, args=(file_path, speed))
        current_audio_thread.daemon = True
        current_audio_thread.start()
        print(f"開始循環播放: {file_path}, 速度: {speed}")
    else:
        # 單次播放
        current_audio_thread = threading.Thread(target=play_audio_once, args=(file_path,))
        current_audio_thread.daemon = True
        current_audio_thread.start()
        print(f"開始單次播放: {file_path}")

# 處理來自ESP32的資料
def process_data(device_name, data):
    # 根據裝置名稱分別處理資料
    if device_name == "ESP32_HornBLE":
        # 處理喇叭控制器資料
        if data[0] == 254:  # 播放指令
            log_message(f"喇叭控制器: 觸發播放")
        else:
            position = data[0]  # 播放位置 (0-100)
            log_message(f"喇叭控制器: 設定播放位置 {position}%")
            
    elif device_name == "ESP32_Wheelspeed2_BLE":
    # 處理輪子速度控制器資料
        global current_playback_speed  # 添加這行來使用全域變數
        
        speed_str = data.decode('utf-8')
        if speed_str == "STOP_PLAYBACK":
            print("輪子速度控制器: 停止播放")
            stop_current_audio()
        else:
            try:
                speed = float(speed_str)
                print(f"輪子速度控制器: 接收到速度值 {speed}")
                
                # 如果當前沒有播放音訊，則開始播放
                if not current_audio_thread or not current_audio_thread.is_alive():
                    print(f"開始以速度 {speed} 播放wheel音效")
                    play_music(wheel_audio_file, loop=True, speed=speed)
                else:
                    # 更新播放速度
                    print(f"更新播放速度為 {speed} (之前為 {current_playback_speed})")
                    current_playback_speed = speed
            except ValueError:
                print(f"輪子速度控制器: 無法解析資料 {speed_str}")
                
    elif device_name == "ESP32_RDP_BLE":
        # 處理輪子觸發控制器資料
        command = data.decode('utf-8')
        log_message(f"輪子觸發控制器: 收到命令 {command}")
        
        if command == "WHEEL_TRIGGER":
            log_message("RDP 按鈕已觸發，播放音效")
            # 停止當前播放的任何音訊
            stop_current_audio()
            # 單次播放 RDP 音效
            play_music(rdp_audio_file, loop=False)
        
    elif device_name == "ESP32_MusicSensor_BLE":
        # 處理歌單控制器資料
        command = data.decode('utf-8')
        log_message(f"歌單控制器: 收到命令 {command}")
        
        # 根據命令選擇並播放對應的音樂
        if command == "SELECT_MUSIC_1":
            log_message("切換到音樂1")
            play_music(music_files["1"], loop=True)
        
        elif command == "SELECT_MUSIC_2":
            log_message("切換到音樂2")
            play_music(music_files["2"], loop=True)
        
        elif command == "SELECT_MUSIC_3":
            log_message("切換到音樂3")
            play_music(music_files["3"], loop=True)

# 回調函數，處理來自裝置的通知
def notification_handler(uuid):
    def handler(_, data):
        process_data(uuid, data)
    return handler

# 連接到一個ESP32
async def connect_to_device(device_name):
    device = await BleakScanner.find_device_by_name(device_name)
    if device is None:
        log_message(f"找不到裝置 {device_name}")
        return None
    
    client = BleakClient(device)
    try:
        await client.connect()
        log_message(f"已連接到 {device_name}")
        # 更新連接狀態
        device_connection_status[device_name] = True
        
        # 訂閱通知
        await client.start_notify(CHARACTERISTIC_UUID, notification_handler(device_name))
        
        return client
    except Exception as e:
        log_message(f"連接到 {device_name} 失敗: {e}")
        device_connection_status[device_name] = False
        return None

# 手動連接到指定設備
async def connect_to_specific_device(device_name):
    if device_name not in ESP32_DEVICES:
        ESP32_DEVICES.append(device_name)
        device_connection_status[device_name] = False
        
    client = await connect_to_device(device_name)
    return client is not None

# 更新設備連接狀態
def update_connection_status(device_name, status):
    device_connection_status[device_name] = status

# 獲取設備連接狀態
def get_connection_status():
    return device_connection_status

# 獲取訊息記錄
def get_message_log():
    return message_log

# 設置音樂檔案路徑
def set_music_file_path(index, new_path):
    global music_files
    if index in music_files and os.path.exists(new_path):
        music_files[index] = new_path
        # 重新加載音頻文件
        try:
            wf = wave.open(new_path, 'rb')
            audio_data = {
                'format': wf.getsampwidth(),
                'channels': wf.getnchannels(),
                'rate': wf.getframerate(),
                'frames': wf.readframes(wf.getnframes())
            }
            loaded_audio_data[new_path] = audio_data
            wf.close()
            log_message(f"已更新並加載音樂 {index}: {new_path}")
            return True
        except Exception as e:
            log_message(f"加載 {new_path} 時發生錯誤: {e}")
            return False
    return False

# 設置RDP音效文件路徑
def set_rdp_audio_file_path(new_path):
    global rdp_audio_file
    if os.path.exists(new_path):
        rdp_audio_file = new_path
        # 重新加載音頻文件
        try:
            wf = wave.open(new_path, 'rb')
            audio_data = {
                'format': wf.getsampwidth(),
                'channels': wf.getnchannels(),
                'rate': wf.getframerate(),
                'frames': wf.readframes(wf.getnframes())
            }
            loaded_audio_data[new_path] = audio_data
            wf.close()
            log_message(f"已更新並加載RDP音效: {new_path}")
            return True
        except Exception as e:
            log_message(f"加載 {new_path} 時發生錯誤: {e}")
            return False
    return False

# 初始化並啟動藍牙服務
async def start_bluetooth_service():
    preload_audio_files()
    # 連接到所有ESP32設備
    clients = []
    for device_name in ESP32_DEVICES:
        client = await connect_to_device(device_name)
        if client:
            clients.append(client)
    
    # 保持連接並處理資料
    try:
        while True:
            await asyncio.sleep(0.1)  # 小延遲，讓其他任務有機會執行
    except Exception as e:
        log_message(f"藍牙服務發生錯誤: {e}")
        # 斷開所有連接
        for client in clients:
            try:
                await client.disconnect()
            except:
                pass

# 啟動後端服務的函數 (用於從UI調用)
def start_backend():
    # 在新線程中啟動藍牙服務
    def run_async_loop():
        asyncio.run(start_bluetooth_service())
    
    # 啟動後端線程
    backend_thread = threading.Thread(target=run_async_loop)
    backend_thread.daemon = True
    backend_thread.start()
    return backend_thread

# 測試播放特定音樂
def test_play_music(index, loop=True):
    if index in music_files:
        play_music(music_files[index], loop)
        return True
    elif index == "RDP":
        play_music(rdp_audio_file, loop=False)
        return True
    return False

# 獲取當前播放的音樂
def get_current_playing_music():
    return current_playing_music

if __name__ == "__main__":
    # 執行主函數
    asyncio.run(start_bluetooth_service())