import os
import sys
import time
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
KAGGLE_EXE = r"C:\Users\LENOVO\miniconda3\envs\phshowoa\Scripts\kaggle.exe"
CREDS_ROOT = Path("D:/Project/Kaggle/credentials")
OUTPUT_ROOT = Path("D:/Project/Kaggle/output")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
PYTHON_EXE = r"C:\Users\LENOVO\miniconda3\envs\phshowoa\python.exe"

# All currently active jobs:
ACTIVE_JOBS = [
    # tafuhihi -> Cdp104
    {"account": "default", "owner": "tafuhihi", "instance": "Cdp104", "slug": "ph-showoa-new-cdp104-s42-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Cdp104", "slug": "ph-showoa-new-cdp104-s48-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Cdp104", "slug": "ph-showoa-new-cdp104-s54-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Cdp104", "slug": "ph-showoa-new-cdp104-s60-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Cdp104", "slug": "ph-showoa-new-cdp104-s66-n6"},

    # account-b -> Cdp201
    {"account": "account-b", "owner": "kanhan162", "instance": "Cdp201", "slug": "ph-showoa-new-cdp201-s42-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Cdp201", "slug": "ph-showoa-new-cdp201-s48-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Cdp201", "slug": "ph-showoa-new-cdp201-s54-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Cdp201", "slug": "ph-showoa-new-cdp201-s60-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Cdp201", "slug": "ph-showoa-new-cdp201-s66-n6"},

    # account-c -> Cdp204
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp204", "slug": "ph-showoa-new-cdp204-s42-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp204", "slug": "ph-showoa-new-cdp204-s48-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp204", "slug": "ph-showoa-new-cdp204-s54-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp204", "slug": "ph-showoa-new-cdp204-s60-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp204", "slug": "ph-showoa-new-cdp204-s66-n6"},

    # account-d -> Cdp206
    {"account": "account-d", "owner": "keith1101", "instance": "Cdp206", "slug": "ph-showoa-new-cdp206-s42-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "Cdp206", "slug": "ph-showoa-new-cdp206-s48-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "Cdp206", "slug": "ph-showoa-new-cdp206-s54-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "Cdp206", "slug": "ph-showoa-new-cdp206-s60-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "Cdp206", "slug": "ph-showoa-new-cdp206-s66-n6"},

    # account-e -> Cdp207
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Cdp207", "slug": "ph-showoa-new-cdp207-s42-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Cdp207", "slug": "ph-showoa-new-cdp207-s48-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Cdp207", "slug": "ph-showoa-new-cdp207-s54-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Cdp207", "slug": "ph-showoa-new-cdp207-s60-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Cdp207", "slug": "ph-showoa-new-cdp207-s66-n6"},

    # account-f -> Cdp102
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp102", "slug": "ph-showoa-new-cdp102-s42-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp102", "slug": "ph-showoa-new-cdp102-s48-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp102", "slug": "ph-showoa-new-cdp102-s54-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp102", "slug": "ph-showoa-new-cdp102-s60-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp102", "slug": "ph-showoa-new-cdp102-s66-n6"},

    # account-g -> Cdp103
    {"account": "account-g", "owner": "vochithanh", "instance": "Cdp103", "slug": "ph-showoa-new-cdp103-s42-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Cdp103", "slug": "ph-showoa-new-cdp103-s48-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Cdp103", "slug": "ph-showoa-new-cdp103-s54-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Cdp103", "slug": "ph-showoa-new-cdp103-s60-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Cdp103", "slug": "ph-showoa-new-cdp103-s66-n6"},

    # Newly allocated Cdp105 (30 runs across acc-f, acc-b, acc-c)
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp105", "slug": "ph-showoa-new-cdp105-s42-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp105", "slug": "ph-showoa-new-cdp105-s48-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp105", "slug": "ph-showoa-new-cdp105-s54-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Cdp105", "slug": "ph-showoa-new-cdp105-s60-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp105", "slug": "ph-showoa-new-cdp105-s66-n6"},

    # Newly allocated Cdp106 (30 runs across acc-d, default, acc-h)
    {"account": "account-d", "owner": "keith1101", "instance": "Cdp106", "slug": "ph-showoa-new-cdp106-s42-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Cdp106", "slug": "ph-showoa-new-cdp106-s48-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp106", "slug": "ph-showoa-new-cdp106-s54-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp106", "slug": "ph-showoa-new-cdp106-s60-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp106", "slug": "ph-showoa-new-cdp106-s66-n6"},

    # Newly allocated Cdp107 (acc-h and acc-f)
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp107", "slug": "ph-showoa-new-cdp107-s42-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp107", "slug": "ph-showoa-new-cdp107-s48-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp107", "slug": "ph-showoa-new-cdp107-s54-n6"},

    # Cdp101 Enhanced verification
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp101", "slug": "ph-showoa-enh-cdp101-s42-n6"},

    # === WAVE 2 ALLOCATIONS (33 Kernels) ===
    # 1. Close-out Cdp201 on kanhan162 (account-b)
    {"account": "account-b", "owner": "kanhan162", "instance": "Cdp201", "slug": "ph-showoa-supp-cdp201-s46-n2"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Cdp201", "slug": "ph-showoa-supp-cdp201-s64-n2"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Cdp201", "slug": "ph-showoa-supp-cdp201-s70-n2"},

    # 2. Close-out Cdp204 on dautromduoicuop (account-c)
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp204", "slug": "ph-showoa-supp-cdp204-s53-n1"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp204", "slug": "ph-showoa-supp-cdp204-s58-n2"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp204", "slug": "ph-showoa-supp-cdp204-s65-n3"},

    # 3. Close-out Cdp206 on keith1101 (account-d)
    {"account": "account-d", "owner": "keith1101", "instance": "Cdp206", "slug": "ph-showoa-supp-cdp206-s46-n2"},
    {"account": "account-d", "owner": "keith1101", "instance": "Cdp206", "slug": "ph-showoa-supp-cdp206-s52-n2"},
    {"account": "account-d", "owner": "keith1101", "instance": "Cdp206", "slug": "ph-showoa-supp-cdp206-s71-n1"},

    # 4. Close-out Cdp207 on giahaohuynh (account-e)
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Cdp207", "slug": "ph-showoa-supp-cdp207-s46-n2"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Cdp207", "slug": "ph-showoa-supp-cdp207-s52-n2"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Cdp207", "slug": "ph-showoa-supp-cdp207-s58-n2"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Cdp207", "slug": "ph-showoa-supp-cdp207-s64-n2"},

    # 5. Close-out Cdp107 on vochithanh (account-g)
    {"account": "account-g", "owner": "vochithanh", "instance": "Cdp107", "slug": "ph-showoa-new-cdp107-s60-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Cdp107", "slug": "ph-showoa-new-cdp107-s66-n6"},

    # 6. Cdp108 on huynhkhackiet (account-f, full 30 runs = 5 kernels)
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp108", "slug": "ph-showoa-new-cdp108-s42-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp108", "slug": "ph-showoa-new-cdp108-s48-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp108", "slug": "ph-showoa-new-cdp108-s54-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp108", "slug": "ph-showoa-new-cdp108-s60-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Cdp108", "slug": "ph-showoa-new-cdp108-s66-n6"},

    # 7. Cdp109 on vnguynduykhoa (account-h, full 30 runs = 5 kernels)
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp109", "slug": "ph-showoa-new-cdp109-s42-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp109", "slug": "ph-showoa-new-cdp109-s48-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp109", "slug": "ph-showoa-new-cdp109-s54-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp109", "slug": "ph-showoa-new-cdp109-s60-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Cdp109", "slug": "ph-showoa-new-cdp109-s66-n6"},

    # 8. Rdp103 on vochithanh (account-g, 3 kernels) + tafuhihi (default, 2 kernels)
    {"account": "account-g", "owner": "vochithanh", "instance": "Rdp103", "slug": "ph-showoa-new-rdp103-s42-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Rdp103", "slug": "ph-showoa-new-rdp103-s48-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Rdp103", "slug": "ph-showoa-new-rdp103-s54-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp103", "slug": "ph-showoa-new-rdp103-s60-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp103", "slug": "ph-showoa-new-rdp103-s66-n6"},

    # 9. Rdp101 on tafuhihi (default, 3 kernels)
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp101", "slug": "ph-showoa-new-rdp101-s42-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp101", "slug": "ph-showoa-new-rdp101-s48-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp101", "slug": "ph-showoa-new-rdp101-s54-n6"},

    # 10. Rdp101 closeout on kanhan162 (account-b) & dautromduoicuop (account-c)
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp101", "slug": "ph-showoa-new-rdp101-s60-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp101", "slug": "ph-showoa-new-rdp101-s66-n6"},

    # 11. Rdp102 on dautromduoicuop (2), keith1101 (2), giahaohuynh (1) -> Full 30 runs!
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp102", "slug": "ph-showoa-new-rdp102-s42-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp102", "slug": "ph-showoa-new-rdp102-s48-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "Rdp102", "slug": "ph-showoa-new-rdp102-s54-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "Rdp102", "slug": "ph-showoa-new-rdp102-s60-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp102", "slug": "ph-showoa-new-rdp102-s66-n6"},

    # 12. Rdp104 on ketvong (account-i, full 30 runs = 5 kernels)
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp104", "slug": "ph-showoa-new-rdp104-s42-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp104", "slug": "ph-showoa-new-rdp104-s48-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp104", "slug": "ph-showoa-new-rdp104-s54-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp104", "slug": "ph-showoa-new-rdp104-s60-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp104", "slug": "ph-showoa-new-rdp104-s66-n6"},

    # 13. Rdp105 on huybahihi (account-j, full 30 runs = 5 kernels)
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp105", "slug": "ph-showoa-new-rdp105-s42-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp105", "slug": "ph-showoa-new-rdp105-s48-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp105", "slug": "ph-showoa-new-rdp105-s54-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp105", "slug": "ph-showoa-new-rdp105-s60-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp105", "slug": "ph-showoa-new-rdp105-s66-n6"},

    # 14. Rdp106 on kaigaming (account-k, full 30 runs = 5 kernels)
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp106", "slug": "ph-showoa-new-rdp106-s42-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp106", "slug": "ph-showoa-new-rdp106-s48-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp106", "slug": "ph-showoa-new-rdp106-s54-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp106", "slug": "ph-showoa-new-rdp106-s60-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp106", "slug": "ph-showoa-new-rdp106-s66-n6"},

    # 15. Rdp107 on kingaminghehe (account-l, full 30 runs = 5 kernels)
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp107", "slug": "ph-showoa-new-rdp107-s42-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp107", "slug": "ph-showoa-new-rdp107-s48-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp107", "slug": "ph-showoa-new-rdp107-s54-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp107", "slug": "ph-showoa-new-rdp107-s60-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp107", "slug": "ph-showoa-new-rdp107-s66-n6"},

    # 16. Rdp108 on khahccngng (account-m, full 30 runs = 5 kernels)
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp108", "slug": "ph-showoa-new-rdp108-s42-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp108", "slug": "ph-showoa-new-rdp108-s48-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp108", "slug": "ph-showoa-new-rdp108-s54-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp108", "slug": "ph-showoa-new-rdp108-s60-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp108", "slug": "ph-showoa-new-rdp108-s66-n6"},
    # 17. RCdp1001 on keith1101 (account-d, full 30 runs)
    {"account": "account-d", "owner": "keith1101", "instance": "RCdp1001", "slug": "ph-showoa-new-rcdp1001-s42-n30"},
    # 18. RCdp1004 on kanhan162 (account-b, full 30 runs)
    {"account": "account-b", "owner": "kanhan162", "instance": "RCdp1004", "slug": "ph-showoa-new-rcdp1004-s42-n30"},
    # 19. RCdp1007 on giahaohuynh (account-e, full 30 runs)
    {"account": "account-e", "owner": "giahaohuynh", "instance": "RCdp1007", "slug": "ph-showoa-new-rcdp1007-s42-n30"},
    # 20. RCdp2501 on keith1101 (account-d, full 30 runs)
    {"account": "account-d", "owner": "keith1101", "instance": "RCdp2501", "slug": "ph-showoa-new-rcdp2501-s42-n30"},
    # 21. RCdp2504 on kanhan162 (account-b, full 30 runs)
    {"account": "account-b", "owner": "kanhan162", "instance": "RCdp2504", "slug": "ph-showoa-new-rcdp2504-s42-n30"},
    # 22. RCdp2507 on vochithanh (account-g, full 30 runs)
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp2507", "slug": "ph-showoa-new-rcdp2507-s42-n30"},

    # 23. RCdp5001 on kanhan162 (account-b, full 30 runs)
    {"account": "account-b", "owner": "kanhan162", "instance": "RCdp5001", "slug": "ph-showoa-new-rcdp5001-s42-n30"},
    # 24. RCdp5004 on keith1101 (account-d, full 30 runs)
    {"account": "account-d", "owner": "keith1101", "instance": "RCdp5004", "slug": "ph-showoa-new-rcdp5004-s42-n30"},
    # 25. RCdp5007 on vochithanh (account-g, full 30 runs)
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp5007", "slug": "ph-showoa-new-rcdp5007-s42-n30"},

    # 26. Rdp109 on giahaohuynh (acc-e, 3 kernels) + vnguynduykhoa (acc-h, 2 kernels) -> Full 30 runs!
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp109", "slug": "ph-showoa-new-rdp109-s42-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp109", "slug": "ph-showoa-new-rdp109-s48-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp109", "slug": "ph-showoa-new-rdp109-s54-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Rdp109", "slug": "ph-showoa-new-rdp109-s60-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Rdp109", "slug": "ph-showoa-new-rdp109-s66-n6"},

    # 27. Rdp110 across kanhan162 (acc-b), dautromduoicuop (acc-c), keith1101 (acc-d), huynhkhackiet (acc-f) -> Full 30 runs!
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp110", "slug": "ph-showoa-new-rdp110-s42-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp110", "slug": "ph-showoa-new-rdp110-s48-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "Rdp110", "slug": "ph-showoa-new-rdp110-s54-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp110", "slug": "ph-showoa-new-rdp110-s60-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp110", "slug": "ph-showoa-new-rdp110-s66-n6"},

    # 28. Rdp111 across kanhan162, giahaohuynh, tafuhihi, dautromduoicuop -> Full 30 runs!
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp111", "slug": "ph-showoa-new-rdp111-s42-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp111", "slug": "ph-showoa-new-rdp111-s48-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp111", "slug": "ph-showoa-new-rdp111-s54-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp111", "slug": "ph-showoa-new-rdp111-s60-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp111", "slug": "ph-showoa-new-rdp111-s66-n6"},

    # 29. Rdp112 across giahaohuynh, huynhkhackiet, kanhan162, huybahihi -> Full 30 runs!
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp112", "slug": "ph-showoa-new-rdp112-s42-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp112", "slug": "ph-showoa-new-rdp112-s48-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp112", "slug": "ph-showoa-new-rdp112-s54-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp112", "slug": "ph-showoa-new-rdp112-s60-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp112", "slug": "ph-showoa-new-rdp112-s66-n6"},

    # 30. Rdp201 across huynhkhackiet, vnguynduykhoa -> Full 30 runs!
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp201", "slug": "ph-showoa-new-rdp201-s42-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp201", "slug": "ph-showoa-new-rdp201-s48-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Rdp201", "slug": "ph-showoa-new-rdp201-s54-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Rdp201", "slug": "ph-showoa-new-rdp201-s60-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Rdp201", "slug": "ph-showoa-new-rdp201-s66-n6"},

    # 31. Rdp202 across kaigaming, tafuhihi, keith1101, vochithanh -> Full 30 runs!
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp202", "slug": "ph-showoa-new-rdp202-s42-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp202", "slug": "ph-showoa-new-rdp202-s48-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp202", "slug": "ph-showoa-new-rdp202-s54-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "Rdp202", "slug": "ph-showoa-new-rdp202-s60-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Rdp202", "slug": "ph-showoa-new-rdp202-s66-n6"},

    # 32. Rdp203 across kaigaming, khahccngng, tafuhihi, dautromduoicuop -> Full 30 runs!
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp203", "slug": "ph-showoa-new-rdp203-s42-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp203", "slug": "ph-showoa-new-rdp203-s48-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp203", "slug": "ph-showoa-new-rdp203-s54-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp203", "slug": "ph-showoa-new-rdp203-s60-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp203", "slug": "ph-showoa-new-rdp203-s66-n6"},

    # 33. Rdp204 across keith1101, huybahihi -> Full 30 runs!
    {"account": "account-d", "owner": "keith1101", "instance": "Rdp204", "slug": "ph-showoa-new-rdp204-s42-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "Rdp204", "slug": "ph-showoa-new-rdp204-s48-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp204", "slug": "ph-showoa-new-rdp204-s54-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp204", "slug": "ph-showoa-new-rdp204-s60-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp204", "slug": "ph-showoa-new-rdp204-s66-n6"},

    # 34. Rdp205 across vochithanh, huybahihi, kaigaming, kingaminghehe -> Full 30 runs!
    {"account": "account-g", "owner": "vochithanh", "instance": "Rdp205", "slug": "ph-showoa-new-rdp205-s42-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Rdp205", "slug": "ph-showoa-new-rdp205-s48-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "Rdp205", "slug": "ph-showoa-new-rdp205-s54-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp205", "slug": "ph-showoa-new-rdp205-s60-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp205", "slug": "ph-showoa-new-rdp205-s66-n6"},

    # 35. Rdp206 across kingaminghehe, khahccngng, tafuhihi, vochithanh -> Full 30 runs!
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp206", "slug": "ph-showoa-new-rdp206-s42-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp206", "slug": "ph-showoa-new-rdp206-s48-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp206", "slug": "ph-showoa-new-rdp206-s54-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp206", "slug": "ph-showoa-new-rdp206-s60-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "Rdp206", "slug": "ph-showoa-new-rdp206-s66-n6"},

    # 36. Rdp207 on ketvong -> Full 30 runs!
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp207", "slug": "ph-showoa-new-rdp207-s42-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp207", "slug": "ph-showoa-new-rdp207-s48-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp207", "slug": "ph-showoa-new-rdp207-s54-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp207", "slug": "ph-showoa-new-rdp207-s60-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "Rdp207", "slug": "ph-showoa-new-rdp207-s66-n6"},

    # 37. Rdp208 across kaigaming, kingaminghehe, khahccngng -> Full 30 runs!
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp208", "slug": "ph-showoa-new-rdp208-s42-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp208", "slug": "ph-showoa-new-rdp208-s48-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp208", "slug": "ph-showoa-new-rdp208-s54-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp208", "slug": "ph-showoa-new-rdp208-s60-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp208", "slug": "ph-showoa-new-rdp208-s66-n6"},

    # 38. Rdp209 across khahccngng, giahaohuynh, vnguynduykhoa, kaigaming, huynhkhackiet -> Full 30 runs!
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp209", "slug": "ph-showoa-new-rdp209-s42-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp209", "slug": "ph-showoa-new-rdp209-s48-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Rdp209", "slug": "ph-showoa-new-rdp209-s54-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp209", "slug": "ph-showoa-new-rdp209-s60-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp209", "slug": "ph-showoa-new-rdp209-s66-n6"},

    # === WAVE 3 (54 KERNELS ALLOCATED OCTOBER 15) ===
    # 39. Rdp210 on kanhan162 (account-b, 5 slots) -> Full 30 runs!
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp210", "slug": "ph-showoa-new-rdp210-s42-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp210", "slug": "ph-showoa-new-rdp210-s48-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp210", "slug": "ph-showoa-new-rdp210-s54-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp210", "slug": "ph-showoa-new-rdp210-s60-n6"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp210", "slug": "ph-showoa-new-rdp210-s66-n6"},

    # 40. Rdp211 on dautromduoicuop (account-c, 5 slots) -> Full 30 runs!
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp211", "slug": "ph-showoa-new-rdp211-s42-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp211", "slug": "ph-showoa-new-rdp211-s48-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp211", "slug": "ph-showoa-new-rdp211-s54-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp211", "slug": "ph-showoa-new-rdp211-s60-n6"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp211", "slug": "ph-showoa-new-rdp211-s66-n6"},

    # 41. RCdp101 on vochithanh (account-g, 5 slots) -> Full 30 runs!
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp101", "slug": "ph-showoa-new-rcdp101-s42-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp101", "slug": "ph-showoa-new-rcdp101-s48-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp101", "slug": "ph-showoa-new-rcdp101-s54-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp101", "slug": "ph-showoa-new-rcdp101-s60-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp101", "slug": "ph-showoa-new-rcdp101-s66-n6"},

    # 42. RCdp102 on vnguynduykhoa (account-h, 5 slots) -> Full 30 runs!
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "RCdp102", "slug": "ph-showoa-new-rcdp102-s42-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "RCdp102", "slug": "ph-showoa-new-rcdp102-s48-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "RCdp102", "slug": "ph-showoa-new-rcdp102-s54-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "RCdp102", "slug": "ph-showoa-new-rcdp102-s60-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "RCdp102", "slug": "ph-showoa-new-rcdp102-s66-n6"},

    # 43. RCdp103 on ketvong (account-i, 5 slots) -> Full 30 runs!
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp103", "slug": "ph-showoa-new-rcdp103-s42-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp103", "slug": "ph-showoa-new-rcdp103-s48-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp103", "slug": "ph-showoa-new-rcdp103-s54-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp103", "slug": "ph-showoa-new-rcdp103-s60-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp103", "slug": "ph-showoa-new-rcdp103-s66-n6"},

    # 44. RCdp104 on huybahihi (account-j, 5 slots) -> Full 30 runs!
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp104", "slug": "ph-showoa-new-rcdp104-s42-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp104", "slug": "ph-showoa-new-rcdp104-s48-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp104", "slug": "ph-showoa-new-rcdp104-s54-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp104", "slug": "ph-showoa-new-rcdp104-s60-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp104", "slug": "ph-showoa-new-rcdp104-s66-n6"},

    # 45. RCdp105 on kaigaming (account-k, 5 slots) -> Full 30 runs!
    {"account": "account-k", "owner": "kaigaming", "instance": "RCdp105", "slug": "ph-showoa-new-rcdp105-s42-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "RCdp105", "slug": "ph-showoa-new-rcdp105-s48-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "RCdp105", "slug": "ph-showoa-new-rcdp105-s54-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "RCdp105", "slug": "ph-showoa-new-rcdp105-s60-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "RCdp105", "slug": "ph-showoa-new-rcdp105-s66-n6"},

    # 46. RCdp106 on kingaminghehe (account-l, 5 slots) -> Full 30 runs!
    {"account": "account-l", "owner": "kingaminghehe", "instance": "RCdp106", "slug": "ph-showoa-new-rcdp106-s42-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "RCdp106", "slug": "ph-showoa-new-rcdp106-s48-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "RCdp106", "slug": "ph-showoa-new-rcdp106-s54-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "RCdp106", "slug": "ph-showoa-new-rcdp106-s60-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "RCdp106", "slug": "ph-showoa-new-rcdp106-s66-n6"},

    # 47. RCdp107 on khahccngng (account-m, 5 slots) -> Full 30 runs!
    {"account": "account-m", "owner": "khahccngng", "instance": "RCdp107", "slug": "ph-showoa-new-rcdp107-s42-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "RCdp107", "slug": "ph-showoa-new-rcdp107-s48-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "RCdp107", "slug": "ph-showoa-new-rcdp107-s54-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "RCdp107", "slug": "ph-showoa-new-rcdp107-s60-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "RCdp107", "slug": "ph-showoa-new-rcdp107-s66-n6"},

    # 48. RCdp108 across giahaohuynh, huynhkhackiet -> Full 30 runs!
    {"account": "account-e", "owner": "giahaohuynh", "instance": "RCdp108", "slug": "ph-showoa-new-rcdp108-s42-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "RCdp108", "slug": "ph-showoa-new-rcdp108-s48-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "RCdp108", "slug": "ph-showoa-new-rcdp108-s54-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "RCdp108", "slug": "ph-showoa-new-rcdp108-s60-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "RCdp108", "slug": "ph-showoa-new-rcdp108-s66-n6"},

    # 49. RCdp201 across huynhkhackiet, keith1101, tafuhihi, vnguynduykhoa -> Full 30 runs!
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "RCdp201", "slug": "ph-showoa-new-rcdp201-s42-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "RCdp201", "slug": "ph-showoa-new-rcdp201-s48-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "RCdp201", "slug": "ph-showoa-new-rcdp201-s54-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "RCdp201", "slug": "ph-showoa-new-rcdp201-s60-n6"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "RCdp201", "slug": "ph-showoa-new-rcdp201-s66-n6"},

    # 50. RCdp205 across keith1101, huynhkhackiet -> Full 30 runs!
    {"account": "account-d", "owner": "keith1101", "instance": "RCdp205", "slug": "ph-showoa-new-rcdp205-s42-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "RCdp205", "slug": "ph-showoa-new-rcdp205-s48-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "RCdp205", "slug": "ph-showoa-new-rcdp205-s54-n6"},
    {"account": "account-d", "owner": "keith1101", "instance": "RCdp205", "slug": "ph-showoa-new-rcdp205-s60-n6"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "RCdp205", "slug": "ph-showoa-new-rcdp205-s66-n6"},

    # 51. RCdp206 across tafuhihi, giahaohuynh -> Full 30 runs!
    {"account": "default", "owner": "tafuhihi", "instance": "RCdp206", "slug": "ph-showoa-new-rcdp206-s42-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "RCdp206", "slug": "ph-showoa-new-rcdp206-s48-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "RCdp206", "slug": "ph-showoa-new-rcdp206-s54-n6"},
    {"account": "default", "owner": "tafuhihi", "instance": "RCdp206", "slug": "ph-showoa-new-rcdp206-s60-n6"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "RCdp206", "slug": "ph-showoa-new-rcdp206-s66-n6"},

    # 52. RCdp207 on giahaohuynh -> 6 runs!
    {"account": "account-e", "owner": "giahaohuynh", "instance": "RCdp207", "slug": "ph-showoa-new-rcdp207-s42-n6"},

    # 53. RCdp202 across vnguynduykhoa, ketvong, kaigaming, kingaminghehe, khahccngng -> Full 30 runs!
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "RCdp202", "slug": "ph-showoa-new-rcdp202-s42-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp202", "slug": "ph-showoa-new-rcdp202-s48-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "RCdp202", "slug": "ph-showoa-new-rcdp202-s54-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "RCdp202", "slug": "ph-showoa-new-rcdp202-s60-n6"},
    {"account": "account-m", "owner": "khahccngng", "instance": "RCdp202", "slug": "ph-showoa-new-rcdp202-s66-n6"},

    # 54. RCdp203 across vnguynduykhoa, kingaminghehe, kaigaming -> Full 30 runs!
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "RCdp203", "slug": "ph-showoa-new-rcdp203-s42-n6"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "RCdp203", "slug": "ph-showoa-new-rcdp203-s48-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "RCdp203", "slug": "ph-showoa-new-rcdp203-s54-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "RCdp203", "slug": "ph-showoa-new-rcdp203-s60-n6"},
    {"account": "account-k", "owner": "kaigaming", "instance": "RCdp203", "slug": "ph-showoa-new-rcdp203-s66-n6"},

    # 55. RCdp204 on vochithanh (account-g, 5 slots) -> Full 30 runs!
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp204", "slug": "ph-showoa-new-rcdp204-s42-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp204", "slug": "ph-showoa-new-rcdp204-s48-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp204", "slug": "ph-showoa-new-rcdp204-s54-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp204", "slug": "ph-showoa-new-rcdp204-s60-n6"},
    {"account": "account-g", "owner": "vochithanh", "instance": "RCdp204", "slug": "ph-showoa-new-rcdp204-s66-n6"},

    # 56. RCdp207 on ketvong (account-i, 4 slots) -> Full 30 runs!
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp207", "slug": "ph-showoa-new-rcdp207-s48-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp207", "slug": "ph-showoa-new-rcdp207-s54-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp207", "slug": "ph-showoa-new-rcdp207-s60-n6"},
    {"account": "account-i", "owner": "ketvong", "instance": "RCdp207", "slug": "ph-showoa-new-rcdp207-s66-n6"},

    # 57. RCdp208 on huybahihi (account-j, 5 slots) -> Full 30 runs!
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp208", "slug": "ph-showoa-new-rcdp208-s42-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp208", "slug": "ph-showoa-new-rcdp208-s48-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp208", "slug": "ph-showoa-new-rcdp208-s54-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp208", "slug": "ph-showoa-new-rcdp208-s60-n6"},
    {"account": "account-j", "owner": "huybahihi", "instance": "RCdp208", "slug": "ph-showoa-new-rcdp208-s66-n6"},

    # === WAVE 5 ALLOCATIONS (30 Supplemental Kernels) ===
    # 1. dautromduoicuop (account-c, 5 slots) -> Closes Cdp204, RCdp201, Rdp206
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Cdp204", "slug": "ph-showoa-supp-cdp204-s70-n2"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "RCdp201", "slug": "ph-showoa-supp-rcdp201-s46-n2"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "RCdp201", "slug": "ph-showoa-supp-rcdp201-s52-n2"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "RCdp201", "slug": "ph-showoa-supp-rcdp201-s58-n2"},
    {"account": "account-c", "owner": "dautromduoicuop", "instance": "Rdp206", "slug": "ph-showoa-supp-rdp206-s68-n2"},

    # 2. kanhan162 (account-b, 5 slots) -> Closes Rdp201 completely!
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp201", "slug": "ph-showoa-supp-rdp201-s46-n2"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp201", "slug": "ph-showoa-supp-rdp201-s52-n2"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp201", "slug": "ph-showoa-supp-rdp201-s58-n2"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp201", "slug": "ph-showoa-supp-rdp201-s64-n2"},
    {"account": "account-b", "owner": "kanhan162", "instance": "Rdp201", "slug": "ph-showoa-supp-rdp201-s69-n3"},

    # 3. huynhkhackiet (account-f, 4 slots) -> Rdp206 (part 2)
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp206", "slug": "ph-showoa-supp-rdp206-s46-n2"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp206", "slug": "ph-showoa-supp-rdp206-s52-n2"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp206", "slug": "ph-showoa-supp-rdp206-s58-n2"},
    {"account": "account-f", "owner": "huynhkhackiet", "instance": "Rdp206", "slug": "ph-showoa-supp-rdp206-s64-n2"},

    # 4. tafuhihi (default, 1 slot) -> Closes Rdp206 completely!
    {"account": "default", "owner": "tafuhihi", "instance": "Rdp206", "slug": "ph-showoa-supp-rdp206-s70-n2"},

    # 5. khahccngng (account-m, 4 slots) -> Rdp205 (part 1)
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp205", "slug": "ph-showoa-supp-rdp205-s45-n3"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp205", "slug": "ph-showoa-supp-rdp205-s51-n3"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp205", "slug": "ph-showoa-supp-rdp205-s57-n3"},
    {"account": "account-m", "owner": "khahccngng", "instance": "Rdp205", "slug": "ph-showoa-supp-rdp205-s64-n2"},

    # 6. kaigaming (account-k, 1 slot) -> Closes Rdp205 completely!
    {"account": "account-k", "owner": "kaigaming", "instance": "Rdp205", "slug": "ph-showoa-supp-rdp205-s69-n3"},

    # 7. kingaminghehe (account-l, 3 slots) -> Rdp210 (part 1)
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp210", "slug": "ph-showoa-supp-rdp210-s46-n2"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp210", "slug": "ph-showoa-supp-rdp210-s51-n3"},
    {"account": "account-l", "owner": "kingaminghehe", "instance": "Rdp210", "slug": "ph-showoa-supp-rdp210-s57-n3"},

    # 8. giahaohuynh (account-e, 3 slots) -> Closes Rdp210 completely + Rdp202 (part 1)
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp210", "slug": "ph-showoa-supp-rdp210-s63-n3"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp210", "slug": "ph-showoa-supp-rdp210-s69-n3"},
    {"account": "account-e", "owner": "giahaohuynh", "instance": "Rdp202", "slug": "ph-showoa-supp-rdp202-s45-n3"},

    # 9. keith1101 (account-d, 2 slots) -> Rdp202 (part 2)
    {"account": "account-d", "owner": "keith1101", "instance": "Rdp202", "slug": "ph-showoa-supp-rdp202-s51-n3"},
    {"account": "account-d", "owner": "keith1101", "instance": "Rdp202", "slug": "ph-showoa-supp-rdp202-s57-n3"},

    # 10. vnguynduykhoa (account-h, 2 slots) -> Closes Rdp202 completely!
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Rdp202", "slug": "ph-showoa-supp-rdp202-s63-n3"},
    {"account": "account-h", "owner": "vnguynduykhoa", "instance": "Rdp202", "slug": "ph-showoa-supp-rdp202-s69-n3"},
]

