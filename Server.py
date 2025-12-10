import sys, socket

from ServerWorker import ServerWorker

class Server:	
	
	def main(self):
		try:
			SERVER_PORT = int(sys.argv[1])
		except:
			print("[Usage: Server.py Server_port]\n")
		rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		rtspSocket.bind(('', SERVER_PORT))
		rtspSocket.listen(5)        

		try:
			while True:
				clientInfo = {}
				clientInfo['rtspSocket'] = rtspSocket.accept()
				ServerWorker(clientInfo).run()		
		except KeyboardInterrupt:
			rtspSocket.close()
			print("\nServer Shut Down")
		finally:
			rtspSocket.close()
			sys.exit(0)

if __name__ == "__main__":
	(Server()).main()


