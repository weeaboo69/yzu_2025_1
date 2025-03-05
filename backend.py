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

current_playing_music = None  # 目前正在播放的音樂編號

device_audio_threads = {
    "ESP32_HornBLE": None,
    "ESP32_Wheelspeed2_BLE": None,
    "ESP32_RDP_BLE": None,
    "ESP32_MusicSensor_BLE": None
}

device_stop_flags = {
    "ESP32_HornBLE": False,
    "ESP32_Wheelspeed2_BLE": False,
    "ESP32_RDP_BLE": False,
    "ESP32_MusicSensor_BLE": False
}

device_playback_speeds = {
    "ESP32_HornBLE": 1.0,
    "ESP32_Wheelspeed2_BLE": 1.0,
    "ESP32_RDP_BLE": 1.0,
    "ESP32_MusicSensor_BLE": 1.0
}

hornPlayed = False
horn_mode_switched = False
audio_stream = None  # 用於儲存音訊流的全局變數
loaded_audio_data = {}

horn_audio_file_before = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/horn_before.wav"  # 切換前的喇叭音效
horn_audio_file_after = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/horn_after.wav"   # 切換後的喇叭音效
wheel_audio_file = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/wheel_sound.wav"  
music_files = {
    "1": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/1.wav",
    "2": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/2.wav",
    "3": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/3.wav"
}
rdp_audio_file = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP.wav"