# Dynamically import Wave 6 allocations
try:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from prepare_and_dispatch_wave6_65slots import ALLOCATIONS as WAVE6_ALLOCATIONS
    for item in WAVE6_ALLOCATIONS:
        ACTIVE_JOBS.append({
            "account": item["account"],
            "owner": item["owner"],
            "instance": item["instance"],
            "slug": item["slug"],
        })
except Exception as e:
    print(f"Warning: could not import wave 6 allocations: {e}")


def get_env(account):
    env = os.environ.copy()
    if account == "default":
        env["KAGGLE_CONFIG_DIR"] = str(CREDS_ROOT / "tafuhihi")
    else:
        env["KAGGLE_CONFIG_DIR"] = str(CREDS_ROOT / account)
    return env

def get_status(job):
    ref = f"{job['owner']}/{job['slug']}"
    res = subprocess.run([KAGGLE_EXE, "kernels", "status", ref], env=get_env(job["account"]), capture_output=True, text=True)
    out = res.stdout.strip()
    err = res.stderr.strip()
    if "COMPLETE" in out:
        return "COMPLETE"
    elif "RUNNING" in out:
        return "RUNNING"
    elif "QUEUED" in out:
        return "QUEUED"
    elif "ERROR" in out:
        return "ERROR"
    elif "CANCEL_ACKNOWLEDGED" in out or "CANCELLED" in out:
        return "CANCELLED"
    elif "404" in out or "Not Found" in out or "404" in err or "Not Found" in err:
        # Try pushing if local job build dir exists
        possible_dirs = [
            PROJECT_ROOT / "build_jobs_wave6" / job["slug"],
            PROJECT_ROOT / "build_jobs_wave5" / job["slug"],
            PROJECT_ROOT / "build_jobs_wave3" / job["slug"],
            PROJECT_ROOT / "build_jobs_account_m" / job["slug"],
            PROJECT_ROOT / "build_jobs_account_l" / job["slug"],
            PROJECT_ROOT / "build_jobs_account_k" / job["slug"],
            PROJECT_ROOT / "build_jobs_account_j" / job["slug"],
            PROJECT_ROOT / "build_jobs_account_i" / job["slug"],
            PROJECT_ROOT / "build_jobs_wave2_part2" / job["slug"],
            PROJECT_ROOT / "build_jobs_rdp103" / job["slug"],
            PROJECT_ROOT / "build_jobs_wave2" / job["slug"],
        ]
        for pdir in possible_dirs:
            if pdir.exists():
                print(f"Kernel {ref} not found on Kaggle. Attempting push from {pdir}...", flush=True)
                pres = subprocess.run([KAGGLE_EXE, "kernels", "push", "-p", str(pdir)], env=get_env(job["account"]), capture_output=True, text=True)
                if pres.returncode == 0 and "Kernel version 1 successfully pushed" in pres.stdout:
                    print(f"Successfully auto-pushed {ref}!", flush=True)
                    return "RUNNING"
                else:
                    print(f"Auto-push attempt for {ref}: {pres.stdout.strip()} {pres.stderr.strip()}", flush=True)
                    return "PENDING_SLOT"
        return "NOT_FOUND"
    return out if out else err

