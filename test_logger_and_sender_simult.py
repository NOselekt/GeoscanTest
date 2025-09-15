from Logger import Logger
from Sender import Sender
import time
import threading

def main():
    # Запуск логгера
    logger = Logger(modem_ip="127.0.0.1",
                    recv_port=5001,
                    send_port=5002,
                    logfile="session_log.jsonl")
    logger.start()

    # Запуск эмулятора
    sender = Sender(logger_ip="127.0.0.1",
                    send_port=5001,
                    recv_port=5002)
    sender.start()

    # Через несколько секунд отправим команду getlog
    def send_command_later():
        time.sleep(5)
        command = {"command": "getlog", "interval": 1, "device": 2, "sensor": "temp"}
        logger.send_command(command)

    threading.Thread(target=send_command_later, daemon=True).start()

    try:
        # Работаем ~20 секунд, чтобы увидеть обмен
        time.sleep(20)
    finally:
        sender.stop()
        logger.stop()

        # Получаем статистику по устройству 2
        stats = logger.get_stats(2)
        print(f"[STATS] Device 2 → WARNINGS: {stats['WARNINGS']}, ERRORS: {stats['ERRORS']}")

if __name__ == "__main__":
    main()
