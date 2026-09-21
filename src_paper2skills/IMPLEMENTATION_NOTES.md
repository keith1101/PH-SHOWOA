# Đối chiếu triển khai Java với PH-SHOWOA

Tài liệu này ghi rõ phần lấy trực tiếp từ [paper](../.agents/PH-SHOWOA_markdown/PH-SHOWOA_2026.md), phần sửa mâu thuẫn và phần phải chọn cách triển khai vì paper thiếu chi tiết. Các hướng dẫn trong `.agents` được dùng làm tài liệu tham khảo; khi chúng lặp lại lỗi hoặc mâu thuẫn của pseudocode, mô hình bài toán ở Section 3 và vai trò vòng SA ngoài ở Algorithm 1 là cơ sở giải quyết.

## Bản đồ Algorithms 1–10

| Thuật toán trong paper | Mã Java | Hành vi triển khai |
| --- | --- | --- |
| 1. PH-SHOWOA | [`Solver.solve`, `Solver.update`](src/main/java/phshowoa/Solver.java) | Khởi tạo; cập nhật song song; chấp nhận qua SA; lưu global best; local search chu kỳ 25; đa dạng hóa sau 50 vòng đình trệ. |
| 2. Initialization | [`Solver.initializeSA`, `Solver.construct`](src/main/java/phshowoa/Solver.java), [`Operators.perturb`](src/main/java/phshowoa/Operators.java) | Tạo `S0` bằng chèn khả thi; SA dùng TD; đề xuất swap, insert, reverse, Pd-shift, Pd-exchange. |
| 3. UPDATE_POSITION_HYBRID | [`Solver.update`](src/main/java/phshowoa/Solver.java) | Nhánh SHO nếu `r < pHybrid`, nhánh WOA trong trường hợp còn lại. |
| 4. BasedOnWOAUpdate | [`Operators.woa`, `Operators.relink`](src/main/java/phshowoa/Operators.java) | Hệ số A/C theo tuyến; encircling/spiral ánh xạ sang thứ tự khách; perturb có kiểm soát; rollback/sửa khả thi; trả candidate cho SA ngoài. |
| 5. BasedOnSHOUpdate | Nhánh SHO của [`Solver.update`](src/main/java/phshowoa/Solver.java) | Tournament tối đa 3 cá thể không lặp; crossover; mutation xác suất 0.35; trả candidate cho SA ngoài. |
| 6. CrossoverGuided | [`Operators.crossover`](src/main/java/phshowoa/Operators.java) | Giữ 1 hoặc 2 tuyến từ best; lấy thứ tự partner rồi current, bỏ khách đã giữ/trùng; tái dựng và kiểm tra đầy đủ. |
| 7. MutationOperators | [`Operators.mutate`](src/main/java/phshowoa/Operators.java) | Chọn trong tuyến hoặc giữa tuyến với xác suất bằng nhau; kiểm tra toàn nghiệm, rollback nếu sai. |
| 8. CombinedLocalSearch | [`Operators.localSearch`](src/main/java/phshowoa/Operators.java) | First improvement theo thứ tự 2-opt, relocate trong/giữa tuyến, swap giữa tuyến; thử sửa candidate và bắt đầu lại từ 2-opt sau cải thiện. |
| 9. FeasibilityCheck | [`Evaluator.checkRoute`, `Evaluator.isFeasible`](src/main/java/phshowoa/Evaluator.java) | Kiểm tra tải vật lý, cửa sổ thời gian, depot, đội xe và đúng một lần cho mỗi khách; không thay đổi nghiệm. |
| 10. RepairProcedure | [`Repair.repair`, `Repair.insert`](src/main/java/phshowoa/Repair.java) | Xử lý trùng/thiếu khách, tải/thời gian, hạn đội xe, 2-opt và kiểm tra cuối; trả `null` khi sửa thất bại. |

`Solution` giữ các tuyến chỉ gồm chỉ số khách hàng, depot hai đầu là ngầm định. Constructor sao chép dữ liệu tuyến và loại tuyến rỗng; mọi toán tử làm việc trên bản sao. `Problem` sao chép input khi tạo, các mảng công khai được xem là chỉ đọc trong bộ giải.

## Sửa các mâu thuẫn ảnh hưởng tính đúng

### Tải xe theo Section 3

