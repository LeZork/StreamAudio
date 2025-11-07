import socket
import struct
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

# КОНСИСТЕНТНЫЕ НАСТРОЙКИ - ДОЛЖНЫ СОВПАДАТЬ С СЕРВЕРОМ
# Можно настроить через GUI
DEFAULT_CHUNK = 256  # Уменьшено для минимальной задержки
DEFAULT_RATE = 44100
CHANNELS = 2
FORMAT = 'int16'
MULTICAST_GROUP = '224.1.1.1'
PORT = 5007

# Профили задержки (должны совпадать с сервером)
LATENCY_PROFILES = {
    'Минимальная': {'chunk': 128, 'rate': 44100},
    'Низкая': {'chunk': 256, 'rate': 44100},
    'Средняя': {'chunk': 512, 'rate': 44100},
    'Высокая': {'chunk': 1024, 'rate': 44100}
}

class MulticastAudioReceiverGUI:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.stream = None
        self.audio_queue = queue.Queue(maxsize=2)  # Ограничиваем очередь для минимальной задержки
        self.last_packet_time = 0
        self.last_audio_level = 0.0
        self.chunk_size = DEFAULT_CHUNK
        self.sample_rate = DEFAULT_RATE
        self.expected_packet_interval = self.chunk_size / self.sample_rate  # Ожидаемый интервал между пакетами
        self.setup_gui()
        self.refresh_devices()
        
    def setup_gui(self):
        """Настройка графического интерфейса"""
        self.root.title("🎧 Audio Stream Client")
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
        
        # Заголовок
        header_frame = tk.Frame(main_frame, bg=bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = tk.Label(header_frame, 
                               text="🎧 Audio Stream Client", 
                               font=('Segoe UI', 18, 'bold'),
                               bg=bg_color, fg=accent_color)
        title_label.pack()
        
        subtitle_label = tk.Label(header_frame,
                                  text="Прием и воспроизведение аудио потока",
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
        
        # Выбор устройства
        device_frame = ttk.LabelFrame(main_frame, text="🔊 Выбор устройства вывода", padding="15")
        device_frame.pack(fill=tk.X, pady=(0, 15))
        
        device_inner = tk.Frame(device_frame, bg='#313244')
        device_inner.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(device_inner, text="Динамики:", 
                font=('Segoe UI', 9), bg='#313244', fg='#cdd6f4').grid(row=0, column=0, sticky=tk.W, padx=(10, 10), pady=10)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(device_inner, textvariable=self.device_var, 
                                        state="readonly", width=45)
        self.device_combo.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=10)
        
        refresh_btn = ttk.Button(device_inner, text="🔄 Обновить", command=self.refresh_devices)
        refresh_btn.grid(row=0, column=2, padx=5, pady=10)
        
        device_inner.columnconfigure(1, weight=1)
        
        # Информация об устройстве
        self.device_info_var = tk.StringVar(value="")
        device_info_label = tk.Label(main_frame, textvariable=self.device_info_var, 
                                     font=('Segoe UI', 8), bg=bg_color, fg='#6c7086')
        device_info_label.pack(pady=(0, 15))
        
        # Настройки подключения
        settings_frame = ttk.LabelFrame(main_frame, text="🌐 Настройки подключения", padding="15")
        settings_frame.pack(fill=tk.X, pady=(0, 15))
        
        settings_inner = tk.Frame(settings_frame, bg='#313244')
        settings_inner.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(settings_inner, text="Группа:", 
                font=('Segoe UI', 9), bg='#313244', fg='#cdd6f4').grid(row=0, column=0, sticky=tk.W, padx=(10, 10), pady=8)
        self.group_var = tk.StringVar(value=MULTICAST_GROUP)
        group_entry = ttk.Entry(settings_inner, textvariable=self.group_var, width=18)
        group_entry.grid(row=0, column=1, padx=5, pady=8)
        
        tk.Label(settings_inner, text="Порт:", 
                font=('Segoe UI', 9), bg='#313244', fg='#cdd6f4').grid(row=0, column=2, sticky=tk.W, padx=(20, 10), pady=8)
        self.port_var = tk.StringVar(value=str(PORT))
        port_entry = ttk.Entry(settings_inner, textvariable=self.port_var, width=12)
        port_entry.grid(row=0, column=3, padx=5, pady=8)
        
        # Статус
        self.status_var = tk.StringVar(value="⏸ Готов к подключению")
        status_frame = ttk.LabelFrame(main_frame, text="📡 Статус", padding="15")
        status_frame.pack(fill=tk.X, pady=(0, 15))
        
        status_inner = tk.Frame(status_frame, bg='#313244')
        status_inner.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_label = tk.Label(status_inner, textvariable=self.status_var, 
                                     font=('Segoe UI', 10, 'bold'), bg='#313244', fg='#89b4fa',
                                     anchor='w', padx=10, pady=8)
        self.status_label.pack(fill=tk.X)
        
        # Статистика
        stats_frame = ttk.LabelFrame(main_frame, text="📈 Статистика", padding="15")
        stats_frame.pack(fill=tk.X, pady=(0, 15))
        
        stats_inner = tk.Frame(stats_frame, bg='#313244')
        stats_inner.pack(fill=tk.X, padx=5, pady=5)
        
        self.stats_var = tk.StringVar(value="Пакетов получено: 0\nПотерь: 0%\nСкорость: 0 пакетов/сек\nЗадержка: ~0 мс")
        self.stats_label = tk.Label(stats_inner, textvariable=self.stats_var,
                                   font=('Consolas', 10), bg='#313244', fg='#cdd6f4',
                                   justify=tk.LEFT, anchor='w', padx=10, pady=8)
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
        
        # Кнопки управления
        button_frame = tk.Frame(main_frame, bg='#1e1e2e')
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_btn = tk.Button(button_frame, text="▶️ Начать прослушивание", 
                                   command=self.start_receive,
                                   font=('Segoe UI', 11, 'bold'),
                                   bg='#a6e3a1', fg='#1e1e2e',
                                   activebackground='#94e2d5', activeforeground='#1e1e2e',
                                   relief=tk.FLAT, padx=20, pady=12,
                                   cursor='hand2',
                                   state=tk.NORMAL if SOUNDDEVICE_AVAILABLE else tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 15))
        
        self.stop_btn = tk.Button(button_frame, text="⏹️ Остановить", 
                                  command=self.stop_receive, state=tk.DISABLED,
                                  font=('Segoe UI', 11, 'bold'),
                                  bg='#f38ba8', fg='#1e1e2e',
                                  activebackground='#eba0ac', activeforeground='#1e1e2e',
                                  relief=tk.FLAT, padx=20, pady=12,
                                  cursor='hand2', disabledforeground='#6c7086')
        self.stop_btn.pack(side=tk.LEFT)
        
        # Инициализация переменных для статистики
        self.packet_count = 0
        self.lost_packets = 0
        self.start_time = 0
        self.last_packet_time = 0
        self.estimated_latency = 0.0
        
    def update_settings_info(self):
        """Обновить информацию о настройках"""
        info_text = f"""Частота: {self.sample_rate} Hz | Каналы: {CHANNELS} | Формат: {FORMAT} | Размер чанка: {self.chunk_size}
Должны совпадать с сервером!"""
        self.settings_info_var.set(info_text)
    
    def on_latency_profile_change(self, event=None):
        """Обработка изменения профиля задержки"""
        profile = self.latency_profile_var.get()
        if profile in LATENCY_PROFILES:
            config = LATENCY_PROFILES[profile]
            self.chunk_size = config['chunk']
            self.sample_rate = config['rate']
            self.expected_packet_interval = self.chunk_size / self.sample_rate
            self.update_settings_info()
    
    def refresh_devices(self):
        """Обновить список устройств вывода"""
        if not SOUNDDEVICE_AVAILABLE:
            return
            
        devices = []
        self.device_info = {}
        
        try:
            hostapi_info = sd.query_hostapis()
            device_list = sd.query_devices()
            
            for i, device in enumerate(device_list):
                if device['max_output_channels'] > 0:
                    hostapi_name = hostapi_info[device['hostapi']]['name']
                    device_name = f"{i}: {device['name']} ({hostapi_name})"
                    devices.append(device_name)
                    self.device_info[device_name] = {
                        'index': i,
                        'device': device
                    }
            
            self.device_combo['values'] = devices
            if devices and not self.device_var.get():
                self.device_combo.set(devices[0])
                if devices[0] in self.device_info:
                    self.show_device_info(self.device_info[devices[0]]['device'])
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить список устройств: {e}")
    
    def show_device_info(self, device):
        """Показать информацию об устройстве"""
        info_text = f"Частота: {int(device['default_samplerate'])} Hz, "
        info_text += f"Каналы: {device['max_output_channels']}"
        self.device_info_var.set(info_text)
    
    def setup_network(self):
        """Настройка multicast приемника"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
        port = int(self.port_var.get())
        self.sock.bind(('', port))
    
        multicast_group = self.group_var.get()
        group = socket.inet_aton(multicast_group)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
        # Минимизируем буфер и таймаут для низкой задержки
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32768)  # Уменьшенный буфер
        self.sock.settimeout(0.01)  # Минимальный таймаут для быстрой реакции
        # Отключаем loopback для multicast
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)
    
    def audio_output_callback(self, outdata, frames, time, status):
        """Callback для вывода аудио - оптимизирован"""
        if self.running:
            try:
                # Получаем данные из очереди с таймаутом
                audio_data = self.audio_queue.get_nowait()
            
                # Используем memoryview для избежания копирования
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
                # Решейпим для стерео вывода
                if len(audio_array) >= frames * CHANNELS:
                    audio_array = audio_array[:frames * CHANNELS].reshape(-1, CHANNELS)
                    outdata[:] = audio_array
                    
                    # Вычисляем уровень звука для индикатора
                    self.last_audio_level = float(np.abs(audio_array).max()) / 32768.0
                else:
                    # Если данных недостаточно, заполняем нулями
                    outdata.fill(0)
                    self.last_audio_level = 0.0
                
            except queue.Empty:
                outdata.fill(0)
                self.last_audio_level = 0.0
            except Exception as e:
                print(f"Audio output error: {e}")
                outdata.fill(0)
                self.last_audio_level = 0.0
    
    def start_receive(self):
        """Начать прием аудио"""
        if not SOUNDDEVICE_AVAILABLE:
            messagebox.showerror("Ошибка", "SoundDevice не доступен")
            return
            
        try:
            selected_device = self.device_var.get()
            if not selected_device:
                messagebox.showerror("Ошибка", "Выберите устройство вывода")
                return
            
            device_info = self.device_info[selected_device]
            device_index = device_info['index']
            
            # Настраиваем сеть
            self.setup_network()
            
            # Запускаем аудио вывод
            self.running = True
            self.packet_count = 0
            self.lost_packets = 0
            self.start_time = time.time()
            self.last_packet_time = time.time()
            self.estimated_latency = 0.0
            self.last_audio_level = 0.0
            
            # Запускаем поток для приема данных
            self.receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
            
            print(f"Starting output: {self.sample_rate}Hz, {CHANNELS} channels, format: {FORMAT}, chunk: {self.chunk_size}")
            
            # Запускаем аудио вывод
            self.stream = sd.OutputStream(
                device=device_index,
                channels=CHANNELS,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,  # Настраиваемый размер для баланса задержки/качества
                callback=self.audio_output_callback,
                dtype=FORMAT,  # Используем int16 напрямую
                latency='low'  # Минимальная задержка устройства
            )
            self.stream.start()
            
            # Обновляем интерфейс
            self.status_var.set("▶️ Прослушивание активно")
            self.status_label.config(fg='#a6e3a1')  # Зеленый цвет для активного статуса
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.device_combo.config(state=tk.DISABLED)
            self.latency_combo.config(state=tk.DISABLED)  # Блокируем изменение во время работы
            
            # Запускаем поток для статистики
            self.stats_thread = threading.Thread(target=self.update_stats, daemon=True)
            self.stats_thread.start()
            
        except Exception as e:
            error_msg = f"Не удалось начать прослушивание: {e}"
            messagebox.showerror("Ошибка", error_msg)
            self.stop_receive()
    
    def receive_loop(self):
        """Главный цикл приема данных - оптимизирован"""
        expected_size = self.chunk_size * CHANNELS * 2  # 16-bit = 2 bytes per sample
        
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
                current_time = time.time()
                
                # Проверяем размер данных
                if len(data) >= expected_size:
                    # Умная обработка переполнения очереди
                    try:
                        self.audio_queue.put_nowait(data)
                        self.packet_count += 1
                        
                        # Оцениваем задержку на основе интервала между пакетами
                        if self.last_packet_time > 0:
                            interval = current_time - self.last_packet_time
                            # Задержка = разница между ожидаемым и реальным интервалом
                            delay_diff = interval - self.expected_packet_interval
                            if delay_diff > 0:
                                self.estimated_latency = delay_diff * 1000  # в миллисекундах
                        
                        self.last_packet_time = current_time
                    except queue.Full:
                        # Удаляем старый пакет и добавляем новый
                        try:
                            self.audio_queue.get_nowait()
                            self.audio_queue.put_nowait(data)
                            self.packet_count += 1
                            self.lost_packets += 1  # Считаем как потерю старого пакета
                            self.last_packet_time = current_time
                        except queue.Empty:
                            pass
                else:
                    self.lost_packets += 1
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                    self.lost_packets += 1
    
    def update_stats(self):
        """Обновление статистики в GUI с задержкой и уровнем"""
        while self.running:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                packets_per_sec = self.packet_count / elapsed
                total_packets = self.packet_count + self.lost_packets
                loss_rate = (self.lost_packets / total_packets) * 100 if total_packets > 0 else 0
                
                # Оценка общей задержки (сетевая + буфер)
                buffer_delay = (self.audio_queue.qsize() * self.expected_packet_interval * 1000) if not self.audio_queue.empty() else 0
                total_delay = self.estimated_latency + buffer_delay
                
                # Форматирование статистики с цветовыми индикаторами
                delay_status = "🟢" if total_delay < 50 else "🟡" if total_delay < 100 else "🔴"
                loss_status = "🟢" if loss_rate < 5 else "🟡" if loss_rate < 15 else "🔴"
                
                stats_text = f"Пакетов получено: {self.packet_count}\nПотери: {loss_status} {loss_rate:.1f}%\nСкорость: {packets_per_sec:.1f} пакетов/сек\nЗадержка: {delay_status} ~{total_delay:.1f} мс"
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
    
    def stop_receive(self):
        """Остановить прием"""
        self.running = False
        
        if hasattr(self, 'stream') and self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None
        
        if hasattr(self, 'sock'):
            try:
                self.sock.close()
            except:
                pass
        
        # Очищаем очередь
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # Обновляем интерфейс
        self.status_var.set("⏸ Прослушивание остановлено")
        self.status_label.config(fg='#89b4fa')  # Синий цвет для остановленного статуса
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.device_combo.config(state=tk.NORMAL)
        self.latency_combo.config(state=tk.NORMAL)  # Разблокируем после остановки

if __name__ == "__main__":
    root = tk.Tk()
    app = MulticastAudioReceiverGUI(root)
    root.mainloop()