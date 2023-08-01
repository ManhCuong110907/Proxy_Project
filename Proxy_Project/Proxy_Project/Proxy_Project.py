import socket
import threading
import ssl
import os
from datetime import datetime, time
cache_data = {}
config = {}
# Hàm đọc file config
def read_config_file(file_path, config):
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=')
                key = key.strip()
                value = value.strip()
                if key == 'cache_time':
                    limit_time,_,unit = value.split(' ',2)
                    config[key] = int(limit_time)
                elif key == 'whitelisting':
                    config[key] = [site.strip() for site in value.split(',')]
                elif key == 'time':
                    start_time, end_time = value.split('-')
                    config['start_time'] = int(start_time.strip())
                    config['end_time'] = int(end_time.strip())

# Hàm kiểm tra xem hiện tại có trong khung giờ cho phép hay không
def is_within_time_range(config):
    current_time = datetime.now()
    return config['start_time'] <= current_time.hour <= config['end_time']

# Hàm truy cập 403
def Error403(client_socket):
    with open('error403.html', 'r') as file:
            response_data = file.read()

        # Tạo phản hồi HTTP chứa nội dung của trang HTML mặc định
    response = f"HTTP/1.1 200 OK\r\nContent-Length: {len(response_data)}\r\n\r\n{response_data}"
    client_socket.sendall(response.encode())

# Hàm xử lý input
def handle_client(client_socket):
    request_data = client_socket.recv(4096)
    request_lines = request_data.split(b'\r\n')

    # Tìm kiếm URL và phương thức yêu cầu
    request_line = request_lines[0].decode()
    request_method, url, _ = request_line.split()

    # Xử lý URL
    #http://oosc.online/

    if url.startswith("http://"):
        url = url[7:]
    elif url.startswith("https://"):
        url = url[8:]

    # Tách thông tin hostname và port (nếu có)
    #testphp.vulnweb.com/login.php
    if '/' in url:
        host_path = url.split('/', 1)
        host = host_path[0]
        path = '/' + host_path[1]
    #oosc.online
    else:
        host = url
        path = '/'
    #kshdfskjh:12124
    if ':' in host:
        remote_host, remote_port = host.split(':', 1)
        remote_port = int(remote_port)
    else:
        remote_host = host
        remote_port = 80
    arrayName = ["GET", "POST", "HEAD"]
    if request_method in arrayName and is_within_time_range(config) and host in config['whitelisting']:
        # Kết nối tới máy chủ web từ xa
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.connect((remote_host, remote_port))

        # Gửi yêu cầu HTTP tới máy chủ web từ xa
        # GET / HTTP/1.1\r\nHost: oosc.online \r\n\r\n 
        remote_request = f"{request_method} {path} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode()
        remote_socket.sendall(remote_request)

        # Nhận phản hồi từ máy chủ web từ xa và gửi lại cho trình duyệt
        while True:
            remote_data = remote_socket.recv(4096)
            if len(remote_data) == 0:
                break 
            client_socket.sendall(remote_data)

        # Đóng kết nối
        remote_socket.close()
        client_socket.close()
    else:
         Error403(client_socket)
         client_socket.close()

def proxy_server():
    local_host = '127.0.0.1'  # Địa chỉ IP của máy cục bộ (localhost)
    local_port = 8000  # Cổng để lắng nghe các kết nối từ trình duyệt

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Tạo socket TCP
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Cho phép sử dụng lại địa chỉ cổng ngay khi socket bị đóng
    server_socket.bind((local_host, local_port))  # Ràng buộc socket tới địa chỉ IP và cổng cục bộ
    server_socket.listen(5)  # Lắng nghe kết nối từ trình duyệt, giới hạn đợi đến 5 kết nối

    print(f"Proxy đang lắng nghe trên {local_host}:{local_port}")

    while True:
        client_socket, client_addr = server_socket.accept()  # Chấp nhận kết nối mới từ trình duyệt
        client_handler = threading.Thread(target=handle_client, args=(client_socket,))
        client_handler.start()  # Bắt đầu xử lý kết nối từ trình duyệt

if __name__ == "__main__":
    read_config_file("File_Config.txt", config)
    proxy_server()

