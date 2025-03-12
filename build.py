import PyInstaller.__main__
import os

# 音訊檔案路徑
audio_files = [
    'C:/Users/maboo/yzu_2025/yzu_2025_1/audio/horn_before.wav',
    'C:/Users/maboo/yzu_2025/yzu_2025_1/audio/horn_after.wav',
    'C:/Users/maboo/yzu_2025/yzu_2025_1/audio/wheel_sound.wav',
    'C:/Users/maboo/yzu_2025/yzu_2025_1/audio/1.wav',
    'C:/Users/maboo/yzu_2025/yzu_2025_1/audio/2.wav',
    'C:/Users/maboo/yzu_2025/yzu_2025_1/audio/3.wav',
    'C:/Users/maboo/yzu_2025/yzu_2025_1/audio/RDP.wav'
]

# 建立 --add-data 參數
add_data_args = []
for audio_file in audio_files:
    # 獲取檔案的絕對路徑和檔名
    filename = os.path.basename(audio_file)
    # 將檔案加入到打包的資源中，放到 'audio' 資料夾
    add_data_args.append(f'--add-data={audio_file};audio/')

# 組合所有參數
args = [
    'app_ui.py',  # 您的主程式入口點
    '--name=音樂控制系統',  # 設定輸出的應用程式名稱
    '--onefile',  # 打包成單一檔案
    '--windowed',  # 不顯示命令列視窗
    # '--icon=app_icon.ico',  # 應用程式圖示（如果您有的話，請取消註解）
]

# 將音訊檔案參數加入
args.extend(add_data_args)

# 執行 PyInstaller
PyInstaller.__main__.run(args)