# Antigravity Rules & Command Execution Policy

## 1. Denylist: Banned Commands (STRICTLY PROHIBITED)
The agent must **NEVER** propose or execute the following commands under any circumstances:

### Git Destructive Operations
- `git push --force` or `git push -f`
- `git reset --hard`
- `git clean -fd`, `git clean -f`, or `git clean -x`
- `git branch -D`
- `git checkout -- .` or `git restore .`

### Bulk Deletion & Filesystem Destruction
- PowerShell: `Remove-Item -Recurse -Force`, `rmdir /s /q`, `rd /s /q`
- Command Prompt: `del /f /s /q`, `del *.*`
- Linux/Bash: `rm -rf /*`, `rm -rf ~*`, `rm -rf .*`, `mkfs.*`, `dd if=* of=*`
- Formatting disks: `Format-Volume`, `format *:`, `fdisk`

### Operating System & Process Termination
- `Stop-Computer`, `shutdown`, `reboot`, `init 0`, `init 6`
- `Stop-Process -Force` (except explicitly created child background tasks)
- `Set-ExecutionPolicy Unrestricted`
- Modifying system registries or permissions: `chmod -R 777 /`, `chown -R`

### Database & Environment Leakage
- `DROP DATABASE`, `drop database`, `prisma migrate reset`, `typeorm schema:drop`
- Dumping all environment secrets to logs or chat: `Get-ChildItem env:`, `printenv`, `env`

---

## 2. Asklist: Commands Requiring Explicit Confirmation
The agent must ask the user explicitly before running:
- Any `git push` command.
- Package installations that alter global state (`npm install -g`, `pip install` outside virtual environments).
- Terminating long-running background servers or services.

---

## 3. Allowlist: Safe Commands (Safe to Run Automatically)
The agent is encouraged to run safe, read-only and standard workflow commands in the sandbox:
- Workspace inspection: `Get-ChildItem`, `dir`, `ls`, `cat`, `Get-Content`, `type`, `findstr`, `grep`.
- Git status / inspection: `git status`, `git diff`, `git log`, `git branch`.
- Build & test: `cmake --build`, `pytest`, `python -m unittest`, `ctest`.
- Python execution within workspace: `python scripts/...`, `python -m ...`.

---

## 4. Web Access Policy (Network & Browser)

### 4.1. Blacklist / Denylist (STRICTLY PROHIBITED)
The agent must **NEVER** navigate, send HTTP requests, or fetch data from:
- **Cloud Metadata & Private Services**: `169.254.169.254`, `metadata.google.internal`, or unauthorized internal network/intranet subnets.
- **Data Exfiltration & Anonymous File/Paste Sharing**: `pastebin.com`, `transfer.sh`, `file.io`, `anonfiles.com`, webhook/request logger sites (`webhook.site`, `requestcatcher.com`, `burpcollaborator.net`, `ngrok-free.app`) to prevent credential and source leakage.
- **URL Shorteners**: `bit.ly`, `tinyurl.com`, `t.co`, `goo.gl` (must not open unverified redirected endpoints).
- **Personal Social & Entertainment Media**: `facebook.com`, `tiktok.com`, `instagram.com`, `twitter.com`, `x.com`, `discord.com`, `telegram.org` (unless explicitly requested by user for API integration).
- **Online Banking, Financial & Payment Gateways**: `paypal.com`, `stripe.com` dashboards, banking portals.

### 4.2. Whitelist / Allowlist (Permitted for Development & Research)
The agent is permitted to freely read, search, and fetch documentation and code from:
- **Official Documentation & Standards**:
  - `developer.mozilla.org` (MDN), `w3.org`
  - `*.google.com`, `*.dev`, `docs.flutter.dev`, `dart.dev`, `developer.android.com`
  - `learn.microsoft.com`, `docs.microsoft.com`
  - `docs.python.org`, `nodejs.org`, `go.dev`, `rust-lang.org`
- **Official Package Repositories & Registries**:
  - `pypi.org`, `npmjs.com`, `pub.dev`, `pkg.go.dev`, `crates.io`, `nuget.org`, `repo1.maven.org`
- **Developer Q&A and Version Control**:
  - `github.com`, `raw.githubusercontent.com`, `gitlab.com`
  - `stackoverflow.com`, `stackexchange.com`