Algorithm 9 in trong paper bắt đầu `load=0` và cộng `delivery-pickup`. Quy ước này không mô tả lượng hàng thực trên xe của VRPSPDTW: nó có thể bỏ qua quá tải lúc xuất phát hoặc từ chối tuyến nhận hàng hợp lệ. Bản Java dùng:

```text
load lúc rời depot = tổng delivery của mọi khách trên tuyến
sau khi phục vụ khách c: load = load - delivery[c] + pickup[c]
kiểm tra 0 <= load <= Q lúc xuất phát và sau mọi khách
```

Nhờ đó lượng nhận ở khách cuối cũng được kiểm tra trước khi xe quay về depot. Mỗi khách vẫn là một lần ghé với cả giao và nhận; Pd-shift/Pd-exchange di chuyển cả lượt ghé đó, không tách thành hai đỉnh như bài toán pickup-delivery có cặp nguồn/đích.

### Thời gian, depot, đội xe và độ phủ

Xe rời depot tại `e0`. Ở mỗi khách, tính thời gian đến bằng ma trận `travelTime`, chờ đến `ready`, kiểm tra thời điểm **bắt đầu** phục vụ không vượt `due`, rồi cộng thời gian phục vụ. Cuối tuyến cộng thời gian quay lại depot và kiểm tra hạn `l0`. Việc xuất phát tại thời điểm sớm nhất là đủ cho kiểm tra khả thi khi được phép chờ.

Mỗi nghiệm phải dùng tối đa `J` xe và phục vụ mọi khách đúng một lần. Không cộng thêm 3 xe như parser cũ của repo. Sai số kiểm tra tải/thời gian là `1e-9`; đây là dung sai số học, không phải cho phép vi phạm ràng buộc có chủ đích. `Evaluator` kiểm tra khả thi độc lập với tính fitness, và CLI kiểm tra lại nghiệm cuối trước khi ghi JSON.

### Crossover phải kiểm tra cả tuyến

Algorithm 6 chỉ tích lũy chênh lệch nhu cầu khi dựng tuyến, nên kiểm tra đó không đủ cho tải xuất phát, tải trung gian hay khung thời gian. Khi thêm khách, bản Java đánh giá lại cả tuyến với tổng lượng giao mới, thời gian phục vụ và đường về depot. Sau dựng tuyến, toàn nghiệm phải qua kiểm tra/sửa độ phủ và giới hạn xe. Nếu không sửa được, trả lại nghiệm current khả thi.

### Algorithm 4/5 trả candidate cho Algorithm 1

Algorithm 1 cần nhận candidate để có thể chấp nhận bước đi kém hơn bằng SA. Trong khi đó Algorithm 4 có cập nhật greedy nội bộ rồi trả global best; Algorithm 5 cũng lọc theo fitness trước khi trả và có nhánh trả bestHyena. Làm nguyên như vậy sẽ chặn phần lớn bước kém hơn trước khi chúng tới SA và tăng áp lực hội tụ về best.

Bản Java giữ vai trò điều khiển của Algorithm 1: WOA và SHO tạo candidate khả thi, không cập nhật cá thể quần thể hoặc global best bên trong toán tử và không áp dụng lọc greedy thứ hai. Global best chỉ được xét trong bước hợp nhất của solver. Candidate không thể sửa được thì giữ current. Đây là thay đổi ngữ nghĩa có chủ đích để giải quyết mâu thuẫn pseudocode, không phải bản sao từng dòng Algorithms 4/5.

## Phần paper thiếu định nghĩa cụ thể

### Tạo nghiệm S0 và SA khởi tạo

Paper đưa `S0` vào Algorithm 2 nhưng không cho một thủ tục dựng đầy đủ. Bản Java thử thứ tự khách ưu tiên hạn `due` ở lần đầu, dùng xáo trộn để phân xử các khách cùng hạn; các lần sau dùng thứ tự ngẫu nhiên. Với mỗi khách, thử mọi vị trí trong các tuyến có sẵn và chọn vị trí khả thi có mức tăng khoảng cách nhỏ nhất; chỉ mở tuyến đơn khi không có vị trí chèn. Sau đó sửa/kiểm tra toàn nghiệm, gồm giới hạn `J`.

