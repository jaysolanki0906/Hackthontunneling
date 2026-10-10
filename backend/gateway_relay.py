"""
Surface LoRaWAN Gateway Relay
Runs on a Raspberry Pi connected to a LoRa HAT at the station.
Listens for LoRa packets, calls the cloud backend, sends response back.

Requirements: pip install pyserial requests
Adjust SERIAL_PORT to your LoRa module's serial port.
"""
import serial, requests, time

SERIAL_PORT = "/dev/ttyUSB0"   # Windows: "COM3"
BAUD_RATE   = 9600
BACKEND_URL = "http://your-cloud-server/query"  # Replace with your deployed URL

def send_lora(ser: serial.Serial, message: str):
    ser.write((message + "\n").encode("utf-8"))

def main():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Gateway listening on {SERIAL_PORT}...")

    while True:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        print(f"Received from tunnel: {line}")
        try:
            resp = requests.post(BACKEND_URL, json={"fault": line}, timeout=15)
            answer = resp.json().get("response", "Backend error")
        except Exception as e:
            answer = f"Gateway error: {e}"

        print(f"Sending back: {answer[:80]}...")
        send_lora(ser, answer)
        time.sleep(0.5)

if __name__ == "__main__":
    main()
