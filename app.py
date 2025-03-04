import asyncio
import numpy as np
from bleak import BleakClient, BleakScanner
import pyaudio
import cv2
import time

# 設定ESP32裝置的UUID
ESP32_UUIDS = [
    "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # ESP32-1
    "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",  # ESP32-2
    # ... 添加更多ESP32的UUID
]

# 特性UUID (需要與ESP32端匹配)
CHARACTERISTIC_UUID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# 儲存所有設備的資料
device_data = {uuid: {} for uuid in ESP32_UUIDS}

# 音訊和影像播放函數
def play_audio(audio_data):
    # 實現音訊播放邏輯
    pass

def display_image(image_data):
    # 實現影像顯示邏輯
    pass

# 處理來自ESP32的資料
def process_data(uuid, data):
    # 解析資料並根據需要觸發音訊或影像播放
    device_data[uuid] = parse_data(data)
    
    # 觸發相應的多媒體播放
    if "audio_trigger" in device_data[uuid]:
        play_audio(device_data[uuid]["audio_data"])
    
    if "image_trigger" in device_data[uuid]:
        display_image(device_data[uuid]["image_data"])

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
async def connect_to_device(uuid):
    device = await BleakScanner.find_device_by_name(uuid)
    if device is None:
        print(f"Could not find device with UUID {uuid}")
        return None
    
    client = BleakClient(device)
    try:
        await client.connect()
        print(f"Connected to {uuid}")
        
        # 訂閱通知
        await client.start_notify(CHARACTERISTIC_UUID, notification_handler(uuid))
        
        return client
    except Exception as e:
        print(f"Connection to {uuid} failed: {e}")
        return None

# 主函數
async def main():
    # 連接到所有ESP32設備
    clients = []
    for uuid in ESP32_UUIDS:
        client = await connect_to_device(uuid)
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