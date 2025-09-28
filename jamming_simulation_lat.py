import random
import time
from multiprocessing import Process, Queue, Manager, Value
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Headless režīms – grafiki tiek saglabāti uz diska
import matplotlib.pyplot as plt
from scipy.stats import nakagami
import csv

# Konstantes
TROKSNIS = -95         # Troksnis (dBm)
MAKS_SNR = 40          # Maksimālais SNR, pie kura tiek sasniegta augsta panākumu varbūtība
C_TEORETISKA = 250     # Maksimālā teorētiskā caurlaidspēja (kbps)
OVERHEAD = 0.4         # Papildu izmaksu daļa

def calculate_capacity(rssi):
    # Aprēķina caurlaidspēju (kbps) atkarībā no RSSI
    snr_db = rssi - TROKSNIS
    if snr_db < 0:
        return 0
    P_success = max(0.1, min(1.0, snr_db / MAKS_SNR))
    Duty_Cycle = max(0.1, min(0.8, snr_db / MAKS_SNR))
    return C_TEORETISKA * (1 - OVERHEAD) * P_success * Duty_Cycle

def apply_nakagami(rssi, m=0.8, omega=0.3):
    # Pielietots Nakagami sadalījums, lai iegūtu modificēto RSSI
    nak_factor = nakagami.rvs(m, scale=omega)
    return rssi + 10 * np.log10(nak_factor)

class Jammer:
    # Signāla traucēšana (jamming) paketu ģenerēšanai
    def __init__(self, packet_queue):
        self.packet_queue = packet_queue
        self.active = Value('b', True)

    def jam_packets(self, duration):
        # Ģenerē traucēšanas paketes noteiktu laika periodu
        start_time = time.time()
        while time.time() - start_time < duration:
            if self.active.value:
                rssi_val = random.uniform(-90, -70)
                packet = {
                    "source": "Jammer",
                    "destination": "Broadcast",
                    "rssi": rssi_val,
                    "modified_rssi": apply_nakagami(rssi_val)
                }
                print(f"Jammer ierīce nosūta paketi: {packet}")
                self.packet_queue.put(packet)
                time.sleep(0.1)
            else:
                time.sleep(0.1)

