import socket
import threading
import time

# Define constants for the server address and port.  Using localhost and a non-standard port.
SERVER_ADDRESS = '127.0.0.1'  # Localhost
SERVER_PORT = 2900  # Using a non-standard port for MCP.  MCP traditionally uses 2900.

# -------------------
# MCP Server Function
# -------------------
def mcp_server():
    """
    Starts a simple MCP server that listens for connections and responds to basic commands.
    This server is multi-threaded to handle multiple clients concurrently.
    """
    # Create a socket object.  Use IPv4 and TCP.
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Bind the socket to the specified address and port.
        server_socket.bind((SERVER_ADDRESS, SERVER_PORT))
        # Listen for incoming connections.  The '1' indicates the maximum number of queued connections.
        server_socket.listen(1)
        print(f"MCP Server listening on {SERVER_ADDRESS}:{SERVER_PORT}")

        while True:
            # Accept a connection from a client.  This blocks until a client connects.
            client_socket, client_address = server_socket.accept()
            print(f"Accepted connection from {client_address[0]}:{client_address[1]}")
            # Create a new thread to handle the client connection.
            client_thread = threading.Thread(target=handle_client, args=(client_socket,))
            # Start the thread.
            client_thread.start()

    except Exception as e:
        print(f"Error starting server: {e}")
    finally:
        # Clean up the socket to prevent resource leaks.  This block will execute
        # even if an exception occurs.
        if server_socket:
            server_socket.close()
            print("Server socket closed.")

# -----------------------
# Handle Client Function
# -----------------------
def handle_client(client_socket):
    """
    Handles communication with a connected client.  This function runs in a separate thread.

    Args:
        client_socket: The socket object for the connected client.
    """
    try:
        while True:
            # Receive data from the client.  This blocks until data is received.
            data = client_socket.recv(1024)  # Receive up to 1024 bytes
            if not data:
                # If no data is received, the client has likely disconnected.
                print("Client disconnected.")
                break

            # Decode the received data (which is in bytes) into a string.
            message = data.decode('utf-8').strip()  # Remove leading/trailing whitespace
            print(f"Received from client: {message}")

            # Process the message and generate a response.
            response = process_message(message)

            # Encode the response string into bytes and send it back to the client.
            client_socket.send(response.encode('utf-8'))

    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        # Clean up the client socket.  This is important to free up resources.
        client_socket.close()

# -----------------------
# Process Message Function
# -----------------------

def process_message(message):
    """
    Processes the received message and returns an appropriate response.
    This function implements the basic MCP command handling logic.

    Args:
        message: The message received from the client (string).

    Returns:
        The response message (string).
    """
    # Basic MCP command structure: <command> <argument>
    parts = message.split()
    if not parts:
        return "ERROR: No command received.\n"

    command = parts[0].upper()  # Convert to uppercase for case-insensitivity

    if command == "HELLO":
        if len(parts) > 1:
            name = " ".join(parts[1:])  # Allow for multi-word names
            return f"OK Hello {name}, welcome to the server!\n"
        else:
            return "OK Hello, welcome to the server!\n"
    elif command == "PING":
        return "OK PONG\n"
    elif command == "TIME":
        import datetime
        now = datetime.datetime.now()
        return f"OK The current time is {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
    elif command == "BYE":
        return "OK Goodbye!\n"
    elif command == "ECHO":
        if len(parts) > 1:
          text = " ".join(parts[1:])
          return f"OK {text}\n"
        else:
          return "ERROR: No text to echo.\n"
    elif command == "UPTIME":
        import time
        # Access the start time of the server.
        uptime_seconds = time.time() - start_time
        # Convert seconds to a readable format (days, hours, minutes, seconds)
        days = int(uptime_seconds // (24 * 3600))
        uptime_seconds %= (24 * 3600)
        hours = int(uptime_seconds // 3600)
        uptime_seconds %= 3600
        minutes = int(uptime_seconds // 60)
        seconds = int(uptime_seconds % 60)

        uptime_string = f"OK Server uptime: {days} days, {hours} hours, {minutes} minutes, {seconds} seconds\n"
        return uptime_string
    else:
        return "ERROR: Unknown command.\n"

# -------------------
# MCP Client Function
# -------------------
def mcp_client():
    """
    Starts a simple MCP client that connects to the server and sends commands.
    """
    # Create a socket object.  Use IPv4 and TCP.
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Connect to the server.
        client_socket.connect((SERVER_ADDRESS, SERVER_PORT))
        print(f"Connected to MCP server at {SERVER_ADDRESS}:{SERVER_PORT}")

        while True:
            # Get input from the user.
            message = input("Enter MCP command (or 'quit' to exit): ")
            if message.lower() == 'quit':
                break

            # Send the message to the server.  Encode the string as bytes.
            client_socket.send(message.encode('utf-8'))

            # Receive the response from the server.
            data = client_socket.recv(1024)
            if not data:
                print("Server disconnected.")
                break
            response = data.decode('utf-8').strip()
            print(f"Received from server: {response}")

    except Exception as e:
        print(f"Error connecting to server: {e}")
    finally:
        # Clean up the socket.
        client_socket.close()
        print("Client socket closed.")

if __name__ == "__main__":
    # Determine if the user wants to run the server or the client.
    role = input("Enter 'server' or 'client' to run: ").lower()
    if role == "server":
        # Store the start time of the server
        start_time = time.time()
        mcp_server()
    elif role == "client":
        mcp_client()
    else:
        print("Invalid role. Please enter 'server' or 'client'.")
