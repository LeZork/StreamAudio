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

# Конфигурация
CHUNK = 256
RATE = 44100
CHANNELS = 1
MULTICAST_GROUP = '224.1.1.1'
PORT = 5007

class MulticastAudioSenderGUI:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.stream = None
        self.audio_queue = queue.Queue()
        self.setup_gui()
        self.refresh_devices()
        
        if not SOUNDDEVICE_AVAILABLE:
            messagebox.showerror("Ошибка", 
                               "SoundDevice не установлен. Установите: pip install sounddevice")
        
    def setup_gui(self):
        """Настройка графического интерфейса"""
        self.root.title("Audio Stream Server (SoundDevice)")
        self.root.geometry("500x500")
        self.root.resizable(False, False)
        
        # Стиль
        style = ttk.Style()
        style.configure('TFrame', background='#f0f0f0')
        style.configure('TLabel', background='#f0f0f0', font=('Arial', 10))
        style.configure('Title.TLabel', background='#f0f0f0', font=('Arial', 12, 'bold'))
        style.configure('TButton', font=('Arial', 10))
        style.configure('Start.TButton', background='#4CAF50')
        style.configure('Stop.TButton', background='#f44336')
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        title_label = ttk.Label(main_frame, text="Аудио Сервер (Отправка)", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Статус библиотеки
        lib_status = "SoundDevice: " + ("Доступно" if SOUNDDEVICE_AVAILABLE else "Не доступно")
        lib_label = ttk.Label(main_frame, text=lib_status, 
                             foreground="green" if SOUNDDEVICE_AVAILABLE else "red")
        lib_label.pack(pady=(0, 10))
        
        # Выбор устройства
        device_frame = ttk.LabelFrame(main_frame, text="Выбор устройства ввода", padding="10")
        device_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(device_frame, text="Микрофон:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(device_frame, textvariable=self.device_var, state="readonly", width=50)
        self.device_combo.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10))
        
        refresh_btn = ttk.Button(device_frame, text="Обновить", command=self.refresh_devices)
        refresh_btn.grid(row=0, column=2)
        
        device_frame.columnconfigure(1, weight=1)
        
        # Информация об устройстве
        self.device_info_var = tk.StringVar(value="")
        device_info_label = ttk.Label(main_frame, textvariable=self.device_info_var, foreground="gray")
        device_info_label.pack(pady=(0, 10))
        
        # Настройки потока
        settings_frame = ttk.LabelFrame(main_frame, text="Настройки потока", padding="10")
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
        
        self.status_var = tk.StringVar(value="Готов к запуску")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="blue")
        status_label.pack(anchor=tk.W)
        
        # Статистика
        stats_frame = ttk.LabelFrame(main_frame, text="Статистика", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.stats_var = tk.StringVar(value="Пакетов отправлено: 0\nСкорость: 0 пакетов/сек")
        stats_label = ttk.Label(stats_frame, textvariable=self.stats_var, justify=tk.LEFT)
        stats_label.pack(anchor=tk.W)
        
        # Кнопки управления
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(button_frame, text="Запуск трансляции", 
                                   command=self.start_stream, style='Start.TButton',
                                   state=tk.NORMAL if SOUNDDEVICE_AVAILABLE else tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(button_frame, text="Остановить", 
                                  command=self.stop_stream, style='Stop.TButton', state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        
        # Инициализация переменных для статистики
        self.packet_count = 0
        self.start_time = 0
        
    def refresh_devices(self):
        """Обновить список устройств"""
        if not SOUNDDEVICE_AVAILABLE:
            return
            
        devices = []
        self.device_info = {}
        
        try:
            hostapi_info = sd.query_hostapis()
            device_list = sd.query_devices()
            
            for i, device in enumerate(device_list):
                if device['max_input_channels'] > 0:
                    hostapi_name = hostapi_info[device['hostapi']]['name']
                    # Добавляем информацию о поддерживаемых форматах
                    formats = []
                    if device['default_samplerate']:
                        formats.append(f"{int(device['default_samplerate'])}Hz")
                    
                    device_name = f"{i}: {device['name']} ({hostapi_name})"
                    devices.append(device_name)
                    self.device_info[device_name] = {
                        'index': i,
                        'device': device
                    }
                    
                    # Показываем информацию о выбранном устройстве
                    if device_name == self.device_var.get():
                        self.show_device_info(device)
            
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
        info_text += f"Каналы: {device['max_input_channels']}, "
        info_text += f"Формат: {self.get_sample_format(device)}"
        self.device_info_var.set(info_text)
    
    def get_sample_format(self, device):
        """Получить поддерживаемый формат семплов"""
        # По умолчанию используем float32, так как он широко поддерживается
        return 'float32'
    
    def get_default_sample_rate(self, device_index):
        """Получить частоту дискретизации по умолчанию для устройства"""
        try:
            device_info = sd.query_devices(device_index)
            return int(device_info['default_samplerate'])
        except:
            return RATE
    
    def setup_network(self):
        """Настройка multicast сокета"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
    
    def audio_callback(self, indata, frames, time, status):
        """Callback для обработки аудио данных"""
        if self.running:
            if status:
                print(f"Audio status: {status}")
            
            # Конвертируем в 16-bit PCM
            try:
                # Масштабируем и конвертируем в int16
                audio_data = (indata * 32767).astype(np.int16).tobytes()
                self.audio_queue.put(audio_data)
            except Exception as e:
                print(f"Audio conversion error: {e}")
    
    def send_audio_data(self):
        """Поток для отправки аудио данных"""
        while self.running:
            try:
                audio_data = self.audio_queue.get(timeout=1.0)
                multicast_group = self.group_var.get()
                port = int(self.port_var.get())
                self.sock.sendto(audio_data, (multicast_group, port))
                self.packet_count += 1
            except queue.Empty:
                continue
            except Exception as e:
                if self.running:
                    print(f"Send error: {e}")
    
    def start_stream(self):
        """Начать потоковую передачу"""
        if not SOUNDDEVICE_AVAILABLE:
            messagebox.showerror("Ошибка", "SoundDevice не доступен")
            return
            
        try:
            # Получаем выбранное устройство
            selected_device = self.device_var.get()
            if not selected_device:
                messagebox.showerror("Ошибка", "Выберите устройство ввода")
                return
            
            device_info = self.device_info[selected_device]
            device_index = device_info['index']
            device_details = device_info['device']
            
            # Получаем частоту дискретизации устройства
            device_sample_rate = self.get_default_sample_rate(device_index)
            
            # Настраиваем сеть
            self.setup_network()
            
            # Получаем настройки
            multicast_group = self.group_var.get()
            port = int(self.port_var.get())
            
            # Запускаем аудио поток
            self.running = True
            self.packet_count = 0
            self.start_time = time.time()
            
            # Запускаем поток для отправки данных
            self.send_thread = threading.Thread(target=self.send_audio_data, daemon=True)
            self.send_thread.start()
            
            print(f"Starting stream with device {device_index}, sample rate: {device_sample_rate}")
            
            # Пробуем разные форматы семплов
            sample_formats = ['float32', 'int16', 'int32']
            
            for sample_format in sample_formats:
                try:
                    print(f"Trying sample format: {sample_format}")
                    
                    # Запускаем аудио захват
                    self.stream = sd.InputStream(
                        device=device_index,
                        channels=CHANNELS,
                        samplerate=device_sample_rate,
                        blocksize=CHUNK,
                        callback=self.audio_callback,
                        dtype=sample_format
                    )
                    self.stream.start()
                    print(f"Successfully started with format: {sample_format}")
                    break
                    
                except Exception as format_error:
                    print(f"Failed with format {sample_format}: {format_error}")
                    if hasattr(self, 'stream') and self.stream:
                        self.stream.stop()
                        self.stream.close()
                        self.stream = None
                    
                    if sample_format == sample_formats[-1]:  # Если это последний формат
                        raise format_error
            
            # Обновляем интерфейс
            self.status_var.set(f"Трансляция на {multicast_group}:{port}")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.device_combo.config(state=tk.DISABLED)
            
            # Запускаем поток для статистики
            self.stats_thread = threading.Thread(target=self.update_stats, daemon=True)
            self.stats_thread.start()
            
        except Exception as e:
            error_msg = f"Не удалось запустить трансляцию: {e}\n\n"
            error_msg += "Возможные решения:\n"
            error_msg += "1. Проверьте разрешения для микрофона\n"
            error_msg += "2. Попробуйте другое аудио устройство\n"
            error_msg += "3. Убедитесь, что устройство не используется другой программой"
            messagebox.showerror("Ошибка", error_msg)
            self.stop_stream()
    
    def update_stats(self):
        """Обновление статистики в GUI"""
        while self.running:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                packets_per_sec = self.packet_count / elapsed
                stats_text = f"Пакетов отправлено: {self.packet_count}\nСкорость: {packets_per_sec:.1f} пакетов/сек"
                self.stats_var.set(stats_text)
            time.sleep(2)
    
    def stop_stream(self):
        """Остановить потоковую передачу"""
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
        self.status_var.set("Трансляция остановлена")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.device_combo.config(state=tk.NORMAL)
        self.stats_var.set("Пакетов отправлено: 0\nСкорость: 0 пакетов/сек")
    
    def on_device_selected(self, event=None):
        """Обработчик выбора устройства"""
        selected_device = self.device_var.get()
        if selected_device and selected_device in self.device_info:
            device_details = self.device_info[selected_device]['device']
            self.show_device_info(device_details)

if __name__ == "__main__":
    root = tk.Tk()
    app = MulticastAudioSenderGUI(root)
    
    # Добавляем обработчик выбора устройства
    app.device_combo.bind('<<ComboboxSelected>>', app.on_device_selected)
    
    root.mainloop()