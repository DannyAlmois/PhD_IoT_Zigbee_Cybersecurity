Lai izmantotu palaižprogrammas un simulācijas, nepieciešams:
1. CC2531 — uzraudzības (sniffing) modulis;
2. RZUSBStick — uzbrukuma veikšanai izmantojams modulis;
3. HackRF One — izmanto aizsardzības un pretpasākumu veikšanai;
4. Killerbee Python bibliotēka — nepieciešama, lai nodrošinātu komunikāciju ar IEEE 802.15.4 ierīcēm un veiktu uzbrukumu/simulāciju scenārijus.

Palaižprogrammas apraksts:
1. analyze_dos2601_lat.py - Analizē DoS uzbrukuma rezultātus Zigbee tīklā (RSSI, caurlaidspēja, traucējumi).
2. analyze_rssi_injection5.py - Analizē un uzrauga laikā RSSI Zigbee tīkla, kad tiek veikta pakešu injekcija.
3. analyze_rssi_nakagami260120254.py - Analizē un veica RSSI analīzi, izmantojot Nakagami sadalījumu, lai novērtētu signāla kvalitāti dažādos apstākļos (uzbrukuma laikā, piemēram).
4. attack_jamming1901.py - Ģenerē signāla traucēšana (jamming) uzbrukumu, izmantojot RZUSBStick.
5. attack_jamming_prevent19013.py - Demonstrē signāla traucēšana (jamming) uzbrukuma novēršanu ar CC2531 un HackRF One, aktivējot aizsardzības mehānismus. 
6. create_interference_with_nakagami16.py - Veic pakešu injekcijas uzbrukumu, sutījot mākslīgus traucējumu paketes ar zemāku RSSI vērtību.
7. dos_attack05121.py - Palaiž DoS (Denial of Service) uzbrukumu Zigbee tīklam, simulējot intensīvu pakešu sūtīšanu.
8. dos_prevent18013.py - Aktivē DoS uzbrukuma novēršanas stratēģiju ar HackRF One.
9. hackrf_prevent_inject24011.py - Demonstrē, kā ar HackRF One var novērst pakešu injekcijas uzbrukumu, uzraugot un bloķējot kaitīgo trafiku.
10. jamming_simulation_lat.py - Veic signāla traucēšanas (jamming) uzbrukuma simulāciju laboratorijas apstākļos (RSSI un caurlaidspējas analīze), analizējot tīkla reakciju un drošības mehānismus.
11. packet_inj_sim21011_lat.py - Simulē pakešu injekcijas uzbrukumu, analizējot tīkla reakciju un drošības mehānismus.
12. zigbee_dos_simulation20018_lat.py - Simulē DoS uzbrukumu Zigbee tīklā, analizējot tīkla reakciju un drošības mehānismus.
