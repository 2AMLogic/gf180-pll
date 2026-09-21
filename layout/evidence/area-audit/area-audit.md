| Block | Footprint (um) | bbox (um2) | Drawn (um2) | Fill | Whitespace |
|---|---|---|---|---|---|
| `vco_block` | 172.52 x 184.48 | 31,826 | 12,468 | 39.2 % | 19,358 (60.8 %) |
| `pfd_cp` | 432.66 x 81.55 | 35,281 | 6,030 | 17.1 % | 29,251 (82.9 %) |
| `divider_chain` | 1317.66 x 100.29 | 132,148 | 27,973 | 21.2 % | 104,175 (78.8 %) |
| `lock_detector` | 119.30 x 62.60 | 7,468 | 2,013 | 27.0 % | 5,455 (73.0 %) |

| Block | comp (um2) | comp share | Device band (um) | No-device band (um) | Metal2 tracks | Packed track floor (um) | Metal2 fill over devices |
|---|---|---|---|---|---|---|---|
| `vco_block` | 4,387.1 | 13.78 % | 183.48 | 1.00 | 46 | 34.50 | 5.9 % |
| `pfd_cp` | 1,562.1 | 4.43 % | 37.18 | 44.37 | 57 | 42.75 | 0.9 % |
| `divider_chain` | 1,352.5 | 1.02 % | 26.32 | 73.97 | 73 | 54.75 | 1.0 % |
| `lock_detector` | 556.4 | 7.45 % | 55.00 | 7.60 | 23 | 17.25 | 2.4 % |

| Reference netlist | Devices | Shared-diffusion candidates | Column area freed by merging every one (um2) | Sum W*L (um2) |
|---|---|---|---|---|
| `divider_chain` | 452 | 40 (nfet_03v3: 34, pfet_03v3: 6) | 125.4 | 260.3 |

Metal2 track pitch 0.75 um; device bands coalesced across diffusion gaps < 6.0 um.
