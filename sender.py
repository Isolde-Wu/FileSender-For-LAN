#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import threading
import json
import time
import os
import pickle
from datetime import datetime

DISCOVERY_PORT = 8888
TCP_PORT = 9000
BROADCAST_ADDR = '<broadcast>'
HEARTBEAT_INTERVAL = 5
PEER_TIMEOUT = 15
CHUNK_SIZE = 8192
RECV_DIR = "received"
MANUAL_PEERS_FILE = "manual_peers.json"

peers = {}
peer_alias_file = "peers.dat"
lock = threading.Lock()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def load_peer_aliases():
    if os.path.exists(peer_alias_file):
        with open(peer_alias_file, 'rb') as f:
            return pickle.load(f)
    return {}

def save_peer_aliases(aliases):
    with open(peer_alias_file, 'wb') as f:
        pickle.dump(aliases, f)

def load_manual_peers():
    if os.path.exists(MANUAL_PEERS_FILE):
        with open(MANUAL_PEERS_FILE, 'r', encoding='utf-8') as f:
            manual_list = json.load(f)
        for item in manual_list:
            ip = item['ip']
            peers[ip] = {
                "hostname": item.get("hostname", ip),
                "alias": item.get("alias", ""),
                "tcp_port": item.get("tcp_port", TCP_PORT),
                "last_seen": time.time(),
                "manual": True
            }
            if item.get("alias"):
                custom_aliases[ip] = item["alias"]
        save_peer_aliases(custom_aliases)

def save_manual_peers():
    manual_list = []
    with lock:
        for ip, info in peers.items():
            if info.get("manual", False):
                manual_list.append({
                    "ip": ip,
                    "hostname": info.get("hostname", ip),
                    "alias": info.get("alias", ""),
                    "tcp_port": info.get("tcp_port", TCP_PORT)
                })
    with open(MANUAL_PEERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(manual_list, f, indent=2, ensure_ascii=False)

custom_aliases = load_peer_aliases()
load_manual_peers()

def get_display_name(ip, peer_info):
    if ip in custom_aliases and custom_aliases[ip]:
        return custom_aliases[ip]
    return peer_info.get('alias', peer_info.get('name', ip))

def send_broadcast(my_alias):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    my_info = {
        "name": socket.gethostname(),
        "alias": my_alias,
        "tcp_port": TCP_PORT,
        "timestamp": time.time()
    }
    while True:
        msg = json.dumps(my_info).encode('utf-8')
        sock.sendto(msg, (BROADCAST_ADDR, DISCOVERY_PORT))
        time.sleep(HEARTBEAT_INTERVAL)

def recv_broadcast():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', DISCOVERY_PORT))
    local_ip = get_local_ip()
    while True:
        try:
            data, addr = sock.recvfrom(2048)
            peer_ip = addr[0]
            if peer_ip == local_ip:
                continue
            info = json.loads(data.decode('utf-8'))
            with lock:
                if peer_ip in peers and peers[peer_ip].get("manual", False):
                    peers[peer_ip]["last_seen"] = time.time()
                else:
                    peers[peer_ip] = {
                        "hostname": info.get("name", ""),
                        "alias": info.get("alias", ""),
                        "tcp_port": info.get("tcp_port", TCP_PORT),
                        "last_seen": time.time(),
                        "manual": False
                    }
        except Exception as e:
            print(f"Broadcast receive error: {e}")

def cleanup_peers():
    while True:
        time.sleep(5)
        now = time.time()
        with lock:
            expired = [ip for ip, info in peers.items() 
                       if not info.get("manual", False) and now - info["last_seen"] > PEER_TIMEOUT]
            for ip in expired:
                del peers[ip]

def start_tcp_server():
    if not os.path.exists(RECV_DIR):
        os.makedirs(RECV_DIR)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', TCP_PORT))
    server.listen(5)
    print(f"TCP file receiving service started on port {TCP_PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_recv_file, args=(conn, addr), daemon=True).start()

def handle_recv_file(conn, addr):
    try:
        name_len_data = conn.recv(4)
        if not name_len_data:
            return
        name_len = int.from_bytes(name_len_data, 'big')
        filename = conn.recv(name_len).decode('utf-8')
        size_data = conn.recv(8)
        file_size = int.from_bytes(size_data, 'big')
        filepath = os.path.join(RECV_DIR, os.path.basename(filename))
        base, ext = os.path.splitext(filepath)
        counter = 1
        while os.path.exists(filepath):
            filepath = f"{base}_{counter}{ext}"
            counter += 1
        with open(filepath, 'wb') as f:
            received = 0
            while received < file_size:
                chunk = conn.recv(min(CHUNK_SIZE, file_size - received))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)
        print(f"\n[Receive complete] File from {addr[0]} saved as {filepath}")
    except Exception as e:
        print(f"File receive error: {e}")
    finally:
        conn.close()

def send_file_to_peer(ip, tcp_port, filepath):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, tcp_port))
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        name_bytes = filename.encode('utf-8')
        sock.sendall(len(name_bytes).to_bytes(4, 'big'))
        sock.sendall(name_bytes)
        sock.sendall(file_size.to_bytes(8, 'big'))
        with open(filepath, 'rb') as f:
            sent = 0
            while sent < file_size:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sock.sendall(chunk)
                sent += len(chunk)
        sock.close()
        return True
    except Exception as e:
        print(f"Send to {ip} failed: {e}")
        return False

def send_file_to_multiple(targets, filepath):
    if not os.path.exists(filepath):
        print("File not found")
        return
    threads = []
    for ip, tcp_port in targets:
        t = threading.Thread(target=send_file_to_peer, args=(ip, tcp_port, filepath))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    print("Batch send complete")

