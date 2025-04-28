# room_manager.py

def get_rooms():
    """Reads all available rooms from storage file."""
    try:
        with open("chat_rooms.txt", "r") as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        # If the file doesn't exist yet, create an empty one
        open("chat_rooms.txt", "w").close()
        return []

def add_room(room_name):
    """Adds a new room to storage if it doesn't already exist."""
    rooms = get_rooms()
    if room_name not in rooms:
        with open("chat_rooms.txt", "a") as file:
            file.write(f"{room_name}\n")
        return True
    return False  # Room already exists
