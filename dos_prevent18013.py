import logging
import numpy as np
from SoapySDR import Device, SOAPY_SDR_TX
from killerbee import KillerBee
import threading
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# HackRF parametri
ZIGBEE_CHANNEL_FREQ = 2425e6  # Zigbee 15 kanāls
SAMPLE_RATE = 2e6  # Diskretizācijas frekvence
GAIN = 47  # Maksimālais signāla pastiprinājums
JAMMING_DURATION = 10  # Traucējumu noveršanas ilgums sekundēs

# CC2531 parametri
ZIGBEE_CHANNEL = 15
HEADERS_TO_DETECT = [b'\x01\x01']  # DoS paketes galvēne (header)
DETECTION_INTERVAL = 0.05  # Paketes pārbaudes intervāls (sekundēs)

# Globālās mainīgās
stop_event = threading.Event()
jam_event = threading.Event()
packets_detected = 0
packets_jammed = 0
packets_in_jamming = 0

def open_hackrf():
    ## HackRF inicializācijas process
    try:
        sdr = Device(dict(driver="hackrf"))
        sdr.setSampleRate(SOAPY_SDR_TX, 0, SAMPLE_RATE)
        sdr.setFrequency(SOAPY_SDR_TX, 0, ZIGBEE_CHANNEL_FREQ)
        sdr.setGain(SOAPY_SDR_TX, 0, GAIN)
        logging.info("HackRF veiksmīgi inicializēts.")
        return sdr
    except Exception as e:
        logging.error(f"HackRF kļūda: {e}")
        return None

def jam_channel(sdr):
    global packets_in_jamming
    try:
        stream = sdr.setupStream(SOAPY_SDR_TX, "CF32")
        sdr.activateStream(stream)

        logging.info("HackRF: Uzbrukuma novēršanas process")
        start_time = time.time()
        while time.time() - start_time < JAMMING_DURATION:
            noise = (np.random.uniform(-1, 1, int(SAMPLE_RATE)) +
                     1j * np.random.uniform(-1, 1, int(SAMPLE_RATE))).astype(np.complex64)
            sr = sdr.writeStream(stream, [noise], len(noise))
            if sr.ret < 0:
                logging.error("Kļūda trokšņa pārraides laikā.")
            time.sleep(0.05)
        sdr.deactivateStream(stream)
        sdr.closeStream(stream)
        logging.info("HackRF: Novēršanas process pabeigts.")
    except Exception as e:
        logging.error(f"Novēršanas kļuda: {e}")

def sniff_with_cc2531():
   ## Pakešu analīze, izmantojot CC2531 snifferi
    global packets_detected, packets_jammed, packets_in_jamming
    try:
        kb = KillerBee(device="1:2")
        kb.set_channel(ZIGBEE_CHANNEL)
        logging.info(f"Zigbee sniffers CC2531: {ZIGBEE_CHANNEL}.")

        while not stop_event.is_set():
            packet = kb.pnext()
            if packet:
                payload = packet.get("bytes", b"")
                header = payload[:len(HEADERS_TO_DETECT[0])]
                timestamp = datetime.now()

                if header in HEADERS_TO_DETECT:
                    packets_detected += 1
                    if jam_event.is_set():
                        packets_in_jamming += 1
                        logging.info(f"Pakete ir bloķēta: Galvēne={header.hex()}, Время={timestamp}")
                    else:
                        logging.info(f"DoS pakets atklats: Galvēne={header.hex()}, Время={timestamp}")
                        jam_event.set()
                else:
                    logging.debug(f"Paketes bez bloķēšanas: Galvēne={header.hex()}, Время={timestamp}")
            time.sleep(DETECTION_INTERVAL)
    except Exception as e:
        logging.error(f"CC2531 kļuda: {e}")
    finally:
        kb.close()
        logging.info("CC2531 darbības ir aptūreta.")

def main(runtime):
    ## Galvenais atklāšanas un bloķēšanas process.
    global packets_detected, packets_jammed, packets_in_jamming
    sdr = open_hackrf()
    if not sdr:
        logging.error("HackRF neizdevās inicializēt. Programmas pabeigšana.")
        return

    sniff_thread = threading.Thread(target=sniff_with_cc2531)
    sniff_thread.start()

    start_time = time.time()
    try:
        while time.time() - start_time < runtime:
            if jam_event.is_set():
                packets_jammed += 1
                jam_channel(sdr)
                jam_event.clear()
            time.sleep(0.1)
    except KeyboardInterrupt:
        logging.info("Programmas pārtraukšana. Pabeigšana...")
    finally:
        stop_event.set()
        sniff_thread.join()
        if sdr:
            del sdr

        logging.info(f"Atklāto pakešu skaits: {packets_detected}")
        logging.info(f"Novērstu paketes skaits: {packets_jammed}")

if __name__ == "__main__":
    runtime = 120  # Darbības ilgums
    main(runtime)
