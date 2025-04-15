# Chat Room Application

A terminal-based real-time chat application built with Python socket programming for CS 381 Computer Networks course.

## Features

- Socket-based communication (TCP for reliable messaging, UDP for real-time features)
- User authentication (login/registration)
- Real-time chat with typing indicators 
- Server notifications
- Fault tolerance with heartbeat mechanism
- Network monitoring and performance tracking
- Security with password encryption (for user accounts)

## Project Structure

```
chat_room_app/
├── server/
│   ├── server.py         # Main server code
│   └── user_db.json      # User database (created on first run)
├── client/
│   └── client.py         # Client application
├── common/
│   └── messages.py       # Shared message handling utilities
├── README.md             # Documentation
└── requirements.txt      # Project dependencies
```

## Requirements

- Python 3.8 or higher
- Dependencies listed in requirements.txt:
  - cryptography (for future security enhancements)
  - psutil (for network monitoring)

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running the Application

### Starting the Server

```bash
cd server
python server.py
```

The server will start on localhost (127.0.0.1) with:
- TCP port: 5000
- UDP port: 5001

Server commands:
- `users` - List connected users
- `stats` - Show server statistics
- `broadcast <message>` - Send message to all users
- `shutdown` - Stop the server

### Starting the Client

```bash
cd client
python client.py [server_host]
```

If `server_host` is not specified, it defaults to localhost (127.0.0.1).

Client commands (available after login):
- `/help` - Show help message
- `/clear` - Clear the screen
- `/exit` - Exit the chat
- `/users` - Show active users

## Project Requirements Met

1. **Socket Programming:** Uses Python socket library for network communication
2. **Process-to-Process Communication:** Server and clients communicate over the network
3. **Multiple Sockets:** Uses both TCP (reliable messaging) and UDP (typing indicators) sockets
4. **Input from Keyboard:** User input for messaging
5. **Output to File:** Logging to server.log and client.log
6. **Client/Server Architecture:** Centralized server with multiple clients
7. **Network Security:** Authentication with password encryption (stored in JSON)
8. **Fault Tolerance:** Heartbeat mechanism to detect and handle disconnections
9. **Network Monitoring:** Tracking bytes sent/received, active connections, and message stats

## Implementation Details

The application is implemented in Python with the following architecture:

- **Server:** Handles all client connections, authentication, and message routing
  - Maintains a list of connected clients
  - Broadcasts messages to appropriate recipients
  - Handles both TCP (reliable messaging) and UDP (real-time updates) communication

- **Client:** Connects to the server and provides the user interface
  - Handles user authentication (login/registration)
  - Displays incoming messages and notifications
  - Sends chat messages and typing indicators

- **Messages:** Common module shared between client and server
  - Defines message types and formats
  - Provides serialization/deserialization of messages

## Testing

To test the application:

1. Start the server
2. Connect multiple clients from different terminals
3. Register new users or login with existing credentials
4. Exchange messages between clients
5. Test features like typing indicators and server notifications
6. Try disconnecting clients to test fault tolerance

## Future Enhancements

- End-to-end message encryption
- File sharing capabilities
- Group chat rooms
- Message history persistence
- Support for multimedia messages
- Web or GUI-based client interface

## Contributors

- Tate Mouser
- Connor Lane

## License

This project is academic in nature and created for CS 381 Computer Networks course at WKU.