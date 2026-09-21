# PH-SHOWOA bằng Java từ paper và skills

Thư mục này triển khai độc lập bộ giải PH-SHOWOA cho bài toán giao và nhận hàng đồng thời có khung thời gian (VRPSPDTW), bằng Java 8 và thư viện chuẩn. Nguồn đối chiếu là [paper đã chuyển sang Markdown](../.agents/PH-SHOWOA_markdown/PH-SHOWOA_2026.md) và các tài liệu thuật toán trong [`.agents`](../.agents). Hai tài liệu `docs/walkthrough.md` và `docs/agent_knowledge_transfer.md` cung cấp bối cảnh cho các bản Python/C++ có sẵn.

Bộ giải thực hiện Algorithms 1–10, với các chỗ mâu thuẫn hoặc thiếu định nghĩa được ghi rõ trong [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md). Mục tiêu là ưu tiên số xe `NV`, sau đó tổng quãng đường `TD`, đồng thời giữ đầy đủ ràng buộc tải, thời gian, depot, số xe có sẵn và phục vụ mỗi khách đúng một lần. Đây là triển khai thuật toán; việc tái lập toàn bộ bảng kết quả và kiểm định thống kê của paper là một công việc riêng.

## Biên dịch và kiểm thử

Cài JDK 8 trở lên, bảo đảm `java` và `javac` có trong `PATH`. Chạy các lệnh sau từ thư mục gốc repo `PH-SHOWOA`.

PowerShell:

```powershell
.\src_paper2skills\build.ps1
.\src_paper2skills\build.ps1 -Test
```

Linux/macOS hoặc môi trường có POSIX shell:

```sh
sh src_paper2skills/build.sh
sh src_paper2skills/build.sh --test
```

Script biên dịch đặt bytecode vào `src_paper2skills/build/classes`. Kiểm thử không cần JUnit, Maven, Gradle hay thư viện bên ngoài. Bộ kiểm thử bao phủ tải lúc xuất phát và tải trung gian, lượt nhận hàng cuối tuyến, chờ và thời gian phục vụ, hạn depot, giới hạn đội xe, độ phủ khách hàng, dữ liệu có hướng, sửa nghiệm, mục tiêu thứ bậc, SA và kết quả tuần tự/song song với cùng seed.

Các lệnh đã kiểm chứng và kết quả chạy thực được ghi riêng trong [VERIFICATION.md](VERIFICATION.md); báo cáo đó phân biệt kiểm thử tính đúng với thí nghiệm so sánh paper.

## Chạy thử

Ví dụ nhỏ dùng ID khách hàng không liên tục:

```powershell
java -Xmx1g -cp src_paper2skills/build/classes phshowoa.Main src_paper2skills/examples/tiny.txt --iterations 50 --population 10 --workers 2 --seed 42 --output src_paper2skills/results/tiny
```

Ví dụ có ma trận khoảng cách và thời gian khác nhau, ID bắt đầu từ 1, thứ tự dòng depot không đứng đầu:

```powershell
java -Xmx1g -cp src_paper2skills/build/classes phshowoa.Main src_paper2skills/examples/tiny-directed.vrpsdptw --iterations 50 --population 10 --workers 2 --output src_paper2skills/results/tiny-directed
```

Chạy một instance thực với cấu hình quần thể/vòng lặp của paper:

```powershell
java -Xmx1g -cp src_paper2skills/build/classes phshowoa.Main data/Wang_Chen/rcdp1001.txt --iterations 1000 --population 30 --workers 4 --seed 42 --output src_paper2skills/results/rcdp1001
```

PowerShell cũng có wrapper tự biên dịch trước mỗi lần chạy:

```powershell
.\src_paper2skills\run.ps1 data/Wang_Chen/rcdp1001.txt --workers 4 --output src_paper2skills/results/rcdp1001-wrapper
```

CLI mặc định chạy **một lần**. Paper chạy 30 lần độc lập; cần truyền `--runs 30` để thực hiện số lần tương ứng:

```powershell
java -Xmx1g -cp src_paper2skills/build/classes phshowoa.Main data/Wang_Chen/rcdp1001.txt --iterations 1000 --population 30 --runs 30 --seed 42 --workers 4 --output src_paper2skills/results/rcdp1001-30runs
```

Các lần lặp dùng seed từ `42` đến `71` trong ví dụ này. Có thể truyền nhiều đường dẫn instance trước các tùy chọn. Các instance và các lần chạy được xử lý lần lượt; song song hóa nằm bên trong mỗi lần chạy.

## Benchmark nhiều instance

Script [`scripts/benchmark_java.py`](../scripts/benchmark_java.py) là bản tương ứng với `benchmark_cpp.py` cho Java. Nó biên dịch Java một lần, chạy từng instance/seed trong JVM riêng, kiểm tra JSON khả thi mà solver xuất ra, lưu artifact từng run, hỗ trợ resume theo fingerprint của source/input/cấu hình, rồi tạo `summary.csv` và `report.md`.

Script cần Python 3.9+ và `java`/`javac` có trong `PATH`. Chạy smoke test một instance:

```powershell
python scripts\benchmark_java.py --instances RCdp1001 --repeats 1 --iterations 2 --population 3 --workers 1 --init-moves 0 --output-tag java-smoke
```

Chạy đúng quy mô lặp của paper trên 16 instance mặc định:

```powershell
python scripts\benchmark_java.py --repeats 30 --iterations 1000 --population 30 --workers 4 --output-tag java-paper-30runs
```

Kết quả nằm trong `batch_results/<output-tag>/`: mỗi run có log, JSON của Java, history CSV và `summary.json` của benchmark. Chạy lại cùng cấu hình sẽ dùng lại run đã thành công; dùng `--skip-build` khi class file hiện tại đã được biên dịch. Các giá trị paper trong report chỉ là tham chiếu mô tả: khi so TD, cần ưu tiên dòng `TD @ Paper NV`/`Same-NV gap`, vì Java tối ưu lexicographic và có các hiệu chỉnh đã ghi trong `IMPLEMENTATION_NOTES.md`.

## Tùy chọn

| Tùy chọn | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `--iterations` | `1000` | Số thế hệ tiến hóa; `0` chỉ khởi tạo quần thể. |
| `--population` | `30` | Số cá thể trong một quần thể. |
| `--workers` | `min(30, availableProcessors)` | Số luồng; tối thiểu 1. |
| `--seed` | `42` | Seed gốc; mỗi lần chạy tăng thêm 1. |
| `--runs` | `1` | Số lần chạy cho mỗi instance. |
| `--output` | `src_paper2skills/results` | Thư mục đầu ra của một batch. |
| `--quiet` | tắt | Ẩn tiến độ; vẫn in kết quả cuối mỗi lần chạy. |
| `--init-temperature` | `1.0` | Nhiệt độ ban đầu của SA khởi tạo. |
| `--init-cooling` | `0.90` | Hệ số giảm nhiệt của SA khởi tạo. |
| `--init-min-temperature` | `0.01` | Ngưỡng dừng giảm nhiệt. |
| `--init-moves` | `20` | Số đề xuất láng giềng ở mỗi mức nhiệt; `0` bỏ qua SA khởi tạo. |
| `--construction-attempts` | `200` | Số lần thử tạo nghiệm khả thi ban đầu cho mỗi cá thể. |
| `--ls-interval` | `25` | Chu kỳ local search trên nghiệm tốt nhất; tính từ chỉ số vòng lặp 0. |
| `--stagnation` | `50` | Số vòng không có cải thiện đáng kể trước khi đa dạng hóa. |
| `--epsilon` | `0.0001` | Ngưỡng cải thiện TD để đặt lại bộ đếm đình trệ khi NV bằng nhau. |
| `--mutation-probability` | `0.35` | Xác suất mutation sau crossover của nhánh SHO. |
| `--diversification-fraction` | `0.20` | Tỷ lệ cá thể kém nhất được đa dạng hóa. |
| `--diversification-moves` | `5` | Số lần mutation cho mỗi cá thể được chọn để đa dạng hóa. |

