import logging
import random
import time
from multiprocessing import Process, Queue, Value, Manager, Event
from queue import Empty
import numpy as np
import matplotlib.pyplot as plt
import csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Константы
NOISE_FLOOR = -95       # Troksnis (dBm)
MAX_SNR = 40            # Maksimālais SNR, pie kura tiek sasniegta augsta panākumu varbūtība
C_THEORETICAL = 250     # Maksimālā teorētiskā caurlaidspēja (kbps)
OVERHEAD = 0.4          # Papildu izmaksu daļa

def nakagami_fading(m, omega, size=1):
    # Pielietots Nakagami sadalījums, lai iegūtu modificēto RSSI
    return np.random.gamma(shape=m, scale=omega / m, size=size)

def apply_nakagami_rssi(base_rssi, m, omega):
    fading = nakagami_fading(m, omega, size=1)[0]
    return base_rssi + 10 * np.log10(fading)

def calculate_capacity(rssi):
   # Aprēķina caurlaidspēju (kbps) atkarībā no RSSI
    snr_db = rssi - NOISE_FLOOR  # Расчёт SNR
    if snr_db < 0:
        return 0
    P_success = max(0.1, min(1.0, snr_db / MAX_SNR))
    Duty_Cycle = max(0.1, min(0.8, snr_db / MAX_SNR))
    capacity = C_THEORETICAL * (1 - OVERHEAD) * P_success * Duty_Cycle
    return capacity

def smooth(data, window_size=5):
    if len(data) < window_size:
        return data
    return np.convolve(data, np.ones(window_size) / window_size, mode='valid')

class ZigBeePacket:
    def __init__(self, source, destination, rssi):
        self.source = source
        self.destination = destination
        self.rssi = rssi
        self.modified_rssi = apply_nakagami_rssi(rssi, m=0.8, omega=0.3)

class DeviceSimulator:
    def __init__(self, device_id, queue_main):
        self.device_id = device_id
        self.queue_main = queue_main

    def run(self, stop_event, start_time):
        while not stop_event.is_set():
            rssi = random.uniform(-50, -40)  # Ierīces ar pieļaujamo RSSI
            packet = ZigBeePacket(self.device_id, "Broadcast", rssi)
            self.queue_main.put(packet)
            logging.info(f"[Ierīce] {self.device_id} -> RSSI={rssi:.2f}, Mod={packet.modified_rssi:.2f}")
            time.sleep(random.uniform(1, 3))
        logging.info(f"[Ierīce] {self.device_id} beidz savu darbību.")

class DosAttacker:
    def __init__(self, queue_main, queue_def):
        self.queue_main = queue_main
        self.queue_def = queue_def

    def run(self, stop_event):
        count = 0
        while not stop_event.is_set():
            rssi = random.uniform(-70, -60)  # RSSI DoS uzbrucējiem
            packet = ZigBeePacket("DoS-Attacker", "Broadcast", rssi)
            self.queue_main.put(packet)
            self.queue_def.put(packet)
            count += 1
            logging.info(f"[DoS] Pakete #{count} -> RSSI={rssi:.2f}, Mod={packet.modified_rssi:.2f}")
            time.sleep(0.5)
        logging.info("[DoS] Atlikušās darbības beigtas.")

class Defender:
    def __init__(self, queue_def, jammer_efficiency):
        self.queue_def = queue_def
        self.jammer_efficiency = jammer_efficiency
        self.detected_packets = Value('i', 0)
        self.jammed_packets = Value('i', 0)

    def run(self, stop_event, start_time, duration, timestamps, original_rssi, modified_rssi, jamming_moments):
        jamming_duration = 0.5  
        last_jamming_end = 0.0
        while not stop_event.is_set():
            try:
                packet = self.queue_def.get(timeout=0.1)
                current_time = time.time() - start_time  
                timestamps.append(current_time)
                original_rssi.append(packet.rssi)
                modified_rssi.append(packet.modified_rssi)
                if packet.source == "DoS-Attacker":
                    with self.detected_packets.get_lock():
                        self.detected_packets.value += 1
                    if random.random() < self.jammer_efficiency:
                        if current_time > last_jamming_end:
                            with self.jammed_packets.get_lock():
                                self.jammed_packets.value += 1
                            jamming_moments.append((current_time, current_time + jamming_duration))
                            last_jamming_end = current_time + jamming_duration
                            logging.info(f"Traucējam DoS paketi pie {current_time:.2f}s, gaismošanas ilgums {jamming_duration} s.")
            except Empty:
                pass
            except Exception as e:
                logging.error(f"[Aizsargs] Kļūda: {e}")
            time.sleep(0.05)
        logging.info("[Aizsargs] Beidz savu darbību.")