# 設定ESP32裝置的UUID
ESP32_DEVICES = [
    "ESP32_HornBLE",           # 喇叭控制器
    #"ESP32_Wheelspeed2_BLE",   # 輪子速度控制器
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
    try:
        wf = wave.open(horn_audio_file_before, 'rb')
        audio_data = {
            'format': wf.getsampwidth(),
            'channels': wf.getnchannels(),
            'rate': wf.getframerate(),
            'frames': wf.readframes(wf.getnframes())
        }
        loaded_audio_data[horn_audio_file_before] = audio_data
        wf.close()
        print(f"已加載: {horn_audio_file_before}")
    except Exception as e:
        print(f"加載 {horn_audio_file_before} 時發生錯誤: {e}")

    # 加載切換後的喇叭音效
    try:
        wf = wave.open(horn_audio_file_after, 'rb')
        audio_data = {
            'format': wf.getsampwidth(),
            'channels': wf.getnchannels(),
            'rate': wf.getframerate(),
            'frames': wf.readframes(wf.getnframes())
        }
        loaded_audio_data[horn_audio_file_after] = audio_data
        wf.close()
        print(f"已加載: {horn_audio_file_after}")
    except Exception as e:
        print(f"加載 {horn_audio_file_after} 時發生錯誤: {e}")

def play_audio_loop(device_name, file_path, initial_speed=1.0):
    """使用預加載的資料循環播放音訊，支援速度控制"""
    global device_stop_flags, device_playback_speeds
    
    if file_path not in loaded_audio_data:
        print(f"錯誤: 找不到預加載的音效檔案 {file_path}")
        return
    
    device_playback_speeds[device_name] = initial_speed
    audio_data = loaded_audio_data[file_path]
    p = pyaudio.PyAudio()
    
    # 取得原始資料
    original_frames = audio_data['frames']
    original_rate = audio_data['rate']
    
    device_stop_flags[device_name] = False
    last_speed = device_playback_speeds[device_name]
    
    # 循環播放
    while not device_stop_flags[device_name]:
        # 根據當前速度計算新的播放率
        adjusted_rate = int(original_rate * device_playback_speeds[device_name])
        
        # 開啟新的音訊流，使用調整後的播放率
        stream = p.open(format=p.get_format_from_width(audio_data['format']),
                       channels=audio_data['channels'],
                       rate=adjusted_rate,
                       output=True)
                       
        print(f"{device_name} 播放速度已設定為: {device_playback_speeds[device_name]}, 調整後播放率: {adjusted_rate}")
        
        # 分段播放整個檔案
        chunk = 512
        for i in range(0, len(original_frames), chunk * audio_data['format'] * audio_data['channels']):
            if device_stop_flags[device_name] or last_speed != device_playback_speeds[device_name]:
                break
                
            chunk_data = original_frames[i:i + chunk * audio_data['format'] * audio_data['channels']]
            if len(chunk_data) > 0:
                stream.write(chunk_data)
        
        # 關閉流，準備下一次迭代
        stream.stop_stream()
        stream.close()
        
        # 更新上次速度
        last_speed = device_playback_speeds[device_name]
    
    # 清理資源
    p.terminate()
    print(f"{device_name} 音訊播放停止")

def play_audio_once(device_name, file_path, speed=1.0):
    """使用預加載的資料播放音訊一次，支援速度控制"""
    global device_stop_flags
    
    if file_path not in loaded_audio_data:
        print(f"錯誤: 找不到預加載的音效檔案 {file_path}")
        return
    
    audio_data = loaded_audio_data[file_path]
    p = pyaudio.PyAudio()
    
    # 開啟音訊流，使用調整後的播放率
    adjusted_rate = int(audio_data['rate'] * speed)
    stream = p.open(format=p.get_format_from_width(audio_data['format']),
                   channels=audio_data['channels'],
                   rate=adjusted_rate,  # 這裡使用調整後的採樣率
                   output=True)
    
    print(f"{device_name} 使用速度因子: {speed}, 原始採樣率: {audio_data['rate']}, 調整後採樣率: {adjusted_rate}")
    
    # 設定較小的資料塊大小以減少延遲
    chunk = 512
    
    # 將二進制資料轉換為可讀取的位置
    frames = audio_data['frames']
    
    device_stop_flags[device_name] = False
    
    # 分段播放整個檔案
    for i in range(0, len(frames), chunk * audio_data['format'] * audio_data['channels']):
        if device_stop_flags[device_name]:
            break
        chunk_data = frames[i:i + chunk * audio_data['format'] * audio_data['channels']]
        if len(chunk_data) > 0:
            stream.write(chunk_data)
    
    # 關閉資源
    stream.stop_stream()
    stream.close()
    p.terminate()
    print(f"{device_name} 單次音訊播放完成")

def stop_device_audio(device_name):
    """停止指定裝置正在播放的音訊"""
    global device_audio_threads, device_stop_flags
    
    if device_audio_threads[device_name] and device_audio_threads[device_name].is_alive():
        device_stop_flags[device_name] = True
        device_audio_threads[device_name].join(timeout=1.0)  # 等待線程結束，最多1秒
        print(f"已停止 {device_name} 的音訊播放")
    
    device_stop_flags[device_name] = False

def play_device_music(device_name, file_path, loop=True, speed=1.0):
    """開始為指定裝置播放音樂"""
    global device_audio_threads, device_playback_speeds
    
    # 先停止該裝置當前播放的音訊
    stop_device_audio(device_name)
    
    # 設定初始速度
    device_playback_speeds[device_name] = speed
    
    if loop:
        # 啟動新的播放線程
        device_audio_threads[device_name] = threading.Thread(
            target=play_audio_loop, 
            args=(device_name, file_path, speed)
        )
        device_audio_threads[device_name].daemon = True
        device_audio_threads[device_name].start()
        print(f"開始為 {device_name} 循環播放: {file_path}, 速度: {speed}")
    else:
        # 單次播放
        device_audio_threads[device_name] = threading.Thread(
            target=play_audio_once, 
            args=(device_name, file_path, speed)
        )
        device_audio_threads[device_name].daemon = True
        device_audio_threads[device_name].start()
        print(f"開始為 {device_name} 單次播放: {file_path}, 速度: {speed}")

# 處理來自ESP32的資料
def process_data(device_name, data):
    # 根據裝置名稱分別處理資料
    if device_name == "ESP32_HornBLE":
    # 處理喇叭控制器資料
        global horn_mode_switched, hornPlayed
        
        if data[0] == 254:  # 播放指令 (開始彎曲)
            print(f"喇叭控制器: 偵測到彎曲開始")
            # 重置播放標記
            hornPlayed = False
            # 根據當前模式選擇音效檔案
            horn_file = horn_audio_file_after if horn_mode_switched else horn_audio_file_before
            play_device_music(device_name, horn_file, loop=False)
            print(f"喇叭控制器: 開始播放音效 {horn_file}")
            # 標記已播放
            hornPlayed = True
        elif data[0] == 253:  # 停止指令 (停止彎曲)
            print(f"喇叭控制器: 偵測到彎曲結束")
            # 無論正在播放什麼音效 (before或after)，都停止播放
            stop_device_audio(device_name)
            # 重置 switch 狀態和播放標記
            horn_mode_switched = False
            hornPlayed = False
            print("喇叭控制器: 已重置模式狀態和播放標記")
        else:
            position = data[0]  # 播放位置 (0-100)
            print(f"喇叭控制器: 設定播放位置 {position}%")
            
            # 記錄之前的模式狀態
            prev_mode_switched = horn_mode_switched
            
            # 檢查是否已達到 100 以切換模式
            if position >= 100 and not horn_mode_switched:
                horn_mode_switched = True
                print("喇叭控制器: 達到 100%，切換到反向模式和新音效")
            
            # 選擇當前模式對應的音效檔案
            horn_file = horn_audio_file_after if horn_mode_switched else horn_audio_file_before
            
            # 模式發生變化時，停止當前播放並播放新音效
            if prev_mode_switched != horn_mode_switched:
                print("喇叭控制器: 模式切換，中斷當前音效並播放新音效")
                stop_device_audio(device_name)
                play_device_music(device_name, horn_file, loop=False)
                hornPlayed = True
                
            # 根據當前模式計算播放速度
            if not horn_mode_switched:
    # 第一次達到 100 前：位置值 0-100 對應速度 0.3-3.0，100 是最快
                speed = 0.3 + (position / 100.0) * 2.7
            else:
            # 第一次達到 100 後：位置值 0-100 對應速度 3.0-0.3，100 是最慢
                speed = 3.0 - (position / 100.0) * 2.7

        # 確保速度在合理範圍內
            speed = max(0.3, min(3.0, speed))
            
            print(f"喇叭控制器: 模式 {'反向' if horn_mode_switched else '正向'}, 調整播放速度為 {speed}")
            
            # 如果已經播放過音效並且音效仍在播放中，只更新速度
            if hornPlayed and device_audio_threads[device_name] and device_audio_threads[device_name].is_alive():
                device_playback_speeds[device_name] = speed
            # 如果已經播放過但音效已結束，不要重新播放
            elif hornPlayed:
                print("喇叭控制器: 音效已播放過，等待停止彎曲指令")
            # 如果尚未播放過（這種情況理論上不應該發生，因為應該先收到 254）
            else:
                print("喇叭控制器: 尚未收到開始彎曲指令，但收到位置值")

    elif device_name == "ESP32_Wheelspeed2_BLE":
        # 處理輪子速度控制器資料
        speed_str = data.decode('utf-8')
        if speed_str == "STOP_PLAYBACK":
            print("輪子速度控制器: 停止播放")
            stop_device_audio(device_name)
        else:
            try:
                speed = float(speed_str)
                print(f"輪子速度控制器: 接收到速度值 {speed}")
                
                # 如果當前沒有播放音訊，則開始播放
                if not device_audio_threads[device_name] or not device_audio_threads[device_name].is_alive():
                    print(f"開始以速度 {speed} 播放wheel音效")
                    play_device_music(device_name, wheel_audio_file, loop=True, speed=speed)
                else:
                    # 更新播放速度
                    print(f"更新播放速度為 {speed} (之前為 {device_playback_speeds[device_name]})")
                    device_playback_speeds[device_name] = speed
            except ValueError:
                print(f"輪子速度控制器: 無法解析資料 {speed_str}")

    elif device_name == "ESP32_RDP_BLE":
        # 處理輪子觸發控制器資料
        command = data.decode('utf-8')
        print(f"輪子觸發控制器: 收到命令 {command}")
        
        if command == "WHEEL_TRIGGER":
            print("RDP 按鈕已觸發，播放音效")
            # 單次播放 RDP 音效
            play_device_music(device_name, rdp_audio_file, loop=False)

    elif device_name == "ESP32_MusicSensor_BLE":
        # 處理歌單控制器資料
        command = data.decode('utf-8')
        print(f"歌單控制器: 收到命令 {command}")
        
        # 根據命令選擇並播放對應的音樂
        if command == "SELECT_MUSIC_1":
            print("切換到音樂1")
            play_device_music(device_name, music_files["1"], loop=True)
        
        elif command == "SELECT_MUSIC_2":
            print("切換到音樂2")
            play_device_music(device_name, music_files["2"], loop=True)
        
        elif command == "SELECT_MUSIC_3":
            print("切換到音樂3")
            play_device_music(device_name, music_files["3"], loop=True)

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