# auth_manager.py

def save_credentials(username, password):
    """Save a new username and password to the credentials file."""
    with open("user_credentials.txt", "a") as file:
        file.write(f"{username}:{password}\n")
    return True

def check_credentials(username, password):
    """Verify a username and password against stored credentials."""
    try:
        with open("user_credentials.txt", "r") as file:
            for line in file:
                stored_username, stored_password = line.strip().split(":")
                if username == stored_username and password == stored_password:
                    return True
    except FileNotFoundError:
        # No user credentials file exists yet
        pass
    return False
