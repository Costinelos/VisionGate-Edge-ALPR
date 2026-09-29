import socket
import threading
import logging
import os
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BluetoothServer(threading.Thread):
    def __init__(self, system_callback):
        super().__init__(daemon=True)
        self.callback = system_callback
        self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self.running = True
        self.client_socket = None

    def run(self):
        try:
            os.system("sudo fuser -k 1/rfcomm > /dev/null 2>&1")

            self.sock.bind(("00:00:00:00:00:00", 1))
            self.sock.listen(1)
            logger.info("BT Server initialized on Port 1. Listening for connections...")

            while self.running:
                client, addr = self.sock.accept()
                logger.info(f"Connection established with: {addr}")


                self.client_socket = client

                self.handle_client(client)
        except Exception as e:
            logger.error(f"Server error: {e}")

    def handle_client(self, client):
        try:
            while self.running:
                data = client.recv(1024)
                if not data:
                    break

                raw_data = data.decode('utf-8', errors='ignore').strip()


                log_preview = raw_data if len(raw_data) < 50 else raw_data[:50] + "..."
                logger.info(f"Received payload: '{log_preview}'")

                if raw_data:

                    response = self.callback(raw_data)

                    if response:
                        try:

                            msg_bytes = (str(response) + "\n").encode('utf-8')
                            client.sendall(msg_bytes)
                        except Exception as e:
                            logger.error(f"Failed to send response: {e}")
                            break

        except Exception as e:
            logger.warning(f"Connection interrupted: {e}")
        finally:
            client.close()


            self.client_socket = None

            logger.info("Client disconnected.")