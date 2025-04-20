import socket
from threading import Thread
import os

class Client:

    def __init__(self, host, port):
        self.socket = socket.socket()
        self.socket.connect((host, port))
        self.name = input("Enter your name: ")

        self.talk_to_server()

    def talk_to_server(self):
        self.socket.send(self.name.encode())
        Thread(target = self.receiveMessage).start()
        self.send_message()

    def send_message(self):
        while True:
            clientInput = input("")
            message = self.name + ": " + clientInput
            self.socket.send(message.encode())

    def receiveMessage(self):
        while True:
            serverMessage = self.socket.recv(1024).decode()
            if not serverMessage.strip():
                os._exit(0)
            print("\033[32m" + serverMessage + "\033[0m")


if __name__ == '__main__':
    Client("127.0.0.1", 5000)
