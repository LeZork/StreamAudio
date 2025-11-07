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
# Можно настроить через GUI
DEFAULT_CHUNK = 256  # Уменьшено для минимальной задержки
DEFAULT_RATE = 44100  # Стандартная частота
CHANNELS = 2  # Стерео
FORMAT = 'int16'  # Единый формат
MULTICAST_GROUP = '224.1.1.1'
PORT = 5007

# Профили задержки
LATENCY_PROFILES = {
    'Минимальная': {'chunk': 128, 'rate': 44100},
    'Низкая': {'chunk': 256, 'rate': 44100},
    'Средняя': {'chunk': 512, 'rate': 44100},
    'Высокая': {'chunk': 1024, 'rate': 44100}
}

class GameAudioStreamServer:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.stream = None
        self.audio_queue = queue.Queue(maxsize=2)  # Ограничиваем очередь для минимальной задержки
        self.last_audio_level = 0.0
        self.dropped_packets = 0
        self.chunk_size = DEFAULT_CHUNK
        self.sample_rate = DEFAULT_RATE
        self.setup_gui()
        self.refresh_devices()
        
    def setup_gui(self):
        """Настройка GUI для игрового стриминга"""
        self.root.title("🎮 Game Audio Stream Server")
        self.root.geometry("600x700")
        self.root.configure(bg='#1e1e2e')
        
        # Настройка стилей
        style = ttk.Style()
        style.theme_use('clam')
        
        # Цветовая схема
        bg_color = '#1e1e2e'
        fg_color = '#cdd6f4'
        accent_color = '#89b4fa'
        success_color = '#a6e3a1'
        warning_color = '#f9e2af'
        error_color = '#f38ba8'
        
        # Настройка стилей
        style.configure('Title.TLabel', background=bg_color, foreground=accent_color, 
                       font=('Segoe UI', 16, 'bold'))
        style.configure('Header.TLabel', background=bg_color, foreground=fg_color, 
                       font=('Segoe UI', 10, 'bold'))
        style.configure('Info.TLabel', background=bg_color, foreground=success_color, 
                       font=('Segoe UI', 9))
        style.configure('Status.TLabel', background=bg_color, foreground=accent_color, 
                       font=('Segoe UI', 9, 'bold'))
        style.configure('TLabelFrame', background=bg_color, foreground=accent_color, 
                       font=('Segoe UI', 9, 'bold'), borderwidth=2)
        style.configure('TLabelFrame.Label', background=bg_color, foreground=accent_color)
        style.configure('TFrame', background=bg_color)
        style.configure('TButton', font=('Segoe UI', 9), padding=8)
        style.map('TButton', background=[('active', accent_color)])
        
        # Стили для прогресс-баров
        style.configure('green.Horizontal.TProgressbar', 
                       background='#a6e3a1', troughcolor='#313244', borderwidth=0)
        style.configure('yellow.Horizontal.TProgressbar', 
                       background='#f9e2af', troughcolor='#313244', borderwidth=0)
        style.configure('red.Horizontal.TProgressbar', 
                       background='#f38ba8', troughcolor='#313244', borderwidth=0)
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок с градиентом
        header_frame = tk.Frame(main_frame, bg=bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = tk.Label(header_frame, 
                               text="🎮 Game Audio Stream Server", 
                               font=('Segoe UI', 18, 'bold'),
                               bg=bg_color, fg=accent_color)
        title_label.pack()
        
        subtitle_label = tk.Label(header_frame,
                                  text="Высокопроизводительный стриминг аудио",
                                  font=('Segoe UI', 9),
                                  bg=bg_color, fg=fg_color)
        subtitle_label.pack(pady=(5, 0))
        
        # Настройки качества/задержки
        quality_frame = ttk.LabelFrame(main_frame, text="⚙️ Настройки качества/задержки", padding="15")
        quality_frame.pack(fill=tk.X, pady=(0, 15))
        
        quality_inner = tk.Frame(quality_frame, bg='#313244')
        quality_inner.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(quality_inner, text="Профиль задержки:", 
                font=('Segoe UI', 9), bg='#313244', fg='#cdd6f4').grid(row=0, column=0, sticky=tk.W, padx=(10, 15), pady=10)
        self.latency_profile_var = tk.StringVar(value='Низкая')
        self.latency_combo = ttk.Combobox(quality_inner, textvariable=self.latency_profile_var,
                                     values=list(LATENCY_PROFILES.keys()), state="readonly", width=18)
        self.latency_combo.grid(row=0, column=1, padx=5, pady=10)
        self.latency_combo.bind('<<ComboboxSelected>>', self.on_latency_profile_change)
        
        # Информация о настройках
        settings_info = ttk.LabelFrame(main_frame, text="📊 Текущие настройки", padding="15")
        settings_info.pack(fill=tk.X, pady=(0, 15))
        
        self.settings_info_var = tk.StringVar()
        self.update_settings_info()
        settings_label = tk.Label(settings_info, textvariable=self.settings_info_var, 
                                  font=('Consolas', 9), bg='#313244', fg='#a6e3a1',
                                  justify=tk.LEFT, anchor='w', padx=10, pady=8)
        settings_label.pack(fill=tk.X)
        
        # Раздел системного звука
        system_frame = ttk.LabelFrame(main_frame, text="🎤 Захват системного звука", padding="15")
        system_frame.pack(fill=tk.X, pady=(0, 15))
        
        system_inner = tk.Frame(system_frame, bg='#313244')
        system_inner.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(system_inner, text="Устройство захвата:", 
                font=('Segoe UI', 9), bg='#313244', fg='#cdd6f4').grid(row=0, column=0, sticky=tk.W, padx=(10, 10), pady=10)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(system_inner, textvariable=self.device_var, 
                                        state="readonly", width=45)
        self.device_combo.grid(row=0, column=1, padx=5, sticky=tk.EW, pady=10)
        
        refresh_btn = ttk.Button(system_inner, text="🔄 Обновить", 
                               command=self.refresh_devices)
        refresh_btn.grid(row=0, column=2, padx=5, pady=10)
        
        system_inner.columnconfigure(1, weight=1)
        
        # Инструкция
        info_frame = tk.Frame(main_frame, bg='#45475a', relief=tk.FLAT)
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        info_text = """💡 Для захвата звука из игр:
  1. Используйте 'Stereo Mix' или 'Что слышно'
  2. Или установите VoiceMeeter
  3. Убедитесь, что в игре звук включен"""
        
        info_label = tk.Label(info_frame, text=info_text, 
                             font=('Segoe UI', 9), bg='#45475a', fg='#89b4fa',
                             justify=tk.LEFT, anchor='w', padx=15, pady=10)
        info_label.pack(fill=tk.X)
        
        # Настройки сети
        network_frame = ttk.LabelFrame(main_frame, text="🌐 Настройки сети", padding="15")
        network_frame.pack(fill=tk.X, pady=(0, 15))
        
        network_inner = tk.Frame(network_frame, bg='#313244')
        network_inner.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(network_inner, text="Multicast группа:", 
                font=('Segoe UI', 9), bg='#313244', fg='#cdd6f4').grid(row=0, column=0, sticky=tk.W, padx=(10, 10), pady=8)
        self.group_var = tk.StringVar(value=MULTICAST_GROUP)
        group_entry = ttk.Entry(network_inner, textvariable=self.group_var, width=18)
        group_entry.grid(row=0, column=1, padx=5, pady=8)
        
        tk.Label(network_inner, text="Порт:", 
                font=('Segoe UI', 9), bg='#313244', fg='#cdd6f4').grid(row=0, column=2, sticky=tk.W, padx=(20, 10), pady=8)
        self.port_var = tk.StringVar(value=str(PORT))
        port_entry = ttk.Entry(network_inner, textvariable=self.port_var, width=12)
        port_entry.grid(row=0, column=3, padx=5, pady=8)
        
        # Статус
        self.status_var = tk.StringVar(value="⏸ Готов к захвату игрового звука")
        status_frame = ttk.LabelFrame(main_frame, text="📡 Статус", padding="15")
        status_frame.pack(fill=tk.X, pady=(0, 15))
        
        status_inner = tk.Frame(status_frame, bg='#313244')
        status_inner.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_label = tk.Label(status_inner, textvariable=self.status_var, 
                                     font=('Segoe UI', 10, 'bold'), bg='#313244', fg='#89b4fa',
                                     anchor='w', padx=10, pady=8)
        self.status_label.pack(fill=tk.X)
        
        # Статистика
        self.stats_var = tk.StringVar(value="Пакетов отправлено: 0")
        stats_frame = ttk.LabelFrame(main_frame, text="📈 Статистика", padding="15")
        stats_frame.pack(fill=tk.X, pady=(0, 15))
        
        stats_inner = tk.Frame(stats_frame, bg='#313244')
        stats_inner.pack(fill=tk.X, padx=5, pady=5)
        
        self.stats_label = tk.Label(stats_inner, textvariable=self.stats_var,
                                   font=('Consolas', 10), bg='#313244', fg='#cdd6f4',
                                   anchor='w', padx=10, pady=8)
        self.stats_label.pack(fill=tk.X)
        
        # Индикатор уровня звука
        level_frame = ttk.LabelFrame(main_frame, text="🔊 Уровень звука", padding="15")
        level_frame.pack(fill=tk.X, pady=(0, 20))
        
        level_inner = tk.Frame(level_frame, bg='#313244')
        level_inner.pack(fill=tk.X, padx=5, pady=5)
        
        self.level_var = tk.StringVar(value="Уровень: 0%")
        level_text_label = tk.Label(level_inner, textvariable=self.level_var,
                                   font=('Segoe UI', 10, 'bold'), bg='#313244', fg='#a6e3a1',
                                   anchor='w', padx=10, pady=(5, 10))
        level_text_label.pack(fill=tk.X)
        
        # Прогресс-бар для уровня звука с цветовой индикацией
        progress_frame = tk.Frame(level_inner, bg='#313244')
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        self.level_progress = ttk.Progressbar(progress_frame, mode='determinate', maximum=100, length=500)
        self.level_progress.pack(fill=tk.X)
        
        # Цветовые индикаторы уровня
        level_indicators = tk.Frame(level_inner, bg='#313244')
        level_indicators.pack(fill=tk.X, padx=10, pady=(5, 0))
        
        tk.Label(level_indicators, text="Тихо", font=('Segoe UI', 7), bg='#313244', fg='#6c7086').pack(side=tk.LEFT)
        tk.Label(level_indicators, text="Норма", font=('Segoe UI', 7), bg='#313244', fg='#6c7086').pack(side=tk.LEFT, padx=150)
        tk.Label(level_indicators, text="Громко", font=('Segoe UI', 7), bg='#313244', fg='#6c7086').pack(side=tk.RIGHT)
        
        # Кнопки
        button_frame = tk.Frame(main_frame, bg='#1e1e2e')
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_btn = tk.Button(button_frame, text="▶️ Начать стрим", 
                                   command=self.start_stream,
                                   font=('Segoe UI', 11, 'bold'),
                                   bg='#a6e3a1', fg='#1e1e2e',
                                   activebackground='#94e2d5', activeforeground='#1e1e2e',
                                   relief=tk.FLAT, padx=20, pady=12,
                                   cursor='hand2')
        self.start_btn.pack(side=tk.LEFT, padx=(0, 15))
        
        self.stop_btn = tk.Button(button_frame, text="⏹️ Остановить", 
                                 command=self.stop_stream, state=tk.DISABLED,
                                 font=('Segoe UI', 11, 'bold'),
                                 bg='#f38ba8', fg='#1e1e2e',
                                 activebackground='#eba0ac', activeforeground='#1e1e2e',
                                 relief=tk.FLAT, padx=20, pady=12,
                                 cursor='hand2', disabledforeground='#6c7086')
        self.stop_btn.pack(side=tk.LEFT)
    
    def update_settings_info(self):
        """Обновить информацию о настройках"""
        info_text = f"""Частота: {self.sample_rate} Hz | Каналы: {CHANNELS} | Формат: {FORMAT} | Размер чанка: {self.chunk_size}
ВАЖНО: Эти настройки должны совпадать на клиенте!"""
        self.settings_info_var.set(info_text)
    
    def on_latency_profile_change(self, event=None):
        """Обработка изменения профиля задержки"""
        profile = self.latency_profile_var.get()
        if profile in LATENCY_PROFILES:
            config = LATENCY_PROFILES[profile]
            self.chunk_size = config['chunk']
            self.sample_rate = config['rate']
            self.update_settings_info()
    
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
            
            # Настройка сети с минимальными буферами и оптимизациями
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32768)  # Уменьшенный буфер отправки
            # Отключаем алгоритм Нейгла для UDP (не влияет, но для ясности)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)  # Отключаем loopback
            
            self.running = True
            self.packet_count = 0
            self.dropped_packets = 0
            self.start_time = time.time()
            self.last_audio_level = 0.0
            
            # Запуск потоков
            self.send_thread = threading.Thread(target=self.send_audio_data, daemon=True)
            self.send_thread.start()
            
            print(f"Starting audio capture: {self.sample_rate}Hz, {CHANNELS} channels, format: {FORMAT}, chunk: {self.chunk_size}")
            
            # Запуск аудио захвата с правильными параметрами
            # Используем меньший blocksize для минимальной задержки
            self.stream = sd.InputStream(
                device=device_index,
                channels=CHANNELS,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,  # Настраиваемый размер для баланса задержки/качества
                callback=self.audio_callback,
                dtype=FORMAT,  # Используем int16 напрямую
                latency='low'  # Минимальная задержка устройства
            )
            self.stream.start()
            
            self.status_var.set("▶️ Стриминг игрового звука активен")
            self.status_label.config(fg='#a6e3a1')  # Зеленый цвет для активного статуса
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.latency_combo.config(state=tk.DISABLED)  # Блокируем изменение во время работы
            
            # Статистика
            self.stats_thread = threading.Thread(target=self.update_stats, daemon=True)
            self.stats_thread.start()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка запуска: {e}")
    
    def audio_callback(self, indata, frames, time, status):
        """Callback для захвата аудио - оптимизирован для минимальной задержки"""
        if self.running:
            # Вычисляем уровень звука для индикатора (до конвертации)
            self.last_audio_level = float(np.abs(indata).max()) / 32768.0
            
            # Используем tobytes() напрямую (indata уже numpy array)
            audio_data = indata.tobytes()
            
            try:
                # Неблокирующая запись в очередь
                self.audio_queue.put_nowait(audio_data)
            except queue.Full:
                # Умная обработка переполнения: удаляем старый пакет и добавляем новый
                try:
                    self.audio_queue.get_nowait()  # Удаляем старый
                    self.audio_queue.put_nowait(audio_data)  # Добавляем новый
                    if hasattr(self, 'dropped_packets'):
                        self.dropped_packets += 1
                except queue.Empty:
                    pass
    
    def send_audio_data(self):
        """Отправка аудио данных - оптимизировано"""
        multicast_addr = (self.group_var.get(), int(self.port_var.get()))
        
        while self.running:
            try:
                audio_data = self.audio_queue.get(timeout=0.01)  # Уменьшенный таймаут
                # Используем sendto без проверок для максимальной скорости
                self.sock.sendto(audio_data, multicast_addr)
                self.packet_count += 1
            except queue.Empty:
                continue
            except Exception as e:
                if self.running:
                    print(f"Send error: {e}")
    
    def update_stats(self):
        """Обновление статистики с индикатором уровня"""
        while self.running:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                speed = self.packet_count / elapsed
                drop_rate = (self.dropped_packets / (self.packet_count + self.dropped_packets) * 100) if (self.packet_count + self.dropped_packets) > 0 else 0
                stats_text = f"Пакетов отправлено: {self.packet_count} ({speed:.1f}/сек)"
                if self.dropped_packets > 0:
                    stats_text += f" | Пропущено: {self.dropped_packets} ({drop_rate:.1f}%)"
                self.stats_var.set(stats_text)
                
                # Обновляем индикатор уровня звука с цветовой индикацией
                level_percent = int(self.last_audio_level * 100)
                self.level_var.set(f"Уровень: {level_percent}%")
                self.level_progress['value'] = level_percent
                
                # Цветовая индикация уровня звука
                if level_percent < 30:
                    self.level_progress['style'] = 'green.Horizontal.TProgressbar'
                elif level_percent < 70:
                    self.level_progress['style'] = 'yellow.Horizontal.TProgressbar'
                else:
                    self.level_progress['style'] = 'red.Horizontal.TProgressbar'
                
            time.sleep(0.1)  # Более частое обновление для плавности
    
    def stop_stream(self):
        """Остановка стриминга"""
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if hasattr(self, 'sock'):
            self.sock.close()
        
        self.status_var.set("⏸ Стриминг остановлен")
        self.status_label.config(fg='#89b4fa')  # Синий цвет для остановленного статуса
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.latency_combo.config(state=tk.NORMAL)  # Разблокируем после остановки

if __name__ == "__main__":
    root = tk.Tk()
    app = GameAudioStreamServer(root)
    root.mainloop()