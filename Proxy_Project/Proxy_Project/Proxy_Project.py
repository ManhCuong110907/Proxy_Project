import socket
import threading
import ssl
import os
from datetime import datetime, time
import time
import shutil
from urllib import response
cache_data = {}
config = {}
timeout_in_seconds = 2 # Thời gian chờ tối đa là 10 giây


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
def delete_folder_after_delay(folder_path, url):
    # Đợi một khoảng thời gian cache_time
    time.sleep(config['cache_time'])
    
    # Xoá file
    try:
        shutil.rmtree(folder_path)
        cache_data.pop(url)
    except OSError as e:
        return
def find_content_length(request_data):
    for line in request_data:
        if line.startswith(b"Content-Length:"):
            content_length = int(line.split(":")[1].strip())
            return content_length
    return None
def read_chunked_data(socket):
    socket.settimeout(timeout_in_seconds)
    try:
        print("chunked")
        data = b""
        while True:
            chunk_size = socket.recv(4096)
            if not chunk_size:
                break
            chunk_size = int(chunk_size, 16)
            chunk_data = socket.recv(chunk_size)
            data += chunk_data
            socket.recv(2)  # Discard CRLF at the end of each chunk
            if chunk_size == 0:
                break 
    except socket.timeout:
        print("Socket timeout occurred. Connection may be lost or no data received.")
    except Exception as e:
        print(f"An error occurred: {e}")
    
    return data
def get_infor(client_socket):
    request_data = client_socket.recv(20000)
    request_lines = request_data.split(b'\r\n')
    # Tìm kiếm URL và phương thức yêu cầu
    request_line = request_lines[0].decode()
    
    if request_line:
        request_method, url, _ = request_line.split()
        arrayName = ["GET", "POST", "HEAD"]
        image_name = None

        if any(ext in url for ext in ['.png', '.jpg', '.gif', '.ico']):
            file_name = os.path.basename(url)
            image_name, _ = os.path.splitext(file_name)
        
        # Xử lý URL
        if url.startswith("http://"):
            url = url[7:]
        elif url.startswith("https://"):
            url = url[8:]

        # Tách thông tin hostname và port (nếu có)
        if '/' in url:
            host_path = url.split('/', 1)
            host = host_path[0]
            path = '/' + host_path[1]
        else:
            host = url
            path = '/'

        if ':' in host:
            remote_host, remote_port = host.split(':', 1)
            remote_port = int(remote_port)
        else:
            remote_host = host
            remote_port = 80
        
        return request_method, url, image_name, remote_host, remote_port, path, host, request_data
    return None, None, None, None, None, None, None , None
def Keep_alive(remote_socket,client_socket, pre_response_data, request_data):
    while True:
        remote_socket.settimeout(timeout_in_seconds)
        request_method, url, image_name, remote_host, remote_port, path, host, request_data = get_infor(client_socket)
        response_header = b""
        try:
            print("header")
            while True:
                chunk = remote_socket.recv(4096)  # Nhận dữ liệu theo mảnh (chunk) nhỏ
                response_header += chunk
                if b"\r\n\r\n" in response_header:
                    break
        except socket.timeout:
            print("Socket timeout occurred. Connection may be lost or no data received.")
        except Exception as e:
            print(f"An error occurred: {e}")
        response_body = b''
        if b"transfer-encoding: chunked" in   response_header.lower():
            remote_socket.sendall(request_data)
            response_body = read_chunked_data(remote_socket)
        elif b"content-length" in   response_header.lower():
            content_length = find_content_length(response_body)
            remote_socket.sendall(request_data)
            # Read and process data based on Content-Length
            try:
                print("length")
                expected_length = int(content_length)
                while expected_length > 0:
                    chunk = remote_socket.recv(min(4096, expected_length))
                    if not chunk:
                        break
                    response_body += chunk
                    expected_length -= len(chunk)
            except socket.timeout:
                print("Socket timeout occurred. Connection may be lost or no data received.")
            except Exception as e:
                print(f"An error occurred: {e}")
        response_data = response_header + response_body
        if b'content-type: image/' in response_header.lower():
            image_path = create_image_path(host, response_data, image_name)
            save_image(host,response_data, url, image_path)
        client_socket.sendall(response_data)
        pre_response_data = response_data
        if b"Connection: close" in response_header:
            break

