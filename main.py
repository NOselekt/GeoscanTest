import json
from Logger import Logger


if __name__ == "__main__":
    logger = Logger()
    logger.start()

    try:
        while True:
            command = input("Введите команду в формате\n"
                        "{\"command\":<команда>,\"interval\":<интервал>,"
                        "\"device\":<устройство>,\"sensor\":<датчик>}:\n")
            if not command:
                continue
            if command.strip() == "quit":
                break
            command = json.loads(command)
            if command["command"] == "getlog":
                logger.send_command(command)
            elif command["command"] == "getstats":
                _, device = command.values()
                print(logger.get_stats(int(device)))
            else:
                print("Неопознанная команда")
    except KeyboardInterrupt:
        pass
    finally:
        logger.stop()
