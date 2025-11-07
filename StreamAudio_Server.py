import socket
import time
import threading
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
import queue

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

# КОНСИСТЕНТНЫЕ НАСТРОЙКИ - ДОЛЖНЫ СОВПАДАТЬ С КЛИЕНТОМ
CHUNK = 1024  # Увеличиваем для стабильности
RATE = 44100  # Стандартная частота
CHANNELS = 2  # Стерео
FORMAT = 'int16'  # Единый формат
MULTICAST_GROUP = '224.1.1.1'
PORT = 5007

class GameAudioStreamServer:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.stream = None
        self.audio_queue = queue.Queue()
        self.setup_gui()
        self.refresh_devices()
        
    def setup_gui(self):
        """Настройка GUI для игрового стриминга"""
        self.root.title("Game Audio Stream Server - FIXED")
        self.root.geometry("550x550")
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="🎮 Стриминг Игрового Звука (ИСПРАВЛЕННЫЙ)", 
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Информация о настройках
        settings_info = ttk.LabelFrame(main_frame, text="Текущие настройки", padding="10")
        settings_info.pack(fill=tk.X, pady=(0, 10))
        
        info_text = f"""Частота: {RATE} Hz | Каналы: {CHANNELS} | Формат: {FORMAT} | Размер чанка: {CHUNK}
ВАЖНО: Эти настройки должны совпадать на клиенте!"""
        ttk.Label(settings_info, text=info_text, foreground="green").pack()
        
        # Раздел системного звука
        system_frame = ttk.LabelFrame(main_frame, text="Захват системного звука", padding="10")
        system_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(system_frame, text="Устройство захвата:").grid(row=0, column=0, sticky=tk.W)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(system_frame, textvariable=self.device_var, 
                                        state="readonly", width=50)
        self.device_combo.grid(row=0, column=1, padx=5, sticky=tk.EW)
        
        refresh_btn = ttk.Button(system_frame, text="🔍 Обновить", 
                               command=self.refresh_devices)
        refresh_btn.grid(row=0, column=2, padx=5)
        
        system_frame.columnconfigure(1, weight=1)
        
        # Инструкция
        info_text = """Для захвата звука из игр:
1. Используйте 'Stereo Mix' или 'Что слышно'
2. Или установите VoiceMeeter
3. Убедитесь, что в игре звук включен"""
        
        info_label = ttk.Label(main_frame, text=info_text, foreground="blue",
                              justify=tk.LEFT)
        info_label.pack(pady=10)
        
        # Настройки сети
        network_frame = ttk.LabelFrame(main_frame, text="Настройки сети", padding="10")
        network_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(network_frame, text="Multicast группа:").grid(row=0, column=0, sticky=tk.W)
        self.group_var = tk.StringVar(value=MULTICAST_GROUP)
        ttk.Entry(network_frame, textvariable=self.group_var, width=15).grid(row=0, column=1, padx=5)
        
        ttk.Label(network_frame, text="Порт:").grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        self.port_var = tk.StringVar(value=str(PORT))
        ttk.Entry(network_frame, textvariable=self.port_var, width=10).grid(row=0, column=3, padx=5)
        
        # Статус
        self.status_var = tk.StringVar(value="Готов к захвату игрового звука")
        status_frame = ttk.LabelFrame(main_frame, text="Статус", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(status_frame, textvariable=self.status_var, foreground="blue").pack(anchor=tk.W)
        
        # Статистика
        self.stats_var = tk.StringVar(value="Пакетов отправлено: 0")
        stats_frame = ttk.LabelFrame(main_frame, text="Статистика", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(stats_frame, textvariable=self.stats_var).pack(anchor=tk.W)
        
        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(button_frame, text="🎮 Начать стрим", 
                                  command=self.start_stream)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(button_frame, text="⏹️ Остановить", 
                                 command=self.stop_stream, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
    
    def refresh_devices(self):
        """Обновить список устройств с поиском Stereo Mix"""
        if not SOUNDDEVICE_AVAILABLE:
            return
            
        devices = []
        self.device_info = {}
        
        try:
            device_list = sd.query_devices()
            
            # Сначала ищем устройства для системного захвата
            stereo_mix_devices = self.find_stereo_mix_devices(device_list)
            devices.extend(stereo_mix_devices)
            
            # Затем обычные микрофоны
            for i, device in enumerate(device_list):
                if device['max_input_channels'] > 0:
                    device_name = f"{i}: {device['name']}"
                    # Пропускаем если уже добавили как Stereo Mix
                    if not any(device_name in stereo_mix for stereo_mix in stereo_mix_devices):
                        devices.append(device_name)
                        self.device_info[device_name] = {
                            'index': i,
                            'device': device,
                            'type': 'microphone'
                        }
            
            self.device_combo['values'] = devices
            
            # Автоматически выбираем Stereo Mix если найден
            if stereo_mix_devices:
                self.device_combo.set(stereo_mix_devices[0])
            elif devices:
                self.device_combo.set(devices[0])
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить устройства: {e}")
    
    def find_stereo_mix_devices(self, device_list):
        """Найти устройства для захвата системного звука"""
        stereo_mix_devices = []
        
        for i, device in enumerate(device_list):
            if device['max_input_channels'] > 0:
                device_name_lower = device['name'].lower()
                
                # Ключевые слова для системного захвата
                stereo_mix_keywords = [
                    'stereo mix', 'what you hear', 'waveout mix',
                    'mix stereo', 'system sounds', 'voicemeeter', 'cable'
                ]
                
                if any(keyword in device_name_lower for keyword in stereo_mix_keywords):
                    device_name = f"{i}: {device['name']} 🔊 СИСТЕМНЫЙ ЗВУК"
                    stereo_mix_devices.append(device_name)
                    self.device_info[device_name] = {
                        'index': i,
                        'device': device,
                        'type': 'stereo_mix'
                    }
        
        return stereo_mix_devices
    
    def start_stream(self):
        """Запуск стриминга игрового звука"""
        try:
            selected_device = self.device_var.get()
            if not selected_device:
                messagebox.showerror("Ошибка", "Выберите устройство захвата")
                return
            
            device_info = self.device_info[selected_device]
            device_index = device_info['index']
            
            # Настройка сети
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            
            self.running = True
            self.packet_count = 0
            self.start_time = time.time()
            
            # Запуск потоков
            self.send_thread = threading.Thread(target=self.send_audio_data, daemon=True)
            self.send_thread.start()
            
            print(f"Starting audio capture: {RATE}Hz, {CHANNELS} channels, format: {FORMAT}")
            
            # Запуск аудио захвата с правильными параметрами
            self.stream = sd.InputStream(
                device=device_index,
                channels=CHANNELS,
                samplerate=RATE,
                blocksize=CHUNK,
                callback=self.audio_callback,
                dtype=FORMAT  # Используем int16 напрямую
            )
            self.stream.start()
            
            self.status_var.set("🎮 Стриминг игрового звука активен")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            
            # Статистика
            self.stats_thread = threading.Thread(target=self.update_stats, daemon=True)
            self.stats_thread.start()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка запуска: {e}")
    
    def audio_callback(self, indata, frames, time, status):
        """Callback для захвата аудио"""
        if self.running:
            # Используем данные напрямую (уже в int16)
            audio_data = indata.tobytes()
            self.audio_queue.put(audio_data)
    
    def send_audio_data(self):
        """Отправка аудио данных"""
        while self.running:
            try:
                audio_data = self.audio_queue.get(timeout=1.0)
                self.sock.sendto(audio_data, (self.group_var.get(), int(self.port_var.get())))
                self.packet_count += 1
            except queue.Empty:
                continue
    
    def update_stats(self):
        """Обновление статистики"""
        while self.running:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                speed = self.packet_count / elapsed
                self.stats_var.set(f"Пакетов отправлено: {self.packet_count} ({speed:.1f}/сек)")
            time.sleep(2)
    
    def stop_stream(self):
        """Остановка стриминга"""
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if hasattr(self, 'sock'):
            self.sock.close()
        
        self.status_var.set("Стриминг остановлен")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = GameAudioStreamServer(root)
    root.mainloop()