class AntiJammer:
    # AntiJammer atklāšanai un novēršanai
    def __init__(self, packet_queue, jammer, jamming_efficiency=0.8, shared_data=None):
        self.packet_queue = packet_queue
        self.jammer = jammer
        self.jamming_efficiency = jamming_efficiency
        self.successful_counters = 0
        self.failed_counters = 0
        self.total_packets = 0

        # Izmantojam Manager koplietojamos sarakstus
        if shared_data is None:
            manager = Manager()
            self.timestamps = manager.list()
            self.original_rssi = manager.list()
            self.modified_rssi = manager.list()
            self.capacities = manager.list()
            self.sources = manager.list()
            self.jamming_timestamps = manager.list()
        else:
            self.timestamps = shared_data['timestamps']
            self.original_rssi = shared_data['original_rssi']
            self.modified_rssi = shared_data['modified_rssi']
            self.capacities = shared_data['capacities']
            self.sources = shared_data['sources']
            self.jamming_timestamps = shared_data['jamming_timestamps']

    def monitor_and_counter(self, duration):
        # Monitorē paketes un mēģina novērst traucēšanu.
        start_time = time.time()
        while time.time() - start_time < duration:
            if not self.packet_queue.empty():
                packet = self.packet_queue.get()
                print(f"AntiJammer saņem paketi: {packet}")
                current_time = time.time() - start_time
                self.timestamps.append(current_time)
                self.original_rssi.append(packet["rssi"])
                self.modified_rssi.append(packet["modified_rssi"])
                self.capacities.append(calculate_capacity(packet["modified_rssi"]))
                self.sources.append(packet.get("source", "unknown"))
                self.total_packets += 1
                if packet["source"] == "Jammer":
                    if random.random() < self.jamming_efficiency:
                        self.successful_counters += 1
                        self.jamming_timestamps.append(current_time)
                        print("AntiJammer: Traucēšana novērsta! Aizkavēju jammer darbību uz 3 sekundēm.")
                        self.jammer.active.value = False
                        time.sleep(3)
                        self.jammer.active.value = True
                    else:
                        self.failed_counters += 1
            time.sleep(0.05)
        # Procentu aprēķins visiem paketes
        overall_success_percent = (self.successful_counters / self.total_packets * 100) if self.total_packets > 0 else 0
        overall_failure_percent = (self.failed_counters / self.total_packets * 100) if self.total_packets > 0 else 0
        print(f"Kopā apstrādāto paketu skaits: {self.total_packets}")
        print(f"Veiksmīgi novērstie traucēšanas notikumi: {self.successful_counters} ({overall_success_percent:.2f}%)")
        print(f"Neveiksmīgi novērstie traucēšanas notikumi: {self.failed_counters} ({overall_failure_percent:.2f}%)")
        # Aprēķinam procentuālo daļu nojamto (jammed) paketu starp tikai jammer pakētēm
        jammer_total = self.successful_counters + self.failed_counters
        if jammer_total > 0:
            jammer_success_percent = (self.successful_counters / jammer_total * 100)
        else:
            jammer_success_percent = 0
        print(f"Traucēšanas paketes veiksmīgi novērstās procentuāli (tikai Jammer): {jammer_success_percent:.2f}%")

    def plot_results(self, output_prefix="results"):
        # Veido grafikus ar matplotlib 
        if not self.timestamps:
            print("Nav datu, lai zīmētu grafikus.")
            return

        def filter_jammer(ts, values, srcs, jamming_ts, tolerance=0.01, jammer_source="Jammer"):
            filt_ts = []
            filt_vals = []
            for t, v, src in zip(ts, values, srcs):
                remove = False
                if src == jammer_source:
                    for jt in jamming_ts:
                        if abs(t - jt) < tolerance:
                            remove = True
                            break
                if not remove:
                    filt_ts.append(t)
                    filt_vals.append(v)
            return filt_ts, filt_vals

        # --- RSSI grafiks ---
        plt.figure(figsize=(10, 6))
        plt.plot(self.timestamps, self.original_rssi, 'b.-', label='Oriģinālais RSSI (visi paketes)')
        plt.plot(self.timestamps, self.modified_rssi, 'g.-', label='Modificētais RSSI (visi paketes)')
        avg_ori_all = np.mean(self.original_rssi)
        avg_mod_all = np.mean(self.modified_rssi)
        plt.axhline(avg_ori_all, color='blue', linestyle='dotted', label=f"Vidējais oriģinālais RSSI ({avg_ori_all:.2f})")
        plt.axhline(avg_mod_all, color='green', linestyle='dotted', label=f"Vidējais modificētais RSSI ({avg_mod_all:.2f})")
        filt_ts_ori, filt_ori = filter_jammer(self.timestamps, self.original_rssi, self.sources, self.jamming_timestamps)
        filt_ts_mod, filt_mod = filter_jammer(self.timestamps, self.modified_rssi, self.sources, self.jamming_timestamps)
        avg_ori_filt = np.mean(filt_ori) if filt_ori else float('nan')
        avg_mod_filt = np.mean(filt_mod) if filt_mod else float('nan')
        plt.axhline(avg_ori_filt, color='blue', linestyle='dashdot', label=f"Atjaunotais oriģinālais RSSI ({avg_ori_filt:.2f})")
        plt.axhline(avg_mod_filt, color='green', linestyle='dashdot', label=f"Atjaunotais modificētais RSSI ({avg_mod_filt:.2f})")
        for jt in self.jamming_timestamps:
            plt.axvline(jt, color='red', linestyle='--')
        plt.title("RSSI laika gaitā")
        plt.xlabel("Laiks (s)")
        plt.ylabel("RSSI (dBm)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{output_prefix}_rssi.png")
        plt.close()

        # --- Caurlaidspējas grafiks ---
        capacities_real = [calculate_capacity(x) for x in self.original_rssi]
        avg_cap_mod_all = np.mean(self.capacities)
        avg_cap_real_all = np.mean(capacities_real)
        _, filt_cap_mod = filter_jammer(self.timestamps, self.capacities, self.sources, self.jamming_timestamps)
        _, filt_cap_real = filter_jammer(self.timestamps, capacities_real, self.sources, self.jamming_timestamps)
        avg_cap_mod_filt = np.mean(filt_cap_mod) if filt_cap_mod else float('nan')
        avg_cap_real_filt = np.mean(filt_cap_real) if filt_cap_real else float('nan')

        plt.figure(figsize=(10, 6))
        plt.plot(self.timestamps, self.capacities, 'm.-', label='Modificētā caurlaidspēja (visi paketes)')
        plt.axhline(avg_cap_mod_all, color='magenta', linestyle='dotted', label=f"Vidējā modificētā caurlaidspēja ({avg_cap_mod_all:.2f})")
        plt.axhline(avg_cap_mod_filt, color='black', linestyle='dashdot', label=f"Atjaunotā modificētā caurlaidspēja ({avg_cap_mod_filt:.2f})")
        plt.plot(self.timestamps, capacities_real, 'c.-', label='Reālā caurlaidspēja (visi paketes)')
        plt.axhline(avg_cap_real_all, color='cyan', linestyle='dotted', label=f"Vidējā reālā caurlaidspēja ({avg_cap_real_all:.2f})")
        plt.axhline(avg_cap_real_filt, color='orange', linestyle='dashdot', label=f"Atjaunotā reālā caurlaidspēja ({avg_cap_real_filt:.2f})")
        for jt in self.jamming_timestamps:
            plt.axvline(jt, color='red', linestyle='--')
        plt.title("Caurlaidspējas laika gaitā")
        plt.xlabel("Laiks (s)")
        plt.ylabel("Caurlaidspēja (kbps)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(f"{output_prefix}_capacity.png")
        plt.close()

    def save_csv(self, output_filename="results_data.csv"):
        """
        Saglabā datus CSV failā nākotnes trendline analīzei.
        Kolonnas: Laiks (s), Oriģinālais RSSI, Modificētais RSSI, Caurlaidspēja (kbps), Avots.
        """
        with open(output_filename, mode='w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Laiks (s)", "Oriģinālais RSSI", "Modificētais RSSI", "Caurlaidspēja (kbps)", "Avots"])
            for t, r, mr, cap, src in zip(self.timestamps, self.original_rssi, self.modified_rssi, self.capacities, self.sources):
                writer.writerow([t, r, mr, cap, src])

class SimulatedDevice:
    # Klase ierīces ZigBee paketes ģenerēšanai
    def __init__(self, device_id, packet_queue):
        self.device_id = device_id
        self.packet_queue = packet_queue

    def generate_packet(self):
        # Izveidots pakets ar normālu RSSI
        rssi = random.uniform(-50, -30)
        modified_rssi = apply_nakagami(rssi)
        packet = {
            "source": self.device_id,
            "destination": "Broadcast",
            "rssi": rssi,
            "modified_rssi": modified_rssi,
        }
        print(f"Ierīce {self.device_id} nosūta paketi: {packet}")
        self.packet_queue.put(packet)

    def run(self, duration):
        # Ģenerē paketes noteiktu laika periodu
        start_time = time.time()
        while time.time() - start_time < duration:
            self.generate_packet()
            time.sleep(random.uniform(1, 3))

def main():
    try:
        duration = int(input("Ievadi simulācijas ilgumu sekundēs: "))
        num_devices = int(input("Ievadi ierīču skaitu tīklā: "))
    except Exception as e:
        print(f"Kļūda ievadē: {e}")
        return

    packet_queue = Queue()

    # Izveido simulācijas ierīču procesus
    device_processes = [
        Process(target=SimulatedDevice(f"Device{i}", packet_queue).run, args=(duration,))
        for i in range(1, num_devices + 1)
    ]

    jammer = Jammer(packet_queue)
    jammer_process = Process(target=jammer.jam_packets, args=(duration,))

    # Izveidojam Manager, lai koplietotu datus starp procesiem
    manager = Manager()
    shared_data = {
        'timestamps': manager.list(),
        'original_rssi': manager.list(),
        'modified_rssi': manager.list(),
        'capacities': manager.list(),
        'sources': manager.list(),
        'jamming_timestamps': manager.list()
    }

    antijammer = AntiJammer(packet_queue, jammer, jamming_efficiency=0.8, shared_data=shared_data)
    antijammer_process = Process(target=antijammer.monitor_and_counter, args=(duration,))

    try:
        for p in device_processes:
            p.start()
        jammer_process.start()
        antijammer_process.start()

        for p in device_processes:
            p.join()
        jammer_process.join()
        antijammer_process.join()

        antijammer.plot_results(output_prefix="sim_results")
        antijammer.save_csv(output_filename="sim_results_data.csv")
    except Exception as e:
        print(f"Kļūda simulācijas laikā: {e}")

    print("Simulācija pabeigta. Grafiki saglabāti, dati saglabāti CSV failā.")

if __name__ == "__main__":
    main()
