import logging
import numpy as np
from killerbee import KillerBee
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import time

# Žurnāla konfigurācija
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Konstantes
KANĀLS = 15  # Zigbee kanāls
ILGUMS = 60  # Uzraudzības laiks sekundēs
IERĪCE = "1:3"  # Sniffer ierīce
EXPECTED_HEADER = b"\xAA\xBB"  # Injektora galvēne

# Nakagami sadalījuma parametri
M = 0.8
OMEGA = 0.3

# Grafiku faili izveide
IZVADES_FAILS_RSSI = "rssi_analysis_with_injector.png"
IZVADES_FAILS_CAPACITY = "capacity_analysis_with_injector.png"

# Dati analīzei
timestamps = []
original_rssi = []
modified_rssi = []
real_capacity = []
theoretical_capacity = []
injection_points = []
jamming_periods = []

# Mainīgie signāla bloķēšanas noteikšanai
last_injection_time = None


def nakagami_fading(m, omega, size=1):
    # Nakagami sadalījuma vērtību ģenerēšana
    return np.random.gamma(shape=m, scale=omega / m, size=size)


def apply_nakagami_rssi(base_rssi, m, omega):
    # Nakagami sadalījuma pielietošana RSSI vērtībai
    fading = nakagami_fading(m=m, omega=omega, size=1)[0]
    return base_rssi + 10 * np.log10(fading)


def decode_rssi(encoded_rssi):
    # Dekodēta RSSI atšifrēšana
    return encoded_rssi - 256 if encoded_rssi > 127 else encoded_rssi


def calculate_capacity_extended(rssi, c_theoretical=250, overhead=0.4, noise_floor=-95, max_snr=40):
    # Caurlaidspējas aprēķins
    snr_db = rssi - noise_floor
    if snr_db < 0:
        return 0

    P_success = max(0.1, min(1.0, snr_db / max_snr))
    Duty_Cycle = max(0.1, min(0.8, snr_db / max_snr))
    capacity = c_theoretical * (1 - overhead) * P_success * Duty_Cycle
    return capacity


def detect_jamming_v2(current_time):
    # Aizsardzības noteikšana, pamatojoties uz intervāliem starp injekcijām
    global last_injection_time, jamming_periods
    expected_interval = 2.0  # Paredzamais maksimālais intervāls starp injekcijām (sekundēs)
    if last_injection_time is not None:
        elapsed_time = (current_time - last_injection_time).total_seconds()
        if elapsed_time > expected_interval:
            # Ja intervāls pārsniedz gaidīto, fiksējam slāpēšanu.
            start_time = last_injection_time
            end_time = current_time
            jamming_periods.append((start_time, end_time))
            logging.warning(f"Jamming Detected: {start_time} - {end_time}")
    last_injection_time = current_time  # Atjauninām laiku, kad veikta pēdējā injekcija


def process_packet(packet):
    # Pakešu apstrāde
    global timestamps, original_rssi, modified_rssi, real_capacity, theoretical_capacity, injection_points, last_injection_time
    
    current_time = datetime.now()
    payload = packet.get("bytes", b"")

    if payload.startswith(EXPECTED_HEADER):
        encoded_rssi = payload[len(EXPECTED_HEADER)]
        rssi = decode_rssi(encoded_rssi)
        injection_points.append((len(timestamps), rssi))
        logging.info(f"Injector: RSSI={rssi} dBm")
        detect_jamming_v2(current_time)
    else:
        rssi = packet.get("rssi", None)
        if rssi is None:
            logging.warning("Packet without RSSI value. Skiped.")
            return
        logging.info(f"Packet: RSSI={rssi} dBm")

    if rssi >= 0:
        logging.warning(f"Excluded packet with positive RSSI: {rssi}")
        return

    nakagami_rssi = apply_nakagami_rssi(rssi, M, OMEGA)
    real_cap = calculate_capacity_extended(rssi)
    theoretical_cap = calculate_capacity_extended(nakagami_rssi)

    timestamps.append(current_time.strftime("%Y-%m-%d %H:%M:%S"))
    original_rssi.append(rssi)
    modified_rssi.append(nakagami_rssi)
    real_capacity.append(real_cap)
    theoretical_capacity.append(theoretical_cap)


def sniff_and_analyze(device, channel, duration):
    # Uzraudzība CC2531 un RSSI paketes apstrāde
    try:
        kb = KillerBee(device=device)
        kb.set_channel(channel)
        logging.info(f"Monitoring on channel {channel} started for {duration} seconds.")
    except Exception as e:
        logging.error(f"Device error: {e}")
        return

    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            packet = kb.pnext()
            if packet:
                process_packet(packet)
        except Exception as e:
            logging.error(f"Packet error: {e}")
    kb.close()
    logging.info("Monitoring is over.")
    plot_results()


def plot_results():
    # Grafiku izveidošana
    if not timestamps:
        logging.warning("Nav datu grafiku izveidei.")
        return

    times_dt = [datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") for ts in timestamps]
    seconds = [(t - times_dt[0]).total_seconds() for t in times_dt]

    # RSSI grafiks
    plt.figure(figsize=(14, 8))
    plt.plot(seconds, original_rssi, label="Oriģinālais RSSI", linestyle="-", color="blue")
    plt.plot(seconds, modified_rssi, label="Modificetais RSSI (Nakagami)", linestyle="--", color="orange")
    plt.scatter(
        [seconds[idx] for idx, _ in injection_points],
        [-90] * len(injection_points),
        color="red",
        alpha=0.7,
        label="Injekcija (RSSI -90)",
        s=50
    )
    for start, end in jamming_periods:
        start_sec = (start - times_dt[0]).total_seconds()
        end_sec = (end - times_dt[0]).total_seconds()
        plt.axvspan(start_sec, end_sec, color="purple", alpha=0.3, label="Injekcijas slāpēšana")

    plt.xlabel("Laiks (sec)", fontsize=12)
    plt.ylabel("RSSI (dBm)", fontsize=12)
    plt.title("RSSI analīze ar injekciju un slāpēšanu", fontsize=14)
    plt.legend(loc="upper right", fontsize=10)
    plt.grid()
    plt.tight_layout()
    plt.savefig(IZVADES_FAILS_RSSI)
    plt.close()

    # Caurlaidspējas grafiks
    plt.figure(figsize=(14, 8))
    plt.plot(seconds, real_capacity, label="Oriģināla caurlaidspēja (kbit/s)", linestyle="-", color="blue")
    plt.plot(seconds, theoretical_capacity, label="Modificeta caurlaidspēja (kbit/s)", linestyle="--", color="orange")
    plt.xlabel("Laiks (sec)", fontsize=12)
    plt.ylabel("Caurlaidspēja (kbit/s)", fontsize=12)
    plt.title("Caurlaidspējas analīze", fontsize=14)
    plt.legend(loc="upper right", fontsize=10)
    plt.grid()
    plt.tight_layout()
    plt.savefig(IZVADES_FAILS_CAPACITY)
    plt.close()


if __name__ == "__main__":
    sniff_and_analyze(IERĪCE, KANĀLS, ILGUMS)
