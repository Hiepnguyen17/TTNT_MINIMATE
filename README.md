# MINIMATE — baseline terminal tuần 9

Chương trình Python dùng luật/từ khóa tiếng Việt, SQLite cục bộ và ESP32 giả lập. Không dùng LLM, machine learning hoặc phần cứng thật. Cần Python 3.10 trở lên; chỉ dùng thư viện chuẩn, không cần `pip install`.

## Chạy

Từ thư mục project:

```text
python src/main.py
```

Nhập mỗi yêu cầu trên một dòng. Nhập `/quit`, gửi EOF hoặc Ctrl+C để thoát. Dữ liệu mặc định ở `data/minimate.db`, được giữ khi mở lại chương trình và bị loại khỏi Git. Có thể chọn tệp khác bằng `python src/main.py --db data/demo.db`.

## Ví dụ câu nhập

```text
Xin chào
Bắt đầu học 25 phút
Còn bao lâu?
Trạng thái phiên học?
Nhắc lại
Dừng học
Bắt đầu học
25 phút
Hủy phiên học
Nhắc tôi đi thi sau 2 ngày lúc 8 giờ
Xem lịch đã lưu
Tại sao trời xanh?
Ngày mai 8 giờ
/quit
```

Mỗi yêu cầu có JSON response gồm `intent`, `confidence`, `action`, `text`, `device_state`, `session_state`. Điểm confidence là điểm quy ước của luật, không phải xác suất mô hình. Các dòng `ESP32 <- {...}` mô phỏng lệnh gửi đến ESP32. Backend chỉ gửi `set_state` và `speak`, không điều khiển màn hình hoặc loa. `speak` chỉ in lệnh, không phát âm thanh. Adapter có hàm `receive` để thử sự kiện JSON giả lập trong unit test; terminal nhập text trực tiếp, không giả vờ đã nhận audio thật.

## Cấu trúc

| Tệp | Trách nhiệm |
|---|---|
| `src/main.py` | Vòng lặp terminal, nhận text, kiểm tra hết giờ trong lúc chờ nhập, in JSON và gửi lệnh mô phỏng. |
| `src/minimate/intent_baseline.py` | Chuẩn hóa Unicode/chữ thường/khoảng trắng, nhận diện đúng 7 nhóm intent theo tài liệu. |
| `src/minimate/task_manager.py` | Điều phối, xử lý lời nhắc, tạo phản hồi bằng mẫu câu; phần Response Generator được giữ dưới dạng tạo response trong module này. |
| `src/minimate/session_manager.py` | Quản lý bắt đầu và hết giờ, tính thời gian còn lại. |
| `src/minimate/storage.py` | SQLite: phiên hiện tại, lịch sử lệnh, lời nhắc; thay đổi phiên/lời nhắc và ghi lệnh trong cùng giao dịch. |
| `src/minimate/esp32_client.py` | Mô phỏng giao tiếp JSON; không có driver phần cứng. |
| `tests/test_baseline.py` | Kiểm thử baseline, nghiệp vụ, lưu trữ và giao tiếp giả lập. |
| `docs/architecture.md` | Bản sao nguyên nội dung kiến trúc gốc ở root. |

## Quy ước và giới hạn baseline

- Một phiên học tại một thời điểm. Thời lượng là số nguyên dương kèm `phút` hoặc `giờ`, tối đa 24 giờ; đây là giới hạn kiểm tra đầu vào của bản chạy thử. Thiếu/sai thời lượng thì chờ nhập bổ sung, không tự đặt mặc định.
- Khi hết giờ, phiên trở về `idle`; không tự hủy khi đóng terminal. Khi mở lại, kiểm tra thời điểm kết thúc đã lưu.
- Lời nhắc hỗ trợ mẫu `Nhắc tôi <nội dung> sau <N> ngày lúc <H> giờ [<M> phút]`, dùng giờ địa phương của máy tính, yêu cầu thời điểm tương lai. Thiếu thông tin thì nhập lại đầy đủ câu. Chỉ lưu và liệt kê; chưa có chức năng tự phát thông báo đến hạn.
- `repeat_response` nhắc lại chữ từ SQLite, không chạy lại hành động. Câu hỏi mở trả thông báo module hội thoại sẽ tích hợp sau.
- `out_of_scope` xử lý câu chưa hiểu hoặc ngoài phạm vi. Baseline chỉ hỗ trợ các mẫu nêu trên, không hiểu toàn bộ tiếng Việt hoặc mọi kiểu câu phủ định/phức hợp.
- `speaking` là mô phỏng xuất phản hồi. Chưa có STT, TTS, micro, ESP32 thật, OLED/TFT hay loa thật.
- Tài liệu kiến trúc hiện tại đã khớp yêu cầu 7 intent và lời nhắc. Giữ nguyên cả bản gốc và bản trong `docs`; tài liệu có lỗi chữ “hai bảng” nhưng liệt kê ba bảng, chương trình triển khai đủ cả ba. Intent `open_question` có trạng thái xử lý `processing`, rồi `speaking` khi xuất phản hồi mẫu.

## Kiểm thử

```text
python -m unittest discover -s tests -v
```

Tests dùng SQLite trong bộ nhớ hoặc thư mục tạm và đồng hồ cố định, không sửa dữ liệu chạy thật. Bao gồm đủ 7 intent, bắt đầu/hủy, chờ thời lượng, thời gian còn lại/hết giờ, nhắc lại không khởi động lại, lời nhắc hợp lệ/sai, lưu và mở lại SQLite, hoàn tác khi ghi thất bại và JSON ESP32.