Mỗi cá thể có tối đa 200 lần dựng theo mặc định. Nếu một số cá thể thất bại nhưng có một cá thể dựng được, dùng nghiệm đó làm hạt giống cho SA của các vị trí còn thiếu với RNG riêng. Nếu tất cả thất bại, báo lỗi rõ ràng; heuristic không cung cấp chứng minh vô nghiệm.

Section 4.2 nói rõ tối ưu TD ở giai đoạn khởi tạo, trong khi pseudocode dùng tên `CalculateObjective` không thống nhất. Bản Java dùng **TD cho cả chấp nhận và lưu nghiệm tốt nhất trong SA khởi tạo**. Quần thể tạo xong mới được xếp theo `(NV, TD)`.

Các mặc định do triển khai chọn là `T0=1`, `alpha=0.9`, `Tmin=0.01`, 20 đề xuất mỗi mức nhiệt. Mỗi đề xuất chọn đều một trong 5 toán tử; toán tử không áp dụng được trở thành bước không đổi. Candidate sai ràng buộc bị loại. Xác suất chấp nhận dùng công thức chuẩn hóa của Algorithm 1 với `1e-6` ở mẫu để xử lý TD bằng 0. Kiểm tra cấu hình từ chối lịch giảm nhiệt vượt 100.000 mức hoặc bị đứng do độ chính xác số thực, để tránh vòng khởi tạo không kết thúc.

### Ánh xạ WOA liên tục sang tuyến rời rạc

Paper gọi `ENCIRCLING_PREY` và `SPIRAL_MOVEMENT` nhưng không cung cấp đủ mã/formula rời rạc để khôi phục duy nhất chúng. Bản Java dùng thứ tự tương đối của **các khách chung** giữa tuyến hiện tại và tuyến best cùng chỉ số. Các khách chung giữ nguyên tập vị trí đang chiếm trong tuyến; phép chèn theo hạng điều chỉnh thứ tự tại các vị trí này về thứ tự trong best. ID khách hàng không được dùng như tọa độ số học.

Với `m` khách chung, số bước chèn được chặn trong `[1,m-1]` khi `m>=2`:

- Encircling: `ceil(m × (1-|A|) × C/2)`; dấu A chọn đầu thứ tự được chỉnh trước.
- Spiral: đặt `l=C-1`, rồi lấy `ceil(m × min(1, |exp(l) × cos(2πl)|))`; dấu l chọn đầu thứ tự được chỉnh trước.

Nếu có ít hơn 2 khách chung, hai phép này không đổi tuyến. Chỉ xử lý các chỉ số tuyến đến `min(currentRoutes,bestRoutes)-1`, như Algorithm 4. Khi `p<0.5` và `|A|>=1`, chọn thao tác trong/giữa tuyến theo nhánh ngẫu nhiên có trong pseudocode. Mỗi thay đổi sai ràng buộc bị rollback; sau cùng kiểm tra toàn nghiệm, thử repair nếu cần, rồi giữ current khi thất bại. Không mở hàng loạt tuyến đơn làm fallback vì có thể vượt `J`.

Ánh xạ theo hạng là lựa chọn kỹ thuật của bản này. Nó ảnh hưởng động lực tìm kiếm và không được diễn giải như mã WOA rời rạc gốc của tác giả đã được khôi phục.

### SHO và tác dụng thực của Algorithm 6

Tournament lấy tối đa 3 cá thể khác vị trí, không hoàn lại; chọn theo `(NV, TD)`. Crossover giữ 1 tuyến của best với xác suất 0.6 hoặc 2 tuyến với xác suất 0.4, giới hạn bởi số tuyến thực có; các tuyến được chọn ngẫu nhiên và giữ nguyên thứ tự khách.

Phần còn lại được duyệt theo **partner trước, current sau**, dùng tập có thứ tự để loại trùng theo pseudocode. Khi partner là nghiệm đầy đủ, nó đã cung cấp tất cả khách chưa giữ, nên current thường không đóng góp thêm thứ tự khách; current chủ yếu còn vai trò nghiệm dự phòng. Vì vậy không khẳng định đây là phép trộn có tác dụng từ cả ba bố mẹ trong mọi lần crossover, dù phần diễn giải của paper dùng mô tả đó. Không tự bổ sung một cơ chế trộn ba bố mẹ khác ngoài Algorithm 6.

