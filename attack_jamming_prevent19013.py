import threading
import logging
import time
import random
import numpy as np
from killerbee import KillerBee
from SoapySDR import Device, SOAPY_SDR_TX

# Logging iestatījumi
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Parametri
ZIGBEE_CHANNEL = 15
CC2531_INTERFACE = "1:4"
ZIGBEE_CHANNEL_FREQ = 2425e6  # Zigbee 15 kanāls
SAMPLE_RATE = 2e6  # Diskretizācijas frekvence
GAIN = 47  # Maksimālais signāla pastiprinājums
JAM_HEADER = b"\xFF\xFF\xFF\xFF\xFF"  # Uzbrukuma galvēne (header)
JAMMING_DURATION = 10  # Traucējumu noveršanas ilgums sekundēs
AMPLITUDE = 1.0  # Amplitūda
FREQ_VARIATION = 2e5  # Signāla variācija (200 kHz)
RUNTIME = 120  # Programmas darbības ilgums

stop_signal = threading.Event()
jamming_count = 0  # Paketēs, kas noversti bloķēšanas procesā
detected_packets = 0  # Atrasto paketes skaits

def open_hackrf():
    try:
        sdr = Device(dict(driver="hackrf"))
        logging.info("HackRF veiksmīgi inicializēts.")
        return sdr
    except Exception as e:
        logging.error(f"HackRF inicializācijas kļūda: {e}")
        return None

def jam_zigbee_channel(sdr, freq, duration):
    global jamming_count
    try:
        sdr.setSampleRate(SOAPY_SDR_TX, 0, SAMPLE_RATE)
        sdr.setFrequency(SOAPY_SDR_TX, 0, freq)
        sdr.setGain(SOAPY_SDR_TX, 0, GAIN)

        stream = sdr.setupStream(SOAPY_SDR_TX, "CF32")
        sdr.activateStream(stream)

        logging.info(f"Signāla noveršana {freq / 1e6} МГц.")
        start_time = time.time()

        while time.time() - start_time < duration and not stop_signal.is_set():
            varied_freq = freq + random.uniform(-FREQ_VARIATION, FREQ_VARIATION)
            sdr.setFrequency(SOAPY_SDR_TX, 0, varied_freq)
            noise = (np.random.uniform(-AMPLITUDE, AMPLITUDE, int(SAMPLE_RATE)) +
                     1j * np.random.uniform(-AMPLITUDE, AMPLITUDE, int(SAMPLE_RATE))).astype(np.complex64)
            sr = sdr.writeStream(stream, [noise], len(noise))
            if sr.ret >= 0:
                jamming_count += 1

        sdr.deactivateStream(stream)
        sdr.closeStream(stream)
        logging.info("Noveršanas pabeigta.")
    except Exception as e:
        logging.error(f"Kļuda: {e}")

def sniff_cc2531():
    global detected_packets
    try:
        kb = KillerBee(device=CC2531_INTERFACE)
        kb.set_channel(ZIGBEE_CHANNEL)
        logging.info(f"Zigbee sniffers CC2531: {ZIGBEE_CHANNEL}.")

        while not stop_signal.is_set():
            packet = kb.pnext()
            if packet:
                detected_packets += 1
                header = packet.get("bytes", b"")[:len(JAM_HEADER)]
                logging.info(f"Sniffers: Paketes galvene: {header.hex()}")

                if header.startswith(JAM_HEADER):
                    logging.warning("Atklāts uzbrukuma pakets! Aktivizējam traucējumus.")
                    sdr = open_hackrf()
                    if sdr:
                        jam_zigbee_channel(sdr, ZIGBEE_CHANNEL_FREQ, JAMMING_DURATION)
    except Exception as e:
        logging.error(f"Sniffera kļuda: {e}")
    finally:
        logging.info("Sniffers CC2531 aptūrets.")

def main(runtime):
    start_time = time.time()
    sniff_thread = threading.Thread(target=sniff_cc2531)
    sniff_thread.start()

    while time.time() - start_time < runtime:
        time.sleep(1)

    stop_signal.set()
    sniff_thread.join()
    logging.info(f"Atklāto pakešu skaits: {detected_packets}")
    logging.info(f"Novērstu paketes skaits: {jamming_count}")

if __name__ == "__main__":
    main(RUNTIME)
