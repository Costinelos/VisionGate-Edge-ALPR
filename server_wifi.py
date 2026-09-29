import socket
import logging
import time

logger = logging.getLogger(__name__)


class WifiServer:
    def __init__(self, callback, host='0.0.0.0', port=5000):
        self.callback = callback
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = False

    def start(self):
        while not self.running:
            try:
                self.server.bind((self.host, self.port))
                self.server.listen(5)
                self.running = True
                logger.info(f"WifiServer a pornit si asculta pe portul {self.port}")
            except Exception as e:
                logger.error(f"Astept ca reteaua sa fie gata... ({e})")
                time.sleep(2)

        try:
            while self.running:
                client_socket, addr = self.server.accept()
                try:
                    data = client_socket.recv(2048).decode('utf-8').strip()
                    if data:
                        response = self.callback(data)
                        if response:
                            client_socket.sendall((str(response) + "\n").encode('utf-8'))
                except Exception as e:
                    logger.error(f"Eroare procesare client: {e}")
                finally:
                    client_socket.close()
        except Exception as e:
            logger.error(f"WifiServer a picat: {e}")
        finally:
            self.server.close()
            self.running = False