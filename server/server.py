import socket
import threading
import json
import time
import os
import sys
import select
import logging
from datetime import datetime
import psutil

# Add parent directory to path so we can import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.messages import MessageType, format_message, parse_message, serialize_message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Chat-Server")

# Constants
TCP_PORT = 5000
UDP_PORT = 5001
HOST = '127.0.0.1'  # localhost
USER_DB_FILE = 'user_db.json'
MAX_CLIENTS = 100
BUFFER_SIZE = 1024
HEARTBEAT_INTERVAL = 10  # seconds

class ChatServer:
    def __init__(self):
        # Initialize server state
        self.tcp_clients = {}  # {client_socket: {"username": username, "address": addr}}
        self.udp_client_addresses = {}  # {username: (ip, port)}
        self.tcp_socket = None
        self.udp_socket = None
        self.user_db = self._load_user_db()
        self.lock = threading.Lock()
        self.running = False
        
        # Network monitoring
        self.message_count = 0
        self.start_time = time.time()
        self.network_stats = {
            "bytes_sent": 0,
            "bytes_received": 0,
            "messages_processed": 0,
            "active_connections": 0
        }

    def _load_user_db(self):
        """Load user database from JSON file or create if not exists"""
        try:
            if os.path.exists(USER_DB_FILE):
                with open(USER_DB_FILE, 'r') as f:
                    return json.load(f)
            else:
                # Create a default user database
                default_db = {"users": {}}
                with open(USER_DB_FILE, 'w') as f:
                    json.dump(default_db, f)
                return default_db
        except Exception as e:
            logger.error(f"Error loading user database: {e}")
            return {"users": {}}

    def _save_user_db(self):
        """Save user database to JSON file"""
        try:
            with open(USER_DB_FILE, 'w') as f:
                json.dump(self.user_db, f)
        except Exception as e:
            logger.error(f"Error saving user database: {e}")

    def setup_sockets(self):
        """Set up TCP and UDP sockets"""
        try:
            # Set up TCP socket
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_socket.bind((HOST, TCP_PORT))
            self.tcp_socket.listen(MAX_CLIENTS)
            logger.info(f"TCP server started at {HOST}:{TCP_PORT}")
            
            # Set up UDP socket
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind((HOST, UDP_PORT))
            logger.info(f"UDP server started at {HOST}:{UDP_PORT}")
            
            self.running = True
            return True
        except Exception as e:
            logger.error(f"Error setting up sockets: {e}")
            return False

    def start(self):
        """Start the server with multiple threads for different tasks"""
        if not self.setup_sockets():
            return False
        
        # Start threads
        threading.Thread(target=self.accept_tcp_connections, daemon=True).start()
        threading.Thread(target=self.handle_udp_messages, daemon=True).start()
        threading.Thread(target=self.monitor_network, daemon=True).start()
        threading.Thread(target=self.heartbeat_check, daemon=True).start()
        
        logger.info("Chat server is running. Press Ctrl+C to stop.")
        
        try:
            while self.running:
                cmd = input("Server command (help for commands): ")
                self.handle_server_command(cmd)
        except KeyboardInterrupt:
            logger.info("Server shutdown requested...")
        finally:
            self.shutdown()
        
        return True

    def handle_server_command(self, cmd):
        """Handle commands entered on the server console"""
        cmd = cmd.lower().strip()
        
        if cmd == "help":
            print("Available commands:")
            print("  users - List connected users")
            print("  stats - Show server statistics")
            print("  broadcast <message> - Send message to all users")
            print("  shutdown - Stop the server")
        elif cmd == "users":
            print(f"Connected users ({len(self.tcp_clients)}):")
            for client_data in self.tcp_clients.values():
                print(f"  {client_data['username']} from {client_data['address']}")
        elif cmd == "stats":
            uptime = time.time() - self.start_time
            print(f"Server uptime: {int(uptime)} seconds")
            print(f"Active connections: {len(self.tcp_clients)}")
            print(f"Messages processed: {self.network_stats['messages_processed']}")
            if uptime > 0:
                print(f"Messages per second: {self.network_stats['messages_processed'] / uptime:.2f}")
            print(f"Bytes sent: {self.network_stats['bytes_sent']}")
            print(f"Bytes received: {self.network_stats['bytes_received']}")
        elif cmd.startswith("broadcast "):
            message = cmd[10:]  # Remove "broadcast " prefix
            self.broadcast_message(
                format_message(MessageType.SERVER_NOTIFICATION, "SERVER", message)
            )
            print(f"Broadcast sent: {message}")
        elif cmd == "shutdown":
            print("Shutting down server...")
            self.running = False
        else:
            print("Unknown command. Type 'help' for available commands.")

    def accept_tcp_connections(self):
        """Accept and handle new TCP client connections"""
        while self.running:
            try:
                client_socket, addr = self.tcp_socket.accept()
                threading.Thread(
                    target=self.handle_tcp_client,
                    args=(client_socket, addr),
                    daemon=True
                ).start()
                logger.info(f"New connection from {addr}")
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")
                    time.sleep(1)  # Avoid CPU spinning on errors
                    
    def handle_tcp_client(self, client_socket, address):
        """Handle communication with a TCP client"""
        username = None
        
        try:
            # Wait for authentication
            auth_success = False
            auth_attempts = 0
            
            while not auth_success and auth_attempts < 3:
                # Set a timeout for authentication
                client_socket.settimeout(30)
                
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break
                    
                self.network_stats["bytes_received"] += len(data)
                message_str = data.decode('utf-8')
                logger.debug(f"Auth message received: {message_str}")
                
                # Check if this is a registration message
                is_registration = "registration=true" in message_str
                
                # Parse the regular message parts
                message = parse_message(message_str.split(":registration=true")[0] if is_registration else message_str)
                
                if not message or message["type"] != MessageType.AUTH:
                    client_socket.send(serialize_message(
                        format_message(MessageType.AUTH_FAIL, "SERVER", "Authentication required")
                    ).encode('utf-8'))
                    auth_attempts += 1
                    continue
                
                username = message["sender"]
                password = message["content"]
                
                # Handle based on registration or login
                if is_registration:
                    # Registration request
                    with self.lock:
                        if username in self.user_db["users"]:
                            client_socket.send(serialize_message(
                                format_message(MessageType.AUTH_FAIL, "SERVER", "Username already exists")
                            ).encode('utf-8'))
                        else:
                            self.user_db["users"][username] = password
                            self._save_user_db()
                            auth_success = True
                            logger.info(f"New user registered: {username}")
                else:
                    # Login request
                    with self.lock:
                        if username in self.user_db["users"] and self.user_db["users"][username] == password:
                            auth_success = True
                            logger.info(f"User logged in: {username}")
                        else:
                            client_socket.send(serialize_message(
                                format_message(MessageType.AUTH_FAIL, "SERVER", "Invalid credentials")
                            ).encode('utf-8'))
                            auth_attempts += 1
            
            if not auth_success:
                client_socket.send(serialize_message(
                    format_message(MessageType.AUTH_FAIL, "SERVER", "Authentication failed after multiple attempts")
                ).encode('utf-8'))
                client_socket.close()
                return
                
            # Authentication successful
            client_socket.send(serialize_message(
                format_message(MessageType.AUTH_SUCCESS, "SERVER", f"Welcome, {username}!")
            ).encode('utf-8'))
            
            # Reset timeout to None (blocking mode) for regular operation
            client_socket.settimeout(None)
            
            # Register client
            with self.lock:
                self.tcp_clients[client_socket] = {"username": username, "address": address, "last_active": time.time()}
                self.network_stats["active_connections"] = len(self.tcp_clients)
            
            # Broadcast join notification
            join_msg = format_message(MessageType.JOIN, "SERVER", f"{username} has joined the chat")
            self.broadcast_message(join_msg, exclude=client_socket)
            
            # Main message loop
            while self.running:
                readable, _, _ = select.select([client_socket], [], [], 0.5)
                
                if client_socket in readable:
                    data = client_socket.recv(BUFFER_SIZE)
                    if not data:
                        break
                    
                    self.network_stats["bytes_received"] += len(data)
                    message_str = data.decode('utf-8')
                    message = parse_message(message_str)
                    
                    if not message:
                        continue
                    
                    # Update last active timestamp
                    with self.lock:
                        if client_socket in self.tcp_clients:
                            self.tcp_clients[client_socket]["last_active"] = time.time()
                    
                    # Process message based on type
                    # Process message based on type
                    if message["type"] == MessageType.CHAT:
                        # Regular chat message, broadcast to all
                        logger.debug(f"Broadcasting chat message from {username}: {message['content']}")
                        self.broadcast_message(message)  # Remove source=client_socket parameter
                        self.network_stats["messages_processed"] += 1
                    elif message["type"] == MessageType.HEARTBEAT:
                        # Respond to heartbeat
                        response = format_message(MessageType.HEARTBEAT, "SERVER", "ACK")
                        client_socket.send(serialize_message(response).encode('utf-8'))
                    elif message["type"] == MessageType.TYPING:
                        # Forward typing indicator via UDP to save TCP bandwidth
                        typing_msg = format_message(MessageType.TYPING, username, "")
                        self.broadcast_udp_message(typing_msg)
        
        except Exception as e:
            logger.error(f"Error handling client {username if username else address}: {e}")
        finally:
            # Clean up when client disconnects
            if client_socket in self.tcp_clients:
                with self.lock:
                    username = self.tcp_clients[client_socket]["username"]
                    del self.tcp_clients[client_socket]
                    if username in self.udp_client_addresses:
                        del self.udp_client_addresses[username]
                    self.network_stats["active_connections"] = len(self.tcp_clients)
            
            try:
                client_socket.close()
            except:
                pass
                
            if username:
                # Broadcast leave notification
                leave_msg = format_message(MessageType.LEAVE, "SERVER", f"{username} has left the chat")
                self.broadcast_message(leave_msg)
                logger.info(f"Client {username} disconnected")
            else:
                logger.info(f"Client {address} disconnected (unauthenticated)")

    def handle_udp_messages(self):
        """Handle incoming UDP messages (typing indicators, etc.)"""
        self.udp_socket.settimeout(0.5)  # Short timeout to check running flag
        
        while self.running:
            try:
                data, addr = self.udp_socket.recvfrom(BUFFER_SIZE)
                self.network_stats["bytes_received"] += len(data)
                
                message_str = data.decode('utf-8')
                message = parse_message(message_str)
                
                if not message:
                    continue
                
                if message["type"] == MessageType.TYPING:
                    # Register client's UDP address for typing indicators
                    username = message["sender"]
                    with self.lock:
                        self.udp_client_addresses[username] = addr
                    
                    # Broadcast typing indicator to other clients
                    self.broadcast_udp_message(message, exclude_addr=addr)
                
            except socket.timeout:
                # This is expected due to the short timeout
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error handling UDP message: {e}")
                    time.sleep(0.1)  # Avoid CPU spinning on errors


    def broadcast_message(self, message, source=None, exclude=None):
        """Broadcast a message to all TCP clients"""
        message_str = serialize_message(message)
        if not message_str:
            return
        
        encoded_message = message_str.encode('utf-8')
        
        with self.lock:
            for client_socket in list(self.tcp_clients.keys()):
                if client_socket != exclude:
                    # Changed this condition - previously it was excluding both the source and exclude
                    # which means messages from the source weren't being broadcast to others
                    try:
                        client_socket.send(encoded_message)
                        self.network_stats["bytes_sent"] += len(encoded_message)
                    except Exception as e:
                        logger.error(f"Error sending to client: {e}")
                        # Client will be removed in the main handler thread

    def broadcast_udp_message(self, message, exclude_addr=None):
        """Broadcast a UDP message to all registered UDP clients"""
        message_str = serialize_message(message)
        if not message_str:
            return
        
        encoded_message = message_str.encode('utf-8')
        
        with self.lock:
            for addr in list(self.udp_client_addresses.values()):
                if addr != exclude_addr:
                    try:
                        self.udp_socket.sendto(encoded_message, addr)
                        self.network_stats["bytes_sent"] += len(encoded_message)
                    except Exception as e:
                        logger.error(f"Error sending UDP message: {e}")

    def heartbeat_check(self):
        """Periodically check client connections and remove inactive ones"""
        while self.running:
            time.sleep(HEARTBEAT_INTERVAL)
            current_time = time.time()
            
            with self.lock:
                inactive_clients = []
                for client_socket, client_data in list(self.tcp_clients.items()):
                    if current_time - client_data["last_active"] > HEARTBEAT_INTERVAL * 3:
                        # Client might be disconnected, try to ping
                        try:
                            heartbeat = format_message(MessageType.HEARTBEAT, "SERVER", "PING")
                            client_socket.send(serialize_message(heartbeat).encode('utf-8'))
                        except:
                            # Failed to send, mark for removal
                            inactive_clients.append(client_socket)
                
                # Remove inactive clients
                for client_socket in inactive_clients:
                    try:
                        username = self.tcp_clients[client_socket]["username"]
                        del self.tcp_clients[client_socket]
                        client_socket.close()
                        
                        # Broadcast leave notification
                        leave_msg = format_message(MessageType.LEAVE, "SERVER", 
                                                 f"{username} has been disconnected (timeout)")
                        self.broadcast_message(leave_msg)
                        logger.info(f"Removed inactive client: {username}")
                    except:
                        pass
                
                self.network_stats["active_connections"] = len(self.tcp_clients)

    def monitor_network(self):
        """Collect and log network statistics"""
        last_log_time = time.time()
        
        while self.running:
            time.sleep(5)  # Log every 5 seconds
            
            current_time = time.time()
            elapsed = current_time - last_log_time
            
            # Get network usage from psutil
            network_io = psutil.net_io_counters()
            
            logger.info(f"Network stats: "
                       f"Active Connections: {self.network_stats['active_connections']}, "
                       f"Messages Processed: {self.network_stats['messages_processed']}, "
                       f"Bytes Sent: {self.network_stats['bytes_sent']}, "
                       f"Bytes Received: {self.network_stats['bytes_received']}, "
                       f"Bytes/s: {(self.network_stats['bytes_sent'] + self.network_stats['bytes_received']) / elapsed if elapsed > 0 else 0:.2f}")
            
            last_log_time = current_time

    def shutdown(self):
        """Clean shutdown of the server"""
        logger.info("Shutting down server...")
        self.running = False
        
        # Notify clients
        shutdown_msg = format_message(MessageType.SERVER_NOTIFICATION, "SERVER", "Server is shutting down")
        self.broadcast_message(shutdown_msg)
        
        # Close client connections
        for client_socket in list(self.tcp_clients.keys()):
            try:
                client_socket.close()
            except:
                pass
        
        # Close server sockets
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
        
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    server = ChatServer()
    server.start()