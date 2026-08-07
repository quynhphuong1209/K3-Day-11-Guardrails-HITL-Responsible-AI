# VinBank Chatbot Demo

Giao diện chatbot tương tác để test guardrails trong Assignment 11.

## Cài đặt

```powershell
# 1. Cài Flask (nếu chưa có)
pip install flask flask-cors

# Hoặc cài toàn bộ từ requirements.txt
pip install -r requirements.txt
```

## Chạy Demo

### Bước 1: Khởi động Backend Server

```powershell
# Từ thư mục gốc project
python demo/server.py
```

Server sẽ chạy tại: `http://localhost:8000`

### Bước 2: Mở Frontend

Mở file `demo/chat.html` trong trình duyệt:
- Cách 1: Double-click file `chat.html`
- Cách 2: `start demo/chat.html` (Windows)

## Tính năng

### ✅ Giao diện Chat Thực Tế
- Chat bubbles với avatar
- Typing indicator animation
- Auto-scroll messages
- Responsive design

### 🛡️ Guardrails Active
- Input injection detection
- Output content filtering
- Topic filtering
- Secret redaction

### 🎯 Quick Tests
Chatbot có sẵn các suggestion cards để test:

1. **Lãi suất tiết kiệm** - Câu hỏi banking hợp lệ
2. **Thẻ tín dụng** - Dịch vụ ngân hàng
3. **Test Injection** - Prompt injection tiếng Anh
4. **Test Multilingual** - Injection tiếng Việt

### 📊 Visual Feedback
- ✅ Tin nhắn hợp lệ: màu xanh dương (user), xám (bot)
- ⛔ Tin nhắn bị chặn: viền đỏ + background đỏ nhạt
- 🟢 Status indicator: "Guardrails Active" (live pulse)

## Kiến trúc

```
Frontend (chat.html)
    ↓ HTTP POST /chat
Backend (server.py)
    ↓ call agent
Protected Agent
    → InputGuardrailPlugin
    → Gemini LLM
    → OutputGuardrailPlugin
    ↓ return response
Frontend (display)
```

## API Endpoints

### `POST /chat`
**Request:**
```json
{
  "message": "Lãi suất tiết kiệm 12 tháng là bao nhiêu?"
}
```

**Response:**
```json
{
  "response": "Lãi suất tiết kiệm 12 tháng hiện tại là...",
  "blocked": false,
  "metadata": {}
}
```

### `GET /health`
Health check endpoint.

## Screenshots

### Safe Query
![Safe](../outputs/chat_safe.png)

### Blocked Attack
![Blocked](../outputs/chat_blocked.png)

## Troubleshooting

### Lỗi: `Connection refused`
- Kiểm tra server đã chạy chưa: `python demo/server.py`
- Kiểm tra port 8000 chưa bị chiếm bởi process khác

### Lỗi: `CORS error`
- Server đã có `flask-cors` enabled
- Nếu vẫn lỗi, thử mở chat.html qua HTTP server thay vì file://

### Lỗi: `Module not found`
```powershell
pip install flask flask-cors python-dotenv google-genai google-adk
```

## Tech Stack

**Frontend:**
- Pure HTML/CSS/JavaScript
- Inter font (Google Fonts)
- CSS animations & gradients
- Fetch API

**Backend:**
- Flask (Python web framework)
- Flask-CORS (cross-origin support)
- Google ADK + Gemini
- Async/await with asyncio

**Design:**
- Deep navy background (#0B0E14)
- Cyan/Teal accents (#22D3EE, #4FD1C5)
- Glassmorphism effects
- Smooth animations
