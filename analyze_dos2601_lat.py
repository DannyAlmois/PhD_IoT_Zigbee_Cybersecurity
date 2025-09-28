import logging
import numpy as np
from killerbee import KillerBee
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import csv

# Žurnāla konfigurācija
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Parametri
KANĀLS = 15  # Zigbee kanāls
ILGUMS = 120  # Uzraudzības laiks sekundēs
IERĪCE = "1:3"  # Sniffer ierīce
HEADERS_TO_DETECT = [b"\x01\x01"]  # DoS uzbrukuma galvene
NO_DOS_TIMEOUT = 0.2  # Laiks līdz trokšņa noteikšanai (sekundēs)

# Konstantes
NOISE_FLOOR = -95  # Trokšņa līmenis dBm
C_THEORETICAL = 250  # Teorētiskā caurlaidspēja (kbit/s)
OVERHEAD = 0.4  # Papildu slodze (40%)
MAX_SNR = 40  # Maksimālais SNR (normalizācijai)
M = 0.8  # Nakagami formas parametrs
OMEGA = 0.3  # Vidējā jauda

# Dati analīzei
timestamps = []
original_rssi = []
modified_rssi = []
real_capacity = []
modified_capacity = []
dos_flags = []  # DoS uzbrukumu marķieri
jamming_intervals = []  # Trokšņu periodi [(start_time, end_time)]


def nakagami_fading(m, omega, size=1):
    # Nakagami sadalījuma vērtību ģenerēšana
    return np.random.gamma(shape=m, scale=omega / m, size=size)


def apply_nakagami_rssi(base_rssi, m, omega):
    # Nakagami sadalījuma pielietošana RSSI vērtībai
    fading = nakagami_fading(m=m, omega=omega, size=1)[0]
    return base_rssi + 10 * np.log10(fading)


def calculate_capacity(rssi):
    # Caurlaidspējas aprēķins
    snr_db = rssi - NOISE_FLOOR
    if snr_db < 0:
        return 0
    P_success = max(0.1, min(1.0, snr_db / MAX_SNR))
    Duty_Cycle = max(0.1, min(0.8, snr_db / MAX_SNR))
    capacity = C_THEORETICAL * (1 - OVERHEAD) * P_success * Duty_Cycle
    return capacity


def detect_jamming(last_dos_time, current_time):
    # Pārbauda, vai noticis troksnis
    global jamming_intervals
    if last_dos_time and (current_time - last_dos_time).total_seconds() > NO_DOS_TIMEOUT:
        start_time = last_dos_time + timedelta(seconds=NO_DOS_TIMEOUT)
        end_time = current_time
        jamming_intervals.append((start_time, end_time))
        logging.warning(f"Jamming Detected: {start_time} - {end_time}")


def save_to_csv(filename):
    # Datu saglabāšana CSV failā
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Timestamp", "Oriģinālais RSSI", "Modificētais RSSI", "Reālā caurlaidspēja", "Modificētā caurlaidspēja", "DoS Marķieris"])
        for i in range(len(timestamps)):
            writer.writerow([
                timestamps[i].strftime("%Y-%m-%d %H:%M:%S"),
                original_rssi[i],
                modified_rssi[i],
                real_capacity[i],
                modified_capacity[i],
                dos_flags[i]
            ])
    logging.info(f"Dati saglabāti failā: {filename}")


def sniff_and_analyze(device, channel, duration):
    # Snifferis un datu analīze
    try:
        kb = KillerBee(device=device)
        kb.set_channel(channel)
        logging.info(f"Sākts monitorings uz kanāla {channel} ar ierīci {device}.")
    except Exception as e:
        logging.error(f"Kļūda ierīces inicializācijā: {e}")
        return

    start_time = time.time()
    last_dos_time = None

    while time.time() - start_time < duration:
        try:
            packet = kb.pnext()
            current_time = datetime.now()
            if packet:
                payload = packet.get("bytes", b"")
                rssi = packet.get("rssi", None)
                if rssi is None or rssi > 0:  # Izslēdzam pozitīvās RSSI vērtības
                    continue

                timestamps.append(current_time)
                original_rssi.append(rssi)
                mod_rssi = apply_nakagami_rssi(rssi, M, OMEGA)
                modified_rssi.append(mod_rssi)

                capacity = calculate_capacity(rssi)
                modified_cap = calculate_capacity(mod_rssi)

                real_capacity.append(capacity)
                modified_capacity.append(modified_cap)

                # DoS uzbrukumu apstrāde
                if payload[:2] in HEADERS_TO_DETECT:
                    dos_flags.append(1)
                    logging.info(f"DoS uzbrukums: RSSI={rssi} dBm")
                    last_dos_time = current_time
                else:
                    dos_flags.append(0)

            # Pārbaude uz troksni
            detect_jamming(last_dos_time, current_time)

        except Exception as e:
            logging.error(f"Kļūda paketes apstrādē: {e}")

    kb.close()
    save_to_csv("dos_analysis_data_with_flags.csv")
    logging.info("Monitorings pabeigts.")
    plot_results()