def download_output(job):
    ref = f"{job['owner']}/{job['slug']}"
    out_dir = OUTPUT_ROOT / job["instance"] / job["slug"]
    has_runs = False
    if out_dir.exists():
        if any(out_dir.rglob("runs.csv")) or any(out_dir.rglob("run.json")):
            has_runs = True
        elif any(f.stat().st_size > 1000 for f in out_dir.glob("*.log")):
            has_runs = True

    if has_runs:
        print(f"Output for {ref} already exists at {out_dir}. Skipping re-download.", flush=True)
        return True
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading output for {ref} to {out_dir}...", flush=True)
    res = subprocess.run([KAGGLE_EXE, "kernels", "output", ref, "-p", str(out_dir)], env=get_env(job["account"]), capture_output=True, text=True)
    print(f"Download result: {res.stdout.strip()}", flush=True)
    return res.returncode == 0

def update_sheet():
    print("Updating Google Sheet...", flush=True)
    try:
        res = subprocess.run([PYTHON_EXE, "scripts/update_google_sheet_pop30.py"], cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=180)
        print(f"Update sheet stdout:\n{res.stdout}", flush=True)
        if res.stderr:
            print(f"Update sheet stderr:\n{res.stderr}", flush=True)
    except subprocess.TimeoutExpired:
        print("Update sheet timed out after 180 seconds. Continuing...", flush=True)
    except Exception as e:
        print(f"Update sheet exception: {e}", flush=True)

