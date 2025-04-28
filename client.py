# client.py
import socket
from threading import Thread
import os
from auth_manager import save_credentials, check_credentials
from room_manager import get_rooms, add_room

class Client:
    # Set up the client, connect to server, and start authentication
    def __init__(self, host, port):
        self.socket = socket.socket()
        self.socket.connect((host, port))
        self.name = self.authenticate()
        
        if self.name:
            self.start_chat()
        else:
            print("Authentication failed. Exiting.")
            os._exit(0)
    
    # After login/signup, start chatting by joining or creating a room
    def start_chat(self):
        self.room = self.select_room()
        if self.room:
            self.talk_to_server()
        else:
            print("Room selection failed. Exiting.")
            os._exit(0)

    # Handles user signup/login authentication
    def authenticate(self):
        while True:
            choice = input("Type 'signup' or 'login': ").lower()
            
            if choice == "signup":
                username = input("Enter username: ")
                password = input("Enter password: ")
                save_credentials(username, password)
                print("Signup successful!")
                return username
                
            elif choice == "login":
                username = input("Enter username: ")
                password = input("Enter password: ")
                if check_credentials(username, password):
                    print("Login successful!")
                    return username
                else:
                    print("Invalid credentials. Try again.")
            else:
                print("Invalid choice. Please type 'signup' or 'login'.")
    
    # Select an existing room or create a new onee
    def select_room(self):
        while True:
            choice = input("Type 'join' to join a room or 'create' to create a new room: ").lower()
            
            if choice == "join":
                rooms = get_rooms()
                if not rooms:
                    print("No rooms available. Please create one.")
                    continue
                
                print("Available rooms:")
                for room in rooms:
                    print(f"- {room}")
                
                room_name = input("Enter room name to join: ")
                if room_name in rooms:
                    return room_name
                else:
                    print("Room not found. Try again.")
            
            elif choice == "create":
                room_name = input("Enter new room name: ")
                add_room(room_name)
                print(f"Room '{room_name}' created successfully!")
                return room_name
            
            else:
                print("Invalid choice. Please type 'join' or 'create'.")

    # Start communicating with the server once authenticated and in a room
    def talk_to_server(self):
        # Send name and room info to the server
        self.socket.send(f"{self.name}:{self.room}".encode())
        
        # Start a thread to constantly receive incoming messages
        self.receive_thread = Thread(target=self.receiveMessage)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        self.send_message()

    # Allow user to send messages to serverr
    def send_message(self):
        print(f"You joined room: {self.room}. Type 'back' to return to room selection or 'bye' to exit.")
        while True:
            clientInput = input("")
            
            if clientInput.lower() == "back":
                # Notify server we are leaving the room
                self.socket.send(f"{self.name}: leaving room".encode())
                
                # Reset connection and let user pick a new room
                self.socket.close()
                self.socket = socket.socket()
                self.socket.connect(("127.0.0.1", 5000))
                self.start_chat()
                return
            
            message = self.name + ": " + clientInput
            self.socket.send(message.encode())

    # Listen for incoming messsages from the server
    def receiveMessage(self):
        while True:
            try:
                serverMessage = self.socket.recv(1024).decode()
                if not serverMessage.strip():
                    return
                print("\033[32m" + serverMessage + "\033[0m")
            except:
                # Socket closed or error
                return

if __name__ == '__main__':
    Client("127.0.0.1", 5000)
