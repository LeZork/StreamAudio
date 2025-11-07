import socket
import struct
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

class MulticastTesterGUI:
    def __init__(self, root):
        self.root = root
        self.setup_gui()
        self.is_testing = False
        
    def setup_gui(self):
        """Настройка графического интерфейса тестера"""
        self.root.title("Multicast Network Tester")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # Стиль
        style = ttk.Style()
        style.configure('TFrame', background='#f0f0f0')
        style.configure('TLabel', background='#f0f0f0', font=('Arial', 10))
        style.configure('Title.TLabel', background='#f0f0f0', font=('Arial', 12, 'bold'))
        style.configure('TButton', font=('Arial', 10))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        title_label = ttk.Label(main_frame, text="Тестер Multicast Сети", style='Title.TLabel')
        title_label.pack(pady=(0, 15))
        
        # Настройки подключения
        connection_frame = ttk.LabelFrame(main_frame, text="Настройки Multicast", padding="10")
        connection_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(connection_frame, text="Multicast группа:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.group_var = tk.StringVar(value='224.1.1.1')
        group_entry = ttk.Entry(connection_frame, textvariable=self.group_var, width=15)
        group_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        ttk.Label(connection_frame, text="Порт:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.port_var = tk.StringVar(value='5007')
        port_entry = ttk.Entry(connection_frame, textvariable=self.port_var, width=10)
        port_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 20))
        
        ttk.Label(connection_frame, text="Таймаут (сек):").grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.timeout_var = tk.StringVar(value='3')
        timeout_entry = ttk.Entry(connection_frame, textvariable=self.timeout_var, width=5)
        timeout_entry.grid(row=0, column=5, sticky=tk.W)
        
        # Тестовые пакеты
        packet_frame = ttk.LabelFrame(main_frame, text="Тестовые пакеты", padding="10")
        packet_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(packet_frame, text="Количество пакетов:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.packet_count_var = tk.StringVar(value='5')
        count_entry = ttk.Entry(packet_frame, textvariable=self.packet_count_var, width=5)
        count_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        ttk.Label(packet_frame, text="Интервал (сек):").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.interval_var = tk.StringVar(value='1.0')
        interval_entry = ttk.Entry(packet_frame, textvariable=self.interval_var, width=5)
        interval_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 20))
        
        ttk.Label(packet_frame, text="Размер пакета:").grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.packet_size_var = tk.StringVar(value='1024')
        size_entry = ttk.Entry(packet_frame, textvariable=self.packet_size_var, width=5)
        size_entry.grid(row=0, column=5, sticky=tk.W)
        
        # Результаты тестирования
        results_frame = ttk.LabelFrame(main_frame, text="Результаты тестирования", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.results_text = scrolledtext.ScrolledText(results_frame, height=15, width=70, font=('Consolas', 9))
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        # Статусная строка
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_var = tk.StringVar(value="Готов к тестированию")
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT)
        
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # Кнопки управления
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.test_single_btn = ttk.Button(button_frame, text="Быстрый тест", 
                                         command=self.run_single_test)
        self.test_single_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.test_extended_btn = ttk.Button(button_frame, text="Расширенный тест", 
                                           command=self.run_extended_test)
        self.test_extended_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(button_frame, text="Остановить", 
                                  command=self.stop_test, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        clear_btn = ttk.Button(button_frame, text="Очистить лог", 
                              command=self.clear_log)
        clear_btn.pack(side=tk.LEFT)
        
    def log_message(self, message, is_error=False):
        """Добавить сообщение в лог"""
        timestamp = time.strftime("%H:%M:%S")
        tag = "[ERROR]" if is_error else "[INFO]"
        log_line = f"{timestamp} {tag} {message}\n"
        
        self.results_text.insert(tk.END, log_line)
        self.results_text.see(tk.END)
        self.root.update()
        
    def clear_log(self):
        """Очистить лог"""
        self.results_text.delete(1.0, tk.END)
        
    def validate_inputs(self):
        """Проверка корректности введенных данных"""
        try:
            multicast_group = self.group_var.get()
            port = int(self.port_var.get())
            timeout = float(self.timeout_var.get())
            
            # Проверка multicast адреса
            if not multicast_group.startswith('224.'):
                raise ValueError("Multicast адрес должен начинаться с 224.")
            
            # Проверка порта
            if not (1024 <= port <= 65535):
                raise ValueError("Порт должен быть в диапазоне 1024-65535")
                
            return True
            
        except ValueError as e:
            self.log_message(f"Ошибка ввода: {e}", True)
            return False
    
    def run_single_test(self):
        """Запуск быстрого теста"""
        if not self.validate_inputs():
            return
            
        self.is_testing = True
        self.test_single_btn.config(state=tk.DISABLED)
        self.test_extended_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start()
        
        test_thread = threading.Thread(target=self._single_test_thread, daemon=True)
        test_thread.start()
    
    def run_extended_test(self):
        """Запуск расширенного теста"""
        if not self.validate_inputs():
            return
            
        self.is_testing = True
        self.test_single_btn.config(state=tk.DISABLED)
        self.test_extended_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start()
        
        test_thread = threading.Thread(target=self._extended_test_thread, daemon=True)
        test_thread.start()
    
    def stop_test(self):
        """Остановить тестирование"""
        self.is_testing = False
        self.progress.stop()
        self.test_single_btn.config(state=tk.NORMAL)
        self.test_extended_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Тестирование остановлено")
    
    def _single_test_thread(self):
        """Поток для быстрого теста"""
        try:
            multicast_group = self.group_var.get()
            port = int(self.port_var.get())
            timeout = float(self.timeout_var.get())
            
            self.status_var.set("Выполняется быстрый тест...")
            self.log_message(f"Начало быстрого теста: {multicast_group}:{port}")
            
            # Создаем сокеты
            sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_send.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            
            sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock_recv.bind(('', port))
            
            group = socket.inet_aton(multicast_group)
            mreq = struct.pack('4sL', group, socket.INADDR_ANY)
            sock_recv.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock_recv.settimeout(timeout)
            
            # Отправка тестового пакета
            test_data = b'quick_test_packet'
            start_time = time.time()
            sock_send.sendto(test_data, (multicast_group, port))
            self.log_message(f"Отправлен тестовый пакет: {len(test_data)} байт")
            
            # Попытка приема
            try:
                data, addr = sock_recv.recvfrom(1024)
                end_time = time.time()
                latency = (end_time - start_time) * 1000  # в миллисекундах
                
                self.log_message(f"Тест УСПЕШЕН: получено {len(data)} байт от {addr}")
                self.log_message(f"Задержка: {latency:.2f} мс")
                self.log_message(f"Данные: {data[:50]}{'...' if len(data) > 50 else ''}")
                
            except socket.timeout:
                self.log_message("Тест НЕ УДАЛСЯ: пакет не получен (таймаут)", True)
            
            sock_send.close()
            sock_recv.close()
            
            self.status_var.set("Быстрый тест завершен")
            
        except Exception as e:
            self.log_message(f"Ошибка при выполнении теста: {e}", True)
            self.status_var.set("Ошибка тестирования")
        
        finally:
            self.stop_test()
    
    def _extended_test_thread(self):
        """Поток для расширенного тестирования"""
        try:
            multicast_group = self.group_var.get()
            port = int(self.port_var.get())
            timeout = float(self.timeout_var.get())
            packet_count = int(self.packet_count_var.get())
            interval = float(self.interval_var.get())
            packet_size = int(self.packet_size_var.get())
            
            self.status_var.set("Выполняется расширенный тест...")
            self.log_message(f"Начало расширенного теста: {multicast_group}:{port}")
            self.log_message(f"Параметры: {packet_count} пакетов, интервал {interval}с, размер {packet_size} байт")
            
            # Создаем сокеты
            sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_send.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            
            sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock_recv.bind(('', port))
            
            group = socket.inet_aton(multicast_group)
            mreq = struct.pack('4sL', group, socket.INADDR_ANY)
            sock_recv.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock_recv.settimeout(timeout)
            
            received_count = 0
            lost_count = 0
            total_latency = 0
            min_latency = float('inf')
            max_latency = 0
            
            # Запускаем прием в отдельном потоке
            def receiver_thread():
                nonlocal received_count, total_latency, min_latency, max_latency
                while self.is_testing and received_count < packet_count:
                    try:
                        data, addr = sock_recv.recvfrom(packet_size + 100)
                        receive_time = time.time()
                        
                        # Извлекаем время отправки из данных
                        if len(data) >= 8:  # как минимум timestamp
                            send_time = struct.unpack('d', data[:8])[0]
                            latency = (receive_time - send_time) * 1000
                            
                            received_count += 1
                            total_latency += latency
                            min_latency = min(min_latency, latency)
                            max_latency = max(max_latency, latency)
                            
                            self.log_message(f"Пакет {received_count}: задержка {latency:.2f} мс")
                            
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.is_testing:
                            self.log_message(f"Ошибка приема: {e}", True)
            
            receiver = threading.Thread(target=receiver_thread, daemon=True)
            receiver.start()
            
            # Отправка пакетов
            for i in range(packet_count):
                if not self.is_testing:
                    break
                    
                # Создаем тестовые данные с timestamp
                send_time = time.time()
                timestamp_data = struct.pack('d', send_time)  # 8 bytes для double
                test_data = timestamp_data + b'X' * (packet_size - 8)
                
                try:
                    sock_send.sendto(test_data, (multicast_group, port))
                    self.log_message(f"Отправлен пакет {i+1}/{packet_count}")
                except Exception as e:
                    self.log_message(f"Ошибка отправки пакета {i+1}: {e}", True)
                    lost_count += 1
                
                time.sleep(interval)
            
            # Даем время на прием последних пакетов
            time.sleep(timeout)
            
            # Статистика
            lost_count += packet_count - received_count
            loss_percentage = (lost_count / packet_count) * 100 if packet_count > 0 else 0
            avg_latency = total_latency / received_count if received_count > 0 else 0
            
            self.log_message("=" * 50)
            self.log_message("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
            self.log_message(f"Отправлено пакетов: {packet_count}")
            self.log_message(f"Получено пакетов: {received_count}")
            self.log_message(f"Потеряно пакетов: {lost_count}")
            self.log_message(f"Потери: {loss_percentage:.1f}%")
            
            if received_count > 0:
                self.log_message(f"Средняя задержка: {avg_latency:.2f} мс")
                self.log_message(f"Минимальная задержка: {min_latency:.2f} мс")
                self.log_message(f"Максимальная задержка: {max_latency:.2f} мс")
            
            if loss_percentage < 5:
                self.log_message("КАЧЕСТВО СЕТИ: ОТЛИЧНОЕ")
            elif loss_percentage < 20:
                self.log_message("КАЧЕСТВО СЕТИ: УДОВЛЕТВОРИТЕЛЬНОЕ")
            else:
                self.log_message("КАЧЕСТВО СЕТИ: ПЛОХОЕ", True)
            
            sock_send.close()
            sock_recv.close()
            
            self.status_var.set("Расширенный тест завершен")
            
        except Exception as e:
            self.log_message(f"Ошибка при выполнении теста: {e}", True)
            self.status_var.set("Ошибка тестирования")
        
        finally:
            self.stop_test()

def test_multicast():
    """Оригинальная функция тестирования (сохранена для совместимости)"""
    MULTICAST_GROUP = '224.1.1.1'
    PORT = 5007
    
    # Тест отправки
    sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_send.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    
    # Тест приема
    sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_recv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_recv.bind(('', PORT))
    
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    sock_recv.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock_recv.settimeout(2.0)
    
    # Отправка тестового пакета
    test_data = b'test'
    sock_send.sendto(test_data, (MULTICAST_GROUP, PORT))
    print("Test packet sent")
    
    # Попытка приема
    try:
        data, addr = sock_recv.recvfrom(1024)
        print(f"Multicast test SUCCESS: received {data} from {addr}")
        return True
    except socket.timeout:
        print("Multicast test FAILED: no packet received")
        return False
    
    sock_send.close()
    sock_recv.close()

if __name__ == "__main__":
    # Запуск графического интерфейса
    root = tk.Tk()
    app = MulticastTesterGUI(root)
    root.mainloop()