def plot_results():
    # Grafiku izveide un saglabāšana
    if not timestamps:
        logging.warning("Nav datu grafika izveidei.")
        return

    times_seconds = [(ts - timestamps[0]).total_seconds() for ts in timestamps]

    # Vidējās vērtības
    mean_original_rssi = np.mean(original_rssi) if original_rssi else 0
    mean_modified_rssi = np.mean(modified_rssi) if modified_rssi else 0
    mean_real_capacity = np.mean(real_capacity) if real_capacity else 0
    mean_modified_capacity = np.mean(modified_capacity) if modified_capacity else 0

    # RSSI grafiks
    plt.figure(figsize=(12, 6))
    plt.plot(times_seconds, original_rssi, label="Oriģinālais RSSI", color="blue")
    plt.plot(times_seconds, modified_rssi, label="Modificētais RSSI", color="orange")
    plt.scatter(
        [times_seconds[i] for i, flag in enumerate(dos_flags) if flag == 1],
        [original_rssi[i] for i, flag in enumerate(dos_flags) if flag == 1],
        label="DoS uzbrukums",
        color="red",
        marker='x',
        s=50
    )

    # Trokšņa apgabals ar vienreizēju marķieri
    if jamming_intervals:
        jamming_logged = False
        for start, end in jamming_intervals:
            start_sec = (start - timestamps[0]).total_seconds()
            end_sec = (end - timestamps[0]).total_seconds()
            if not jamming_logged:
                plt.axvspan(start_sec, end_sec, color="purple", alpha=0.3, label="Pretpasākuma ierīce")
                jamming_logged = True
            else:
                plt.axvspan(start_sec, end_sec, color="purple", alpha=0.3)

    plt.axhline(y=mean_original_rssi, color="green", linestyle="--", label=f"Vidējais oriģinālais RSSI: {mean_original_rssi:.2f} dBm")
    plt.axhline(y=mean_modified_rssi, color="cyan", linestyle="--", label=f"Vidējais modificētais RSSI: {mean_modified_rssi:.2f} dBm")
    plt.xlabel("Laiks (sekundes)")
    plt.ylabel("RSSI (dBm)")
    plt.title("RSSI analīze un DoS uzbrukumi")
    plt.legend(loc="upper right")
    plt.grid()
    plt.tight_layout()
    plt.savefig("rssi_analysis.png")
    plt.close()

    # Caurlaidspējas grafiks
    plt.figure(figsize=(12, 6))
    plt.plot(times_seconds, real_capacity, label="Reālā caurlaidspēja", color="blue")
    plt.plot(times_seconds, modified_capacity, label="Modificētā caurlaidspēja", color="orange")
    plt.axhline(y=mean_real_capacity, color="green", linestyle="--", label=f"Vidējā reālā caurlaidspēja: {mean_real_capacity:.2f} kbit/s")
    plt.axhline(y=mean_modified_capacity, color="cyan", linestyle="--", label=f"Vidējā modificētā caurlaidspēja: {mean_modified_capacity:.2f} kbit/s")
    plt.xlabel("Laiks (sekundes)")
    plt.ylabel("Caurlaidspēja (kbit/s)")
    plt.title("Caurlaidspējas analīze")
    plt.legend(loc="upper right")
    plt.grid()
    plt.tight_layout()
    plt.savefig("capacity_analysis.png")
    plt.close()

if __name__ == "__main__":
    sniff_and_analyze(device=IERĪCE, channel=KANĀLS, duration=ILGUMS)
