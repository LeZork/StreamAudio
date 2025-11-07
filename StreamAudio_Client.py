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
        
    def setup_gui(self):
        """Настройка графического интерфейса"""
        # Цветовая схема (определяем сначала)
        bg_color = '#1e1e2e'
        fg_color = '#cdd6f4'
        accent_color = '#89b4fa'
        success_color = '#a6e3a1'
        warning_color = '#f9e2af'
        error_color = '#f38ba8'
        
        self.root.title("🎧 Audio Stream Client")
        self.root.geometry("700x600")
        self.root.minsize(650, 550)
        self.root.configure(bg=bg_color)
        
        # Настройка стилей
        style = ttk.Style()
        style.theme_use('clam')
        
        # Настройка стилей (компактные)
        style.configure('Title.TLabel', background=bg_color, foreground=accent_color, 
                       font=('Segoe UI', 14, 'bold'))
        style.configure('Header.TLabel', background=bg_color, foreground=fg_color, 
                       font=('Segoe UI', 9, 'bold'))
        style.configure('Info.TLabel', background=bg_color, foreground=success_color, 
                       font=('Segoe UI', 8))
        style.configure('Status.TLabel', background=bg_color, foreground=accent_color, 
                       font=('Segoe UI', 8, 'bold'))
        style.configure('TLabelFrame', background=bg_color, foreground=accent_color, 
                       font=('Segoe UI', 8, 'bold'), borderwidth=1)
        style.configure('TLabelFrame.Label', background=bg_color, foreground=accent_color)
        style.configure('TFrame', background=bg_color)
        style.configure('TButton', font=('Segoe UI', 8), padding=4)
        style.map('TButton', background=[('active', accent_color)])
        
        # Стили для прогресс-баров
        style.configure('green.Horizontal.TProgressbar', 
                       background='#a6e3a1', troughcolor='#313244', borderwidth=0)
        style.configure('yellow.Horizontal.TProgressbar', 
                       background='#f9e2af', troughcolor='#313244', borderwidth=0)
        style.configure('red.Horizontal.TProgressbar', 
                       background='#f38ba8', troughcolor='#313244', borderwidth=0)
        
        # Основной фрейм без прокрутки
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок компактный
        header_frame = tk.Frame(main_frame, bg=bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 8))
        
        title_label = tk.Label(header_frame, 
                               text="🎧 Audio Stream Client", 
                               font=('Segoe UI', 14, 'bold'),
                               bg=bg_color, fg=accent_color)
        title_label.pack(side=tk.LEFT)
        
        # Компактная панель настроек в одну строку
        settings_row = tk.Frame(main_frame, bg=bg_color)
        settings_row.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(settings_row, text="Профиль:", 
                font=('Segoe UI', 8), bg=bg_color, fg=fg_color).pack(side=tk.LEFT, padx=(0, 5))
        self.latency_profile_var = tk.StringVar(value='Низкая')
        self.latency_combo = ttk.Combobox(settings_row, textvariable=self.latency_profile_var,
                                     values=list(LATENCY_PROFILES.keys()), state="readonly", width=12)
        self.latency_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.latency_combo.bind('<<ComboboxSelected>>', self.on_latency_profile_change)
        
        self.settings_info_var = tk.StringVar()
        self.update_settings_info()
        settings_label = tk.Label(settings_row, textvariable=self.settings_info_var, 
                                  font=('Consolas', 7), bg=bg_color, fg='#a6e3a1')
        settings_label.pack(side=tk.LEFT)
        
        # Компактная панель устройств и сети
        device_network_frame = ttk.LabelFrame(main_frame, text="🔊 Устройство и сеть", padding="8")
        device_network_frame.pack(fill=tk.X, pady=(0, 8))
        
        device_network_inner = tk.Frame(device_network_frame, bg='#313244')
        device_network_inner.pack(fill=tk.X, padx=3, pady=3)
        
        # Устройство вывода
        tk.Label(device_network_inner, text="Динамики:", 
                font=('Segoe UI', 8), bg='#313244', fg='#cdd6f4').grid(row=0, column=0, sticky=tk.W, padx=(5, 5), pady=5)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(device_network_inner, textvariable=self.device_var, 
                                        state="readonly", width=30)
        self.device_combo.grid(row=0, column=1, padx=5, sticky=tk.EW, pady=5)
        
        refresh_btn = ttk.Button(device_network_inner, text="🔄", 
                               command=self.refresh_devices, width=3)
        refresh_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Сеть
        tk.Label(device_network_inner, text="Группа:", 
                font=('Segoe UI', 8), bg='#313244', fg='#cdd6f4').grid(row=0, column=3, sticky=tk.W, padx=(15, 5), pady=5)
        self.group_var = tk.StringVar(value=MULTICAST_GROUP)
        group_entry = ttk.Entry(device_network_inner, textvariable=self.group_var, width=12)
        group_entry.grid(row=0, column=4, padx=2, pady=5)
        
        tk.Label(device_network_inner, text="Порт:", 
                font=('Segoe UI', 8), bg='#313244', fg='#cdd6f4').grid(row=0, column=5, sticky=tk.W, padx=(8, 5), pady=5)
        self.port_var = tk.StringVar(value=str(PORT))
        port_entry = ttk.Entry(device_network_inner, textvariable=self.port_var, width=8)
        port_entry.grid(row=0, column=6, padx=2, pady=5)
        
        device_network_inner.columnconfigure(1, weight=1)
        
        # Компактная панель статуса и статистики в одну строку
        status_stats_frame = ttk.LabelFrame(main_frame, text="📡 Статус и статистика", padding="8")
        status_stats_frame.pack(fill=tk.X, pady=(0, 8))
        
        status_stats_inner = tk.Frame(status_stats_frame, bg='#313244')
        status_stats_inner.pack(fill=tk.X, padx=3, pady=3)
        
        self.status_var = tk.StringVar(value="⏸ Готов")
        self.status_label = tk.Label(status_stats_inner, textvariable=self.status_var, 
                                     font=('Segoe UI', 8, 'bold'), bg='#313244', fg='#89b4fa',
                                     anchor='w', padx=5, width=15)
        self.status_label.grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        
        self.stats_var = tk.StringVar(value="Пакетов: 0 | Потери: 0% | Задержка: 0мс")
        self.stats_label = tk.Label(status_stats_inner, textvariable=self.stats_var,
                                   font=('Consolas', 8), bg='#313244', fg='#cdd6f4',
                                   anchor='w', padx=5)
        self.stats_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=3)
        
        # Компактный индикатор уровня звука
        level_frame = ttk.LabelFrame(main_frame, text="🔊 Уровень звука", padding="8")
        level_frame.pack(fill=tk.X, pady=(0, 8))
        
        level_inner = tk.Frame(level_frame, bg='#313244')
        level_inner.pack(fill=tk.X, padx=3, pady=3)
        
        self.level_var = tk.StringVar(value="0%")
        level_text_label = tk.Label(level_inner, textvariable=self.level_var,
                                   font=('Segoe UI', 9, 'bold'), bg='#313244', fg='#a6e3a1',
                                   anchor='w', padx=5, width=5)
        level_text_label.pack(side=tk.LEFT, padx=5)
        
        self.level_progress = ttk.Progressbar(level_inner, mode='determinate', maximum=100, length=400)
        self.level_progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Кнопки управления - компактные
        button_frame = tk.Frame(main_frame, bg='#1e1e2e')
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        button_container = tk.Frame(button_frame, bg='#1e1e2e')
        button_container.pack(expand=True)
        
        self.start_btn = tk.Button(button_container, text="▶️ Начать прослушивание", 
                                   command=self.start_receive,
                                   font=('Segoe UI', 10, 'bold'),
                                   bg='#a6e3a1', fg='#1e1e2e',
                                   activebackground='#94e2d5', activeforeground='#1e1e2e',
                                   relief=tk.FLAT, padx=20, pady=10,
                                   cursor='hand2', width=23,
                                   state=tk.NORMAL if SOUNDDEVICE_AVAILABLE else tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = tk.Button(button_container, text="⏹️ Остановить", 
                                  command=self.stop_receive, state=tk.DISABLED,
                                  font=('Segoe UI', 10, 'bold'),
                                  bg='#f38ba8', fg='#1e1e2e',
                                  activebackground='#eba0ac', activeforeground='#1e1e2e',
                                  relief=tk.FLAT, padx=20, pady=10,
                                  cursor='hand2', disabledforeground='#6c7086', width=18)
        self.stop_btn.pack(side=tk.LEFT)
        
        # Инициализация переменных для статистики
        self.packet_count = 0
        self.lost_packets = 0
        self.start_time = 0
        self.last_packet_time = 0
        self.estimated_latency = 0.0
        
    def update_settings_info(self):
        """Обновить информацию о настройках"""
        info_text = f"{self.sample_rate}Hz | {CHANNELS}ch | {FORMAT} | chunk:{self.chunk_size}"
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
                
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить список устройств: {e}")
    
    def setup_network(self):
        """Настройка multicast приемника"""
        try:
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
            self.sock.settimeout(0.1)  # Увеличенный таймаут для отладки
            # Включаем loopback для multicast (чтобы работало на одном компьютере)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            
            print(f"[DEBUG] Multicast настроен: группа={multicast_group}, порт={port}")
            print(f"[DEBUG] Сокет привязан к порту {port}")
        except Exception as e:
            print(f"[ERROR] Ошибка настройки сети: {e}")
            raise
    
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
            self.status_var.set("▶️ Активен")
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
        print(f"[DEBUG] Ожидаемый размер пакета: {expected_size} байт (chunk={self.chunk_size}, channels={CHANNELS})")
        
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
                current_time = time.time()
                
                # Отладочная информация для первых пакетов
                if self.packet_count < 5:
                    print(f"[DEBUG] Получен пакет #{self.packet_count + 1}: размер={len(data)} байт, от {addr}")
                
                # Проверяем размер данных (более гибкая проверка - допускаем небольшие отклонения)
                if len(data) >= expected_size * 0.9:  # Допускаем 10% отклонение
                    # Обрезаем до нужного размера если больше
                    if len(data) > expected_size:
                        data = data[:expected_size]
                    
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
                    if self.lost_packets < 5:  # Выводим только первые несколько ошибок
                        print(f"[WARNING] Пакет отклонен: размер {len(data)} байт, ожидается ~{expected_size} байт")
                    self.lost_packets += 1
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[ERROR] Receive error: {e}")
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
                
                # Форматирование статистики с цветовыми индикаторами (компактное)
                delay_status = "🟢" if total_delay < 50 else "🟡" if total_delay < 100 else "🔴"
                loss_status = "🟢" if loss_rate < 5 else "🟡" if loss_rate < 15 else "🔴"
                
                stats_text = f"Пакетов: {self.packet_count} | Потери: {loss_status} {loss_rate:.1f}% | Задержка: {delay_status} {total_delay:.0f}мс"
                self.stats_var.set(stats_text)
                
                # Обновляем индикатор уровня звука с цветовой индикацией
                level_percent = int(self.last_audio_level * 100)
                self.level_var.set(f"{level_percent}%")
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
        self.status_var.set("⏸ Готов")
        self.status_label.config(fg='#89b4fa')  # Синий цвет для остановленного статуса
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.device_combo.config(state=tk.NORMAL)
        self.latency_combo.config(state=tk.NORMAL)  # Разблокируем после остановки

if __name__ == "__main__":
    root = tk.Tk()
    app = MulticastAudioReceiverGUI(root)
    root.mainloop()