- **Open-Access Journals, Preprints & Conferences**:
  - Preprints: `arxiv.org`, `biorxiv.org`, `medrxiv.org`, `osf.io`
  - Conferences & ML Proceedings: `openreview.net`, `proceedings.mlr.press` (PMLR), `neurips.cc` (`papers.nips.cc`), `openaccess.thecvf.com` (CVF: CVPR/ICCV), `aclanthology.org` (ACL/EMNLP)
  - Open Access Publishers & Repositories: `ncbi.nlm.nih.gov/pmc` (PMC), `europepmc.org`, `doaj.org`, `plos.org`, `frontiersin.org`, `nature.com/articles/*` (Open Access), `biomedcentral.com` (BMC)
  - Academic Indices & Bibliographies: `openalex.org`, `semanticscholar.org`, `crossref.org`, `dblp.org`
- **Search Engines**: `google.com`, `bing.com`, `duckduckgo.com`

### 4.3. Asklist: Actions Requiring Explicit Confirmation
The agent must ask the user explicitly before:
- Downloading executable binaries, installers, or scripts (`.exe`, `.msi`, `.bat`, `.ps1`, `.sh`) from external websites.
- Submitting form actions, authentication tokens, API keys, or project-specific source code to third-party endpoints.
- Accessing unknown, non-standard HTTP/HTTPS endpoints outside the whitelist.

---

## 5. Theoretical Rigor & Verification Before Conclusion Policy (QUY CHUẨN KIỂM CHỨNG LÝ THUYẾT VÀ BẢO CHỨNG KẾT LUẬN)

Tất cả các Agent (bao gồm Main Agent và mọi Subagents) phải tuân thủ nghiêm ngặt nguyên tắc kiểm chứng lý thuyết trước khi đưa ra bất kỳ kết luận, dự đoán, hoặc số liệu nào:

### 5.1. Cấm Tuyệt Đối Suy Đoán Cảm Tính (Zero Unverified Assertions)
- **Không suy diễn chủ quan:** Mọi nhận định về độ khả thi, tính đúng đắn, chất lượng nghiệm, độ phức tạp thuật toán, hoặc tốc độ thực thi bắt buộc phải có chứng minh toán học, công thức tường minh, hoặc trích xuất số liệu thực nghiệm trực tiếp từ log đo đạc thực tế.
- **Đối chiếu Cận Dưới & Định lý Toán học:** Trước khi kết luận một nghiệm là tối ưu hoặc đánh giá một nghiên cứu, Agent phải đối chiếu với các cận dưới lý thuyết (Theoretical Lower Bounds, Clique Incompatibility, BKS thế giới, Bất đẳng thức tam giác Euclid). Không bao giờ thừa nhận các số liệu phá vỡ quy luật vật lý/toán học mà không chỉ rõ bản chất vi phạm.

### 5.2. Nguyên Tắc Tính Toán Dự Toán Tài Nguyên & Thời Gian (Rigorous Time & Resource Estimation)
Khi dự toán thời gian hoàn thành cho bất kỳ quy trình tính toán, benchmark hay batch pipeline nào:
1. **Bắt buộc dùng công thức toán học:**
   $$\text{Thời gian tổng thể} = \frac{\sum_{i=1}^M (\text{Số runs}_i \times \text{Thời gian thực tế đo được}_i)}{\text{Số worker song song hiệu dụng}} \times \text{Hệ số overhead/timeout}$$
2. **Không áp dụng quy luật tuyến tính cào bằng:** Phải phân tách rõ các nhóm bài toán (ví dụ: nhóm bài toán nhỏ/khung giờ hẹp vs. nhóm bài toán lớn/khung giờ rộng) dựa trên thời gian chạy thực tế đo được từ các lần chạy trước trong log.
3. **Tuân thủ Giới hạn Nền tảng:** Phải tính đến các ngưỡng timeout vật lý của hạ tầng (ví dụ: ngưỡng 9 giờ của Kaggle, thời gian I/O, thời gian tải snapshot, số wave chia nhỏ). Tuyệt đối không đưa ra những con số phi thực tế khi chưa nhân với số đợt chạy thực tế.

### 5.3. Thẩm Định Ràng Buộc Khả Thi Tuyệt Đối (Strict Feasibility Verification)
- Không bao giờ công nhận một giải pháp là "hoàn thành" hay "khả thi" nếu chưa kiểm tra 100% các ràng buộc kỹ thuật của bài toán (Capacity động từng chặng, Time Windows cứng, Depot bounds, Customer uniqueness).
- Khi thuật toán sinh ra nghiệm vi phạm ràng buộc (infeasible), phải báo cáo rõ ràng trạng thái vi phạm và ghi chú cụ thể nguyên nhân vi phạm, không đánh tráo khái niệm giữa nghiệm thô và nghiệm hợp lệ.

