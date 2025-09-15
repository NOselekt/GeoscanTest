import socket
import json
import threading
import time
import random
from datetime import datetime

BUFFER_SIZE = 4096


class Sender:
    def __init__(self,
                 logger_ip: str = "127.0.0.1",
                 send_port: int = 5001,
                 recv_port: int = 5002):
        """
        Конструктор класса
        :param logger_ip: ip логгера, куда отправляются данные
        :param send_port: порт для отправки телеметрии и логов
        :param recv_port: порт для приёма команд от логгера
        """
        self.logger_ip = logger_ip
        self.send_port = send_port
        self.recv_port = recv_port

        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receive_socket.bind(("0.0.0.0", self.recv_port))

        self.running = False

    def start(self) -> None:
        """
        Запуск потоков эмулятора
        :return: None
        """
        self.running = True
        threading.Thread(target=self._send_telemetry_loop, daemon=True).start()
        threading.Thread(target=self._listen_commands_loop, daemon=True).start()
        print(f"[INFO] Sender started (send → {self.send_port}, listen ← {self.recv_port})")

    def stop(self) -> None:
        """
        Остановка эмулятора
        :return: None
        """
        self.running = False
        self.send_socket.close()
        self.receive_socket.close()
        print("[INFO] Sender stopped")

    def _make_message(self, source: str, device: int, sensor: str, value: str) -> str:
        """
        Формирование строки сообщения с контрольной суммой
        :param source: источник (online / log)
        :param device: номер устройства
        :param sensor: имя датчика
        :param value: значение датчика или сообщение
        :return: готовая строка сообщения
        """
        dt = datetime.now()
        body = f"{dt.strftime('%d-%m-%Y')} {dt.strftime('%H-%M-%S.%f')[:-3]} {source} {device} {sensor} {value}"
        checksum = sum(body.encode("ascii"))
        return f"{body} {checksum}"

    def _send_packet(self, message: str) -> None:
        """
        Отправка UDP пакета
        :param message: строка сообщения
        :return: None
        """
        packet = {"recv_time": time.time(), "message": message}
        data = json.dumps(packet).encode("utf-8")
        self.send_socket.sendto(data, (self.logger_ip, self.send_port))

    def _send_telemetry_loop(self) -> None:
        """
        Фоновая отправка телеметрии
        :return: None
        """
        while self.running:
            try:
                msg = self._make_message("online",
                                         random.randint(1, 6),
                                         "temp",
                                         str(round(random.uniform(20, 30), 1)))
                self._send_packet(msg)
            except Exception as e:
                print("[ERROR] Telemetry send failed:", e)
            time.sleep(2)

    def _listen_commands_loop(self) -> None:
        """
        Фоновое ожидание команд от логгера
        :return: None
        """
        while self.running:
            try:
                data, _ = self.receive_socket.recvfrom(BUFFER_SIZE)
                command = json.loads(data.decode("utf-8"))
                print("[INFO] Received command:", command)
                if command.get("command") == "getlog":
                    self._send_logs(command)
            except Exception as e:
                print("[ERROR] Receiving command:", e)

    def _send_logs(self, command: dict) -> None:
        """
        Отправка блока логов (log_start → данные → log_end)
        :param command: команда запроса логов
        :return: None
        """
        # log_start
        start_msg = self._make_message("log", 0, "system", "log_start")
        self._send_packet(start_msg)
        time.sleep(1)

        # несколько записей логов
        for _ in range(5):
            device = random.randint(1, 6)
            sensor = "sensor" + str(random.randint(1, 3))
            if random.random() < 0.3:
                value = "WARNING_temp_high"
            elif random.random() < 0.1:
                value = "ERROR_sensor_fail"
            else:
                value = str(round(random.uniform(10, 50), 1))
            log_msg = self._make_message("log", device, sensor, value)
            self._send_packet(log_msg)
            time.sleep(0.5)

        # log_end
        end_msg = self._make_message("log", 0, "system", "log_end")
        self._send_packet(end_msg)
        print("[INFO] Logs sent to logger")
