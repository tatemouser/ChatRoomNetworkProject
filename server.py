import socket
import logging
from threading import Thread

logging.basicConfig(filename = "chat.log", format = "%(asctime)s %(message)s", filemode = "w")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class Server:
    Clients = []


    def __init__(self, host, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((host, port))
        self.socket.listen(5)
        print("Server listening for connections")

    def listen(self):
        while True:
            client, addr = self.socket.accept()
            print("Connection from: " + str(addr))
            
            name = client.recv(1024).decode()
            newClient = {'client_name': name, 'client_socket': client}

            self.broadcast_message(name, name + " has joined the chat!")

            Server.Clients.append(newClient)
            Thread(target = self.handle_new_client, args = (newClient,)).start()
    
    def handle_new_client(self, client):
        name = client['client_name']
        client_socket = client['client_socket']
        while True:
            message = client_socket.recv(1024).decode()

            if (message.strip() == name + ": bye" or not message.strip()):
                self.broadcast_message(name, name + " has left the chat!")
                Server.Clients.remove(client)
                client_socket.close()
            else:
                self.broadcast_message(name, message)
            
            logger.info(message)
    
    def broadcast_message(self, sender, message):
        for client in self.Clients:
            socket = client['client_socket']
            name = client['client_name']
            if (name != sender):
                socket.send(message.encode())
    

if __name__ == '__main__':
    server = Server('127.0.0.1', 5000)
    server.listen()