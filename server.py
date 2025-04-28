# server.py
import socket
import logging
from threading import Thread

# Setup logging for server messages
logging.basicConfig(filename="chat.log", format="%(asctime)s %(message)s", filemode="w")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class Server:
    # Stoore rooms and the clients inside each room
    Rooms = {}  # Format: {room_name: [client1, client2, ...]}

    def __init__(self, host, port):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((host, port))
        self.socket.listen(5)
        print("Server listening for connections")

    # Constantly listen for new client connections
    def listen(self):
        while True:
            client, addr = self.socket.accept()
            print("Connection from: " + str(addr))
            
            info = client.recv(1024).decode()
            name, room = info.split(":", 1)
            
            newClient = {'client_name': name, 'client_socket': client, 'room': room}
            
            # Create the room if it doesn't exist
            if room not in Server.Rooms:
                Server.Rooms[room] = []
                
            # Add the new client to the room
            Server.Rooms[room].append(newClient)
            
            # Notify the room that a new user has joined
            self.broadcast_message(name, room, f"{name} has joined the room!")
            
            Thread(target=self.handle_new_client, args=(newClient,)).start()
    
    # Handle messages and disconnections from a specific client
    def handle_new_client(self, client):
        name = client['client_name']
        room = client['room']
        client_socket = client['client_socket']
        
        try:
            while True:
                try:
                    message = client_socket.recv(1024).decode()
                    
                    if not message.strip():
                        raise ConnectionError("Empty message received")
                    
                    if message.strip() == name + ": bye":
                        self.broadcast_message(name, room, f"{name} has left the chat!")
                        self.remove_client_from_room(client, room)
                        client_socket.close()
                        break
                    elif message.strip() == name + ": leaving room":
                        self.broadcast_message(name, room, f"{name} has left the room.")
                        self.remove_client_from_room(client, room)
                        break
                    else:
                        self.broadcast_message(name, room, message)
                    
                    logger.info(f"[{room}] {message}")
                    
                except ConnectionError:
                    # Handle case where client disconnects unexpectedly
                    self.broadcast_message(name, room, f"{name} has left the room!")
                    self.remove_client_from_room(client, room)
                    client_socket.close()
                    break
        except Exception as e:
            print(f"Error handling client {name} in room {room}: {e}")
            self.remove_client_from_room(client, room)
            try:
                client_socket.close()
            except:
                pass
    
    # Remove a clientt from their current room
    def remove_client_from_room(self, client, room):
        if room in Server.Rooms and client in Server.Rooms[room]:
            Server.Rooms[room].remove(client)
            if not Server.Rooms[room]:
                del Server.Rooms[room]
    
    # Send a message to all users in th same room except the sender
    def broadcast_message(self, sender, room, message):
        if room in Server.Rooms:
            for client in Server.Rooms[room]:
                if client['client_name'] != sender:
                    try:
                        client['client_socket'].send(message.encode())
                    except:
                        # Remove clients that failed to receive the messagee
                        Server.Rooms[room].remove(client)

if __name__ == '__main__':
    server = Server('127.0.0.1', 5000)
    server.listen()
