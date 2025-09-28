import logging
import numpy as np
from killerbee import KillerBee
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

KANĀLS = 15
ILGUMС = 120
IERĪCE = "1:3"
IZVADES_FAILS_RSSI = "rssi_analysis_adaptive_jamming.png"
IZVADES_FAILS_CAPACITY = "capacity_analysis_adaptive_jamming.png"
CSV_FAILS = "zigbee_sniffing_results.csv"

# Konstantes
C_THEORETICAL = 250
OVERHEAD = 0.4
NOISE_FLOOR = -95
MAX_SNR = 40
M = 0.8
OMEGA = 0.3
JAMMING_THRESHOLD = 2  # Slieksnis (sekundēs) troksņa noteikšanai
JAMMING_PACKET_HEADER = b"\xFF\xFF"  # Troksņa paketes galvene

# Dati
timestamps = []
real_rssi = []
nakagami_rssi = []
real_capacity = []
theoretical_capacity = []
jamming_intervals = []
jamming_packets = []  # Troksņa paketes marķieri
normal_packets = []  # Parastās paketes marķieri

def nakagami_fading(m, omega, size=1):
    return np.random.gamma(shape=m, scale=omega / m, size=size)

def apply_nakagami_rssi(base_rssi, m, omega):
    fading = nakagami_fading(m=m, omega=omega, size=1)[0]
    return base_rssi + 10 * np.log10(fading)

def calculate_capacity(rssi):
    snr_db = rssi - NOISE_FLOOR
    if snr_db < 0:
        return 0
    P_success = max(0.1, min(1.0, snr_db / MAX_SNR))
    Duty_Cycle = max(0.1, min(0.8, snr_db / MAX_SNR))
    return C_THEORETICAL * (1 - OVERHEAD) * P_success * Duty_Cycle

def detect_jamming(last_packet_time, current_time):
    global jamming_intervals
    if last_packet_time and (current_time - last_packet_time).total_seconds() > JAMMING_THRESHOLD:
        start_time = last_packet_time + timedelta(seconds=JAMMING_THRESHOLD)
        end_time = current_time
        jamming_intervals.append((start_time, end_time))
        logging.warning(f"Jamming Detected: {start_time} - {end_time}")

def save_to_csv(filename):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "Laikspiedols", "Reālais RSSI", "Nakagami RSSI", "Reālā caurlaidspēja", 
            "Teorētiskā caurlaidspēja", "Troksnis", "Troksņa pakete", "Parastā pakete"
        ])
        for i in range(len(timestamps)):
            jamming_flag = any(start <= timestamps[i] <= end for start, end in jamming_intervals)
            writer.writerow([
                timestamps[i].strftime("%Y-%m-%d %H:%M:%S"),
                real_rssi[i],
                nakagami_rssi[i],
                real_capacity[i],
                theoretical_capacity[i],
                int(jamming_flag),  # 1 ja trokšņa laikā, citādi 0
                jamming_packets[i],  # 1 ja troksņa pakete, citādi 0
                normal_packets[i]  # 1 ja parastā pakete, citādi 0
            ])
    logging.info(f"Dati saglabāti failā: {filename}")

def sniff_and_analyze(device, channel, duration):
    try:
        kb = KillerBee(device=device)
        kb.set_channel(channel)
        logging.info(f"Monitorings sākts uz kanāla {channel} ar ierīci {device}.")
    except Exception as e:
        logging.error(f"Ierīces inicializācijas kļūda: {e}")
        return

    start_time = time.time()
    last_packet_time = None

    while time.time() - start_time < duration:
        try:
            packet = kb.pnext()
            current_time = datetime.now()
            if packet:
                rssi = packet.get("rssi", None)
                payload = packet.get("bytes", b"")

                if rssi is None or rssi > 0:
                    continue

                last_packet_time = current_time
                timestamps.append(current_time)
                real_rssi.append(rssi)
                nakagami_value = apply_nakagami_rssi(rssi, M, OMEGA)
                nakagami_rssi.append(nakagami_value)

                real_cap = calculate_capacity(rssi)
                theo_cap = calculate_capacity(nakagami_value)

                real_capacity.append(real_cap)
                theoretical_capacity.append(theo_cap)

                # Troksņa paketes pārbaude
                is_jamming_packet = 1 if payload[:2] == JAMMING_PACKET_HEADER else 0
                jamming_packets.append(is_jamming_packet)

                # Parasto pakešu fiksēšana
                is_normal_packet = 1 if not is_jamming_packet else 0
                normal_packets.append(is_normal_packet)

                logging.info(f"Laiks={current_time}, RSSI={rssi} dBm, Caurlaidspēja={real_cap:.2f} kbit/s, Troksnis={is_jamming_packet}, Parastā pakete={is_normal_packet}")

            detect_jamming(last_packet_time, current_time)

        except Exception as e:
            logging.error(f"Paketes apstrādes kļūda: {e}")

    kb.close()
    save_to_csv(CSV_FAILS)
    plot_results()

