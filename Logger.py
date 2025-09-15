import socket
import json
import threading
import queue
import datetime

BUFFER_SIZE = 4096
DEVICES = {
    0: "BlackBox",
    1: "EmergencySystem",
    2: "OxygenSystem",
    3: "Climatic",
    4: "RadiationShield",
    5: "PressureSystem",
    6: "Lighting"
}


class Logger:
    def __init__(self, modem_ip: str = "192.168.1.2",
                 recv_port: int = 5001,
                 send_port: int = 5002,
                 logfile: str = "session_log.jsonl"):
        """
        Конструктор класса
        :param modem_ip: ip, через который будут приниматься и отправляться данные
        :param recv_port: порт для принятия сообщений
        :param send_port: порт для отправки сообщений
        :param logfile: файл для записи логов
        """
        self.modem_ip = modem_ip
        self.receive_port = recv_port
        self.send_port = send_port
        self.logfile = logfile

        self.receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receive_socket.bind((modem_ip, self.receive_port))

        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.running = False
        self.waiting_logs = False
        self.waiting_logs_started = datetime.datetime.now()
        self.command_queue = queue.Queue()
        self.log_lock = threading.Lock()


    def start(self) -> None:
        """
        Запуск основного потока приёма
        :return: None
        """
        self.running = True
        threading.Thread(target=self._recv_loop, daemon=True).start()
        print("[INFO] Logger started", self.receive_port)

    def stop(self) -> None:
        """
        Остановка логгера
        :return: None
        """
        self.running = False
        self.receive_socket.close()
        self.send_socket.close()
        print("[INFO] Logger stopped")

    def _recv_loop(self) -> None:
        """
        Фоновый поток приёма данных
        :return: None
        """
        while self.running:
            try:
                data, _ = self.receive_socket.recvfrom(BUFFER_SIZE)
                packet = json.loads(data.decode("utf-8"))
                self._process_packet(packet)
            except Exception as exception:
                print("[ERROR] Receiving packet:", exception)

    def _process_packet(self, packet: dict) -> None:
        """
        Обработка входящего пакета от модема.
        Формат: {"recv_time": <время отправки>, "message": "сообщение"}
        :param packet: полученный пакет данных
        :return: None
        """
        raw_message = packet.get("message")
        parsed = self._parse_message(raw_message)
        if not parsed:
            return

        if parsed["source"] == "online":
            self._handle_telemetry(self._make_final_form(parsed))

        elif parsed["source"] == "log":
            self._handle_log(parsed)
            self.waiting_logs_started = datetime.datetime.now()


    def _parse_message(self, raw_message: str) -> dict | None:
        """
        Парсинг строки вида:
        "<дата> <время> <источник> <номер устройства> <имя датчика> <показания> <контрольная сумма>"
        :param raw_message: сообщение на входе
        :return: сообщение после проверки (dict)
        """
        try:
            parts = raw_message.strip().split()
            if len(parts) < 7:
                return None

            date, time, source, device, sensor, value, checksum = parts
            device = int(device)
            checksum = int(checksum)
            if device not in DEVICES.keys():
                return None
            only_message = " ".join(parts[:-1])
            calculated_checksum = sum(only_message.encode("ascii"))
            if checksum != calculated_checksum:
                print("DAMAGED MESSAGE, checksum: ", checksum, " calculated_checksum", calculated_checksum)
                return None

            to_return = {
                "date": date,
                "time": time,
                "source": source,
                "device": device,
                "sensor": sensor
            }

            if value.startswith("WARNING") or value.startswith("ERROR"):
                to_return["failure"] = value
            else:
                to_return["value"] = value

            return to_return

        except:
            return None

    def _handle_telemetry(self, message: dict) -> None:
        """
        Обработка телеметрии
        :param message: сообщение для обработки
        :return: None
        """
        print(f"[TELEMETRY] {message}")

    def _handle_log(self, message: dict) -> None:
        """
        Обработка логов (WARNING/ERROR отдельно)
        :param message: сообщение для обработки
        :return: None
        """
        value = message.get("value")
        if value:
            if message["sensor"] == "system" and message["value"] == "log_start":
                # Здесь я так и не решил, как будет лучше начать ожидание логов:
                # ждать после получения "log_start", который может и не прийти,
                # или после получения команды
                self.waiting_logs = True
                print("[INFO] Log download started")
            elif message["sensor"] == "system" and message["value"] == "log_end":
                self.waiting_logs = False
                print("[INFO] Log download ended")
                self.send_command()
        else:
            print(f"[FAILURE] {self._make_final_form(message)}")

    def _make_final_form(self, message: dict) -> dict:
        """
        Приводит сообщение к конечному виду для вывода
        :param message: сообщение, которое будет приведено к конечному виду
        :return: сообщение в конечном виде (dict)
        """
        value = message.get("value")
        final_form = {
            "device": message["device"],
            "sensor": message["sensor"],
        }
        if value:
            final_form["value"] = value
        else:
            final_form["failure"] = message.get("failure")
        return final_form


    def _save_to_file(self, log: dict) -> None:
        """
        Сохранение данных в лог-файл
        :param log: данные для сохранения
        :return:
        """
        with self.log_lock, open(self.logfile, "a", encoding="utf-8") as logfile:
            logfile.write(json.dumps(log, ensure_ascii=False) + "\n")

    def send_command(self, command: dict | None = None) -> None:
        """
        Отправка команды запроса логов
        :param command: команда для отправки на космический аппарат
        В случае None ничего не делает
        :return: None
        """
        if command:
            self.command_queue.put(command)
            print("[INFO] Command queued:", command)
        queue_empty = self.command_queue.empty()
        if not self.waiting_logs and not queue_empty:
            command_sent = self.command_queue.get()
            self.send_socket.sendto(json.dumps(command_sent).encode("utf-8"), (self.modem_ip, self.send_port))
            print("[INFO] Command sent:", command_sent)
            self._save_to_file(command_sent)
            self.waiting_logs = True
            return

        if (datetime.datetime.now() - self.waiting_logs_started).seconds >= 15:
            # Если отправка логов задерживается дольше 15 секунд, перестаём её ждать
            self.waiting_logs = False
            if not queue_empty:
                self.send_command()


    def get_stats(self, device: int) -> dict:
        """
        Статистика по предупреждениям/ошибкам для устройства
        :param device: устройство, по которому ищем предупреждения/ошибки
        :return: словарь с числом предупреждений/ошибок
        """
        warnings = 0
        errors = 0
        with self.log_lock, open(self.logfile, "r", encoding="utf-8") as logfile:
            line = logfile.readline()
            while line:
                line = json.loads(line)
                if device == line.get("device"):
                    if "WARNING" in line.get("failure", ""):
                        warnings += 1
                    if "ERROR" in line.get("failure", ""):
                        errors += 1
                line = logfile.readline()
        return {
            "WARNINGS": warnings,
            "ERRORS": errors
        }