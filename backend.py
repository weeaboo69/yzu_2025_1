import asyncio
import numpy as np
from bleak import BleakClient, BleakScanner
import pyaudio
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
import sounddevice as sd
import scipy.io.wavfile as wavfile
import serial
import threading
from multiprocessing import Process
import pygame

serial_device = None
serial_connected = False

audio_mixer = None

# 歌單控制器狀態變數
songlist_connected = False
songlist_current_playing_music = None
songlist_last_update = time.time()

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

device_audio_channels = {
    "ESP32_HornBLE": None,
    "ESP32_HornBLE_2":None,
    "ESP32_Wheelspeed2_BLE": None,
    "ESP32_RDP_BLE": None,
    "ESP32_MusicSensor_BLE": None,
    "ESP32_test_remote": None,
    "Serial_Device": None
}

# 裝置與適配器的映射關係
DEVICE_ADAPTER_MAP = {
    "ESP32_MusicSensor_BLE": "hci0",  # 音樂控制器走主適配器
    "ESP32_HornBLE": "hci0",          # 喇叭控制器也走主適配器
    "ESP32_HornBLE_2": "hci0",
    "ESP32_RDP_BLE": "hci0",          # RDP控制器走外接適配器
    "ESP32_Wheelspeed2_BLE": "hci0",  # 輪子速度控制器走外接適配器
    "ESP32_test_remote":"hci0"
}

device_audio_threads = {
    "ESP32_HornBLE": None,
    "ESP32_HornBLE_2":None,
    "ESP32_Wheelspeed2_BLE": None,
    "ESP32_RDP_BLE": None,
    "ESP32_MusicSensor_BLE": None,
    "ESP32_test_remote":None,
    "Serial_Device": None
}

device_stop_flags = {
    "ESP32_HornBLE": False,
    "ESP32_HornBLE_2":False,    
    "ESP32_Wheelspeed2_BLE": False,
    "ESP32_RDP_BLE": False,
    "ESP32_MusicSensor_BLE": False,
    "ESP32_test_remote":False,
    "Serial_Device": False
}

device_playback_speeds = {
    "ESP32_HornBLE": 1.0,
    "ESP32_HornBLE_2":10,
    "ESP32_Wheelspeed2_BLE": 1.0,
    "ESP32_RDP_BLE": 1.0,
    "ESP32_MusicSensor_BLE": 1.0,
    "ESP32_test_remote":1.0,
    "Serial_Device": 1.0
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
    "2": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_JZ.wav",  # 音樂2對應的RDP音效
    "3": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP.wav",  # 音樂3對應的RDP音效
    "default": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP.wav",    # 默認的RDP音效
    "RDP_2": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_2.wav",  # 按鈕2按下時播放
    "RDP_3_before": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_3_before.wav", # 按鈕3按下時循環播放
    "RDP_3_after": "C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP_3_after.wav"   # 按鈕3放開時播放
}