def filter_packets_during_jamming(timestamps, values, sources, jamming_moments, dos_source="DoS-Attacker"):
  # Filtrē paketes: ja pakete ir no DoS uzbrucēja un tās laiks atbilst bloķēšanas intervālam, tad tā tiek izslēgta no aprēķina.
    filtered_timestamps = []
    filtered_values = []
    for t, val, src in zip(timestamps, values, sources):
        in_jamming = False
        for interval in jamming_moments:
            start, end = interval
            if start <= t <= end:
                in_jamming = True
                break
        if src == dos_source and in_jamming:
            continue
        filtered_timestamps.append(t)
        filtered_values.append(val)
    return filtered_timestamps, filtered_values

def plot_results(timestamps, original_rssi, modified_rssi, jamming_moments,
                 output_prefix, dos_timestamps, dos_rssi, packet_sources):
    if not timestamps:
        logging.error("Nav savākto datu, lai uzzīmētu grafikus.")
        return

    # Datu izlīdzināšana grafikam
    smoothed_timestamps = smooth(timestamps, window_size=5)
    smoothed_original = smooth(original_rssi, window_size=5)
    smoothed_modified = smooth(modified_rssi, window_size=5)

    # Filtrējam datus: noņemsim DoS paketes, kas saņemtas traucējumu periodos
    filtered_timestamps, filtered_original = filter_packets_during_jamming(
        timestamps, original_rssi, packet_sources, jamming_moments)
    _, filtered_modified = filter_packets_during_jamming(
        timestamps, modified_rssi, packet_sources, jamming_moments)
    
    avg_original = np.mean(original_rssi)
    avg_modified = np.mean(modified_rssi)
    avg_original_filtered = np.mean(filtered_original) if filtered_original else np.nan
    avg_modified_filtered = np.mean(filtered_modified) if filtered_modified else np.nan

    plt.figure(figsize=(10, 6))
    plt.plot(smoothed_timestamps, smoothed_original, label='Oriģinālais RSSI (visi paketes)', color='blue')
    plt.plot(smoothed_timestamps, smoothed_modified, label='Modificētais RSSI (visi paketes)', color='green')
    plt.axhline(y=avg_original, color='blue', linestyle='dotted', 
                label=f'Vidējais oriģinālais RSSI ({avg_original:.2f})')
    plt.axhline(y=avg_modified, color='green', linestyle='dotted', 
                label=f'Vidējais modificētais RSSI ({avg_modified:.2f})')
    plt.axhline(y=avg_original_filtered, color='blue', linestyle='dashdot', 
                label=f'Atjaunots oriģinālais RSSI ({avg_original_filtered:.2f})')
    plt.axhline(y=avg_modified_filtered, color='green', linestyle='dashdot', 
                label=f'Atjaunots modificētais RSSI ({avg_modified_filtered:.2f})')
    if dos_timestamps and dos_rssi:
        plt.scatter(dos_timestamps, dos_rssi, marker='o', color='red', label='DoS Paketes')
    for i, jm in enumerate(jamming_moments):
        if isinstance(jm, tuple):
            start, end = jm
            plt.axvspan(start, end, color='red', alpha=0.3, label='Traucēšanas periods' if i == 0 else None)
        else:
            plt.axvline(x=jm, color='red', linestyle='dashed', label='Traucēšanas brīdis' if i == 0 else None)
    plt.title("RSSI laika gaitā")
    plt.xlabel("Laiks (s)")
    plt.ylabel("RSSI (dBm)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{output_prefix}_rssi.png")
    plt.close()

    # Caurlaidspējas grafiks
    smoothed_cap_original = [calculate_capacity(x) for x in smoothed_original]
    smoothed_cap_modified = [calculate_capacity(x) for x in smoothed_modified]
    all_cap_original = [calculate_capacity(x) for x in original_rssi]
    all_cap_modified = [calculate_capacity(x) for x in modified_rssi]
    avg_cap_original = np.mean(all_cap_original)
    avg_cap_modified = np.mean(all_cap_modified)
    filtered_cap_original = [calculate_capacity(x) for x in filtered_original]
    filtered_cap_modified = [calculate_capacity(x) for x in filtered_modified]
    avg_cap_original_filtered = np.mean(filtered_cap_original) if filtered_cap_original else np.nan
    avg_cap_modified_filtered = np.mean(filtered_cap_modified) if filtered_cap_modified else np.nan

    plt.figure(figsize=(10, 6))
    plt.plot(smoothed_timestamps, smoothed_cap_original, label='Oriģinālā caurlaidspēja (visi paketes)', color='blue')
    plt.plot(smoothed_timestamps, smoothed_cap_modified, label='Modificētā caurlaidspēja (visi paketes)', color='green')
    plt.axhline(y=avg_cap_original, color='blue', linestyle='dotted', 
                label=f'Vidējā oriģinālā caurlaidspēja ({avg_cap_original:.2f})')
    plt.axhline(y=avg_cap_modified, color='green', linestyle='dotted', 
                label=f'Vidējā modificētā caurlaidspēja ({avg_cap_modified:.2f})')
    plt.axhline(y=avg_cap_original_filtered, color='blue', linestyle='dashdot', 
                label=f'Atjaunotā oriģinālā caurlaidspēja ({avg_cap_original_filtered:.2f})')
    plt.axhline(y=avg_cap_modified_filtered, color='green', linestyle='dashdot', 
                label=f'Atjaunotā modificētā caurlaidspēja ({avg_cap_modified_filtered:.2f})')
    for i, jm in enumerate(jamming_moments):
        if isinstance(jm, tuple):
            start, end = jm
            plt.axvspan(start, end, color='red', alpha=0.3, label='Traucēšanas periods' if i == 0 else None)
        else:
            plt.axvline(x=jm, color='red', linestyle='dashed', label='Traucēšanas brīdis' if i == 0 else None)
    plt.title("Caurlaidspēja laika gaitā")
    plt.xlabel("Laiks (s)")
    plt.ylabel("Caurlaidspēja (kbps)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{output_prefix}_capacity.png")
    plt.close()

