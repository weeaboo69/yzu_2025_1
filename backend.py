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

current_audio_thread = None
stop_current_audio_flag = False
current_playing_music = None  # 目前正在播放的音樂編號
audio_stream = None  # 用於儲存音訊流的全局變數
loaded_audio_data = {}

music_files = {
    "1": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/1.wav",
    "2": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/2.wav",
    "3": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/3.wav"
}
rdp_audio_file = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP.wav"

# 設定ESP32裝置的UUID
ESP32_DEVICES = [
    #"ESP32_HornBLE",           # 喇叭控制器
    #"ESP32_Wheelspeed2_BLE",   # 輪子速度控制器
    "ESP32_RDP_BLE",           # 輪子觸發控制器
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
        log_message(f"已加載: {rdp_audio_file}")
    except Exception as e:
        log_message(f"加載 {rdp_audio_file} 時發生錯誤: {e}")

def play_audio_loop(file_path):
    """使用預加載的資料循環播放音訊"""
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
    frame_count = len(frames) // (audio_data['format'] * audio_data['channels'])
    
    stop_current_audio_flag = False
    
    # 循環播放
    while not stop_current_audio_flag:
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
    log_message("音訊播放停止")

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
    """停止目前正在播放的音訊"""
    global current_audio_thread, stop_current_audio_flag
    
    if current_audio_thread and current_audio_thread.is_alive():
        stop_current_audio_flag = True
        current_audio_thread.join(timeout=1.0)  # 等待線程結束，最多1秒
        log_message("已停止先前的音訊播放")
    
    stop_current_audio_flag = False

def play_music(file_path, loop=True):
    """開始播放指定的音樂檔案"""
    global current_audio_thread, current_playing_music
    
    # 記錄目前播放的音樂
    for key, path in music_files.items():
        if path == file_path:
            current_playing_music = key
            break
    else:
        if file_path == rdp_audio_file:
            current_playing_music = "RDP"
        else:
            current_playing_music = None
    
    # 先停止當前播放
    stop_current_audio()
    
    if loop:
        # 啟動新的播放線程
        current_audio_thread = threading.Thread(target=play_audio_loop, args=(file_path,))
        current_audio_thread.daemon = True  # 設為守護線程，主程式結束時會自動結束
        current_audio_thread.start()
        log_message(f"開始循環播放: {file_path}")
    else:
        # 單次播放邏輯
        current_audio_thread = threading.Thread(target=play_audio_once, args=(file_path,))
        current_audio_thread.daemon = True
        current_audio_thread.start()
        log_message(f"開始單次播放: {file_path}")

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
        speed_str = data.decode('utf-8')
        if speed_str == "STOP_PLAYBACK":
            log_message("輪子速度控制器: 停止播放")
        else:
            try:
                speed = float(speed_str)
                log_message(f"輪子速度控制器: 速度設定為 {speed}")
            except ValueError:
                log_message(f"輪子速度控制器: 無法解析資料 {speed_str}")
                
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