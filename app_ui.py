import sys
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import time
import backend

class MusicControlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("音樂控制系統")
        self.root.geometry("800x600")
        self.root.minsize(800, 600)
        
        # 創建主框架
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 創建標頭標籤
        header_label = ttk.Label(self.main_frame, text="ZzzZxw", font=("Arial", 18, "bold"))
        header_label.pack(pady=10)
        
        # 創建一個筆記本 (Notebook) 用於分頁
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 創建主控制頁
        self.control_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.control_frame, text="主控制")
        
        # 創建設定頁
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="設定")
        
        # 創建日誌頁
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="日誌")
        
        # 設置主控制頁
        self.setup_control_tab()
        
        # 設置設定頁
        self.setup_settings_tab()
        
        # 設置日誌頁
        self.setup_log_tab()
        
        # 設置狀態欄
        self.status_bar = ttk.Label(root, text="就緒", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 啟動後端
        self.backend_thread = None
        self.start_backend()
        
        # 設置UI更新回調
        backend.set_ui_update_callback(self.update_log)
        
        # 啟動UI更新線程
        self.running = True
        self.update_thread = threading.Thread(target=self.update_ui_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        # 關閉視窗時的處理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_control_tab(self):
        # 分割控制頁為左右兩部分
        control_paned = ttk.PanedWindow(self.control_frame, orient=tk.HORIZONTAL)
        control_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左側設備連接區域
        device_frame = ttk.LabelFrame(control_paned, text="設備連接")
        control_paned.add(device_frame, weight=1)
        
        # 右側音樂控制區域
        music_frame = ttk.LabelFrame(control_paned, text="音樂控制")
        control_paned.add(music_frame, weight=1)
        
        # 設備連接區域內容
        self.device_tree = ttk.Treeview(device_frame, columns=("Status",), height=10)
        self.device_tree.heading("#0", text="設備名稱")
        self.device_tree.heading("Status", text="連接狀態")
        self.device_tree.column("#0", width=180)
        self.device_tree.column("Status", width=100)
        self.device_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 新增設備框架
        add_device_frame = ttk.Frame(device_frame)
        add_device_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.new_device_var = tk.StringVar()
        ttk.Label(add_device_frame, text="設備名稱:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(add_device_frame, textvariable=self.new_device_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(add_device_frame, text="連接", command=self.connect_new_device).pack(side=tk.LEFT, padx=5)
        ttk.Button(add_device_frame, text="刷新", command=self.refresh_devices).pack(side=tk.LEFT, padx=5)
        
        # 音樂控制區域內容
        # 歌曲選擇區域
        music_selection_frame = ttk.LabelFrame(music_frame, text="歌曲選擇")
        music_selection_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 創建音樂選擇按鈕
        for i in range(1, 4):
            ttk.Button(music_selection_frame, text=f"音樂 {i}", 
                      command=lambda idx=str(i): self.play_music(idx)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # RDP音效按鈕
        ttk.Button(music_selection_frame, text="RDP 音效", 
                  command=lambda: self.play_music("RDP")).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # 播放控制區域
        playback_control_frame = ttk.LabelFrame(music_frame, text="播放控制")
        playback_control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(playback_control_frame, text="停止播放", 
                  command=lambda: backend.stop_current_audio()).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # 目前播放狀態
        status_frame = ttk.LabelFrame(music_frame, text="目前狀態")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.current_music_var = tk.StringVar(value="無播放")
        ttk.Label(status_frame, text="目前播放:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(status_frame, textvariable=self.current_music_var).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
    def setup_settings_tab(self):
        # 音樂檔案設定區域
        music_files_frame = ttk.LabelFrame(self.settings_frame, text="音樂檔案設定")
        music_files_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 音樂檔案路徑設定
        self.music_file_vars = {}
        for i in range(1, 4):
            idx = str(i)
            frame = ttk.Frame(music_files_frame)
            frame.pack(fill=tk.X, padx=5, pady=5)
            
            ttk.Label(frame, text=f"音樂 {i} 路徑:").pack(side=tk.LEFT, padx=5)
            
            self.music_file_vars[idx] = tk.StringVar(value=backend.music_files.get(idx, ""))
            entry = ttk.Entry(frame, textvariable=self.music_file_vars[idx], width=50)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            ttk.Button(frame, text="瀏覽", 
                      command=lambda entry_var=self.music_file_vars[idx]: self.browse_file(entry_var)).pack(side=tk.LEFT, padx=5)
        
        # RDP音效檔案路徑設定
        rdp_frame = ttk.Frame(music_files_frame)
        rdp_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(rdp_frame, text="RDP 音效路徑:").pack(side=tk.LEFT, padx=5)
        
        self.rdp_file_var = tk.StringVar(value=backend.rdp_audio_file)
        entry = ttk.Entry(rdp_frame, textvariable=self.rdp_file_var, width=50)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        ttk.Button(rdp_frame, text="瀏覽", 
                  command=lambda: self.browse_file(self.rdp_file_var)).pack(side=tk.LEFT, padx=5)
        
        # 儲存按鈕
        save_frame = ttk.Frame(music_files_frame)
        save_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(save_frame, text="儲存設定", command=self.save_settings).pack(side=tk.RIGHT, padx=5)
    
    def setup_log_tab(self):
        # 日誌文字區域
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.log_text.config(state=tk.DISABLED)  # 設為只讀
        
        # 清除按鈕
        ttk.Button(self.log_frame, text="清除日誌", command=self.clear_log).pack(side=tk.RIGHT, padx=10, pady=5)
    
    def start_backend(self):
        """啟動後端服務"""
        self.backend_thread = backend.start_backend()
        self.update_status("已啟動後端服務")
    
    def connect_new_device(self):
        """連接新設備"""
        device_name = self.new_device_var.get().strip()
        if not device_name:
            messagebox.showwarning("警告", "請輸入設備名稱")
            return
        
        # 建立新的線程來處理連接，避免凍結UI
        def connect_thread():
            self.update_status(f"正在連接到 {device_name}...")
            
            # 使用asyncio運行連接函數
            import asyncio
            success = asyncio.run(backend.connect_to_specific_device(device_name))
            
            if success:
                self.update_status(f"已成功連接到 {device_name}")
                self.refresh_devices()
            else:
                self.update_status(f"連接到 {device_name} 失敗")
                messagebox.showerror("錯誤", f"無法連接到設備 {device_name}")
        
        t = threading.Thread(target=connect_thread)
        t.daemon = True
        t.start()
    
    def refresh_devices(self):
        """刷新設備列表"""
        # 清空當前樹形列表
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        # 獲取設備連接狀態
        status_dict = backend.get_connection_status()
        
        # 填充樹形列表
        for device_name, connected in status_dict.items():
            status_text = "已連接" if connected else "未連接"
            self.device_tree.insert("", "end", text=device_name, values=(status_text,))
    
    def play_music(self, music_idx):
        """播放選定的音樂"""
        loop = music_idx != "RDP"  # RDP音效不循環播放
        if backend.test_play_music(music_idx, loop):
            music_name = f"音樂 {music_idx}" if music_idx != "RDP" else "RDP 音效"
            self.update_status(f"開始播放 {music_name}")
        else:
            self.update_status("播放失敗")
            messagebox.showerror("錯誤", "無法播放選定的音樂")
    
    def browse_file(self, var):
        """瀏覽並選擇音訊檔案"""
        filepath = filedialog.askopenfilename(
            title="選擇音訊檔案",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
        )
        if filepath:
            var.set(filepath)
    
    def save_settings(self):
        """儲存音樂檔案設定"""
        success = True
        
        # 更新音樂檔案路徑
        for idx, var in self.music_file_vars.items():
            new_path = var.get().strip()
            if new_path and new_path != backend.music_files.get(idx, ""):
                if not backend.set_music_file_path(idx, new_path):
                    success = False
                    messagebox.showerror("錯誤", f"無法設置音樂 {idx} 的路徑: {new_path}")
        
        # 更新RDP音效檔案路徑
        rdp_path = self.rdp_file_var.get().strip()
        if rdp_path and rdp_path != backend.rdp_audio_file:
            if not backend.set_rdp_audio_file_path(rdp_path):
                success = False
                messagebox.showerror("錯誤", f"無法設置RDP音效路徑: {rdp_path}")
        
        if success:
            self.update_status("設定已儲存")
            messagebox.showinfo("成功", "設定已成功儲存")
    
    def update_log(self, message):
        """更新日誌視窗"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)  # 滾動到最底部
        self.log_text.config(state=tk.DISABLED)
    
    def clear_log(self):
        """清除日誌內容"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.update_status("已清除日誌")
    
    def update_status(self, message):
        """更新狀態欄訊息"""
        self.status_bar.config(text=message)
    
    def update_ui_loop(self):
        """定期更新UI元素"""
        while self.running:
            try:
                # 更新目前播放的音樂顯示
                current_music = backend.get_current_playing_music()
                if current_music:
                    if current_music == "RDP":
                        display_text = "RDP 音效"
                    else:
                        display_text = f"音樂 {current_music}"
                else:
                    display_text = "無播放"
                
                self.current_music_var.set(display_text)
                
                # 每5秒更新一次設備列表
                if int(time.time()) % 5 == 0:
                    self.refresh_devices()
                
                time.sleep(0.5)  # 短暫休眠以降低CPU使用率
            except Exception as e:
                print(f"UI更新錯誤: {e}")
                time.sleep(1)
    
    def on_closing(self):
        """關閉程式時的處理"""
        if messagebox.askokcancel("確認", "確定要結束程式嗎?"):
            self.running = False
            try:
                # 停止所有播放
                backend.stop_current_audio()
                # 等待UI更新線程結束
                if self.update_thread.is_alive():
                    self.update_thread.join(timeout=1.0)
            except:
                pass
            
            self.root.destroy()

if __name__ == "__main__":
    # 修正缺少的模組導入
    import os  # 確保backend中使用的os模組被導入
    
    root = tk.Tk()
    app = MusicControlApp(root)
    root.mainloop()