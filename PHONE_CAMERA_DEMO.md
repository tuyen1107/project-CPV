# Demo laptop + camera dien thoai

Script demo da ho tro 3 kieu nguon vao:

- File video
- Webcam laptop hoac webcam ao tu dien thoai
- IP camera URL tu dien thoai

## 1. Chay tu webcam

Neu dien thoai dang duoc map thanh webcam tren Windows, thu lan luot:

```powershell
python scripts/demo_video_tracking.py --source 0 --show --device cpu --no-save
```

Neu khong len hinh, doi `0` thanh `1` hoac `2`.

## 2. Chay tu IP camera tren dien thoai

Laptop va dien thoai phai cung mang Wi-Fi.

Mo app camera tren dien thoai va bat stream. App thuong se cho mot URL dang:

- `http://192.168.x.x:8080/video`
- `http://192.168.x.x:4747/video`
- `rtsp://192.168.x.x:port/...`

Sau do chay:

```powershell
python scripts/demo_video_tracking.py --source "http://192.168.x.x:8080/video" --show --device cpu --no-save
```

Neu muon vua demo vua luu ket qua:

```powershell
python scripts/demo_video_tracking.py --source "http://192.168.x.x:8080/video" --show --device cpu --output runs/detect/phone_demo.mp4
```

## 3. Demo bang video file co san

```powershell
python scripts/demo_video_tracking.py --source "duong_dan_video.mp4" --show --device cpu --output runs/detect/video_demo_tracked.mp4
```

## 4. Cach dung khi thuyet trinh

- Dat dien thoai ngang de khung hinh rong hon
- Quay xa mot chut de rider box bat duoc ca nguoi va dau
- Bam `q` de thoat cua so demo
- Neu may co GPU, doi `--device cpu` thanh `--device 0`

## 5. Neu bi lag hoac khong nhan camera

- Giam kich thuoc anh: them `--imgsz 512` hoac `--imgsz 416`
- Tang nguong tin cay: them `--conf 0.35`
- Thu URL khac cua app dien thoai, vi moi app co endpoint khac nhau
- Thu webcam index khac: `0`, `1`, `2`
