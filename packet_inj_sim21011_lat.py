import random
import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import nakagami
from queue import Queue, Empty
import csv

# Konstantes
TROKSNIS = -95         # Troksnis (dBm)
MAKS_SNR = 40          # Maksimālais SNR, pie kura sasniedzama augsta panākumu varbūtība
C_TEORETISKA = 250     # Maksimālā teorētiskā caurlaidspēja (kbps)
OVERHEAD = 0.4         # Papildu izmaksu daļa

def calculate_capacity(rssi):
    # Aprēķina caurlaidspēju (kbps) atkarībā no RSSI
    snr_db = rssi - TROKSNIS
    if snr_db < 0:
        return 0
    P_success = max(0.1, min(1.0, snr_db / MAKS_SNR))
    Duty_Cycle = max(0.1, min(0.8, snr_db / MAKS_SNR))
    capacity = C_TEORETISKA * (1 - OVERHEAD) * P_success * Duty_Cycle
    return capacity

def apply_fading(rssi, m=0.8, omega=0.3):
    
    ## Piemēro Nakagami sadalījumu RSSI vērtībai
   
    fading_factor = nakagami.rvs(m, scale=omega)
    return rssi + 10 * np.log10(fading_factor)

class PacketInjector:
    # Klase pakešu injekcijai ar zemu RSSI (injektors)
    def __init__(self, packet_queue):
        self.packet_queue = packet_queue

    def inject_packet(self):
        rssi = random.uniform(-90, -85)
        modified_rssi = apply_fading(rssi)
        packet = {
            "source": "Injector",
            "destination": "Broadcast",
            "rssi": rssi,
            "modified_rssi": modified_rssi,
        }
        self.packet_queue.put(packet)
        print(f"Ievietota pakete (Injector) ar RSSI {rssi:.2f} (modificēts: {modified_rssi:.2f})")

class NetworkDevice:
    # Klase haotiski strādājošām ierīcēm
    def __init__(self, device_id, packet_queue):
        self.device_id = device_id
        self.packet_queue = packet_queue

    def send_packet(self):
        rssi = random.uniform(-50, -30)
        modified_rssi = apply_fading(rssi)
        packet = {
            "source": self.device_id,
            "destination": "Broadcast",
            "rssi": rssi,
            "modified_rssi": modified_rssi,
        }
        self.packet_queue.put(packet)
        print(f"{self.device_id} nosūtīja paketi ar RSSI {rssi:.2f} (modificēts: {modified_rssi:.2f})")

class InjectionHandler:
    
    # Klase injekciju atklāšanai un novēršanai.
    # Saglabā oriģinālās un modificētās RSSI vērtības, kā arī aprēķināto caurlaidspēju.
    # Reģistrē arī jamming notikumus, kad injektora paketes tiek noņemtas.
    
    def __init__(self, jamming_efficiency=0.9):
        self.total_injected = 0
        self.removed_injected = 0
        self.rssi_values = []               # Oriģinālie RSSI
        self.modified_rssi_values = []       # Modificētie RSSI
        self.capacities = []                # Caurlaidspēja (aprēķināta no modificētā RSSI)
        self.sources = []                   # Katras paketes avots
        self.jamming_timestamps = []        # Laiki, kad tika veikta novēršana
        self.jamming_efficiency = jamming_efficiency

    def handle_packet(self, packet, current_time):
        rssi = packet.get("rssi", 0)
        modified_rssi = packet.get("modified_rssi", rssi)
        self.rssi_values.append(rssi)
        self.modified_rssi_values.append(modified_rssi)
        self.capacities.append(calculate_capacity(modified_rssi))
        self.sources.append(packet.get("source", "unknown"))
        if packet.get("source") == "Injector":
            self.total_injected += 1
            if random.random() < self.jamming_efficiency:
                self.removed_injected += 1
                self.jamming_timestamps.append(current_time)
                print(f"Noņemta injicētā pakete ar RSSI {rssi:.2f} (modificēts: {modified_rssi:.2f})")

    def get_results(self):
        percentage_removed = (self.removed_injected / self.total_injected * 100
                              if self.total_injected > 0 else 0)
        return {
            "total_injected": self.total_injected,
            "removed_injected": self.removed_injected,
            "percentage_removed": percentage_removed
        }