def save_data_to_csv(timestamps, original_rssi, modified_rssi, output_filename):
    data = []
    for t, orig, mod in zip(timestamps, original_rssi, modified_rssi):
        orig_cap = calculate_capacity(orig)
        mod_cap = calculate_capacity(mod)
        data.append((t, orig, mod, orig_cap, mod_cap))
    data.sort(key=lambda x: x[0])
    with open(output_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Laiks (s)", "Oriģinālais RSSI (dBm)", "Modificētais RSSI (dBm)",
                         "Oriģinālā caurlaidspēja (kbps)", "Modificētā caurlaidspēja (kbps)"])
        writer.writerows(data)

def main():
    duration = 120  # Simulācijas garums
    num_devices = 15
    jammer_efficiency = 1.0  # 100% DoS paketes noveršana

    manager = Manager()
    timestamps = manager.list()
    original_rssi = manager.list()
    modified_rssi = manager.list()
    jamming_moments = manager.list()
    dos_timestamps = manager.list()
    dos_rssi = manager.list()
    packet_sources = manager.list()  # Visas paketes avots

    queue_main = Queue()
    queue_def = Queue()

    stop_event = Event()
    start_time = time.time()

    devices = [DeviceSimulator(f"Ierīce-{i+1}", queue_main) for i in range(num_devices)]
    device_processes = [Process(target=device.run, args=(stop_event, start_time)) for device in devices]

    attacker = DosAttacker(queue_main, queue_def)
    attacker_process = Process(target=attacker.run, args=(stop_event,))

    defender = Defender(queue_def, jammer_efficiency)
    defender_process = Process(target=defender.run, args=(stop_event, start_time, duration, 
                                                            timestamps, original_rssi, modified_rssi, jamming_moments))

    for p in device_processes:
        p.start()
    attacker_process.start()
    defender_process.start()

    while time.time() - start_time < duration:
        try:
            packet = queue_main.get_nowait()
            current_time = time.time() - start_time
            timestamps.append(current_time)
            original_rssi.append(packet.rssi)
            modified_rssi.append(packet.modified_rssi)
            packet_sources.append(packet.source)
            if packet.source == "DoS-Attacker":
                dos_timestamps.append(current_time)
                dos_rssi.append(packet.rssi)
        except Empty:
            pass
        time.sleep(0.1)

    stop_event.set()

    for p in device_processes:
        p.join()
    attacker_process.join()
    defender_process.join()

    timestamps_local = list(timestamps)
    original_rssi_local = list(original_rssi)
    modified_rssi_local = list(modified_rssi)
    jamming_moments_local = list(jamming_moments)
    dos_timestamps_local = list(dos_timestamps)
    dos_rssi_local = list(dos_rssi)
    packet_sources_local = list(packet_sources)

    queue_main.close()
    queue_def.close()
    manager.shutdown()

    logging.info("Simulācija pabeigta. Uzzīmēju rezultātus un saglabāju datus CSV failā...")
    output_prefix = "simulation_results"
    plot_results(timestamps_local, original_rssi_local, modified_rssi_local, jamming_moments_local,
                 output_prefix, dos_timestamps_local, dos_rssi_local, packet_sources_local)
    save_data_to_csv(timestamps_local, original_rssi_local, modified_rssi_local, f"{output_prefix}_data.csv")

    total_detected = defender.detected_packets.value
    total_jammed = defender.jammed_packets.value
    jammed_percentage = (total_jammed / total_detected) * 100 if total_detected > 0 else 0
    logging.info(f"Kopā atklātu DoS paketes: {total_detected}")
    logging.info(f"Kopā traucētu paketes: {total_jammed}")
    logging.info(f"Traucēto paketes procentuālais īpatsvars: {jammed_percentage:.2f}%")

if __name__ == "__main__":
    main()
