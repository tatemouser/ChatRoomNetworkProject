import socket
import threading
import time
import json
import os
import sys
import select
import logging
import getpass
from datetime import datetime

# Check for msvcrt availability on Windows
msvcrt_available = False
if os.name == 'nt':
    try:
        import msvcrt
        msvcrt_available = True
    except ImportError:
        msvcrt_available = False

# Add parent directory to path so we can import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.messages import MessageType, format_message, parse_message, serialize_message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("client.log"),
        logging.StreamHandler(sys.stdout)  # Log to stdout for terminal visibility
    ]
)
logger = logging.getLogger("Chat-Client")

# Constants
TCP_PORT = 5000
UDP_PORT = 5001
SERVER_HOST = '127.0.0.1'  # localhost by default
BUFFER_SIZE = 1024
HEARTBEAT_INTERVAL = 30  # seconds

class ChatClient:
    def __init__(self):
        self.username = None
        self.tcp_socket = None
        self.udp_socket = None
        self.running = False
        self.authenticated = False
        self.last_typing_sent = 0  # Timestamp of last typing indicator
        self.typing_cooldown = 1.0  # Second between typing indicators
        self.last_active_users = set()  # For displaying who's online
        self.heartbeat_last_response = time.time()
        self.lock = threading.Lock()

    def connect(self, host=SERVER_HOST):
        """Connect to the chat server"""
        try:
            # Set up TCP socket
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((host, TCP_PORT))
            logger.info(f"Connected to server at {host}:{TCP_PORT}")
            
            # Set up UDP socket
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Bind to a random port
            self.udp_socket.bind(('0.0.0.0', 0))
            logger.info(f"UDP socket initialized")
            
            self.running = True
            return True
        except Exception as e:
            logger.error(f"Error connecting to server: {e}")
            return False

    def authenticate(self):
        """Handle user authentication (login/registration)"""
        while not self.authenticated and self.running:
            print("\n=== Chat Room Authentication ===")
            print("1. Login")
            print("2. Register")
            print("3. Exit")
            
            choice = input("Choose an option (1-3): ").strip()
            
            if choice == "1":
                # Login
                username = input("Username: ").strip()
                password = getpass.getpass("Password: ")
                
                if self._send_auth(username, password):
                    return True
            elif choice == "2":
                # Register
                username = input("New username: ").strip()
                password = getpass.getpass("New password: ")
                confirm = getpass.getpass("Confirm password: ")
                
                if password != confirm:
                    print("Passwords don't match. Please try again.")
                    continue
                
                if self._send_auth(username, f"REGISTER:{password}"):
                    return True
            elif choice == "3":
                # Exit
                print("Exiting...")
                self.running = False
                return False
            else:
                print("Invalid choice. Please try again.")
        
        return self.authenticated
    
    def _send_auth(self, username, password):
        """Send authentication request to server"""
        try:
            # Determine if this is a registration or login
            is_registration = password.startswith("REGISTER:")
            
            # For registration, we need to format the message differently
            if is_registration:
                # Extract the actual password from the REGISTER prefix
                actual_password = password[9:]  # Skip "REGISTER:"
                auth_msg = format_message(MessageType.AUTH, username, actual_password)
                # Add a registration flag
                auth_msg["registration"] = "true"
            else:
                # Regular login
                auth_msg = format_message(MessageType.AUTH, username, password)
            
            # Manually serialize to include the registration flag if needed
            if is_registration:
                message_str = f"{auth_msg['type']}:{auth_msg['sender']}:{auth_msg['content']}:registration=true"
            else:
                message_str = serialize_message(auth_msg)
                
            self.tcp_socket.send(message_str.encode('utf-8'))
            
            # Debug log what we're sending
            logger.debug(f"Auth message sent: {message_str}")
            
            # Wait for response with timeout
            self.tcp_socket.settimeout(5.0)  # 5 second timeout
            data = self.tcp_socket.recv(BUFFER_SIZE)
            self.tcp_socket.settimeout(None)  # Reset timeout
            
            if not data:
                print("Connection closed by server.")
                self.running = False
                return False
            
            message_str = data.decode('utf-8')
            logger.debug(f"Auth response received: {message_str}")
            message = parse_message(message_str)
            
            if not message:
                print("Invalid response from server.")
                return False
            
            if message["type"] == MessageType.AUTH_SUCCESS:
                print(f"\nAuthentication successful! {message['content']}")
                self.username = username
                self.authenticated = True
                return True
            else:
                print(f"\nAuthentication failed: {message['content']}")
                return False
        except socket.timeout:
            print("\nServer not responding. Please try again.")
            return False
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            print("Connection error during authentication.")
            self.running = False
            return False

    def start(self):
        """Start the client after connection and authentication"""
        if not self.connect():
            return False
        
        if not self.authenticate():
            self.disconnect()
            return False
        
        # Start threads for receiving messages
        threading.Thread(target=self.receive_tcp_messages, daemon=True).start()
        threading.Thread(target=self.receive_udp_messages, daemon=True).start()
        threading.Thread(target=self.heartbeat_thread, daemon=True).start()
        
        # Display welcome message
        self._clear_screen()
        print("\n========================================")
        print(f"Welcome to the Chat Room, {self.username}!")
        print("Type your messages and press Enter to send.")
        print("Type '/help' for available commands.")
        print("========================================\n")
        
        # Main input loop
        try:
            while self.running:
                # Cross-platform input handling
                if os.name == 'nt':  # Windows
                    # Non-blocking input for Windows
                    if msvcrt_available:
                        # Check if input is available
                        if msvcrt.kbhit():
                            # Read all available input until newline
                            input_chars = []
                            while msvcrt.kbhit():
                                char = msvcrt.getwch()
                                if char == '\r':  # Enter key
                                    print()  # Move to next line
                                    user_input = ''.join(input_chars)
                                    self._handle_user_input(user_input)
                                    break
                                else:
                                    print(char, end='', flush=True)
                                    input_chars.append(char)
                        time.sleep(0.1)  # Small sleep to prevent high CPU
                    else:
                        # Fallback for Windows without msvcrt
                        user_input = input()
                        self._handle_user_input(user_input)
                else:  # Unix-like systems
                    # Use select for non-blocking input
                    input_ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                    
                    if input_ready:
                        user_input = sys.stdin.readline().strip()
                        self._handle_user_input(user_input)
                    
        except KeyboardInterrupt:
            print("\nDisconnecting from chat...")
        finally:
            self.disconnect()
        
        return True

    def _handle_user_input(self, user_input):
        """Process user input for messages or commands"""
        if not user_input:
            return
        
        # Handle commands
        if user_input.startswith('/'):
            self._process_command(user_input)
            return
        
        # Regular chat message
        try:
            message = format_message(MessageType.CHAT, self.username, user_input)
            self.tcp_socket.send(serialize_message(message).encode('utf-8'))
            # Print our own message to the screen
            print(f"\033[92m{self.username}: {user_input}\033[0m")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            print("Failed to send message. Server might be down.")
            self.running = False

    def _process_command(self, command):
        """Process client commands"""
        cmd = command.lower().strip()
        
        if cmd == '/help':
            print("\nAvailable commands:")
            print("  /help - Show this help message")
            print("  /clear - Clear the screen")
            print("  /exit - Exit the chat")
            print("  /users - Show active users")
        elif cmd == '/clear':
            self._clear_screen()
        elif cmd == '/exit':
            print("Exiting chat...")
            self.running = False
        elif cmd == '/users':
            print("\nActive users:")
            for user in sorted(self.last_active_users):
                print(f"  {user}")
        else:
            print(f"Unknown command: {command}")

    def receive_tcp_messages(self):
        """Receive and process TCP messages from the server"""
        self.tcp_socket.settimeout(0.5)  # Short timeout to check running flag
        
        while self.running:
            try:
                data = self.tcp_socket.recv(BUFFER_SIZE)
                if not data:
                    print("\nConnection closed by server.")
                    self.running = False
                    break
                
                message_str = data.decode('utf-8')
                message = parse_message(message_str)
                
                if not message:
                    continue
                
                self._process_message(message)
                    
            except socket.timeout:
                # This is expected due to the short timeout
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error receiving TCP message: {e}")
                    print("\nConnection error. Server might be down.")
                    self.running = False
                break

    def receive_udp_messages(self):
        """Receive and process UDP messages (typing indicators, etc.)"""
        self.udp_socket.settimeout(0.5)  # Short timeout to check running flag
        
        while self.running:
            try:
                data, _ = self.udp_socket.recvfrom(BUFFER_SIZE)
                
                message_str = data.decode('utf-8')
                message = parse_message(message_str)
                
                if not message:
                    continue
                
                self._process_message(message)
                    
            except socket.timeout:
                # This is expected due to the short timeout
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error receiving UDP message: {e}")
                    time.sleep(0.1)  # Avoid CPU spinning on errors
    def _process_message(self, message):
        """Process received messages based on type"""
        if message["type"] == MessageType.CHAT:
            # Regular chat message
            sender = message["sender"]
            content = message["content"]
            print(f"\n{sender}: {content}")
            
            # Add to active users
            with self.lock:
                self.last_active_users.add(sender)
                
        elif message["type"] == MessageType.TYPING:
            # Typing indicator
            sender = message["sender"]
            if sender != self.username:
                sys.stdout.write(f"\r{sender} is typing...")
                sys.stdout.flush()
                # Set a timer to clear the typing indicator
                threading.Timer(1.5, self._clear_typing_indicator).start()
        
        elif message["type"] == MessageType.SERVER_NOTIFICATION:
            # Server notification
            content = message["content"]
            print(f"\n\033[93m[SERVER] {content}\033[0m")
            
        elif message["type"] == MessageType.JOIN:
            # User joined
            content = message["content"]
            print(f"\n\033[94m{content}\033[0m")
            
            # Extract username from join message
            if "has joined the chat" in content:
                username = content.split(" has joined")[0]
                with self.lock:
                    self.last_active_users.add(username)
            
        elif message["type"] == MessageType.LEAVE:
            # User left
            content = message["content"]
            print(f"\n\033[91m{content}\033[0m")
            
            # Remove user from active users
            if "has left the chat" in content:
                username = content.split(" has left")[0]
                with self.lock:
                    if username in self.last_active_users:
                        self.last_active_users.remove(username)
                        
        elif message["type"] == MessageType.HEARTBEAT:
            # Update heartbeat response time
            self.heartbeat_last_response = time.time()

    def _clear_typing_indicator(self):
        """Clear the typing indicator from the console"""
        sys.stdout.write("\r" + " " * 50 + "\r")
        sys.stdout.flush()

    def send_typing_indicator(self):
        """Send typing indicator through UDP"""
        current_time = time.time()
        
        # Only send typing indicator if cooldown has passed
        if current_time - self.last_typing_sent > self.typing_cooldown:
            try:
                message = format_message(MessageType.TYPING, self.username, "")
                self.udp_socket.sendto(
                    serialize_message(message).encode('utf-8'),
                    (SERVER_HOST, UDP_PORT)
                )
                self.last_typing_sent = current_time
            except Exception as e:
                logger.error(f"Error sending typing indicator: {e}")

    def heartbeat_thread(self):
        """Send periodic heartbeats to keep connection alive"""
        next_heartbeat = time.time() + HEARTBEAT_INTERVAL
        
        while self.running:
            current_time = time.time()
            
            if current_time >= next_heartbeat:
                try:
                    # Send heartbeat message
                    message = format_message(MessageType.HEARTBEAT, self.username, "PING")
                    self.tcp_socket.send(serialize_message(message).encode('utf-8'))
                    
                    # Check for response timeout
                    if current_time - self.heartbeat_last_response > HEARTBEAT_INTERVAL * 2:
                        logger.warning("Server heartbeat response timeout")
                        print("\nWarning: Server connection might be unstable.")
                    
                    next_heartbeat = current_time + HEARTBEAT_INTERVAL
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {e}")
                    if self.running:
                        print("\nConnection error. Server might be down.")
                        self.running = False
                    break
            
            time.sleep(1)

    def _clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def disconnect(self):
        """Disconnect from the server and clean up"""
        self.running = False
        
        # Close sockets
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except:
                pass
        
        if self.udp_socket:
            try:
                self.udp_socket.close()
            except:
                pass
        
        print("Disconnected from chat server.")

if __name__ == "__main__":
    # Parse command line arguments for server host
    server_host = SERVER_HOST
    if len(sys.argv) > 1:
        server_host = sys.argv[1]
    
    client = ChatClient()
    client.start()
