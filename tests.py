import unittest, json, os
from datetime import datetime
from Logger import Logger

class FakeSocket:
    """Фейковый сокет для тестирования отправки"""
    def __init__(self):
        self.sent = []
    def sendto(self, data, addr):
        self.sent.append((data, addr))
    def close(self): pass

class TestLogger(unittest.TestCase):
    def setUp(self):
        self.logfile = "test_session_log.jsonl"
        try:
            os.remove(self.logfile)
        except FileNotFoundError:
            pass
        self.logger = Logger(modem_ip="127.0.0.1", recv_port=0, send_port=0, logfile=self.logfile)
        self.logger.send_socket = FakeSocket()

    def tearDown(self):
        try: os.remove(self.logfile)
        except FileNotFoundError: pass

    def _make_good_message(self, source="online", device=2, sensor="temp", value="42.0") -> str:
        dt = datetime.now()
        body = f"{dt.strftime('%d-%m-%Y')} {dt.strftime('%H-%M-%S.%f')[:-3]} {source} {device} {sensor} {value}"
        checksum = sum(body.encode("ascii"))
        return f"{body} {checksum}"

    def test_parse_valid_message(self):
        raw = self._make_good_message()
        parsed = self.logger._parse_message(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["device"], 2)
        self.assertEqual(parsed["value"], "42.0")

    def test_parse_invalid_checksum(self):
        raw = "01-01-2025 12-00-00.000 online 2 temp 100 99999"
        parsed = self.logger._parse_message(raw)
        self.assertIsNone(parsed)

    def test_process_telemetry_and_save(self):
        raw = self._make_good_message("online", 2, "temp", "3.14")
        packet = {"recv_time": 1, "message": raw}
        self.logger._process_packet(packet)
        self.logger._save_to_file({"device": 2, "value": "3.14"})
        with open(self.logfile, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertTrue(any("3.14" in l for l in lines))

    def test_send_command(self):
        cmd = {"command": "getlog", "interval": 1, "device": 2, "sensor": "temp"}
        self.logger.waiting_logs = False
        self.logger.send_command(cmd)
        self.assertTrue(len(self.logger.send_socket.sent) > 0)
        sent_json = json.loads(self.logger.send_socket.sent[0][0].decode("utf-8"))
        self.assertEqual(sent_json, cmd)

    def test_get_stats(self):

        with open(self.logfile, "w", encoding="utf-8") as f:
            f.write(json.dumps({"device": 2, "failure": "WARNING: test"}) + "\n")
            f.write(json.dumps({"device": 2, "failure": "ERROR: test"}) + "\n")
            f.write(json.dumps({"device": 3, "failure": "WARNING: other"}) + "\n")

        stats = self.logger.get_stats(2)
        self.assertEqual(stats["WARNINGS"], 1)
        self.assertEqual(stats["ERRORS"], 1)

    def test_log_start_and_end(self):

        cmd = {"command": "getlog", "interval": 1, "device": 2, "sensor": "temp"}
        self.logger.command_queue.put(cmd)


        raw_start = self._make_good_message("log", 0, "system", "log_start")
        packet_start = {"recv_time": 1, "message": raw_start}
        self.logger._process_packet(packet_start)


        self.assertTrue(self.logger.waiting_logs, "Ожидание логов должно быть True после log_start")


        raw_end = self._make_good_message("log", 0, "system", "log_end")
        packet_end = {"recv_time": 2, "message": raw_end}
        self.logger._process_packet(packet_end)


        self.assertGreater(len(self.logger.send_socket.sent), 0, "Команда должна быть отправлена после log_end")


        sent_json = json.loads(self.logger.send_socket.sent[0][0].decode("utf-8"))
        self.assertEqual(sent_json, cmd, "Отправленная команда должна соответствовать ожидаемой")


        self.assertTrue(self.logger.waiting_logs, "После отправки команды ожидание логов снова True")


if __name__ == "__main__":
    unittest.main()