### Đa dạng hóa, local search và sửa nghiệm

Paper gọi `DIVERSIFY` nhưng không mô tả cơ chế. Mặc định của bản Java chọn `ceil(20% × population)` cá thể kém nhất, thực hiện 5 mutation khả thi liên tiếp cho mỗi cá thể. Nếu cá thể vẫn bằng nghiệm ban đầu, thử dựng lại từ thứ tự khách ngẫu nhiên; khi dựng lại thất bại thì giữ ứng viên đang có. Global best được lưu riêng và không bị mất khi quần thể đổi.

Local search dùng first improvement theo Algorithm 8 và không giới hạn số vòng cải thiện. Relocate cho phép trong/giữa các tuyến hiện có; khi tuyến nguồn rỗng thì loại tuyến đó. 2-opt đảo đoạn gồm ít nhất hai khách và tính lại khoảng cách có hướng đầy đủ, không dùng công thức delta giả định đối xứng. Mỗi candidate có thể qua repair trước khi xét mục tiêu.

Repair làm trên bản sao; giữ lần xuất hiện trùng có chi phí chèn biên nhỏ nhất, chèn khách thiếu, xử lý tuyến sai tải/thời gian, giảm đội xe nếu đang vượt `J`, rồi thử 2-opt khả thi. Pha di chuyển khách vi phạm được chặn tối đa `4 × số nút` bước để tránh lặp vô hạn. Khi sửa tải, ưu tiên khách có `|delivery-pickup|` lớn nhất như paper, rồi chèn vào tuyến khác theo mức tăng khoảng cách nhỏ nhất. Khi sửa thời gian, chọn khách trễ đầu tiên hoặc khách cuối tuyến nếu trễ depot; chèn lại được phép đổi thứ tự ngay trong tuyến nguồn. Cụm “earliest arrival” được cụ thể hóa thành thời điểm bắt đầu phục vụ sớm nhất tại vị trí mới, phân xử hòa bằng mức tăng khoảng cách nhỏ nhất. Mọi vị trí chèn đều phải thỏa **mọi** ràng buộc tuyến, và chỉ mở tuyến đơn khi không chèn được vào các tuyến có sẵn. 2-opt của repair giảm TD trong khi vẫn giữ thời gian hợp lệ; với ma trận độc lập, giảm TD không nhất thiết giảm travel time.

Repair có thể tạm tạo nhiều hơn `J` tuyến trong bản sao, rồi thử dồn khách từ một tuyến vào các tuyến khác. Chỉ nghiệm cuối đủ ràng buộc mới được trả ra. Thất bại được biểu diễn bằng `null`, caller giữ nghiệm gốc; không đánh đồng nghiệm chưa sửa được với nghiệm khả thi.

## <a id="ham-muc-tieu"></a>Hàm mục tiêu

So sánh nghiệm tốt nhất, tournament và local search dùng trực tiếp cặp `(NV, TD)`: NV ít hơn luôn tốt hơn; cùng NV thì TD nhỏ hơn tốt hơn.

`operational_cost` giữ đúng hệ số của input: `u1 × NV + u2 × TD`. Một `u1` cố định không tự bảo đảm thứ bậc trên mọi ma trận, đặc biệt dữ liệu có khoảng cách lớn. Với `n` khách, mỗi nghiệm có `n+K` cung và `K<=min(n,J)`. Đặt:

```text
distanceWeight = u2 nếu u2 > 0; ngược lại bằng 1
B = (n + min(n,J)) × max(distance[i][j]) × distanceWeight
vehicleWeight = max(u1, nextUp(B + 1))
fitness = vehicleWeight × NV + distanceWeight × TD
```

Hệ số này lớn hơn một chặn trên của thành phần khoảng cách, kể cả ma trận có hướng không thỏa bất đẳng thức tam giác. Fitness dùng cho SA giữ cùng thứ bậc lý tưởng với `(NV, TD)`, trong giới hạn độ chính xác `double`. Chi phí quá lớn gây tràn fitness hữu hạn được từ chối. Khi `u2=0`, hệ số khoảng cách nội bộ bằng 1 để vẫn tối ưu TD; chi phí vận hành vẫn dùng `u2=0` đúng theo input.

