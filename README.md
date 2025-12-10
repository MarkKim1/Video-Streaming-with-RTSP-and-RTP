# RTSP/RTP Video Streaming System

This project implements a simplified video streaming system using **RTSP** for control messages and **RTP** for transporting JPEG video frames over UDP. The client features a Tkinter-based GUI that mimics a lightweight media player, while the server streams an MJPEG video file one frame at a time. The system was developed for **CS438 – Computer Networks (Lab 4)**.

---

## Features

### 🎬 RTSP Session Control
The client implements the required RTSP methods:
- **SETUP** – Initializes a session and opens the RTP port  
- **PLAY** – Begins receiving RTP packets and rendering frames  
- **PAUSE** – Suspends playback while maintaining session state  
- **TEARDOWN** – Ends session and closes all sockets  

The client UI hides SETUP from the user (as real media players do).  
Pressing **Play** for the first time automatically sends:

1. `SETUP`
2. waits for RTP port initialization  
3. then sends `PLAY`

---

## 📡 RTP Video Streaming & Fragment Reassembly

The server transmits each frame as one or more **RTP packets**.  
Because a JPEG frame can exceed the payload size, frames may arrive **fragmented**.

The client:
- Reads the **marker bit** to detect last fragment  
- Accumulates fragments in a `bytearray`  
- Reassembles them into a full JPEG frame  
- Writes the frame to disk (`cache-<session>.jpg`)  
- Displays it in the Tkinter window

---

## 📊 Session Statistics

On TEARDOWN, the client prints detailed RTP statistics:

- Total packets received  
- Packets lost (sequence number gaps)  
- Loss rate (%)  
- Data rate (bits per second)

Loss and data rate tracking rely on:
- `packetReceived`  
- `packetsLost`  
- `lastSeq`  
- `bytesReceived`  
- `startTime`

---

## 🗂 Project Structure
```bash
├── Client.py
├── Server.py
├── ServerWorker.py        
├── RtpPacket.py
├── movie.Mjpeg
└── README.md
```
---

## ▶️ Running the System

### Start the Server
```bash
python3 Server.py <RTSP-Port>
python3 ClientLauncher.py <Server-Addr> <RTSP-Port> <RTP-Port> <Video-File>
```
