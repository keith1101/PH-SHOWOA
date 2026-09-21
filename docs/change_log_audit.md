# Nhật ký thay đổi và đánh giá cải tiến

**Phạm vi.** Tài liệu này đối chiếu lịch sử Git từ `26f9d21` đến `d45e61f`
với working tree tại thời điểm lập nhật ký. Nó dùng để đánh giá các cải tiến
trên mã cũ một cách có thể tái lập; không coi một số đo đơn lẻ là bằng chứng
rằng thuật toán tốt hơn.

## Cách đọc trạng thái

| Trạng thái | Ý nghĩa |
| --- | --- |
| Đã kiểm tra | Có kiểm tra tự động hoặc kiểm tra tính khả thi trực tiếp trong phiên làm việc hiện tại. |
| Có cơ sở kỹ thuật | Thay đổi giải quyết một giới hạn cụ thể trong mã, nhưng chưa có benchmark đối chứng. |
| Chưa xác nhận | Có tuyên bố hoặc thay đổi về hiệu năng/chất lượng nhưng chưa có thí nghiệm tái lập cùng cấu hình. |
| Cần rà soát | Có thể thay đổi kết quả, tính công bằng của benchmark, hoặc điều kiện khả thi. |

## Dòng thời gian từ Git

| Mốc | Commit | Thay đổi chính | Đánh giá hiện tại |
| --- | --- | --- | --- |
| 17-05-2026 | `26f9d21` | Bản Python VRPSPDTW ban đầu. | Mốc nền để so sánh. |
| 26-06-2026 | `7d82685` | Khôi phục mã Python và thêm `compute_backend.py` cho CPU/Numba/CUDA. | Có cơ sở kỹ thuật; cần kiểm tra kết quả CPU/CUDA bằng cùng seed. |
| 26-06-2026 | `cad8cc2` | Thêm script so sánh với paper. | Có cơ sở kỹ thuật; script không tự chứng minh kết quả solver. |
| 27-06-2026 | `1d57b01` | Kiến trúc hybrid CPU–GPU, GPU proxy và cập nhật operator/search. | Chưa xác nhận lợi ích chất lượng; lợi ích tốc độ phụ thuộc cỡ batch và phần cứng. |
| 29-06-2026 | `4459be8` | Bổ sung SA, kiểm tra/đánh giá batch và nhiều thay đổi trong vòng lặp Python. | Cần rà soát: thay đổi lớn (`529` dòng thêm) nhưng không có commit test đi kèm. |
| 30-06-2026 | `0e0aee5` | Thêm solver C++, CUDA backend, benchmark wrapper và test backend. | Có cơ sở kỹ thuật. Không suy ra C++ cho nghiệm tốt hơn Python nếu chưa cố định seed, budget và mục tiêu. |
| 11-07-2026 | `b30fab4` | Viết lại lớn C++: encoding nghiệm, objective/profile, parity test, CPU/CUDA batch. | Có cơ sở kỹ thuật; test parity là cần thiết nhưng chỉ kiểm tra nhất quán encoding, không đo chất lượng metaheuristic. |
| 13-07-2026 | `13da36b` | Chỉnh operator C++ và benchmark wrapper. | Cần benchmark A/B vì thay đổi operator có thể cải thiện hoặc làm giảm chất lượng. |
| 20-07-2026 | `d45e61f` | Thêm đường chạy full-GPU, deterministic RNG và cập nhật benchmark. | Chưa xác nhận. Đây là đường chạy nghiên cứu, cần chứng minh cùng mục tiêu và cùng ràng buộc với CPU/CUDA batched. |

`c98fb5f` đã xóa cây mã rồi `7d82685` thêm lại trong cùng ngày. Nó không phải
một biến thể solver nên không dùng làm mốc đánh giá.

## Những điều tài liệu cũ đã tuyên bố nhưng chưa đủ bằng chứng

`docs/walkthrough.md` và `docs/agent_knowledge_transfer.md` ghi nhận các số
như tăng tốc `49x`, tăng tốc `1.48x`, và vượt kết quả paper ở một số instance.
Các số này là tín hiệu đáng để kiểm tra, nhưng hiện **chưa xác nhận** vì không
có cùng lúc các thông tin sau trong lịch sử Git:

- revision/binary chính xác, command line hoàn chỉnh, seed và số lần lặp;
- cùng instance parser, cùng giới hạn thời gian và số evaluations;
- kiểm tra tính khả thi độc lập cho mọi lần chạy;
- thống kê qua nhiều seed, thay vì một lần chạy;
- đối chứng cùng máy, cùng backend fallback và warm-up CUDA.