def display_peers():
    with lock:
        if not peers:
            print("No other online nodes (including manually added)")
            return []
        print("\nCurrently online nodes:")
        print("No. | Type | IP Address        | Alias/Name")
        print("-" * 60)
        items = list(peers.items())
        for idx, (ip, info) in enumerate(items, 1):
            type_flag = "[M]" if info.get("manual", False) else "[A]"
            display = get_display_name(ip, info)
            print(f"{idx:3} | {type_flag:3} | {ip:18} | {display}")
        return items

def set_alias_interactive():
    items = display_peers()
    if not items:
        return
    try:
        choice = int(input("Enter the node number to set alias: "))
        if 1 <= choice <= len(items):
            ip, info = items[choice-1]
            current_display = get_display_name(ip, info)
            new_alias = input(f"Enter new alias (current: {current_display}): ").strip()
            if new_alias:
                custom_aliases[ip] = new_alias
                save_peer_aliases(custom_aliases)
                if info.get("manual", False):
                    with lock:
                        peers[ip]["alias"] = new_alias
                    save_manual_peers()
                print(f"Alias for {ip} set to: {new_alias}")
            else:
                if ip in custom_aliases:
                    del custom_aliases[ip]
                    save_peer_aliases(custom_aliases)
                    if info.get("manual", False):
                        with lock:
                            peers[ip]["alias"] = ""
                        save_manual_peers()
                    print(f"Alias for {ip} cleared")
        else:
            print("Invalid number")
    except ValueError:
        print("Input error")

def add_manual_peer():
    print("\n--- Add manual node ---")
    ip = input("Enter target IP address: ").strip()
    if not ip:
        print("IP cannot be empty")
        return
    with lock:
        if ip in peers:
            print(f"Node {ip} already exists, please delete it first if you want to modify")
            return
    port_str = input(f"Enter TCP port (default {TCP_PORT}): ").strip()
    port = int(port_str) if port_str else TCP_PORT
    alias = input("Enter alias (optional, press Enter to skip): ").strip()
    hostname = input("Enter hostname (optional, press Enter to use IP): ").strip()
    if not hostname:
        hostname = ip
    with lock:
        peers[ip] = {
            "hostname": hostname,
            "alias": alias,
            "tcp_port": port,
            "last_seen": time.time(),
            "manual": True
        }
    if alias:
        custom_aliases[ip] = alias
        save_peer_aliases(custom_aliases)
    save_manual_peers()
    print(f"Manual node {ip} added successfully")

def delete_manual_peer():
    items = display_peers()
    if not items:
        return
    manual_items = [(ip, info) for ip, info in items if info.get("manual", False)]
    if not manual_items:
        print("No manually added nodes")
        return
    print("\nManual nodes list:")
    for idx, (ip, info) in enumerate(manual_items, 1):
        display = get_display_name(ip, info)
        print(f"{idx}. {ip} - {display}")
    try:
        choice = int(input("Enter the node number to delete: "))
        if 1 <= choice <= len(manual_items):
            ip, _ = manual_items[choice-1]
            with lock:
                del peers[ip]
            if ip in custom_aliases:
                del custom_aliases[ip]
                save_peer_aliases(custom_aliases)
            save_manual_peers()
            print(f"Manual node {ip} deleted")
        else:
            print("Invalid number")
    except ValueError:
        print("Input error")

def send_files_interactive():
    items = display_peers()
    if not items:
        return
    print("Multi-select supported, e.g., 1,3,5 or 1-3")
    sel = input("Enter node numbers to send (comma or range): ").strip()
    indices = set()
    parts = sel.replace(' ', '').split(',')
    for part in parts:
        if '-' in part:
            start, end = map(int, part.split('-'))
            indices.update(range(start, end+1))
        else:
            if part.isdigit():
                indices.add(int(part))
    targets = []
    for idx in indices:
        if 1 <= idx <= len(items):
            ip, info = items[idx-1]
            tcp_port = info.get("tcp_port", TCP_PORT)
            targets.append((ip, tcp_port))
    if not targets:
        print("No valid nodes selected")
        return
    filepath = input("Enter file path to send: ").strip()
    if not os.path.exists(filepath):
        print("File not found")
        return
    print(f"Preparing to send file to {len(targets)} node(s)...")
    send_file_to_multiple(targets, filepath)

def main():
    print("===== FileSender for LAN =====")
    print("Developed by Isolde")
    print("DSLAB All Rights Reserved")
    my_alias = input("Enter your display alias (press Enter to use hostname): ").strip()
    if not my_alias:
        my_alias = socket.gethostname()
    threading.Thread(target=send_broadcast, args=(my_alias,), daemon=True).start()
    threading.Thread(target=recv_broadcast, daemon=True).start()
    threading.Thread(target=cleanup_peers, daemon=True).start()
    threading.Thread(target=start_tcp_server, daemon=True).start()
    time.sleep(1)

    while True:
        print("\n===== Main Menu =====")
        print("1. Show online nodes")
        print("2. Set node alias")
        print("3. Send file")
        print("4. Add manual node")
        print("5. Delete manual node")
        print("6. Exit")
        cmd = input("Choose: ").strip()
        if cmd == '1':
            display_peers()
        elif cmd == '2':
            set_alias_interactive()
        elif cmd == '3':
            send_files_interactive()
        elif cmd == '4':
            add_manual_peer()
        elif cmd == '5':
            delete_manual_peer()
        elif cmd == '6':
            break
        else:
            print("Invalid command")

if __name__ == "__main__":
    main()