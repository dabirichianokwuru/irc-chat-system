import socket
import sys
import threading
import time
from typing import Dict, List, Set


class IRCServer:
    def __init__(self, host='localhost', port=6667):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False

        #Data structures to manage clients and rooms
        self.clients: Dict[socket.socket, Dict] = {} # Dictionary to hold client data
        self.rooms: Dict[str, Set[socket.socket]] = {}  # Dictionary to hold rooms and their clients
        self.nicknames: Dict[str, socket.socket] = {}  # Map nicknames to sockets

        self.lock = threading.Lock()  # Lock for thread-safe operations

    def start(self):
        #Start the server
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #set the socket option to reuse the address
            self.socket.settimeout(1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)  # Listen for incoming connections, allowing a backlog of 5 connections
            self.running = True

            print(f"IRC Server started on {self.host}:{self.port}")
            print("Waiting for clients to connect...")


            while self.running:
                try:
                    client_socket, address = self.socket.accept() #accept a new client connection, where client_socket is the socket object for the client and address is the address of the client
                    print(f"Connected by {address}")

                    #Start a new thread for each client
                    client_thread = threading.Thread(target=self.handle_client, args=(client_socket, address)) # Create a new thread for each client
                    client_thread.daemon = True  # Set the thread as a daemon so it exits when the main program exits
                    client_thread.start()

                except socket.timeout:
                    continue

                except socket.error:
                    if self.running:
                        print("Socket error occurred while accepting connection.")
                    break
        
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.shutdown()

    def handle_client(self, client_socket, address):
        #Handle individual slient connections
        try:
            client_socket.send(b"NICK: Enter your nickname: ") # Prompt for nickname and send the string as a sequence of bytes
            nickname_data = client_socket.recv(1024).decode('utf-8').strip()  # Receive the nickname from the client
            if not nickname_data:
                client_socket.close()
                return
            
            nickname = nickname_data.replace('NICK ', '') #Replace the NICK command with an empty string to get the nickname


            #check if the nickname is already in use
            with self.lock:
                if nickname in self.nicknames:
                    client_socket.send(b"ERROR: Nickname already in use.\n")
                    client_socket.close()
                    return
                
                #Register the client
                self.clients[client_socket] = {
                    'nickname': nickname,
                    'address': address,
                    'rooms': set()  # Set to hold the rooms the client is in
                }

            client_socket.send(f"Welcome: Hello {nickname}! Type HELP for commands.\n".encode())
            print(f"Client {nickname} connected from {address}")
                

            while self.running:
                try:
                    data = client_socket.recv(1024).decode('utf-8').strip()  # Receive data from the client
                    if not data:
                        break  # If no data, client has disconnected

                    if not self.process_message(client_socket, data):# Process the received message
                        break  

                except socket.error:
                    break

        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            self.disconnect_client(client_socket)

    def process_message(self, client_socket, message):
        #Process client messages according to the IRC protocol
        try:

            if not message:
                return True  # If message is empty, just return

            parts = message.split(' ', 2)  # Split the message into command and arguments
            command = parts[0].upper()  # Get the command in uppercase

            if command == 'CREATE' and len(parts) >= 2:
                self.create_room(client_socket, parts[1])
            elif command == 'JOIN' and len(parts) >= 2:
                self.join_room(client_socket, parts[1])
            elif command == 'LEAVE' and len(parts) >= 2:
                self.leave_room(client_socket, parts[1])
            elif command == 'LIST':
                self.list_rooms(client_socket)
            elif command == 'WHO' and len(parts) >= 2:
                self.list_room_members(client_socket, parts[1])
            elif command == 'MSG' and len(parts) >= 3:
                room_name = parts[1]
                message_text = parts[2]
                self.send_room_message(client_socket, room_name, message_text)
            elif command == 'QUIT':
                return False  # Indicate to disconnect the client
            elif command == 'HELP':
                self.send_help(client_socket)
            else:
                client_socket.send(b"ERROR: Unknown command. Type HELP for commands.\n")

            return True  # Indicate that the message was processed successfully
        
        except Exception as e:
            nickname = "Unknown"
            if client_socket in self.clients:
                nickname = self.clients[client_socket]['nickname']
            print(f"Error processing message from {nickname}: {e}")
            client_socket.send(b"ERROR: Failed to process command.\n")
            return True  # Continue processing other messages

    def create_room(self, client_socket, room_name):
        #Create a new chat room
        with self.lock:
            if room_name in self.rooms:
                client_socket.send(f"ERROR: Room '{room_name}' already exists.\n".encode())
            else:
                self.rooms[room_name] = set() # Set to hold clients in the room\
                nickname = self.clients[client_socket]['nickname'] #set the nickname of the client
                client_socket.send(f"Room '{room_name}' created by {nickname}.\n".encode())
                print(f"Room '{room_name}' created by {nickname}.")

    def join_room(self, client_socket, room_name):
        #Join a client to a room
        with self.lock:
            if room_name not in self.rooms:
                client_socket.send(f"ERROR: Room '{room_name}' does not exist.\n".encode())
                return
            
            nickname = self.clients[client_socket]['nickname']
            self.rooms[room_name].add(client_socket) # Add the client to the room
            self.clients[client_socket]['rooms'].add(room_name) # Add the room to the client's list of rooms


            client_socket.send(f"SUCCESS: Joined room '{room_name}'\n".encode())

            #Notify other clients in the room
            join_msg = f"NOTIFICATION: {nickname} has joined the room '{room_name}'.\n"
            self.broadcast_to_room(room_name, join_msg, client_socket)
            print(f"{nickname} joined room '{room_name}'.")

    def leave_room(self, client_socket, room_name):
        #Remove a client from a room
        with self.lock:
            if room_name not in self.rooms:
                client_socket.send(f"ERROR: Room '{room_name}' does not exist.\n".encode())
                return
            
            if client_socket not in self.rooms[room_name]:
                client_socket.send(f"ERROR: You are not in room '{room_name}'.\n".encode())
                return
            
            nickname = self.clients[client_socket]['nickname']
            self.rooms[room_name].remove(client_socket) # Remove the client from the room
            self.clients[client_socket]['rooms'].remove(room_name) # Remove the room from the client's list of rooms

            client_socket.send(f"SUCCESS: Left room '{room_name}'\n".encode())

            #Notify other clients in the room
            leave_msg = f"NOTIFICATION: {nickname} has left the room '{room_name}'.\n"
            self.broadcast_to_room(room_name, leave_msg, client_socket)
            print(f"{nickname} left room '{room_name}'.")


    def list_rooms(self, client_socket):
        #List all available rooms
        with self.lock:
            if not self.rooms:
                client_socket.send(b"INFO: No rooms available.\n")
            else:
                room_list = "ROOMS:\n"
                for room_name, members in self.rooms.items():
                    room_list += f" - {room_name} ({len(members)} members)\n" # Get the name of each room and the number of members in it
                client_socket.send(room_list.encode())

    def list_room_members(self, client_socket, room_name):
        #List members of a specific room
        with self.lock:
            if room_name not in self.rooms:
                client_socket.send(f"ERROR: Room '{room_name}' does not exist.\n".encode())
                return
            
            members = self.rooms[room_name]
            if not members:
                client_socket.send(f"INFO: No members in room '{room_name}'.\n".encode())
            else:
                member_list = f"Members in room '{room_name}':\n"
                for member_socket in members:
                    nickname = self.clients[member_socket]['nickname']
                    member_list += f" - {nickname}\n" # Get the nickname of each member in the room
                client_socket.send(member_list.encode())

    def send_room_message(self, client_socket, room_name, message):
        #Send a message to all clients in a specific room
        with self.lock:
            if room_name not in self.rooms:
                client_socket.send(f"ERROR: Room '{room_name}' does not exist.\n".encode())
                return
            
            if client_socket not in self.rooms[room_name]:
                client_socket.send(f"ERROR: You are not in room '{room_name}'.\n".encode())
                return
            
            nickname = self.clients[client_socket]['nickname']
            full_message = f"[{room_name}] {nickname}: {message}\n"
            self.broadcast_to_room(room_name, full_message, exclude=client_socket)
            
            client_socket.send(f"MESSAGE_SENT: [{room_name}] {message}\n".encode())

    def broadcast_to_room(self, room_name, message, exclude=None):
        #Broadcast a message to all members of a room
        if room_name not in self.rooms:
            return
        
        for client_socket in self.rooms[room_name].copy():
            if client_socket != exclude:
                try:
                    client_socket.send(message.encode())
                except:
                    #client disconnected, remove from room
                    with self.lock:
                        if room_name in self.rooms:
                            self.rooms[room_name].discard(client_socket)  # Remove disconnected client from the room]

    def send_help(self, client_socket):
        #Send help message to the client
        help_message = (
            "Available commands:\n"
            " - CREATE <room_name>: Create a new room.\n"
            " - JOIN <room_name>: Join an existing room.\n"
            " - LEAVE <room_name>: Leave a room.\n"
            " - LIST: List all available rooms.\n"
            " - WHO <room_name>: List members of a room.\n"
            " - MSG <room_name> <message>: Send a message to a room.\n"
            " - QUIT: Disconnect from the server.\n"
            " - HELP: Show this help message.\n"
        )
        client_socket.send(help_message.encode())

    def disconnect_client(self, client_socket):
        #Disconnect a client and clean up
        with self.lock:
            if client_socket not in self.clients:
                try:
                    client_socket.close()  # Close the client socket if it was already removed
                except:
                    pass
                return  # Client already disconnected
            
            nickname = self.clients[client_socket]['nickname']
            rooms = self.clients[client_socket]['rooms'].copy()


            #Remove from all rooms
            for room_name in rooms:
                if room_name in self.rooms:
                    self.rooms[room_name].discard(client_socket)
                    # Notify other clients in the room
                    leave_msg = f"NOTIFICATION: {nickname} disconnected.\n"
                    self.broadcast_to_room(room_name, leave_msg)

            #Clean up client data
            if client_socket in self.clients:
                del self.clients[client_socket]
            if nickname in self.nicknames:
                del self.nicknames[nickname]  # Remove nickname mapping

            print(f"Client {nickname} disconnected")

            try:
                client_socket.close()  # Close the client socket
            except:
                pass

    def shutdown(self):
        #Shutdown the server
        print("\nShutting down the server...")
        self.running = False

        #Disconnect all clients
        with self.lock:
            for client_socket in list(self.clients.keys()):
                try:
                    client_socket.send(b"SERVER: Server is shutting down.\n")
                    client_socket.close()
                except:
                    pass

        if self.socket:
            self.socket.close()
        print("Server shut down complete.")

def main():
        #Main function to start the server
        server = IRCServer()

        try:
            server.start()
        except KeyboardInterrupt:
            print("\nReceived interrupt signal")
        finally:
            server.shutdown()

    
if __name__ == "__main__":
    main()  # Start the server when the script is run directly