Do đó không nên dùng các con số này để quyết định giữ hay bỏ cải tiến.

## Working tree hiện tại: sửa tính đúng đắn Python

Các file Python dưới đây chưa commit. Chúng không phải một tối ưu tốc độ; mục
tiêu là làm chế độ `--paper_flags` thực thi nhất quán hơn với mô hình paper và
loại nghiệm vi phạm ràng buộc trước khi so sánh chất lượng.

| File | Thay đổi | Trạng thái / ảnh hưởng mong đợi |
| --- | --- | --- |
| `src/data.py`, `src/main.py` | Thêm profile paper: `P=30`, `G=1000`, `30` runs, SA parameters; cho phép population 30 thay vì bắt buộc số chính phương; bỏ nới lỏng số xe. | Đã kiểm tra bằng regression test. Có thể làm nghiệm kém hơn các log cũ vì không còn được phép dùng xe vượt giới hạn. |
| `src/eval.py`, `src/solution.py` | Kiểm tra tải âm/dương, depot, số xe; dựng đúng sequence đảo chiều khi đánh giá move; dùng score cố định `2000*NV + TD`. | Đã kiểm tra bằng regression test. Sửa sai lệch đánh giá có thể thay đổi cả thứ hạng nghiệm. |
| `src/compute_backend.py` | CPU/CUDA insertion kiểm tra cả chặng về depot và tải âm; dùng cùng objective với search. | Đã kiểm tra CPU path. CUDA cần kiểm tra lại trên GPU thật. |
| `src/search_framework.py` | Chặn candidate không khả thi trước SA; repair không vượt fleet; độc lập `run_best`; local search/diversification theo profile paper. | Đã kiểm tra smoke test nhỏ. Chưa benchmark hiệu năng/chất lượng trên bộ 16 instance. |
| `README.md` | Tài liệu hóa profile, các lựa chọn rời rạc chưa xác định trong paper, và giới hạn của scalar objective. | Đã rà soát. |

Đã chạy 12 regression/unit tests cho các phần Python liên quan, gồm kiểm tra
fleet, depot return, tải, đánh giá reverse move, CLI profile và smoke test.
Chưa chạy protocol đầy đủ `30 × 1000` iterations; vì vậy không có kết luận
hiệu năng hoặc chất lượng cho thay đổi này.

## Những phần không thuộc log này

Các file/thư mục untracked như `src_paper2skills/`,
`scripts/benchmark_java.py`, `tests/test_benchmark_java.py`, các thư mục
`kaggle-*`, `outputs/` và `node_modules/` không có commit nền để đối chiếu.
Chúng được tách khỏi đánh giá cải tiến của code cũ cho đến khi được commit với
mục tiêu và validation rõ ràng.

## Quy trình quyết định giữ một cải tiến

Chạy mỗi candidate ở cùng revision dữ liệu và cùng command line, thay đổi duy
nhất là feature đang được đánh giá. Dùng tối thiểu 30 seed, lưu route/seed/log
cho từng run, rồi áp dụng lần lượt các cổng sau:

1. **Tính đúng đắn:** mọi route phải thỏa sức chứa, time window, depot return,
   giới hạn xe, và mỗi customer đúng một lần. Một nghiệm lỗi không được tính
   vào kết quả chất lượng.
2. **Công bằng:** cùng population, iterations/evaluation budget, thời gian
   wall-clock khi đánh giá tốc độ, instance parser và fixed objective.
3. **Chất lượng:** báo cáo riêng `NV`, `TD`, objective và tỷ lệ feasible;
   không chỉ báo cáo cost tổng.
4. **Thống kê:** so sánh paired theo seed, median/mean và kiểm định
   Wilcoxon signed-rank hai phía ở mức `alpha = 0.05`.
5. **Hiệu năng:** benchmark sau CUDA warm-up, trên cùng GPU/driver; tách thời
   gian solver khỏi thời gian compile và I/O.

Chỉ giữ một cải tiến khi nó qua cổng tính đúng đắn và có kết quả không xấu hơn
có ý nghĩa theo tiêu chí đã chọn. Nếu mục tiêu là tốc độ, giới hạn chất lượng
và tỷ lệ feasible phải được nêu trước khi chạy.

## Mẫu kết quả cần thêm cho mỗi thử nghiệm

| Feature / revision | Baseline / revision | Instances | Seeds | Feasible | Median NV | Median TD | Median time | Wilcoxon p | Quyết định |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| _điền sau benchmark_ | _điền sau benchmark_ |  |  |  |  |  |  |  | Giữ / Bỏ / Cần thêm dữ liệu |
