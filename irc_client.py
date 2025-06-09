import socket
import threading
import sys

class IRCClient:
    def __init__(self, host='localhost', port=6667):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.nickname = ""

    def connect(self):
        #Connect to the IRC server

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            
            print(f"Connected to IRC server at {self.host}:{self.port}") 

            # Handle nickname registration
            self.register_nickname()
            
            # Start receiving messages in a separate thread
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()   

            return True 
        
        except Exception as e:
            print(f"Failed to connect to IRC server: {e}")
            return False
        
    def register_nickname(self):
        #Register the nickname with the IRC server
        try:
            # Wait for server prompt
            response = self.socket.recv(1024).decode('utf-8')
            print(response, end='')
            
            # Get nickname from user
            while True:
                nickname = input().strip()
                if nickname:
                    self.nickname = nickname
                    self.socket.send(f"NICK {nickname}".encode())
                    break
                else:
                    print("Please enter a valid nickname: ", end='')
        except Exception as e:
            print(f"Error during nickname registration: {e}")
            self.connected = False

    def receive_messages(self):
        #Receive and display messages from the IRC server
        while self.connected:
            try:
                message = self.socket.recv(1024).decode('utf-8')    
                if not message:
                    break

                # Print the received message
                print(message, end='')

                #Check for server shutdown or error messages
                if "Server is shutting down" in message or "ERROR" in message:
                    print("Server is shutting down or an error occurred.")
                    self.connected = False
                    break

            except socket.error:
                if self.connected:
                    print("Connection lost to server.")
                    break
            except Exception as e:
                print(f"Error receiving message: {e}")
                break

        self.connected = False

    def send_command(self, command):
        #Send a command to the server
        try:
            if not self.connected:
                print("Not connected to server")
                return False
            
            self.socket.send(command.encode())
            return True
        
        except Exception as e:
            print(f"Error sending command: {e}")
            self.connected = False
            return False
        
    def run(self):
        #main client loop
        if not self.connect():
            return
        
        print("\n" + "=" * 50)
        print("IRC CLIENT - Type 'help' for commands or 'quit' to exit")
        print("="*50)

        try:
            while self.connected:
                try:
                    #Get user input
                    user_input = input(f"[{self.nickname}] > ").strip()

                    if not user_input:
                        continue

                    #handle commands
                    if user_input.lower() == 'quit':
                        self.send_command('QUIT')
                        break
                    elif user_input.lower() == 'help':
                        self.show_help()
                        continue
                    elif user_input.lower() == 'clear':
                        import os
                        os.system('cls' if os.name == 'nt' else 'clear')
                        continue

                    #send the command to the server
                    if not self.send_command(user_input):
                        break

                except KeyboardInterrupt:
                    print("\nDisconnecting....")
                    self.send_command('QUIT')
                    break
                except EOFError:
                    print("\nDisconnecting...")
                    break
        finally:
            self.disconnect()

    def show_help(self):
        #Display help information
        help_text = help_text = """
LOCAL COMMANDS:
  help                   - Show this help
  clear                  - Clear screen
  quit                   - Disconnect and exit

SERVER COMMANDS:
  CREATE <room_name>     - Create a new room
  JOIN <room_name>       - Join an existing room
  LEAVE <room_name>      - Leave a room
  LIST                   - List all rooms
  WHO <room_name>        - List members in a room
  MSG <room_name> <text> - Send message to room

EXAMPLES:
  CREATE general
  JOIN general
  MSG general Hello everyone!
  WHO general
  LEAVE general
  LIST
        """
        print(help_text)

    def disconnect(self):
        #Disconnects from the server
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        print("Disconnected from IRC server.")


def main():
        #Main function
        print("IRC Client")
        print("=========")

        #Get server details
        host = input("Enter server host (default: localhost): ").strip()
        if not host:
            host = 'localhost'

        port_input = input("Enter server port (default: 6667): ").strip()
        try:
            port = int(port_input) if port_input else 6667
        except ValueError:
            port = 6667
            print("Invalid port, using default 6667.")

        #Create and run the client
        client = IRCClient(host, port)
        client.run()

if __name__ == "__main__":
    main()


                    