def filter_injected_packets(timestamps, values, sources, jamming_timestamps, tolerance=0.001, inj_source="Injector"):
    
    # Filtrē datus: ja paketes avots ir "Injector" un tās laiks sakrīt ar kādu no gaismošanas notikumiem (ar nelielu toleranci),
    # tad šādas vērtības tiek izņemtas.

    filt_t = []
    filt_v = []
    for t, v, src in zip(timestamps, values, sources):
        remove = False
        if src == inj_source:
            for jt in jamming_timestamps:
                if abs(t - jt) < tolerance:
                    remove = True
                    break
        if not remove:
            filt_t.append(t)
            filt_v.append(v)
    return filt_t, filt_v

def plot_results(timestamps, rssi_values, modified_rssi_values, capacities_mod, sources, jamming_timestamps, output_prefix):
    
    # Izveido grafikus:
     # 1. RSSI laika gaitā: attēlo oriģinālo un modificēto RSSI ar vidējām vērtībām (visi un atjaunotie).
     # 2. Caurlaidspējas laika gaitā: attēlo gan modificēto caurlaidspēju, gan reālo caurlaidspēju (aprēķinātu no oriģinālā RSSI),
     #    ar vidējām vērtībām (visi un atjaunotie).
    
    if not timestamps:
        print("Nav datu, lai zīmētu grafikus.")
        return

    # RSSI grafiks
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, rssi_values, 'b.-', label='Oriģinālais RSSI (visi paketes)')
    plt.plot(timestamps, modified_rssi_values, 'g.-', label='Modificētais RSSI (visi paketes)')
    avg_ori = np.mean(rssi_values)
    avg_mod = np.mean(modified_rssi_values)
    plt.axhline(avg_ori, color='blue', linestyle='dotted', label=f"Vidējais oriģinālais RSSI ({avg_ori:.2f})")
    plt.axhline(avg_mod, color='green', linestyle='dotted', label=f"Vidējais modificētais RSSI ({avg_mod:.2f})")
    filt_t_ori, filt_rssi = filter_injected_packets(timestamps, rssi_values, sources, jamming_timestamps)
    filt_t_mod, filt_mod = filter_injected_packets(timestamps, modified_rssi_values, sources, jamming_timestamps)
    avg_ori_filt = np.mean(filt_rssi) if filt_rssi else float('nan')
    avg_mod_filt = np.mean(filt_mod) if filt_mod else float('nan')
    plt.axhline(avg_ori_filt, color='blue', linestyle='dashdot', label=f"Atjaunotais oriģinālais RSSI ({avg_ori_filt:.2f})")
    plt.axhline(avg_mod_filt, color='green', linestyle='dashdot', label=f"Atjaunotais modificētais RSSI ({avg_mod_filt:.2f})")
    added_label = False
    for jt in jamming_timestamps:
        if not added_label:
            plt.axvline(jt, color='red', linestyle='--', label="Pretpasākuma darbība")
            added_label = True
        else:
            plt.axvline(jt, color='red', linestyle='--')
    plt.title("RSSI laika gaitā")
    plt.xlabel("Laiks (s)")
    plt.ylabel("RSSI (dBm)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{output_prefix}_rssi.png")
    plt.close()

    # Reālā caurlaidspēja aprēķināta no oriģinālā RSSI
    capacities_real = [calculate_capacity(x) for x in rssi_values]
    filt_t_real, filt_cap_real = filter_injected_packets(timestamps, capacities_real, sources, jamming_timestamps)
    _, filt_cap_mod = filter_injected_packets(timestamps, capacities_mod, sources, jamming_timestamps)
    avg_cap_mod_all = np.mean(capacities_mod)
    avg_cap_mod_filt = np.mean(filt_cap_mod) if filt_cap_mod else float('nan')
    avg_cap_real_all = np.mean(capacities_real)
    avg_cap_real_filt = np.mean(filt_cap_real) if filt_cap_real else float('nan')

    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, capacities_mod, 'm.-', label='Modificētā caurlaidspēja (visi paketes)')
    plt.axhline(avg_cap_mod_all, color='magenta', linestyle='dotted', label=f"Vidējā modificētā caurlaidspēja ({avg_cap_mod_all:.2f})")
    plt.axhline(avg_cap_mod_filt, color='black', linestyle='dashdot', label=f"Atjaunotā modificētā caurlaidspēja ({avg_cap_mod_filt:.2f})")
    plt.plot(timestamps, capacities_real, 'c.-', label='Reālā caurlaidspēja (visi paketes)')
    plt.axhline(avg_cap_real_all, color='cyan', linestyle='dotted', label=f"Vidējā reālā caurlaidspēja ({avg_cap_real_all:.2f})")
    plt.axhline(avg_cap_real_filt, color='orange', linestyle='dashdot', label=f"Atjaunotā reālā caurlaidspēja ({avg_cap_real_filt:.2f})")
    for jt in jamming_timestamps:
        plt.axvline(jt, color='red', linestyle='--')
    plt.title("Caurlaidspēja laika gaitā")
    plt.xlabel("Laiks (s)")
    plt.ylabel("Caurlaidspēja (kbps)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{output_prefix}_capacity.png")
    plt.close()

