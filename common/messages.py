# Message types enumeration
class MessageType:
    AUTH = "AUTH"  # Authentication message
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAIL = "AUTH_FAIL"
    CHAT = "CHAT"  # Regular chat message
    TYPING = "TYPING"  # Typing indicator
    SERVER_NOTIFICATION = "SERVER_NOTIFICATION"
    JOIN = "JOIN"  # User joined
    LEAVE = "LEAVE"  # User left
    HEARTBEAT = "HEARTBEAT"  # For fault tolerance

# Helper functions for message formatting
def format_message(msg_type, sender, content="", **kwargs):
    """Format a message as a dictionary with standard fields"""
    message = {
        "type": msg_type,
        "sender": sender,
        "content": content
    }
    # Add any additional fields
    for key, value in kwargs.items():
        message[key] = value
    
    return message

def parse_message(message_str):
    """Parse a message string into its components"""
    try:
        parts = message_str.split(':', 3)
        if len(parts) >= 3:
            msg_type = parts[0]
            sender = parts[1]
            content = parts[2] if len(parts) > 2 else ""
            return {"type": msg_type, "sender": sender, "content": content}
        return None
    except:
        return None

def serialize_message(message_dict):
    """Serialize a message dictionary to string format for transmission"""
    try:
        return f"{message_dict['type']}:{message_dict['sender']}:{message_dict['content']}"
    except KeyError:
        return None