def log_message(message):
    print(f"[LOG] {message}")

def handle_error(error_message):
    print(f"[ERROR] {error_message}")

def validate_file_path(file_path):
    import os
    if not os.path.isfile(file_path):
        handle_error(f"File not found: {file_path}")
        return False
    return True

def read_file(file_path):
    if validate_file_path(file_path):
        with open(file_path, 'rb') as f:
            return f.read()
    return None

def write_file(file_path, data):
    with open(file_path, 'wb') as f:
        f.write(data)