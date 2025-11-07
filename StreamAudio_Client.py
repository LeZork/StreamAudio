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
CHUNK = 1024
RATE = 44100
CHANNELS = 2
FORMAT = 'int16'
MULTICAST_GROUP = '224.1.1.1'
PORT = 5007

class MulticastAudioReceiverGUI:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.stream = None
        self.audio_queue = queue.Queue()
        self.setup_gui()
        self.refresh_devices()
        
    def setup_gui(self):
        """Настройка графического интерфейса"""
        self.root.title("Audio Stream Client - FIXED")
        self.root.geometry("500x550")
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        title_label = ttk.Label(main_frame, text="Аудио Клиент (ИСПРАВЛЕННЫЙ)", 
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Информация о настройках
        settings_info = ttk.LabelFrame(main_frame, text="Текущие настройки", padding="10")
        settings_info.pack(fill=tk.X, pady=(0, 10))
        
        info_text = f"""Частота: {RATE} Hz | Каналы: {CHANNELS} | Формат: {FORMAT} | Размер чанка: {CHUNK}
Должны совпадать с сервером!"""
        ttk.Label(settings_info, text=info_text, foreground="green").pack()
        
        # Выбор устройства
        device_frame = ttk.LabelFrame(main_frame, text="Выбор устройства вывода", padding="10")
        device_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(device_frame, text="Динамики:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(device_frame, textvariable=self.device_var, 
                                        state="readonly", width=50)
        self.device_combo.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10))
        
        refresh_btn = ttk.Button(device_frame, text="Обновить", command=self.refresh_devices)
        refresh_btn.grid(row=0, column=2)
        
        device_frame.columnconfigure(1, weight=1)
        
        # Информация об устройстве
        self.device_info_var = tk.StringVar(value="")
        device_info_label = ttk.Label(main_frame, textvariable=self.device_info_var, foreground="gray")
        device_info_label.pack(pady=(0, 10))
        
        # Настройки подключения
        settings_frame = ttk.LabelFrame(main_frame, text="Настройки подключения", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(settings_frame, text="Группа:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.group_var = tk.StringVar(value=MULTICAST_GROUP)
        group_entry = ttk.Entry(settings_frame, textvariable=self.group_var, width=15)
        group_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        ttk.Label(settings_frame, text="Порт:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.port_var = tk.StringVar(value=str(PORT))
        port_entry = ttk.Entry(settings_frame, textvariable=self.port_var, width=10)
        port_entry.grid(row=0, column=3, sticky=tk.W)
        
        # Статус
        status_frame = ttk.LabelFrame(main_frame, text="Статус", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_var = tk.StringVar(value="Готов к подключению")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="blue")
        status_label.pack(anchor=tk.W)
        
        # Статистика
        stats_frame = ttk.LabelFrame(main_frame, text="Статистика", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.stats_var = tk.StringVar(value="Пакетов получено: 0\nПотерь: 0%\nСкорость: 0 пакетов/сек")
        stats_label = ttk.Label(stats_frame, textvariable=self.stats_var, justify=tk.LEFT)
        stats_label.pack(anchor=tk.W)
        
        # Кнопки управления
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(button_frame, text="Начать прослушивание", 
                                   command=self.start_receive,
                                   state=tk.NORMAL if SOUNDDEVICE_AVAILABLE else tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(button_frame, text="Остановить", 
                                  command=self.stop_receive, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        
        # Инициализация переменных для статистики
        self.packet_count = 0
        self.lost_packets = 0
        self.start_time = 0
        
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
    
        # Увеличиваем буфер и уменьшаем таймаут
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 131072)  # Увеличили буфер
        self.sock.settimeout(0.1)  # Уменьшили таймаут
    
    def audio_output_callback(self, outdata, frames, time, status):
        """Callback для вывода аудио"""
        if self.running:
            try:
                # Получаем данные из очереди с таймаутом
                audio_data = self.audio_queue.get_nowait()
            
                # Конвертируем байты напрямую в numpy array (int16)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
                # Решейпим для стерео вывода
                if len(audio_array) >= frames * CHANNELS:
                    audio_array = audio_array[:frames * CHANNELS].reshape(-1, CHANNELS)
                    outdata[:] = audio_array
                else:
                    # Если данных недостаточно, заполняем нулями
                    outdata.fill(0)
                
            except queue.Empty:
                outdata.fill(0)
            except Exception as e:
                print(f"Audio output error: {e}")
                outdata.fill(0)
    
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
            
            # Запускаем поток для приема данных
            self.receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
            
            print(f"Starting output: {RATE}Hz, {CHANNELS} channels, format: {FORMAT}")
            
            # Запускаем аудио вывод
            self.stream = sd.OutputStream(
                device=device_index,
                channels=CHANNELS,
                samplerate=RATE,
                blocksize=CHUNK,
                callback=self.audio_output_callback,
                dtype=FORMAT  # Используем int16 напрямую
            )
            self.stream.start()
            
            # Обновляем интерфейс
            self.status_var.set(f"Прослушивание {self.group_var.get()}:{self.port_var.get()}")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.device_combo.config(state=tk.DISABLED)
            
            # Запускаем поток для статистики
            self.stats_thread = threading.Thread(target=self.update_stats, daemon=True)
            self.stats_thread.start()
            
        except Exception as e:
            error_msg = f"Не удалось начать прослушивание: {e}"
            messagebox.showerror("Ошибка", error_msg)
            self.stop_receive()
    
    def receive_loop(self):
        """Главный цикл приема данных"""
        expected_size = CHUNK * CHANNELS * 2  # 16-bit = 2 bytes per sample
        
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
                self.packet_count += 1
                
                # Проверяем размер данных
                if len(data) >= expected_size:
                    self.audio_queue.put(data)
                else:
                    self.lost_packets += 1
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                    self.lost_packets += 1
    
    def update_stats(self):
        """Обновление статистики в GUI"""
        while self.running:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                packets_per_sec = self.packet_count / elapsed
                total_packets = self.packet_count + self.lost_packets
                loss_rate = (self.lost_packets / total_packets) * 100 if total_packets > 0 else 0
                
                stats_text = f"Пакетов получено: {self.packet_count}\nПотерь: {loss_rate:.1f}%\nСкорость: {packets_per_sec:.1f} пакетов/сек"
                self.stats_var.set(stats_text)
            time.sleep(2)
    
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
        self.status_var.set("Прослушивание остановлено")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.device_combo.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = MulticastAudioReceiverGUI(root)
    root.mainloop()