def save_data_to_csv(timestamps, rssi_values, modified_rssi_values, capacities, sources, output_filename):
    
    # Saglabā datus CSV failā nākotnes trendline analīzei.
    # Kolonnas: Laiks (s), Oriģinālais RSSI, Modificētais RSSI, Caurlaidspēja (kbps), Avots.
    
    with open(output_filename, mode='w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Laiks (s)", "Oriģinālais RSSI", "Modificētais RSSI", "Caurlaidspēja (kbps)", "Avots"])
        for t, r, mr, cap, src in zip(timestamps, rssi_values, modified_rssi_values, capacities, sources):
            writer.writerow([t, r, mr, cap, src])

def main_injector(duration, jamming_efficiency=0.85):
    
    #Galvenā injekciju un apstrādes cilpa.
    #Simulācija darbojas norādītajā laika periodā (piemēram, 10 s).
    
    packet_queue = Queue()
    handler = InjectionHandler(jamming_efficiency)
    injector = PacketInjector(packet_queue)
    devices = [NetworkDevice(f"Ierīce{i}", packet_queue) for i in range(30)]  

    timestamps = []
    start_time = time.time()

    print("Sākas injekcija un apstrāde...")
    while time.time() - start_time < duration:
        injector.inject_packet()
        for device in devices:
            device.send_packet()
        time.sleep(0.1)
        try:
            packet = packet_queue.get_nowait()
            current_time = time.time() - start_time
            handler.handle_packet(packet, current_time)
            timestamps.append(current_time)
        except Empty:
            pass

    print("Injekcija un apstrāde pabeigta.")
    results = handler.get_results()
    print(f"Kopā injicētās paketes: {results['total_injected']}")
    print(f"Noņemtās injicētās paketes: {results['removed_injected']}")
    print(f"Noņemtās paketes procentuālais īpatsvars: {results['percentage_removed']:.2f}%")
    
    plot_results(timestamps, handler.rssi_values, handler.modified_rssi_values,
                 handler.capacities, handler.sources, handler.jamming_timestamps,
                 "injection_results")
    save_data_to_csv(timestamps, handler.rssi_values, handler.modified_rssi_values,
                     handler.capacities, handler.sources, "injection_results_data.csv")

if __name__ == "__main__":
    main_injector(duration=120)
