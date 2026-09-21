# Kiểm chứng bản Java PH-SHOWOA

Thực hiện ngày 2026-09-05 trong repository này, bằng JDK `1.8.0_172`.
Các kết quả dưới đây kiểm chứng implementation theo những hiệu chỉnh đã được
người dùng xác nhận; chưa phải một nghiên cứu tái lập toàn bộ bảng của paper.

## Kiểm thử

Từ thư mục gốc repository:

```powershell
.\src_paper2skills\build.ps1 -Test
```

**21 nhóm kiểm thử đạt**, không dùng JUnit hoặc thư viện ngoài. Bao gồm:

- Tải hàng giao khi xuất depot, tải trung gian sau pickup và pickup ở khách cuối.
- Waiting, service time, cửa sổ thời gian depot và giới hạn số xe.
- Mỗi khách được phục vụ đúng một lần; phát hiện thiếu/trùng khách.
- Ma trận có hướng, travel time độc lập với distance; parser không tự điền cạnh thiếu.
- Mục tiêu ưu tiên số xe, kể cả khi chi phí tiền tệ cho quãng đường bằng 0.
- Repair sửa coverage, giữ nguyên đầu vào khi thất bại, và sửa thời gian ngay trong tuyến.
- Từ chối lịch SA bị kẹt do giới hạn số thực; công thức SA và chấp nhận nghiệm xấu hơn.
- Các toán tử giữ nguyên cha mẹ, bảo toàn khách, rollback khi cần; local search giảm mục tiêu.
- Local search ở vòng 0/25/50, diversification sau 50 vòng không cải thiện.
- Cùng seed cho nghiệm, số lần chọn toán tử, quyết định SA và toàn bộ lịch sử giống nhau
  giữa 1 và 2 worker trên bài toán kiểm thử.

Parser cũng đã được chạy trên **156 file dữ liệu hiện có** trong `data/`, gồm định
dạng Wang–Chen text và EXPLICIT. Đây là kiểm tra đọc dữ liệu, không phải 156 lần tối ưu.

## Chạy solver trên dữ liệu thực

| Input | Số khách | Iterations | Population | Workers | Runs / seed | NV | TD |
|---|---:|---:|---:|---:|---|---:|---:|
| `data/Wang_Chen/rcdp1001.txt` | 10 | 1000 | 30 | 4 | 30 / 42–71 | 3 ở cả 30 runs | 348.982361908109 ở cả 30 runs |
| `data/Wang_Chen/explicit_rcdp5001.vrpsdptw` | 50 | 1000 | 30 | 4 | 1 / 42 | 9 | 1007.1851569999998 |

Lệnh đã chạy, sau khi build:

```powershell
java -Xmx1g -cp src_paper2skills/build/classes phshowoa.Main data/Wang_Chen/rcdp1001.txt --workers 4 --runs 30 --quiet --output src_paper2skills/results/wc10-30runs
java -Xmx1g -cp src_paper2skills/build/classes phshowoa.Main data/Wang_Chen/explicit_rcdp5001.vrpsdptw --workers 4 --output src_paper2skills/results/wc50-default
```

Run 50 khách có 30.000 cập nhật: 8.088 SHO, 21.912 WOA; SA đã nhận 2.719 ứng viên
xấu hơn, local search chạy 40 lần và diversification chạy 19 lần. Những bộ đếm này
xác nhận các nhánh chính được thực thi, bao gồm cơ chế SA đã được hiệu chỉnh.

Thời gian trong JSON đo từ lúc bắt đầu solver, gồm khởi tạo và tối ưu, không gồm
đọc file và khởi động JVM. Các lệnh được chạy trong phiên phát triển, có chạy đồng
thời và JVM warm-up; không dùng các thời gian này để kết luận speedup so với paper,
Python hoặc C++.

## Kiểm tra độc lập đầu ra

Một phép kiểm tra bằng Python đọc trực tiếp dữ liệu gốc và JSON đầu ra, không gọi
`Evaluator` của Java, đã kiểm tra **33 file kết quả thực tế**: 31 file `RCdp1001`
(30 runs và một run ban đầu), 2 file `RCdp5001` (một smoke run và một full run).
Tất cả đạt các điều kiện sau:

1. SHA-256 của input trùng metadata.
2. Tuyến bắt đầu/kết thúc đúng depot và không vượt số xe cho phép.
3. Mỗi khách xuất hiện đúng một lần.
4. Tải ban đầu và tải sau mọi lần giao/nhận không vượt capacity.
5. Service start và giờ về depot nằm trong time window.
6. Tổng distance và chi phí tính lại khớp JSON.
7. Lịch sử có `iterations + 1` dòng và best-so-far không xấu đi theo thứ tự NV, TD.

Đầu ra từng run, cấu hình và lịch sử CSV nằm trong `results/` (đã gitignore).
Không suy ra nghiệm tối ưu toàn cục hoặc ưu thế thống kê từ những lần chạy này.
Chưa chạy đủ mọi instance × 30 seeds hoặc các baseline/Friedman/Wilcoxon của paper.
