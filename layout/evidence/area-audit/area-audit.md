| Block | Footprint (um) | bbox (um2) | Drawn (um2) | Fill | Whitespace |
|---|---|---|---|---|---|
| `vco_block` | 172.52 x 184.48 | 31,826 | 12,468 | 39.2 % | 19,358 (60.8 %) |
| `pfd_cp` | 344.98 x 76.55 | 26,406 | 6,083 | 23.0 % | 20,323 (77.0 %) |
| `divider_chain` | 1317.66 x 41.99 | 55,329 | 20,413 | 36.9 % | 34,915 (63.1 %) |
| `lock_detector` | 294.80 x 103.75 | 30,586 | 10,555 | 34.5 % | 20,031 (65.5 %) |

| Block | comp (um2) | comp share | Device band (um) | No-device band (um) | Metal2 tracks | Packed track floor (um) | Metal2 fill over devices |
|---|---|---|---|---|---|---|---|
| `vco_block` | 4,387.1 | 13.78 % | 183.48 | 1.00 | 46 | 34.50 | 5.9 % |
| `pfd_cp` | 1,562.1 | 5.92 % | 49.05 | 27.49 | 56 | 42.00 | 3.0 % |
| `divider_chain` | 1,352.5 | 2.44 % | 26.32 | 15.67 | 53 | 39.75 | 15.9 % |
| `lock_detector` | 757.3 | 2.48 % | 54.10 | 49.65 | 48 | 36.00 | 0.4 % |

| Reference netlist | Devices | Shared-diffusion candidates | Column area freed by merging every one (um2) | Sum W*L (um2) |
|---|---|---|---|---|
| `divider_chain` | 452 | 40 (nfet_03v3: 34, pfet_03v3: 6) | 125.4 | 260.3 |

Metal2 track pitch 0.75 um; device bands coalesced across diffusion gaps < 6.0 um.