# Hàm xử lý input
def handle_client(client_socket):
    request_method, url, image_name, remote_host, remote_port, path, host, request_data = get_infor(client_socket)
    arrayName = ["GET", "POST", "HEAD"]
    if host in config['whitelisting']and request_method in arrayName and is_within_time_range(config):
        if url in cache_data:
            cached_data = cache_data[url]
            timestamp = cached_data['timestamp']
            current_time = time.time()
            if current_time - timestamp <= config['cache_time']:
                image_data = cached_data['image_data']
                client_socket.sendall(image_data)
                print("okela")
        else:
            # Kết nối tới máy chủ web từ xa
            remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_socket.connect((remote_host, remote_port))
            remote_socket.settimeout(timeout_in_seconds)
            remote_socket.sendall(request_data)
            # Nhận phản hồi từ máy chủ web từ xa và gửi lại cho trình duyệt
            try:
                response_data = b''
                while True:
                    remote_data = remote_socket.recv(4096)
                    response_data += remote_data
                    if len(remote_data)  <= 0:
                        break 
            except socket.timeout:
                #print("Socket timeout occurred. Connection may be lost or no data received.")
                print("")
            except Exception as e:
                #print(f"An error occurred: {e}")
                print("")
            try:
                client_socket.sendall(response_data)
            except Exception as e:
                #print(f"An error occurred while sending data: {e}")
                print("")
            if not b"Connection: close" in response_data:
                Keep_alive(remote_socket,client_socket, response_data, request_data)
            remote_socket.close()
        # Đóng kết nối
        client_socket.close()  
        #Xoá cache sau cache_time
        delete_folder_after_delay(f"cache/{host}", url)
    else:
            Error403(client_socket)
            client_socket.close()
def create_image_path(host, image_data, image_name):
    folder=f"cache/{str(host)}"
    response_header,response_body = image_data.split(b'\r\n\r\n')
    # Xác định định dạng hình ảnh dựa trên tiêu đề Content-Type
    image_format = 'jpg'  # Đặt giá trị mặc định là .jpg
    if b'content-type: image/png' in response_header:
        image_format = 'png'
    elif b'content-type: image/gif' in response_header:
        image_format = 'gif'
    # Thêm các định dạng hình ảnh khác (nếu cần)

    # Tạo tên tệp hình ảnh dựa trên thời gian hiện tại và định dạng hình ảnh
    image_path = f'{folder}/{image_name}.{image_format}'
    return image_path
def save_image(host,image_data, url, image_path):
    response_header,response_body = image_data.split(b'\r\n\r\n')
    # Tạo một thư mục để lưu hình ảnh (nếu chưa tồn tại)
    folder=f"cache/{str(host)}"
    if not os.path.exists("cache"):
        os.makedirs("cache")
    if not os.path.exists(folder):
        os.makedirs(folder)
        cache_data[url] = {'image_data': image_data, 'timestamp': time.time()}
    # Lưu dữ liệu hình ảnh vào tệp
    with open(image_path, 'wb') as file:
        file.write(response_body)
def proxy_server():
    local_host = '127.0.0.1'  # Địa chỉ IP của máy cục bộ (localhost)
    local_port = 8000  # Cổng để lắng nghe các kết nối từ trình duyệt

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Tạo socket TCP
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Cho phép sử dụng lại địa chỉ cổng ngay khi socket bị đóng
    server_socket.bind((local_host, local_port))  # Ràng buộc socket tới địa chỉ IP và cổng cục bộ
    server_socket.listen(5000)  # Lắng nghe kết nối từ trình duyệt, giới hạn đợi đến 5 kết nối

    print(f"Proxy đang lắng nghe trên {local_host}:{local_port}")
    
    while True:
        client_socket, client_addr = server_socket.accept()  # Chấp nhận kết nối mới từ trình duyệt
        client_handler = threading.Thread(target=handle_client, args=(client_socket,))
        client_handler.start()  # Bắt đầu xử lý kết nối từ trình duyệt

if __name__ == "__main__":
    read_config_file("File_Config.txt", config)
    proxy_server()