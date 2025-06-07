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

                except socket.error:
                    if self.running:
                        print("Socket error occurred while accepting connection.")
        
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
                

                




