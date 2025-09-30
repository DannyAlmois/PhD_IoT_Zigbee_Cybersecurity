Lai izmantotu palaižprogrammas un simulācijas, nepieciešams:
CC2531 — uzraudzības (sniffing) modulis;
RZUSBStick — uzbrukuma veikšanai izmantojams modulis;
HackRF One — izmanto aizsardzības un pretpasākumu veikšanai;
Killerbee Python bibliotēka — nepieciešama, lai nodrošinātu komunikāciju ar IEEE 802.15.4 ierīcēm un veiktu uzbrukumu/simulāciju scenārijus.

analyze_dos2601_lat.py - Analizē DoS uzbrukuma rezultātus Zigbee tīklā (RSSI, caurlaidspēja, traucējumi).
analyze_rssi_injection5.py - Analizē un uzrauga laikā RSSI Zigbee tīkla, kad tiek veikta pakešu injekcija.
analyze_rssi_nakagami260120254.py - Analizē un veica RSSI analīzi, izmantojot Nakagami sadalījumu, lai novērtētu signāla kvalitāti dažādos apstākļos (uzbrukuma laikā, piemēram).
attack_jamming1901.py - Ģenerē signāla traucēšana (jamming) uzbrukumu, izmantojot RZUSBStick.
attack_jamming_prevent19013.py - Demonstrē signāla traucēšana (jamming) uzbrukuma novēršanu ar CC2531 un HackRF One, aktivējot aizsardzības mehānismus. 
create_interference_with_nakagami16.py - Veic pakešu injekcijas uzbrukumu, sutījot mākslīgus traucējumu paketes ar zemāku RSSI vērtību.
dos_attack05121.py - Palaiž DoS (Denial of Service) uzbrukumu Zigbee tīklam, simulējot intensīvu pakešu sūtīšanu.
dos_prevent18013.py - Aktivē DoS uzbrukuma novēršanas stratēģiju ar HackRF One.
hackrf_prevent_inject24011.py - Demonstrē, kā ar HackRF One var novērst pakešu injekcijas uzbrukumu, uzraugot un bloķējot kaitīgo trafiku.
jamming_simulation_lat.py - Veic signāla traucēšanas (jamming) uzbrukuma simulāciju laboratorijas apstākļos (RSSI un caurlaidspējas analīze), analizējot tīkla reakciju un drošības mehānismus.
packet_inj_sim21011_lat.py - Simulē pakešu injekcijas uzbrukumu, analizējot tīkla reakciju un drošības mehānismus.
zigbee_dos_simulation20018_lat.py - Simulē DoS uzbrukumu Zigbee tīklā, analizējot tīkla reakciju un drošības mehānismus.
