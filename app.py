import asyncio
import numpy as np
from bleak import BleakClient, BleakScanner
import pyaudio
import cv2
import time

# 設定ESP32裝置的UUID
ESP32_DEVICES = [
    "ESP32_HornBLE",           # 喇叭控制器
    "ESP32_Wheelspeed2_BLE",   # 輪子速度控制器
    "ESP32_RDP_BLE",           # 輪子觸發控制器
    "ESP32_MusicSensor_BLE"    # 歌單控制器
]

# 特性UUID (需要與ESP32端匹配)
SERVICE_UUID = "180F"
CHARACTERISTIC_UUID = "2A19"

# 儲存所有設備的資料
device_data = {uuid: {} for uuid in ESP32_DEVICES}

# 音訊和影像播放函數
def play_audio(audio_data):
    # 實現音訊播放邏輯
    pass

def display_image(image_data):
    # 實現影像顯示邏輯
    pass

# 處理來自ESP32的資料
def process_data(device_name, data):
    # 根據裝置名稱分別處理資料
    if device_name == "ESP32_HornBLE":
        # 處理喇叭控制器資料
        if data[0] == 254:  # 播放指令
            print(f"喇叭控制器: 觸發播放")
        else:
            position = data[0]  # 播放位置 (0-100)
            print(f"喇叭控制器: 設定播放位置 {position}%")
            
    elif device_name == "ESP32_Wheelspeed2_BLE":
        # 處理輪子速度控制器資料
        speed_str = data.decode('utf-8')
        if speed_str == "STOP_PLAYBACK":
            print("輪子速度控制器: 停止播放")
        else:
            try:
                speed = float(speed_str)
                print(f"輪子速度控制器: 速度設定為 {speed}")
            except ValueError:
                print(f"輪子速度控制器: 無法解析資料 {speed_str}")
                
    elif device_name == "ESP32_RDP_BLE":
        # 處理輪子觸發控制器資料
        command = data.decode('utf-8')
        print(f"輪子觸發控制器: 收到命令 {command}")
        
    elif device_name == "ESP32_MusicSensor_BLE":
        # 處理歌單控制器資料
        command = data.decode('utf-8')
        print(f"歌單控制器: 收到命令 {command}")
        
    # 根據需要觸發相應的音訊或視覺效果

def parse_data(data):
    # 將從ESP32收到的原始資料解析為結構化資料
    # 這裡需要根據您的協議實現
    return {"sensor_value": data}

# 回調函數，處理來自裝置的通知
def notification_handler(uuid):
    def handler(_, data):
        process_data(uuid, data)
    return handler

# 連接到一個ESP32
async def connect_to_device(device_name):
    device = await BleakScanner.find_device_by_name(device_name)
    if device is None:
        print(f"找不到裝置 {device_name}")
        return None
    
    client = BleakClient(device)
    try:
        await client.connect()
        print(f"已連接到 {device_name}")
        
        # 訂閱通知
        await client.start_notify(CHARACTERISTIC_UUID, notification_handler(device_name))
        
        return client
    except Exception as e:
        print(f"連接到 {device_name} 失敗: {e}")
        return None

# 主函數
async def main():
    # 連接到所有ESP32設備
    clients = []
    for device_name in ESP32_DEVICES:
        client = await connect_to_device(device_name)
        if client:
            clients.append(client)
    
    # 保持連接並處理資料
    try:
        while True:
            await asyncio.sleep(0.01)  # 小延遲，讓其他任務有機會執行
    except KeyboardInterrupt:
        # 斷開所有連接
        for client in clients:
            await client.disconnect()

if __name__ == "__main__":
    # 執行主函數
    asyncio.run(main())