`--help` liệt kê cú pháp CLI. Các tham số SA khởi tạo, cách tạo nghiệm ban đầu và cơ chế đa dạng hóa là lựa chọn triển khai cho phần paper chưa đặc tả đầy đủ; ghi chúng cùng seed khi so sánh các lần chạy.

## Dữ liệu đầu vào và kết quả

`InstanceReader` hỗ trợ hai dạng trong repo:

- **Wang–Chen `.txt`:** bảng gồm ID, tọa độ X/Y, lượng giao, lượng nhận, thời gian sẵn sàng, hạn bắt đầu phục vụ và thời gian phục vụ. Dòng đầu tiên của bảng là depot. Từ tọa độ tính khoảng cách Euclid với `double`, thời gian di chuyển bằng khoảng cách; hệ số chi phí mặc định là `u1=2000`, `u2=1` như phần WC của paper.
- **EXPLICIT `.vrpsdptw`:** đọc nguyên các cung có hướng trong `DISTANCETIME_SECTION`, gồm `from,to,distance,time`; đọc depot từ `DEPOT_SECTION` và các hệ số chi phí từ header. Khoảng cách và thời gian được giữ tách biệt. Bắt buộc có mọi cung ngoài đường chéo; self-arc có thể được bỏ qua và có giá trị 0. Thiếu cung, trùng ID, kiểu dữ liệu không hỗ trợ hoặc dữ liệu sai định dạng gây lỗi rõ ràng.

ID bên ngoài được ánh xạ sang chỉ số nội bộ; depot luôn có chỉ số nội bộ 0. JSON đầu ra dùng lại ID gốc và ghi rõ depot ở hai đầu mỗi tuyến. File tọa độ và file EXPLICIT được chuyển đổi từ nó có thể cho TD hơi khác nhau do số chữ số làm tròn đã lưu trong EXPLICIT.

Mỗi lần chạy ghi:

- `<instance>-seed-<seed>.json` với tiền tố thứ tự input: nghiệm, cấu hình, SHA-256 của input, phiên bản Java, NV, TD, chi phí vận hành, fitness, thời gian và bộ đếm thuật toán.
- File `*-history.csv`: nghiệm tốt nhất và số nghiệm khác nhau trong quần thể sau khởi tạo (`iteration=-1`) và sau từng vòng lặp.
- `summary.csv`: mỗi dòng là một instance/lần chạy trong batch hiện tại.

`operational_cost = dispatchCost × NV + unitCost × TD` là chi phí theo dữ liệu. `fitness` dùng hệ số xe được suy ra để bảo đảm ưu tiên số xe; hai trường này có thể khác nhau. Xem công thức và phạm vi áp dụng trong [ghi chú triển khai](IMPLEMENTATION_NOTES.md#ham-muc-tieu).

Thư mục đầu ra đại diện cho một batch. Chạy lại vào cùng thư mục sẽ ghi đè `summary.csv` và các file có cùng tên; CLI chưa có chức năng tiếp tục batch dang dở. Dùng thư mục khác nhau để giữ các thí nghiệm độc lập.

## Phạm vi

Triển khai dùng một quần thể, `ExecutorService`, snapshot theo thế hệ và RNG riêng cho từng cá thể. Nó không dùng các mở rộng islands hoặc CUDA trong bản C++ của repo. Chưa triển khai bộ giải SHO thuần, WOA thuần, kiểm định Friedman/Wilcoxon hay quy trình tái lập toàn bộ bảng thống kê của paper. Các kết quả cũ của Python/C++ không phải kết quả xác nhận cho bản Java này.

Nếu không dựng được nghiệm khả thi sau số lần thử cấu hình, chương trình báo lỗi và không xuất nghiệm không hợp lệ. Thông báo này chỉ cho biết heuristic khởi tạo đã thất bại trong ngân sách thử; nó không chứng minh instance vô nghiệm. Local search duyệt láng giềng và kiểm tra đầy đủ tuyến nên thời gian chạy có thể tăng mạnh trên instance lớn.
