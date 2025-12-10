from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os,time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		self.fragmentBuffer = bytearray()
		# exercise 1 variables
		self.packetReceived = 0
		self.packetsLost = 0
		self.lastSeq = 0
		self.bytesReceived = 0
		self.startTime = None
  		
		
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		# self.setup = Button(self.master, width=10, padx=3, pady=3)
		# self.setup["text"] = "Setup"
		# self.setup["command"] = self.setupMovie
		# self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=10, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=10, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=10, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
	
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
	
	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		
		if self.startTime:
			duration = time.time() - self.startTime
			
			if duration > 0:
				totalPackets = self.packetReceived + self.packetsLost
				lossRate = (self.packetsLost / totalPackets) if totalPackets > 0 else 0
				dataRate = self.bytesReceived * 8 / duration  # bits per second

				print("\n===== RTP SESSION STATISTICS =====")
				print(f"Packets Received: {self.packetReceived}")
				print(f"Packets Lost: {self.packetsLost}")
				print(f"Loss Rate: {lossRate:.2%}")
				print(f"Data Rate: {dataRate:.2f} bps")
				print("=================================\n")
		self.master.destroy() # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		
		if self.state == self.INIT:
			threading.Thread(target=self.autoSetupPlay).start()
			return

		if self.state == self.READY:
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
    
	def autoSetupPlay(self):
		# STEP 1 — SETUP
		self.sendRtspRequest(self.SETUP)

		# WAIT until rtpSocket exists (openRtpPort has been called)
		while not hasattr(self, "rtpSocket"):
			time.sleep(0.01)   # avoid CPU 100%

		# STEP 2 — PLAY
		threading.Thread(target=self.listenRtp).start()
		self.playEvent = threading.Event()
		self.playEvent.clear()
		self.sendRtspRequest(self.PLAY)
	
	def listenRtp(self):		
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					
					currFrameNbr = rtpPacket.seqNum()
					print("Current Seq Num: " + str(currFrameNbr))
     
					if self.packetReceived == 0:
						self.lastSeq = currFrameNbr
					else:
						if currFrameNbr > self.lastSeq + 1:
							self.packetsLost += (currFrameNbr - self.lastSeq - 1)
							#print("current packet Lost: " + str(self.packetsLost))

					self.packetReceived += 1
					self.lastSeq = currFrameNbr
					self.bytesReceived += len(rtpPacket.getPayload())

					# print("Crreunt received Packets: " + str(self.packetReceived))

					# Extract marker bit (MSB of header[1])
					# Extract marker bit (MSB of header[1])
					marker = (rtpPacket.header[1] >> 7) & 0x01

					payload = rtpPacket.getPayload()

					if marker == 0:
						# Middle fragment → accumulate data
						self.fragmentBuffer.extend(payload)

					else:
						# Last fragment → assemble full JPEG
						self.fragmentBuffer.extend(payload)
						completeFrame = bytes(self.fragmentBuffer)
						self.fragmentBuffer = bytearray()  # reset buffer

						if currFrameNbr > self.frameNbr:
							self.frameNbr = currFrameNbr
							self.updateMovie(self.writeFrame(completeFrame))
			except socket.timeout:
				if self.playEvent.isSet(): 
					break

				if self.teardownAcked == 1:
					try:
						self.rtpSocket.shutdown(socket.SHUT_RDWR)
					except OSError:
						pass    # socket already closed → safe to ignore
					finally:
						try:
							self.rtpSocket.close()
						except:
							pass
					break

			except Exception as e:
				print("Unexpected RTP listener error:", e)
				break
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		#-------------
		# TO COMPLETE
		#-------------
		
		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1
			# Write the RTSP request to be sent.
			# request = ...
			request = f"SETUP {self.fileName} RTSP/1.0"
			request += f"\nCSeq: {self.rtspSeq}"
			request += f"\nTransport: RTP/UDP; client_port= {self.rtpPort}"
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.SETUP
		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1
			# Write the RTSP request to be sent.
			# request = ...
			request = f"PLAY {self.fileName} RTSP/1.0"
			request += f"\nSEeq: {self.rtspSeq}"
			request += f"\nSession: {self.sessionId}"
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PLAY
		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1
			# Write the RTSP request to be sent.
			# request = ...
			request = f"PAUSE {self.fileName} RTSP/1.0"
			request += f"\nSEeq: {self.rtspSeq}"
			request += f"\nSession: {self.sessionId}"				
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.PAUSE
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			# Update RTSP sequence number.
			# ...
			self.rtspSeq += 1
			# Write the RTSP request to be sent.
			# request = ...
			request = f"TEARDOWN {self.fileName} RTSP/1.0"
			request += f"\nSEeq: {self.rtspSeq}"
			request += f"\nSession: {self.sessionId}\n"
			# Keep track of the sent request.
			# self.requestSent = ...
			self.requestSent = self.TEARDOWN
		else:
			return
		
		# Send the RTSP request using rtspSocket.
		request_bytes = request.encode('utf-8')
		self.rtspSocket.send(request_bytes)		
		print('\nData sent:\n' + request)
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						#-------------
						# TO COMPLETE
						#-------------
						# Update RTSP state.
						# self.state = ...
						self.state = self.READY
						# Open RTP port.
						self.openRtpPort() 
					elif self.requestSent == self.PLAY:
						self.state = self.PLAYING
						self.startTime = time.time()
					elif self.requestSent == self.PAUSE:
						self.state = self.READY
						
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT
						
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1 
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		#-------------
		# TO COMPLETE
		#-------------
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		
		try:
			# Bind the socket to the address using the RTP port given by the client user
			self.state=self.READY
			self.rtpSocket.bind(('',self.rtpPort))
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()