Do mẫu chuẩn hóa SA chứa fitness hiện tại, thay hệ số xe có thể thay xác suất chấp nhận ngay cả khi thứ tự nghiệm không đổi. JSON lưu riêng `vehicle_weight`, `distance_weight`, hệ số dữ liệu, fitness và operating cost để có thể phân tích ảnh hưởng này. Không sử dụng fitness đã đổi hệ số như thể đó là chi phí gốc của paper.

## Song song hóa và khả năng lặp lại

Chỉ có **một quần thể**. Khởi tạo và các cập nhật cá thể chạy qua `ExecutorService`; mọi worker đọc snapshot quần thể và global best ở đầu thế hệ. Kết quả được hợp nhất theo chỉ số cá thể, sau khi các worker hoàn tất. Không có cập nhật best trực tiếp giữa các worker, islands, migration hoặc CUDA.

Mỗi RNG được suy ra từ seed gốc, pha, vòng lặp và chỉ số cá thể. Với cùng input, cấu hình tìm kiếm và runtime, thay số worker giữ chuỗi quyết định ngẫu nhiên theo cá thể; bộ kiểm thử so sánh chạy tuần tự/song song. Thời gian thực thi không thể giống nhau và không thuộc cam kết lặp lại. Không tuyên bố nghiệm hoặc seed trùng với triển khai Java chưa được cung cấp của tác giả paper.

Vòng lặp đánh số `t=0,...,MAX_ITER-1`, theo Algorithm 1:

```text
a = 2 - 2 × t/MAX_ITER
pHybrid = max(0.15, 0.5 × (1 - t/MAX_ITER))
T = 1 - t/MAX_ITER
P(accept worse) = exp(-(nf-cf)/(1e-6 + T × |cf|))
```

Vì vậy a/T chưa bằng 0 ở lần cập nhật cuối. Local search mặc định chạy tại `t=0,25,50,...`, gồm vòng 0 đúng điều kiện modulo in trong paper. Mọi giảm NV đặt lại bộ đếm đình trệ; khi NV bằng nhau phải giảm TD vượt `epsilon`. Best vẫn được lưu khi có cải thiện TD nhỏ hơn epsilon, nhưng chưa nhất thiết đặt lại bộ đếm.

## Dữ liệu, độ chính xác và giới hạn tái lập

Parser giữ tách biệt ma trận distance/travelTime, hướng của từng cung và ID bên ngoài. EXPLICIT bắt buộc đầy đủ mọi cung khác nút; chỉ đường chéo được suy ra là 0 theo tập cạnh của Section 3. Depot khai báo được ánh xạ vào vị trí nội bộ 0, nên cả ID bắt đầu từ 0/1 và ID không liên tục đều được xử lý.

Wang–Chen dạng tọa độ dùng Euclid không làm tròn trước khi tối ưu và thời gian di chuyển bằng khoảng cách. EXPLICIT giữ các số đã lưu; bản chuyển đổi có làm tròn có thể khác nhẹ so với tính trực tiếp từ tọa độ. Cần đối chiếu cùng file input/SHA-256, quy tắc làm tròn, cấu hình, seed và cách đo thời gian trước khi so TD hoặc tốc độ. Sai số nhỏ cũng có thể thay thứ tự chấp nhận khi hai nghiệm rất gần nhau.

Các giá trị paper được dùng là 1000 vòng, 30 cá thể và, khi chủ động chọn `--runs 30`, 30 lần chạy. CLI mặc định một lần để chạy thử thuận tiện. Các hằng số chưa được paper cho đầy đủ được công khai trong `Config` và ghi vào JSON.

Chưa có mã nguồn Java gốc, định nghĩa rời rạc WOA đầy đủ, cấu hình chi tiết khởi tạo/đa dạng hóa hay seed thí nghiệm của tác giả để bảo đảm khôi phục đúng từng quyết định tìm kiếm. Bản này cũng chưa có baseline SHO thuần/WOA thuần, phân tích Friedman/Wilcoxon, hay tái lập toàn bộ bảng và các so sánh thống kê của paper. Kiểm thử tính đúng, chạy được trên dữ liệu và kết quả khả thi không tự chứng minh chất lượng ngang paper hoặc ưu thế thống kê. Xem [VERIFICATION.md](VERIFICATION.md) cho phạm vi và bằng chứng các lượt kiểm chứng đã thực hiện.