def plot_results():
    if not timestamps:
        logging.warning("Nav datu grafikiem.")
        return

    times_seconds = [(ts - timestamps[0]).total_seconds() for ts in timestamps]

    # Vidējās vērtības
    mean_real_rssi = np.mean(real_rssi) if real_rssi else 0
    mean_nakagami_rssi = np.mean(nakagami_rssi) if nakagami_rssi else 0
    mean_real_capacity = np.mean(real_capacity) if real_capacity else 0
    mean_theoretical_capacity = np.mean(theoretical_capacity) if theoretical_capacity else 0

    # RSSI grafiks
    plt.figure(figsize=(12, 6))
    plt.plot(times_seconds, real_rssi, label="Reālais RSSI", color="blue")
    plt.plot(times_seconds, nakagami_rssi, label="Modificētais RSSI", color="orange")

    label_added = False
    for start, end in jamming_intervals:
        start_sec = (start - timestamps[0]).total_seconds()
        end_sec = (end - timestamps[0]).total_seconds()
        label = "Troksnis" if not label_added else None
        plt.axvspan(start_sec, end_sec, color="purple", alpha=0.3, label=label)
        label_added = True

    normal_packet_times = [times_seconds[i] for i, is_normal in enumerate(normal_packets) if is_normal]
    normal_packet_rssi = [real_rssi[i] for i, is_normal in enumerate(normal_packets) if is_normal]
    plt.scatter(normal_packet_times, normal_packet_rssi, color="green", marker="o", label="Parastās paketes", s=50)

    plt.axhline(y=mean_real_rssi, color="green", linestyle="--", label=f"Vidējais RSSI: {mean_real_rssi:.2f} dBm")
    plt.axhline(y=mean_nakagami_rssi, color="cyan", linestyle="--", label=f"Vidējais modificētais RSSI: {mean_nakagami_rssi:.2f} dBm")
    plt.xlabel("Laiks (sekundes)")
    plt.ylabel("RSSI (dBm)")
    plt.title("RSSI analīze un troksnis")
    plt.legend()
    plt.grid()
    plt.tight_layout()
    plt.savefig(IZVADES_FAILS_RSSI)
    plt.close()

    # Caurlaidspējas grafiks
    plt.figure(figsize=(12, 6))
    plt.plot(times_seconds, real_capacity, label="Reālā caurlaidspēja", color="blue")
    plt.plot(times_seconds, theoretical_capacity, label="Modificēta caurlaidspēja", color="orange")
    plt.axhline(y=mean_real_capacity, color="green", linestyle="--", label=f"Vidējā reālā caurlaidspēja: {mean_real_capacity:.2f} kbit/s")
    plt.axhline(y=mean_theoretical_capacity, color="cyan", linestyle="--", label=f"Vidējā modificēta caurlaidspēja: {mean_theoretical_capacity:.2f} kbit/s")
    plt.xlabel("Laiks (sekundes)")
    plt.ylabel("Caurlaidspēja (kbit/s)")
    plt.title("Caurlaidspējas analīze")
    plt.legend()
    plt.grid()
    plt.tight_layout()
    plt.savefig(IZVADES_FAILS_CAPACITY)
    plt.close()

if __name__ == "__main__":
    sniff_and_analyze(IERĪCE, KANĀLS, ILGUMС)
