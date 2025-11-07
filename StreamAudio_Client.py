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

# Конфигурация должна совпадать с отправителем
CHUNK = 256
RATE = 44100
CHANNELS = 1
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
        
        if not SOUNDDEVICE_AVAILABLE:
            messagebox.showerror("Ошибка", 
                               "SoundDevice не установлен. Установите: pip install sounddevice")
        
    def setup_gui(self):
        """Настройка графического интерфейса"""
        self.root.title("Audio Stream Client (SoundDevice)")
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
        title_label = ttk.Label(main_frame, text="Аудио Клиент (Прием)", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Статус библиотеки
        lib_status = "SoundDevice: " + ("Доступно" if SOUNDDEVICE_AVAILABLE else "Не доступно")
        lib_label = ttk.Label(main_frame, text=lib_status,
                             foreground="green" if SOUNDDEVICE_AVAILABLE else "red")
        lib_label.pack(pady=(0, 10))
        
        # Выбор устройства
        device_frame = ttk.LabelFrame(main_frame, text="Выбор устройства вывода", padding="10")
        device_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(device_frame, text="Динамики:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
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
                                   command=self.start_receive, style='Start.TButton',
                                   state=tk.NORMAL if SOUNDDEVICE_AVAILABLE else tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(button_frame, text="Остановить", 
                                  command=self.stop_receive, style='Stop.TButton', state=tk.DISABLED)
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
        info_text += f"Каналы: {device['max_output_channels']}"
        self.device_info_var.set(info_text)
    
    def get_default_sample_rate(self, device_index):
        """Получить частоту дискретизации по умолчанию для устройства"""
        try:
            device_info = sd.query_devices(device_index)
            return int(device_info['default_samplerate'])
        except:
            return RATE
    
    def setup_network(self):
        """Настройка multicast приемника"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Привязываемся к порту
        port = int(self.port_var.get())
        self.sock.bind(('', port))
        
        # Добавляем в multicast группу
        multicast_group = self.group_var.get()
        group = socket.inet_aton(multicast_group)
        mreq = struct.pack('4sL', group, socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        # Увеличиваем буфер для избежания потерь
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        
        # Таймаут для возможности проверки флага running
        self.sock.settimeout(1.0)
    
    def audio_output_callback(self, outdata, frames, time, status):
        """Callback для вывода аудио"""
        if self.running:
            if status:
                print(f"Output status: {status}")
                
            try:
                # Получаем данные из очереди
                audio_data = self.audio_queue.get_nowait()
                
                # Конвертируем из 16-bit PCM в float для sounddevice
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0
                audio_array = audio_array.reshape(-1, 1)  # Формируем в правильную форму
                
                # Заполняем выходной буфер
                if len(audio_array) >= len(outdata):
                    outdata[:] = audio_array[:len(outdata)]
                else:
                    # Если данных меньше чем нужно, заполняем часть и остальное нулями
                    outdata[:len(audio_array)] = audio_array
                    outdata[len(audio_array):] = 0
                    
            except queue.Empty:
                # Если данных нет, заполняем тишиной
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
            # Получаем выбранное устройство
            selected_device = self.device_var.get()
            if not selected_device:
                messagebox.showerror("Ошибка", "Выберите устройство вывода")
                return
            
            device_info = self.device_info[selected_device]
            device_index = device_info['index']
            device_details = device_info['device']
            
            # Получаем частоту дискретизации устройства
            device_sample_rate = self.get_default_sample_rate(device_index)
            
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
            
            print(f"Starting output stream with device {device_index}, sample rate: {device_sample_rate}")
            
            # Пробуем разные форматы семплов для вывода
            sample_formats = ['float32', 'int16', 'int32']
            
            for sample_format in sample_formats:
                try:
                    print(f"Trying output sample format: {sample_format}")
                    
                    # Запускаем аудио вывод
                    self.stream = sd.OutputStream(
                        device=device_index,
                        channels=CHANNELS,
                        samplerate=device_sample_rate,
                        blocksize=CHUNK,
                        callback=self.audio_output_callback,
                        dtype=sample_format
                    )
                    self.stream.start()
                    print(f"Successfully started output with format: {sample_format}")
                    break
                    
                except Exception as format_error:
                    print(f"Failed with output format {sample_format}: {format_error}")
                    if hasattr(self, 'stream') and self.stream:
                        self.stream.stop()
                        self.stream.close()
                        self.stream = None
                    
                    if sample_format == sample_formats[-1]:  # Если это последний формат
                        raise format_error
            
            # Обновляем интерфейс
            multicast_group = self.group_var.get()
            port = self.port_var.get()
            self.status_var.set(f"Прослушивание {multicast_group}:{port}")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.device_combo.config(state=tk.DISABLED)
            
            # Запускаем поток для статистики
            self.stats_thread = threading.Thread(target=self.update_stats, daemon=True)
            self.stats_thread.start()
            
        except Exception as e:
            error_msg = f"Не удалось начать прослушивание: {e}\n\n"
            error_msg += "Возможные решения:\n"
            error_msg += "1. Проверьте настройки аудио вывода\n"
            error_msg += "2. Попробуйте другое аудио устройство\n"
            error_msg += "3. Убедитесь, что устройство не используется другой программой"
            messagebox.showerror("Ошибка", error_msg)
            self.stop_receive()
    
    def receive_loop(self):
        """Главный цикл приема данных"""
        buffer_size = CHUNK * 2  # 16-bit = 2 bytes per sample
        
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
                self.packet_count += 1
                
                # Проверяем размер данных
                if len(data) >= buffer_size:
                    # Добавляем данные в очередь для воспроизведения
                    self.audio_queue.put(data)
                else:
                    print(f"Received incomplete packet: {len(data)} bytes")
                    self.lost_packets += 1
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:  # Игнорируем ошибки после остановки
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
        
        if hasattr(self, 'receive_thread'):
            self.receive_thread.join(timeout=2.0)
        
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
        self.stats_var.set("Пакетов получено: 0\nПотерь: 0%\nСкорость: 0 пакетов/сек")
    
    def on_device_selected(self, event=None):
        """Обработчик выбора устройства"""
        selected_device = self.device_var.get()
        if selected_device and selected_device in self.device_info:
            device_details = self.device_info[selected_device]['device']
            self.show_device_info(device_details)

if __name__ == "__main__":
    root = tk.Tk()
    app = MulticastAudioReceiverGUI(root)
    
    # Добавляем обработчик выбора устройства
    app.device_combo.bind('<<ComboboxSelected>>', app.on_device_selected)
    
    root.mainloop()