# 設定ESP32裝置的UUID
ESP32_DEVICES = [
    #"ESP32_HornBLE",           # 喇叭控制器
    #"ESP32_HornBLE_2",
    #"ESP32_Wheelspeed2_BLE",   # 輪子速度控制器
    "ESP32_RDP_BLE",           # 輪子觸發控制器
    "ESP32_MusicSensor_BLE",    # 歌單控制器
    "ESP32_test_remote",
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

def auto_detect_serial_port():
    """自動偵測可用的串口"""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        available_ports = []
        
        for port in ports:
            log_message(f"發現串口: {port.device} - {port.description}")
            available_ports.append(port.device)
        
        if available_ports:
            return available_ports
        return None
    except Exception as e:
        log_message(f"自動偵測串口時發生錯誤: {e}")
        return None

# 音樂播放函數
def songlist_play_music(index, loop=True, speed=1.0):
    """開始播放音樂"""
    global songlist_current_playing_music
    
    # 確保前一個音訊真的停止了
    stop_device_audio("ESP32_MusicSensor_BLE")
    
    # 獲取音樂檔案路徑
    if index not in music_files:
        log_message(f"找不到音樂 {index}")
        return False
    
    file_path = music_files[index]
    
    # 更新目前播放的音樂記錄
    songlist_current_playing_music = index
    log_message(f"歌單控制器: 開始播放音樂 {index}")
    
    # 播放音樂
    play_device_music("ESP32_MusicSensor_BLE", file_path, loop, speed)
    
    return True

# 停止播放函數
def songlist_stop_music():
    """停止播放音樂"""
    global songlist_current_playing_music
    
    # 停止音訊播放
    stop_device_audio("ESP32_MusicSensor_BLE")
    
    # 重置播放狀態
    songlist_current_playing_music = None
    
    log_message("歌單控制器: 停止播放音樂")
    return True

def auto_connect_serial_device(preferred_ports=None):
    
    all_ports = auto_detect_serial_port()
    if not all_ports:
        log_message("未發現可用串口")
        return False
    
    # 如果有指定優先埠，先嘗試連接這些埠
    if preferred_ports:
        for port in preferred_ports:
            if port in all_ports:
                try:
                    log_message(f"嘗試連接指定的優先串口: {port}")
                    if connect_serial_device(port):
                        log_message(f"成功連接到指定串口: {port}")
                        return True
                except Exception as e:
                    log_message(f"連接串口 {port} 時發生錯誤: {e}")
    
    # 如果沒有指定優先埠或優先埠連接失敗，嘗試連接所有可用的埠
    for port in all_ports:
        # 如果是優先埠，已經嘗試過了，跳過
        if preferred_ports and port in preferred_ports:
            continue
            
        try:
            log_message(f"嘗試連接串口: {port}")
            if connect_serial_device(port):
                log_message(f"成功自動連接串口: {port}")
                return True
            time.sleep(0.5)  # 短暫延遲避免太快重試
        except Exception as e:
            log_message(f"連接串口 {port} 時發生錯誤: {e}")
    
    log_message("無法自動連接到有線裝置")
    return False

# 移除以下函數
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

def initialize_audio_system():
    global audio_mixer
    # 使用 pygame 的混音模組 - 較容易實現多聲道混音
    import pygame
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    pygame.mixer.set_num_channels(16)  # 支援最多16個同時播放的聲音
    audio_mixer = pygame.mixer
    log_message("初始化音訊系統完成 (使用 pygame 混音器)")

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

def connect_serial_device(port, baudrate=9600):
    """連接有線裝置"""
    global serial_device, serial_connected
    
    try:
        import serial
        serial_device = serial.Serial(port, baudrate, timeout=1)
        serial_connected = True
        log_message(f"已連接到有線裝置，端口: {port}, 波特率: {baudrate}")
        
        # 啟動串口監聽線程
        serial_thread = threading.Thread(target=serial_listener)
        serial_thread.daemon = True
        serial_thread.start()
        
        return True
    except Exception as e:
        log_message(f"連接有線裝置失敗: {e}")
        serial_connected = False
        return False

def disconnect_serial_device():
    """斷開有線裝置連接"""
    global serial_device, serial_connected
    
    if serial_device and serial_connected:
        try:
            serial_device.close()
            log_message("已斷開有線裝置連接")
        except Exception as e:
            log_message(f"斷開有線裝置時發生錯誤: {e}")
        finally:
            serial_connected = False
            serial_device = None

def serial_listener():
    """監聽串口數據"""
    global serial_device, serial_connected
    
    log_message("開始監聽有線裝置...")
    
    while serial_connected and serial_device:
        try:
            if serial_device.in_waiting > 0:
                data = serial_device.readline().decode('utf-8').strip()
                log_message(f"從有線裝置接收: {data}")
                
                # 處理來自有線裝置的命令，與RFID邏輯相同
                process_data("Serial_Device", data.encode('utf-8'))
        except Exception as e:
            log_message(f"讀取串口數據時發生錯誤: {e}")
            time.sleep(1)

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
    
    # 斷開串口連接
    disconnect_serial_device()
    
    log_message("所有藍牙和串口連接已斷開")

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
        chunk = 512
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
                # 直接添加原始音訊數據，不做任何處理或壓縮
                # 重要：確保完全相同的複製
                audio_buffer_copy = chunk_data[:]  # 創建完整副本，避免引用問題
                audio_buffer.append(audio_buffer_copy)
                audio_last_update_time = time.time()
        
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
    chunk = 256
    
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
                # 直接添加原始音訊數據，不做任何處理或壓縮
                # 重要：確保完全相同的複製
                audio_buffer_copy = chunk_data[:]  # 創建完整副本，避免引用問題
                audio_buffer.append(audio_buffer_copy)
                audio_last_update_time = time.time()
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
    global device_audio_threads, device_stop_flags, device_audio_channels
    
    log_message(f"嘗試停止裝置 {device_name} 的音訊播放")
    
    # 如果使用 PyAudio 系統，停止線程
    if device_name in device_audio_threads and device_audio_threads[device_name] and device_audio_threads[device_name].is_alive():
        device_stop_flags[device_name] = True
        device_audio_threads[device_name].join(timeout=1.0)
        print(f"已停止 {device_name} 的音訊播放")
    
    # 如果使用 pygame 混音系統，停止音訊通道
    if device_name in device_audio_channels and device_audio_channels[device_name]:
        device_audio_channels[device_name].stop()
        device_audio_channels[device_name] = None
        print(f"已停止 {device_name} 的 pygame 音訊播放")
    
    # 重置停止標誌
    if device_name in device_stop_flags:
        device_stop_flags[device_name] = False
    
    # 確保該裝置的音訊線程已經結束
    if device_name in device_audio_threads:
        device_audio_threads[device_name] = None

def songlist_play_music_dedicated(index, loop=True, speed=1.0):
    """專用於歌單控制器的播放函數，使用獨立的 pygame 引擎"""
    global songlist_current_playing_music
    
    try:
        # 確保 pygame 已初始化
        if 'pygame' not in sys.modules:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            log_message("為歌單控制器初始化獨立 pygame 混音器")
        
        # 停止當前播放的音樂
        if hasattr(songlist_play_music_dedicated, 'channel') and songlist_play_music_dedicated.channel:
            songlist_play_music_dedicated.channel.stop()
            
        # 獲取音樂檔案路徑
        if index not in music_files:
            log_message(f"找不到音樂 {index}")
            return False
            
        file_path = music_files[index]
        
        # 更新目前播放的音樂記錄
        songlist_current_playing_music = index
        log_message(f"歌單控制器: 開始播放音樂 {index}")
        
        # 載入並播放音樂
        import pygame
        sound = pygame.mixer.Sound(file_path)
        channel = sound.play(-1 if loop else 0)
        
        # 保存引用以便後續控制
        songlist_play_music_dedicated.sound = sound
        songlist_play_music_dedicated.channel = channel
        
        return True
    except Exception as e:
        log_message(f"歌單控制器音樂播放失敗: {e}")
        import traceback
        log_message(traceback.format_exc())
        songlist_current_playing_music = None
        return False

def songlist_stop_music_dedicated():
    """專用於歌單控制器的停止函數"""
    global songlist_current_playing_music
    
    try:
        # 停止播放
        if hasattr(songlist_play_music_dedicated, 'channel') and songlist_play_music_dedicated.channel:
            songlist_play_music_dedicated.channel.stop()
            
        # 重置狀態
        songlist_current_playing_music = None
        log_message("歌單控制器: 停止播放音樂")
        return True
    except Exception as e:
        log_message(f"歌單控制器停止音樂失敗: {e}")
        return False

def play_device_music(device_name, file_path, loop=True, speed=1.0):
    global device_audio_channels, audio_mixer
    
    # 初始化 pygame.mixer (如果還沒初始化)
    if audio_mixer is None:
        initialize_audio_system()
    
    # 停止該裝置先前的音效 (只停止同一裝置的音效，不影響其他裝置)
    if device_name in device_audio_channels and device_audio_channels[device_name]:
        device_audio_channels[device_name].stop()
        time.sleep(0.05)
    
    # 載入並播放新的音效
    try:
        sound = audio_mixer.Sound(file_path)
        channel = sound.play(-1 if loop else 0)
        device_audio_channels[device_name] = channel
        
        # 設定音量和速度
        if channel:
            channel.set_volume(1.0)
        
        log_message(f"開始為 {device_name} 播放: {file_path}, 循環: {loop}")
        return True
    except Exception as e:
        log_message(f"播放音效失敗: {e}")
        return False

# 處理來自ESP32的資料
def process_data(device_name, data):
    global stop_recording, start_recording
    if isinstance(data, bytes):
        try:
            command_str = data.decode('utf-8')
        except UnicodeDecodeError:
            # 如果不是有效的 UTF-8 編碼，那麼可能是二進制數據
            command_str = str(data)
    else:
        command_str = str(data)
    
    log_message(f"{device_name}: 收到命令 {command_str}")
    
    # 處理來自有線裝置的命令（與RFID裝置邏輯相同）
    if device_name == "Serial_Device":
        if command_str == "PLAY_MUSIC_1":
            print("開始播放音樂1")
            play_device_music(device_name, music_files["1"], loop=True)
        
        elif command_str == "PLAY_MUSIC_2":
            print("開始播放音樂2")
            play_device_music(device_name, music_files["2"], loop=True)
        
        elif command_str == "PLAY_MUSIC_3":
            print("開始播放音樂3")
            play_device_music(device_name, music_files["3"], loop=True)
        elif command_str == "STOP_MUSIC":
            print("停止播放音樂zzz")
            stop_device_audio(device_name)

    # 根據裝置名稱分別處理資料
    elif device_name == "ESP32_HornBLE":
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

    elif device_name == "ESP32_HornBLE":
    # 處理喇叭控制器資料
        
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

        if data[0] == 252:  # 播放指令 (開始彎曲)
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
                    
        elif data[0] == 251:  # 停止指令 (停止彎曲)
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
    elif device_name == "ESP32_HornBLE_2":
        if data[0] == 252:  # 播放指令 (開始彎曲)
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
                    
        elif data[0] == 251:  # 停止指令 (停止彎曲)
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
        current_song = songlist_current_playing_music
        # 按鈕3處理邏輯 (會根據當前播放音樂調整行為)
        if command_str == "BUTTON3_PRESSED":
            print("按鈕3已按下，根據目前播放的音樂選擇音效")
            
            # 選擇對應的音效和播放方式
            sound_file = rdp_audio_files.get("RDP_3_before")  # 預設音效
            should_loop = True  # 預設循環播放
            
            if current_song:
                print(f"歌單控制器正在播放音樂: {current_song}")
                
                # 根據不同的音樂選擇不同的音效
                if current_song == "1":
                    sound_file = rdp_audio_files.get("RDP_3_before", sound_file)
                elif current_song == "2":
                    sound_file = rdp_audio_files.get("RDP_2", sound_file)
                elif current_song == "3":
                    sound_file = rdp_audio_files.get("RDP_3_before", sound_file)
            else:
                print("歌單控制器未播放音樂，使用預設音效")
                sound_file = rdp_audio_files.get("RDP_3_before", sound_file)
            
            # 播放選定的音效
            if os.path.exists(sound_file):
                play_device_music(device_name, sound_file, loop=should_loop)
            else:
                log_message(f"找不到音效檔案: {sound_file}")
            
        elif command_str == "BUTTON3_RELEASED":
            print("按鈕3已放開，停止循環並播放 RDP_3_after 音效")
            # 先停止循環播放
            stop_device_audio(device_name)
            # 播放結束音效
            if (not current_song or (current_song != "2")):
                if "RDP_3_after" in rdp_audio_files:
                    play_device_music(device_name, rdp_audio_files["RDP_3_after"], loop=False)
                else:
                    print("找不到 RDP_3_after 音效檔案")

    elif device_name == "ESP32_MusicSensor_BLE":
        # 處理歌單控制器資料
        command = data.decode('utf-8')
        print(f"歌單控制器: 收到命令 {command}")
        
        # 根據命令選擇並播放對應的音樂
        if command == "PLAY_MUSIC_1":
            print("開始播放音樂1")
            songlist_play_music("1", loop=True)
        elif command == "STOP_MUSIC_1":
            print("停止播放音樂1")
            songlist_stop_music()
        
        elif command == "PLAY_MUSIC_2":
            print("開始播放音樂2")
            songlist_play_music("2", loop=True)
        elif command == "STOP_MUSIC_2":
            print("停止播放音樂2")
            songlist_stop_music()
        
        elif command == "PLAY_MUSIC_3":
            print("開始播放音樂3")
            songlist_play_music("3", loop=True)
        elif command == "STOP_MUSIC_3":
            print("停止播放音樂3")
            songlist_stop_music()

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

def connect_serial_device(port, baudrate=9600):
    """連接有線RFID裝置"""
    global serial_device, serial_connected
    
    try:
        serial_device = serial.Serial(port, baudrate, timeout=1)
        serial_connected = True
        log_message(f"已連接到有線RFID裝置，端口: {port}")
        
        # 啟動監聽線程
        threading.Thread(target=listen_serial_device, daemon=True).start()
        return True
    except Exception as e:
        log_message(f"連接有線RFID裝置失敗: {e}")
        return False

def listen_serial_device():
    """監聽有線裝置傳來的訊息"""
    global serial_device, serial_connected
    
    while serial_connected and serial_device:
        try:
            if serial_device.in_waiting > 0:
                line = serial_device.readline().decode('utf-8').strip()
                log_message(f"有線RFID裝置: {line}")
                
                # 處理命令
                if line.startswith("PLAY_MUSIC") or line.startswith("STOP_MUSIC"):
                    # 使用與其他裝置相同的邏輯處理命令
                    process_data("Serial_Device", line)
        except Exception as e:
            log_message(f"讀取有線RFID裝置數據時發生錯誤: {e}")
        time.sleep(0.1)
    
    log_message("有線RFID裝置監聽已停止")

def disconnect_serial_device():
    """斷開有線RFID裝置連接"""
    global serial_device, serial_connected
    
    if serial_device:
        try:
            serial_connected = False
            serial_device.close()
            serial_device = None
            log_message("已斷開有線RFID裝置連接")
        except Exception as e:
            log_message(f"斷開有線RFID裝置時發生錯誤: {e}")

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
    global songlist_connected
    
    # 不再啟動外部歌單控制器
    log_message("啟動整合式歌單控制器...")
    songlist_connected = True
    
    # 在新線程中啟動藍牙和串口服務
    def run_async_loop():
        # 先嘗試自動連接串口裝置
        # auto_connect_result = auto_connect_serial_device(preferred_ports=['COM11'])
        # log_message(f"有線裝置自動連接結果: {auto_connect_result}")
        
        # 然後啟動藍牙服務
        asyncio.run(start_bluetooth_service())
    
    # 啟動後端線程
    backend_thread = threading.Thread(target=run_async_loop)
    backend_thread.daemon = True
    backend_thread.start()
    return backend_thread

def send_command_to_songlist(command, params=None):
    """向歌單控制器發送命令 (整合後直接處理)"""
    try:
        if command == "PLAY_MUSIC":
            index = params.get("index", "1")
            loop = params.get("loop", True)
            return songlist_play_music_dedicated(index, loop)
        elif command == "STOP_MUSIC":
            return songlist_stop_music_dedicated()
        elif command == "UPDATE_CONFIG":
            # 處理配置更新，可能需要額外的實現
            pass
        
        log_message(f"已直接處理命令: {command}")
        return True
    except Exception as e:
        log_message(f"處理命令失敗: {e}")
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
    songlist_stop_music()
    
    current_playing_music = None
    return True

def get_songlist_controller_status():
    """獲取歌單控制器的狀態"""
    global songlist_connected, songlist_current_playing_music
    
    # 現在直接返回內存中的狀態
    return {
        "connected": songlist_connected,
        "playing": songlist_current_playing_music,
        "last_update": time.time()
    }

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

def start_recording(selected_device_index=None):
    """開始錄製系統音訊輸出
    
    Args:
        selected_device_index: 可選的設備索引，如果提供則使用指定設備
    """
    global is_recording, recording_thread
    
    if is_recording:
        log_message("錄音已經在進行中")
        return False
    
    try:
        import soundcard as sc
        import numpy as np
        import scipy.io.wavfile as wavfile
        
        # 設置錄音標誌
        is_recording = True
        
        # 創建時間戳記
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"recording_{timestamp}.wav"
        file_path = os.path.join(STORAGE_DIR, filename)
        
        def recording_function():
            global is_recording
            
            try:
                # 列出所有音訊設備
                speakers_list = sc.all_speakers()
                microphones_list = sc.all_microphones()
                
                log_message(f"所有輸出設備: {[f'{i}: {s.name}' for i, s in enumerate(speakers_list)]}")
                log_message(f"所有輸入設備: {[f'{i}: {m.name}' for i, m in enumerate(microphones_list)]}")
                
                # 如果指定了設備索引，嘗試使用指定設備
                loopback_device = None
                
                if selected_device_index is not None:
                    if selected_device_index < len(microphones_list):
                        loopback_device = microphones_list[selected_device_index]
                        log_message(f"使用選定的設備: {loopback_device.name}")
                    else:
                        log_message(f"選定的設備索引 {selected_device_index} 無效")
                
                # 如果沒有指定設備或指定設備無效，嘗試找到合適的設備
                if not loopback_device:
                    # 嘗試找到立體聲混音設備
                    for mic in speakers_list:
                        if "立體聲混音" in mic.name or "stereo mix" in mic.name.lower():
                            loopback_device = mic
                            log_message(f"找到立體聲混音設備: {mic.name}")
                            break
                
                if not loopback_device and len(speakers_list) > 0:
                    # 如果仍然沒有找到，使用第一個麥克風
                    loopback_device = speakers_list[0]
                    log_message(f"無法找到立體聲混音設備，使用第一個設備: {loopback_device.name}")
                
                if not loopback_device:
                    raise Exception("無法找到合適的錄音設備")
                
                # 開始錄音
                log_message(f"開始使用設備 {loopback_device.name} 錄製系統音訊...")
                
                # 使用 recorder 錄製
                sample_rate = 44100
                all_data = []
                
                with loopback_device.recorder(samplerate=sample_rate, channels=2) as recorder:
                    idx = 0
                    while is_recording:
                        # 每次錄製一小段時間的數據
                        data = recorder.record(sample_rate // 2)  # 錄製約 0.5 秒
                        all_data.append(data)
                        
                        idx += 1
                        if idx % 10 == 0:  # 每 5 秒顯示一次狀態
                            log_message("正在錄音中...")
                
                # 只有在實際錄製了數據時才處理
                if all_data:
                    # 合併所有數據
                    recorded_data = np.concatenate(all_data)
                    
                    # 將數據保存為 WAV 文件
                    wavfile.write(file_path, sample_rate, (recorded_data * 32767).astype(np.int16))
                    
                    log_message(f"錄音完成，檔案已保存到: {file_path}")
                    
                    # 上傳到 Google Drive
                    base_filename = os.path.splitext(os.path.basename(file_path))[0]
                    log_message("正在自動上傳錄音檔案...")
                    download_link = upload_to_google_drive(file_path)
                    
                    if download_link:
                        # 生成 QR Code
                        qr_path = generate_qr_code(download_link, base_filename)
                        
                        log_message(f"上傳成功！下載連結: {download_link}")
                        log_message(f"QR Code 已儲存至: {qr_path}")
                        
                        # 更新UI顯示
                        if ui_update_callback:
                            ui_update_callback(f"錄音已上傳，下載連結: {download_link}")
                    else:
                        log_message("上傳失敗，無法生成下載連結")
                        if ui_update_callback:
                            ui_update_callback("錄音已完成，但上傳失敗")
                else:
                    log_message("未錄到任何音訊數據")
            except Exception as e:
                log_message(f"系統錄音過程中發生錯誤: {e}")
                import traceback
                log_message(traceback.format_exc())
            finally:
                is_recording = False
                if ui_update_callback:
                    ui_update_callback("錄音已完成")
        
        # 創建錄音線程
        recording_thread = threading.Thread(target=recording_function)
        recording_thread.daemon = True
        recording_thread.start()
        
        # 更新UI狀態
        if ui_update_callback:
            ui_update_callback("開始錄音...")
        
        log_message("系統錄音已開始")
        return True
    
    except ImportError:
        log_message("錯誤: 未安裝 soundcard 庫。請執行 'pip install soundcard' 安裝。")
        is_recording = False
        return False
    except Exception as e:
        log_message(f"啟動系統錄音失敗: {e}")
        import traceback
        log_message(traceback.format_exc())
        is_recording = False
        return False

def update_recording_buffer(indata, recorded_data, frames):
    """更新錄音緩衝區，將新捕獲的數據添加到錄音數組中"""
    # 初始化 position 如果不存在
    if not hasattr(update_recording_buffer, 'position'):
        update_recording_buffer.position = 0
    
    # 檢查是否還有空間
    if update_recording_buffer.position + frames <= recorded_data.shape[0]:
        # 將數據複製到錄音陣列中
        recorded_data[update_recording_buffer.position:update_recording_buffer.position+frames] = indata
        update_recording_buffer.position += frames

def stop_recording():
    """停止錄製系統音訊"""
    global is_recording
    
    if not is_recording:
        log_message("目前沒有進行錄音")
        return False
    
    log_message("停止錄音...")
    is_recording = False
    
    # 等待錄音線程結束
    if recording_thread and recording_thread.is_alive():
        recording_thread.join(timeout=5.0)
    
    # 更新UI以顯示處理狀態
    if ui_update_callback:
        ui_update_callback("錄音已停止，正在處理...")
    
    return True

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
        last_silence_check = time.time()
        
        log_message("開始錄製音訊...")
        
        # 等待直到停止錄音
        while is_recording:
            time.sleep(0.1)
        
        log_message("停止錄音，正在處理音訊資料...")
        
        if audio_buffer:
            # 使用 NumPy 來處理合併，可能比 b''.join 更有效
            import numpy as np
            
            # 將所有緩衝區數據轉換為 numpy 數組
            data_arrays = []
            for chunk in audio_buffer:
                # 轉換為 16 位整數數組
                arr = np.frombuffer(chunk, dtype=np.int16)
                data_arrays.append(arr)
            
            # 合併所有數組
            merged_data = np.concatenate(data_arrays)
            
            # 轉換回字節
            merged_audio = merged_data.tobytes()
            
            # 確保使用原始音訊的參數
            channels = 2  # 立體聲
            sample_width = 2  # 16位元
            frame_rate = 44100  # 44.1kHz
            
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
        # 清空緩衝區，為下次錄音做準備
        audio_buffer = []
if __name__ == "__main__":
    # 執行主函數
    asyncio.run(start_bluetooth_service())
    