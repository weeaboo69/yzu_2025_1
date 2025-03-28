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
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import qrcode
import os
import pickle
import json
import tempfile


# 在檔案開頭的全域變數部分添加
audio_buffer = []  # 原有的行
audio_last_update_time = 0  # 新增：最後一次添加音訊數據的時間
audio_format = 2  # 預設值：16位元整數
audio_channels = 2  # 預設值：立體聲
audio_rate = 44100  # 預設值：44.1kHz採樣率
songlist_process = None
# 在全局變數部分添加
device_clients = {}

current_playing_music = None  # 目前正在播放的音樂編號
STORAGE_DIR = r"C:\Users\maboo\yzu_2025\yzu_2025_1\recording"
if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

# 定義藍牙適配器列表
BT_ADAPTERS = [
    "hci0",  # 系統內建藍牙適配器
    "hci1",  # 外接 USB 藍牙適配器 1
    # 如果有更多...
]

# 裝置與適配器的映射關係
DEVICE_ADAPTER_MAP = {
    "ESP32_MusicSensor_BLE": "hci0",  # 音樂控制器走主適配器
    "ESP32_HornBLE": "hci0",          # 喇叭控制器也走主適配器
    "ESP32_RDP_BLE": "hci0",          # RDP控制器走外接適配器
    "ESP32_Wheelspeed2_BLE": "hci0",  # 輪子速度控制器走外接適配器
    "ESP32_test_remote":"hci0"
}

device_audio_threads = {
    "ESP32_HornBLE": None,
    "ESP32_Wheelspeed2_BLE": None,
    "ESP32_RDP_BLE": None,
    "ESP32_MusicSensor_BLE": None,
    "ESP32_test_remote":None
}

device_stop_flags = {
    "ESP32_HornBLE": False,
    "ESP32_Wheelspeed2_BLE": False,
    "ESP32_RDP_BLE": False,
    "ESP32_MusicSensor_BLE": False,
    "ESP32_test_remote":False
}

device_playback_speeds = {
    "ESP32_HornBLE": 1.0,
    "ESP32_Wheelspeed2_BLE": 1.0,
    "ESP32_RDP_BLE": 1.0,
    "ESP32_MusicSensor_BLE": 1.0,
    "ESP32_test_remote":1.0
}

hornPlayed = False
horn_mode_switched = False
audio_stream = None  # 用於儲存音訊流的全局變數
loaded_audio_data = {}

horn_audio_file_before = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/horn_before.wav"  # 切換前的喇叭音效
horn_audio_file_after = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/horn_after.wav"   # 切換後的喇叭音效
wheel_audio_file = {
    "1": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/wheel_sound_before.wav",
    "2": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/wheel_sound_after.wav",
    "OG": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/wheel_sound.wav"
}   
music_files = {
    "1": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/1.wav",
    "2": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/2.wav",
    "3": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/3.wav"
}
rdp_audio_files = {
    "1": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_J.wav",  # 音樂1對應的RDP音效
    "2": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_E.wav",  # 音樂2對應的RDP音效
    "3": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP.wav",  # 音樂3對應的RDP音效
    "default": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP.wav",    # 默認的RDP音效
    "RDP_2_before": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_2_before.wav",  # 按鈕2按下時播放
    "RDP_2_after": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_2_after.wav",   # 按鈕2放開時播放
    "RDP_3_before": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_3_before.wav", # 按鈕3按下時循環播放
    "RDP_3_after": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_3_after.wav"   # 按鈕3放開時播放
}

# 設定ESP32裝置的UUID
ESP32_DEVICES = [
    #"ESP32_HornBLE",           # 喇叭控制器
    "ESP32_Wheelspeed2_BLE",   # 輪子速度控制器
    #"ESP32_RDP_BLE",           # 輪子觸發控制器
    #"ESP32_MusicSensor_BLE",    # 歌單控制器
    "ESP32_test_remote"
]

is_recording = False
recording_thread = None
audio_recording = None

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

SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDENTIALS_PATH = os.path.join(STORAGE_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(STORAGE_DIR, 'token.pickle')

def start_songlist_controller():
    """啟動歌單控制器程式"""
    import subprocess
    import sys
    import os
    
    try:
        # 取得當前目錄
        current_dir = os.path.dirname(os.path.abspath(__file__))
        songlist_path = os.path.join(current_dir, "songlist_controller.py")
        
        # 使用相同的 Python 解釋器啟動程式
        python_exe = sys.executable
        
        # 以子程序方式啟動，不等待其完成
        process = subprocess.Popen([python_exe, songlist_path], 
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  creationflags=subprocess.CREATE_NO_WINDOW)  # 在 Windows 下隱藏命令視窗
        
        log_message("已啟動歌單控制器程式")
        return process
    except Exception as e:
        log_message(f"啟動歌單控制器程式失敗: {e}")
        return None

# 新增到 backend.py 中
async def _disconnect_device(client):
    """安全斷開裝置連接的協程"""
    try:
        if client and client.is_connected:
            # 先停止所有通知
            for uuid in client.services.characteristics:
                try:
                    await client.stop_notify(uuid)
                except:
                    pass
            # 然後斷開連接
            await client.disconnect()
    except Exception as e:
        log_message(f"斷開連接時發生錯誤: {e}")

def disconnect_all_devices():
    """安全斷開所有裝置的連接"""
    log_message("正在斷開所有藍牙連接...")
    
    # 建立一個新的事件循環來執行異步斷開連接操作
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 收集所有已連接的客戶端
    clients = []
    for device_name in ESP32_DEVICES:
        if device_connection_status.get(device_name, False):
            # 假設我們有一個全局字典存儲所有客戶端
            client = device_clients.get(device_name)
            if client:
                clients.append(client)
    
    # 為每個客戶端創建斷開連接的任務
    tasks = [_disconnect_device(client) for client in clients]
    
    if tasks:
        # 運行所有斷開連接的任務
        loop.run_until_complete(asyncio.gather(*tasks))
    
    # 關閉事件循環
    loop.close()
    
    log_message("所有藍牙連接已斷開")

def get_credentials():
    """取得 Google Drive API 的授權憑證"""
    creds = None
    
    # 嘗試從保存的令牌文件載入憑證
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # 如果沒有可用的憑證或已過期，則進行新的授權流程
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # 使用 credentials.json 啟動授權流程
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            
            # 在本地伺服器上運行授權流程
            # 這會打開瀏覽器讓你授權應用程式
            creds = flow.run_local_server(port=0)
        
        # 保存令牌以供下次使用
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def authenticate_google_drive():
    """認證 Google Drive API"""
    creds = None
    # 嘗試從保存的令牌文件加載憑證
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    # 如果沒有可用的憑證或已過期，則重新授權
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        # 保存令牌以供下次使用
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def upload_to_google_drive(file_path):
    """上傳文件到 Google Drive 並設置為公開可訪問"""
    try:
        # 正規化路徑
        file_path = os.path.normpath(file_path)
        
        # 確認檔案存在
        if not os.path.exists(file_path):
            log_message(f"上傳錯誤: 找不到檔案 {file_path}")
            
            # 嘗試在替代位置尋找檔案
            filename = os.path.basename(file_path)
            alternative_locations = [
                r"C:\Users\maboo\yzu_2025\yzu_2025_1",
                os.getcwd(),
                STORAGE_DIR
            ]
            
            for location in alternative_locations:
                alternative_path = os.path.join(location, filename)
                if os.path.exists(alternative_path):
                    log_message(f"在替代位置找到檔案: {alternative_path}")
                    file_path = alternative_path
                    break
            else:
                log_message("在所有可能的位置皆找不到檔案，無法上傳")
                return None
            
        log_message(f"開始上傳檔案: {file_path}")
        
        # 認證並構建服務
        creds = authenticate_google_drive()
        service = build('drive', 'v3', credentials=creds)
        
        # 檔案元數據
        file_metadata = {
            'name': os.path.basename(file_path)
        }
        
        # 上傳媒體文件
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(body=file_metadata,
                                     media_body=media,
                                     fields='id').execute()
        
        # 設置檔案為任何人都能查看
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        service.permissions().create(
            fileId=file.get('id'),
            body=permission
        ).execute()
        
        # 獲取檔案的共享連結
        file = service.files().get(
            fileId=file.get('id'),
            fields='webViewLink'
        ).execute()
        
        download_link = file.get('webViewLink')
        log_message(f"已成功上傳檔案到 Google Drive，下載連結: {download_link}")
        
        return download_link
        
    except Exception as e:
        log_message(f"上傳到 Google Drive 時發生錯誤: {e}")
        
        # 提供更詳細的錯誤信息
        import traceback
        log_message(f"詳細錯誤信息: {traceback.format_exc()}")
        
        return None

def generate_qr_code(url, filename="download_link"):
    """生成 QR Code 並保存為圖片"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        qr_path = os.path.join(STORAGE_DIR, f"{filename}.png")
        img.save(qr_path)
        log_message(f"QR Code 已生成: {qr_path}")
        
        return qr_path
    
    except Exception as e:
        log_message(f"生成 QR Code 時發生錯誤: {e}")
        return None

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
    for key, file_path in rdp_audio_files.items():
        try:
            wf = wave.open(file_path, 'rb')
            audio_data = {
                'format': wf.getsampwidth(),
                'channels': wf.getnchannels(),
                'rate': wf.getframerate(),
                'frames': wf.readframes(wf.getnframes())
            }
            loaded_audio_data[file_path] = audio_data
            wf.close()
            print(f"已加載 RDP 音效: {file_path}")
        except Exception as e:
            print(f"加載 {file_path} 時發生錯誤: {e}")
        
    # 加載 Wheel 音效
    for key, file_path in wheel_audio_file.items():
        try:
            wf = wave.open(file_path, 'rb')
            audio_data = {
                'format': wf.getsampwidth(),
                'channels': wf.getnchannels(),
                'rate': wf.getframerate(),
                'frames': wf.readframes(wf.getnframes())
            }
            loaded_audio_data[file_path] = audio_data
            wf.close()
            print(f"已加載饅頭音效: {file_path}")
        except Exception as e:
            print(f"加載 {file_path} 時發生錯誤: {e}")
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
    global audio_buffer
    
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
        chunk = 256
        for i in range(0, len(original_frames), chunk * audio_data['format'] * audio_data['channels']):
            if device_stop_flags[device_name] or last_speed != device_playback_speeds[device_name]:
                break
                
            chunk_data = original_frames[i:i + chunk * audio_data['format'] * audio_data['channels']]
            if len(chunk_data) > 0:
                # 這裡直接使用原始數據，因為已經通過調整採樣率來改變播放速度
                stream.write(chunk_data)
                
                # 在錄音模式下收集音訊數據
                # 修改 play_audio_loop 函數中的這部分代碼
                if is_recording:
                    # 將正在播放的音訊數據直接添加到錄音緩衝區
                    audio_buffer.append(chunk_data)
                    audio_last_update_time = time.time()  # 新增這行
        
        # 關閉流，準備下一次迭代
        stream.stop_stream()
        stream.close()
        
        # 更新上次速度
        last_speed = device_playback_speeds[device_name]
    
    # 清理資源
    p.terminate()
    print(f"{device_name} 音訊播放停止")

def play_wheel_music_without_stopping(file_path, loop=False, speed=1.0):
    """不中斷先前音訊，為輪子裝置播放新的音效"""
    device_name = "ESP32_Wheelspeed2_BLE"
    global device_playback_speeds
    
    # 設定初始速度
    device_playback_speeds[device_name] = speed
    
    # 啟動新的播放線程（為避免混淆，使用一個獨特的線程名）
    wheel_thread = threading.Thread(
        target=play_audio_once, 
        args=(device_name, file_path, speed)
    )
    wheel_thread.daemon = True
    wheel_thread.start()
    print(f"不中斷先前播放，為 {device_name} 播放: {file_path}, 速度: {speed}")

def play_audio_once(device_name, file_path, speed=1.0):
    """使用預加載的資料播放音訊一次，支援即時速度控制"""
    global device_stop_flags
    global audio_buffer
    
    if file_path not in loaded_audio_data:
        print(f"錯誤: 找不到預加載的音效檔案 {file_path}")
        return
    
    # 提前檢查停止標誌
    if device_stop_flags[device_name]:
        print(f"{device_name} 播放被停止標誌阻止")
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
    
    print(f"{device_name} 單次播放速度設定為: {speed}, 調整後播放率: {adjusted_rate}")
    
    # 使用適中的塊大小
    chunk = 128
    
    try:
        # 分段播放整個檔案
        for i in range(0, len(frames), chunk * original_format * original_channels):
            # 檢查停止標誌
            if device_stop_flags[device_name]:
                print(f"{device_name} 播放被中途停止")
                break
                
            # 獲取當前塊的數據
            chunk_data = frames[i:i + chunk * original_format * original_channels]
            if len(chunk_data) == 0:
                break
            
            # 播放音頻塊
            stream.write(chunk_data)
            
            # 在錄音模式下收集音訊數據
            if is_recording:
                # 將正在播放的音訊數據直接添加到錄音緩衝區
                audio_buffer.append(chunk_data)
                audio_last_update_time = time.time()  # 新增這行
    except Exception as e:
        print(f"播放音訊時出錯: {e}")
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
        print(f"{device_name} 單次音訊播放完成")

def stop_device_audio(device_name):
    """停止指定裝置正在播放的音訊"""
    global device_audio_threads, device_stop_flags
    
    if device_audio_threads[device_name] and device_audio_threads[device_name].is_alive():
        device_stop_flags[device_name] = True
        device_audio_threads[device_name].join(timeout=1.0)  # 等待線程結束，最多1秒
        print(f"已停止 {device_name} 的音訊播放")
    
    device_stop_flags[device_name] = False
    
    # 確保該裝置的音訊線程已經結束
    device_audio_threads[device_name] = None

def play_device_music(device_name, file_path, loop=True, speed=1.0): 
    """開始為指定裝置播放音樂"""
    global device_audio_threads, device_playback_speeds, current_playing_music
    
    # 確保前一個音訊真的停止了
    if device_audio_threads[device_name] and device_audio_threads[device_name].is_alive():
        device_stop_flags[device_name] = True
        device_audio_threads[device_name].join(timeout=0.1)  # 等待最多 0.1 秒
        device_audio_threads[device_name] = None
    
    # 重置停止標誌
    device_stop_flags[device_name] = False
    
    # 更新目前播放的音樂檔案信息
    if device_name == "ESP32_MusicSensor_BLE":
        # 通過文件路徑找出對應的音樂索引
        for idx, path in music_files.items():
            if path == file_path:
                current_playing_music = idx
                break
    elif device_name == "ESP32_RDP_BLE" and file_path == rdp_audio_files:
        current_playing_music = "RDP"
    
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
    global stop_recording, start_recording
    # 根據裝置名稱分別處理資料
    if device_name == "ESP32_HornBLE":
    # 處理喇叭控制器資料
        global horn_mode_switched, hornPlayed
        
        if data[0] == 254:  # 播放指令 (開始彎曲)
            print(f"喇叭控制器: 偵測到彎曲開始, hornPlayed={hornPlayed}")

            # 確保沒有其他音效正在播放
            if not hornPlayed:
                # 先徹底停止任何可能正在播放的音效
                stop_device_audio(device_name)
                
                # 強制終止其他可能存在的播放線程
                if device_audio_threads[device_name] and device_audio_threads[device_name].is_alive():
                    device_stop_flags[device_name] = True
                    print("喇叭控制器: 等待先前的音效停止...")
                    device_audio_threads[device_name].join(timeout=0.3)  # 等待線程結束
                    device_audio_threads[device_name] = None  # 明確釋放線程引用
                
                # 確保標誌正確設置後再播放
                device_stop_flags[device_name] = False
                
                print(f"喇叭控制器: 開始播放音效 {horn_audio_file_before}")
                play_device_music(device_name, horn_audio_file_before, loop=False)
                
                # 標記已播放
                hornPlayed = True
                # 初始化最後的位置值
                process_data.last_position = 0
                # 重置模式切換狀態
                horn_mode_switched = False
                    
        elif data[0] == 253:  # 停止指令 (停止彎曲)
            print(f"喇叭控制器: 偵測到彎曲結束")
            
            # 設置停止標誌
            device_stop_flags[device_name] = True
            
            # 最多嘗試5次停止
            for attempt in range(5):
                # 設置停止標誌
                device_stop_flags[device_name] = True
                
                # 等待一小段時間
                time.sleep(0.1)
                
                # 檢查線程是否還在運行
                if device_audio_threads[device_name] and device_audio_threads[device_name].is_alive():
                    print(f"喇叭控制器: 停止嘗試 {attempt+1}/5")
                else:
                    print("喇叭控制器: 音效已成功停止")
                    break
            
            # 無論如何，都清空音訊線程引用
            device_audio_threads[device_name] = None
            
            # 重置所有狀態標誌
            horn_mode_switched = False
            hornPlayed = False
            device_stop_flags[device_name] = False
            
            print("喇叭控制器: 已徹底重置所有音效和狀態")
            play_device_music(device_name, horn_audio_file_after, loop=False)
            
        else:
            position = data[0]  # 播放位置 (0-100)
            print(f"喇叭控制器: 設定播放位置 {position}%")
            
            # 檢查是否是第一次偵測到值增加
            static_last_position = getattr(process_data, 'last_position', 0)
            
            # 如果現在位置比上一次增加了20以上，且還沒有切換過模式，且已經在播放音效
            if position < static_last_position - 8 and not horn_mode_switched and hornPlayed:
                # 確保目前的音效真的在播放
                if device_audio_threads[device_name] and device_audio_threads[device_name].is_alive():
                    # 切換到 after 音效
                    horn_mode_switched = True
                    print("喇叭控制器: 偵測到彎曲程度增加超過20，切換到新音效")
                    # 停止當前播放並播放新音效
                    stop_device_audio(device_name)
                    
                    # 確保先前的音效真的停止了
                    time.sleep(0.1)
                    if device_audio_threads[device_name] and device_audio_threads[device_name].is_alive():
                        device_stop_flags[device_name] = True
                        device_audio_threads[device_name].join(timeout=0.3)
                        device_audio_threads[device_name] = None
                    
                    print(f"喇叭控制器: 播放新音效 {horn_audio_file_after}")
                    play_device_music(device_name, horn_audio_file_after, loop=False)
                    hornPlayed = True
            
            # 更新上次的位置值
            process_data.last_position = position
    elif device_name == "ESP32_Wheelspeed2_BLE":
        # 處理輪子速度控制器資料
        speed_str = data.decode('utf-8')
        if speed_str == "STOP_PLAYBACK":
            print("輪子速度控制器: 停止播放")
            #stop_device_audio(device_name)
        else:
            try:
                if speed_str == "gjp4":
                    print("開始順時針")
                    #stop_device_audio(device_name)
                    play_wheel_music_without_stopping(wheel_audio_file["1"], loop=False)
                elif speed_str == "su4":
                    print("開始逆時針")
                    #stop_device_audio(device_name)
                    play_wheel_music_without_stopping(wheel_audio_file["2"], loop=False)
            except ValueError:
                print(f"輪子速度控制器: 無法解析資料 {speed_str}")

    elif device_name == "ESP32_RDP_BLE":
    # 處理輪子觸發控制器資料
        command_str = data.decode('utf-8')
        print(f"輪子觸發控制器: 收到命令 {command_str}")
        
        # 檢查是否為按鈕時長命令（原有功能）
        if command_str.startswith("BUTTON_DURATION:"):
            # 原有程式碼不變
            try:
                duration_ms = int(command_str.split(':')[1])
                duration_sec = duration_ms / 1000.0
                print(f"按鈕按下時長: {duration_sec:.2f} 秒")
                
                # 根據時長計算播放速度
                speed = 1.0
                if duration_sec > 1.0 and duration_sec <= 2.0:
                    speed = 0.75
                elif duration_sec > 2.0:
                    speed = 0.5
                
                # 根據當前播放的音樂選擇對應的RDP音效
                rdp_file_to_play = rdp_audio_files.get("default")
                if current_playing_music in ["1", "2", "3"]:
                    rdp_file_to_play = rdp_audio_files.get(current_playing_music, rdp_audio_files["default"])
                    
                print(f"RDP 按鈕已觸發，播放對應音效: {rdp_file_to_play}，速度: {speed}")
                # 單次播放 RDP 音效，使用計算出的速度
                play_device_music(device_name, rdp_file_to_play, loop=False, speed=speed)
            except (ValueError, IndexError) as e:
                print(f"解析按鈕時長出錯: {e}")
        
        # 按鈕2處理邏輯
        elif command_str == "BUTTON2_PRESSED":
            print("按鈕2已按下，播放 RDP_2_before 音效")
            # 確保有此音效文件
            if "RDP_2_before" in rdp_audio_files:
                play_device_music(device_name, rdp_audio_files["RDP_2_before"], loop=False)
            else:
                print("找不到 RDP_2_before 音效檔案")
        
        elif command_str == "BUTTON2_RELEASED":
            print("按鈕2已放開，播放 RDP_2_after 音效")
            # 先停止任何正在播放的音效
            stop_device_audio(device_name)
            # 播放結束音效
            if "RDP_2_after" in rdp_audio_files:
                play_device_music(device_name, rdp_audio_files["RDP_2_after"], loop=False)
            else:
                print("找不到 RDP_2_after 音效檔案")
        
        # 按鈕3處理邏輯
        elif command_str == "BUTTON3_PRESSED":
            print("按鈕3已按下，循環播放 RDP_3_before 音效")
            if "RDP_3_before" in rdp_audio_files:
                play_device_music(device_name, rdp_audio_files["RDP_3_before"], loop=True)
            else:
                print("找不到 RDP_3_before 音效檔案")
        
        elif command_str == "BUTTON3_RELEASED":
            print("按鈕3已放開，停止循環並播放 RDP_3_after 音效")
            # 先停止循環播放
            stop_device_audio(device_name)
            # 播放結束音效
            if "RDP_3_after" in rdp_audio_files:
                play_device_music(device_name, rdp_audio_files["RDP_3_after"], loop=False)
            else:
                print("找不到 RDP_3_after 音效檔案")

    elif device_name == "ESP32_MusicSensor_BLE":
    # 處理歌單控制器資料
        command = data.decode('utf-8')
        print(f"歌單控制器: 收到命令 {command}")
        
        if command == "RECORD_START":
            print("開始錄音")
            start_recording()
        elif command == "RECORD_STOP":
            print("停止錄音")
            stop_recording()

        # 根據命令選擇並播放對應的音樂
        if command == "PLAY_MUSIC_1":
            print("開始播放音樂1")
            play_device_music(device_name, music_files["1"], loop=True)
        elif command == "STOP_MUSIC_1":
            print("停止播放音樂1")
            stop_device_audio(device_name)
        
        elif command == "PLAY_MUSIC_2":
            print("開始播放音樂2")
            play_device_music(device_name, music_files["2"], loop=True)
        elif command == "STOP_MUSIC_2":
            print("停止播放音樂2")
            stop_device_audio(device_name)
        
        elif command == "PLAY_MUSIC_3":
            print("開始播放音樂3")
            play_device_music(device_name, music_files["3"], loop=True)
        elif command == "STOP_MUSIC_3":
            print("停止播放音樂3")
            stop_device_audio(device_name)
    elif device_name == "ESP32_test_remote":
        # 處理測試遙控器資料
        command = data.decode('utf-8')
        print(f"測試遙控器: 收到命令 {command}")
        test_audio_file2 = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/3.wav"
        test_audio_file = "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_2_before.wav"
        
        if command == "BUTTON_13_PRESSED":
            # 記錄按鈕13的狀態，用於切換錄音
            if hasattr(process_data, 'button_13_state') and process_data.button_13_state:
                # 如果已經在錄音，則停止錄音
                print("按鈕13第二次按下，停止錄音")
                stop_recording()
                process_data.button_13_state = False
            else:
                # 開始錄音
                print("按鈕13第一次按下，開始錄音")
                start_recording()
                process_data.button_13_state = True
        
        elif command == "BUTTON_12_PRESSED":
            print("按鈕2已按下，播放 RDP_2_before 音效")
            # 確保有此音效文件
            if "RDP_2_before" in rdp_audio_files:
                play_device_music(device_name, rdp_audio_files["RDP_2_before"], loop=False)
            else:
                print("找不到 RDP_2_before 音效檔案")
        elif command == "BUTTON_14_PRESSED":
                    print("開始播放音樂1")
                    play_device_music(device_name, test_audio_file2, loop=True)
        elif command == "BUTTON_14_UNPRESSED":
            print("停止播放音樂1")
            stop_device_audio(device_name)

# 回調函數，處理來自裝置的通知
def notification_handler(uuid):
    def handler(_, data):
        process_data(uuid, data)
    return handler

# 連接到一個ESP32
async def connect_to_device(device_name):
    # 獲取該裝置應該使用的適配器
    adapter = DEVICE_ADAPTER_MAP.get(device_name, "hci0")
    
    # 使用指定的適配器查找裝置
    log_message(f"使用藍牙適配器 {adapter} 搜尋 {device_name}")
    
    # 在指定適配器上搜尋裝置
    device = await BleakScanner.find_device_by_name(
        device_name, 
        adapter=adapter
    )
    
    if device is None:
        log_message(f"在適配器 {adapter} 上找不到裝置 {device_name}")
        return None
    
    # 連接裝置並返回客戶端
    client = BleakClient(device, adapter=adapter)
    try:
        await client.connect()
        log_message(f"已透過適配器 {adapter} 連接到 {device_name}")
        
        # 更新連接狀態
        device_connection_status[device_name] = True
        
        # 訂閱通知
        await client.start_notify(CHARACTERISTIC_UUID, notification_handler(device_name))
        
        return client
    except Exception as e:
        log_message(f"通過適配器 {adapter} 連接到 {device_name} 失敗: {e}")
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
def set_rdp_audio_files_path(key, new_path):
    """設置特定 RDP 音效文件路徑"""
    global rdp_audio_files
    if os.path.exists(new_path):
        rdp_audio_files[key] = new_path
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
            log_message(f"已更新並加載 RDP 音效 {key}: {new_path}")
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
    global songlist_process
    
    # 先啟動歌單控制器
    songlist_process = start_songlist_controller()
    
    # 在新線程中啟動藍牙服務
    def run_async_loop():
        asyncio.run(start_bluetooth_service())
    
    # 啟動後端線程
    backend_thread = threading.Thread(target=run_async_loop)
    backend_thread.daemon = True
    backend_thread.start()
    return backend_thread

COMM_FILE = os.path.join(tempfile.gettempdir(), "songlist_controller_comm.json")

def send_command_to_songlist(command, params=None):
    """向歌單控制器發送命令"""
    try:
        # 命令格式
        cmd_data = {
            "command": command,
            "params": params or {},
            "timestamp": time.time()
        }
        
        # 寫入臨時文件
        with open(COMM_FILE, 'w') as f:
            json.dump(cmd_data, f)
        
        log_message(f"已發送命令到歌單控制器: {command}")
        return True
    except Exception as e:
        log_message(f"發送命令到歌單控制器失敗: {e}")
        return False

def stop_songlist_controller():
    global songlist_process
    
    if songlist_process:
        try:
            # 嘗試正常關閉程序
            import signal
            songlist_process.send_signal(signal.SIGTERM)
            songlist_process.wait(timeout=1)
        except:
            # 如果無法正常關閉，則強制終止
            try:
                songlist_process.kill()
            except:
                pass
        songlist_process = None
        log_message("已停止歌單控制器程式")

# 測試播放特定音樂
def test_play_music(music_idx, loop=True):
    # 對於音樂1-3，使用歌單控制器
    if music_idx in ["1", "2", "3"]:
        return send_command_to_songlist("PLAY_MUSIC", {
            "index": music_idx,
            "loop": loop
        })
    elif music_idx == "RDP":
        # RDP 音效由主程式控制
        play_device_music("ESP32_RDP_BLE", rdp_audio_files["default"], loop=False)
        return True
    return False

# 獲取當前播放的音樂
def get_current_playing_music():
    return current_playing_music

def stop_current_audio():
    """停止當前播放的所有音訊"""
    global current_playing_music
    
    # 停止主程式控制的所有設備音訊
    for device_name in device_audio_threads.keys():
        stop_device_audio(device_name)
    
    # 停止歌單控制器的音訊
    send_command_to_songlist("STOP_MUSIC")
    
    current_playing_music = None
    return True

def get_songlist_controller_status():
    """獲取歌單控制器的狀態"""
    try:
        if os.path.exists(COMM_FILE + ".status"):
            with open(COMM_FILE + ".status", 'r') as f:
                status = json.load(f)
                return status
        return {"connected": False, "playing": None}
    except:
        return {"connected": False, "playing": None}

def standardize_audio_file(input_file, output_file):
    """使用標準格式處理音訊檔案，確保在不同裝置上播放速度一致"""
    try:
        import subprocess
        
        # 使用 ffmpeg 將音訊檔案轉換為標準格式（44.1kHz、16位、立體聲）
        subprocess.call([
            'ffmpeg', '-i', input_file,
            '-ar', '44100',  # 設定採樣率為 44.1kHz
            '-acodec', 'pcm_s16le',  # 16位編碼
            '-ac', '2',  # 立體聲
            output_file
        ])
        
        return output_file
    except Exception as e:
        log_message(f"標準化音訊檔案時發生錯誤: {e}")
        return input_file

def start_recording():
    """開始直接捕獲程式播放的音訊數據"""
    global is_recording, recording_thread, audio_buffer
    global audio_last_update_time, audio_format, audio_channels, audio_rate
    
    if is_recording:
        log_message("錄音已經在進行中")
        return
    
    # 清空並重新初始化錄音緩衝區
    audio_buffer = []
    audio_last_update_time = time.time()
    
    # 設置默認音訊參數（可能會在播放時更新）
    audio_format = 2
    audio_channels = 2
    audio_rate = 44100
    
    # 設置錄音標誌
    is_recording = True
    log_message("開始錄製程式音訊...")
    
    # 創建時間戳記
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"recording_{timestamp}.wav"
    
    # 創建音訊錄製線程
    recording_thread = threading.Thread(target=record_audio_stream, args=(filename,))
    recording_thread.daemon = True
    recording_thread.start()

def stop_recording():
    """停止錄製程式播放的音訊並上傳到雲端"""
    global is_recording
    
    if not is_recording:
        log_message("目前沒有進行錄音")
        return
    
    # 設置停止錄音標誌
    is_recording = False
    log_message("停止錄音，正在儲存檔案...")
    
    # 等待錄音線程結束
    if recording_thread and recording_thread.is_alive():
        recording_thread.join(timeout=2.0)
    
    # 更新UI以顯示處理狀態
    if ui_update_callback:
        ui_update_callback("錄音已完成，正在處理並上傳...")

def record_audio_stream(filename):
    global is_recording, audio_buffer
    
    try:
        # 檔案路徑設定
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        base_filename = f"recording_{timestamp}"
        full_filename = f"{base_filename}.wav"
        file_path = os.path.join(STORAGE_DIR, full_filename)
        
        # 初始化
        audio_buffer = []
        
        log_message("開始錄製音訊...")
        
        # 等待直到停止錄音
        while is_recording:
            time.sleep(0.1)
        
        log_message("停止錄音，正在處理音訊資料...")
        
        if audio_buffer:
            # 確定所使用的音訊格式參數
            # 使用固定參數，確保與播放匹配
            channels = 2
            sample_width = 2  # 16位元
            frame_rate = 44100  # 44.1kHz
            
            # 合併所有音訊資料
            merged_audio = b''.join(audio_buffer)
            
            # 創建並寫入 WAV 檔案
            wf = wave.open(file_path, 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(frame_rate)
            wf.writeframes(merged_audio)
            wf.close()
            
            log_message(f"錄音完成，音訊檔案已儲存到: {file_path}")
            
            # 上傳到 Google Drive 的代碼保持不變...
            log_message("正在自動上傳錄音檔案...")
            download_link = upload_to_google_drive(file_path)
            
            if download_link:
                # 生成 QR Code
                qr_path = generate_qr_code(download_link, base_filename)
                
                log_message(f"上傳成功！下載連結: {download_link}")
                log_message(f"QR Code 已儲存至: {qr_path}")
            else:
                log_message("上傳失敗，無法生成下載連結")
        else:
            log_message("未收集到任何音訊數據，錄音失敗")
        
    except Exception as e:
        log_message(f"錄音過程中發生錯誤: {e}")
        import traceback
        log_message(traceback.format_exc())
    
    finally:
        is_recording = False
if __name__ == "__main__":
    # 執行主函數
    asyncio.run(start_bluetooth_service())