def monitor_loop():
    completed = set()
    print(f"Starting Campaign Monitor Loop for {len(ACTIVE_JOBS)} kernels...", flush=True)
    
    # Fast initial check: pre-populate completed set from existing disk outputs
    for job in ACTIVE_JOBS:
        key = f"{job['owner']}/{job['slug']}"
        out_dir = OUTPUT_ROOT / job["instance"] / job["slug"]
        if out_dir.exists():
            if any(out_dir.rglob("runs.csv")) or any(out_dir.rglob("run.json")) or any(f.stat().st_size > 1000 for f in out_dir.glob("*.log")):
                completed.add(key)
    print(f"Pre-scan: {len(completed)}/{len(ACTIVE_JOBS)} kernels already completed and stored on local disk.", flush=True)
    
    while len(completed) < len(ACTIVE_JOBS):
        newly_completed = False
        print(f"\n--- Check at {time.strftime('%Y-%m-%d %H:%M:%S')} ---", flush=True)
        
        for job in ACTIVE_JOBS:
            key = f"{job['owner']}/{job['slug']}"
            if key in completed:
                continue
            
            try:
                st = get_status(job)
                time.sleep(0.5)
            except Exception as e:
                print(f"Error checking status for {key}: {e}", flush=True)
                time.sleep(1.0)
                continue

            print(f"[{job['instance']}] {key}: {st}", flush=True)
            
            if st in ("COMPLETE", "CANCELLED"):
                print(f"--> {key} finished ({st})! Downloading output...", flush=True)
                try:
                    if download_output(job):
                        completed.add(key)
                        newly_completed = True
                    time.sleep(1.0)
                except Exception as e:
                    print(f"Error downloading output for {key}: {e}", flush=True)
            elif st == "ERROR":
                print(f"--> WARNING: {key} encountered ERROR!", flush=True)
        
        if newly_completed:
            update_sheet()
            
        print(f"Progress: {len(completed)}/{len(ACTIVE_JOBS)} kernels complete.", flush=True)

        by_owner_running = {}
        for job in ACTIVE_JOBS:
            key = f"{job['owner']}/{job['slug']}"
            if key not in completed:
                by_owner_running[job["owner"]] = by_owner_running.get(job["owner"], 0) + 1
        
        all_owners = sorted(set(j["owner"] for j in ACTIVE_JOBS))
        print("\n=== ACCOUNT CAPACITY STATUS ===", flush=True)
        total_free = 0
        for owner in all_owners:
            r = by_owner_running.get(owner, 0)
            free = max(0, 5 - r)
            total_free += free
            print(f"  {owner:16s}: {r}/5 running -> {free} free slots", flush=True)
        print(f"Total free slots available across all accounts: {total_free}\n", flush=True)

        if len(completed) < len(ACTIVE_JOBS):
            # Polling every 35 minutes (2100s) saves compute and token usage.
            print("Sleeping for 2100 seconds (35 minutes)...", flush=True)
            time.sleep(2100)

    print("\nAll 25 kernels have completed! Running final sheet update...", flush=True)
    update_sheet()

if __name__ == "__main__":
    monitor_loop()
