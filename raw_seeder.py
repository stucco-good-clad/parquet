import hashlib
import struct
import socket
import threading
import time
import os
import urllib.request
import urllib.parse
import random
import string
import sys
import subprocess

TORRENT_FILE = os.environ.get("TORRENT_FILE", "r_3620000.torrent")
BASE_URL = "https://wispy-water-c333.stucco-good-clad.workers.dev"
TARGET_PIECES = [0, 1, 2, 3, 4]
LISTEN_PORT = int(os.environ.get('LISTEN_PORT', '6881'))
ANNOUNCE_PORT = int(os.environ.get('ANNOUNCE_PORT', '6881'))
RUN_MINUTES = int(os.environ.get('RUN_MINUTES', '55'))

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def bdecode(d, i=0):
    if d[i:i+1] == b'd':
        i += 1; r = {}
        while d[i:i+1] != b'e': k, i = bdecode(d, i); v, i = bdecode(d, i); r[k] = v
        return r, i+1
    elif d[i:i+1] == b'l':
        i += 1; r = []
        while d[i:i+1] != b'e': v, i = bdecode(d, i); r.append(v)
        return r, i+1
    elif d[i:i+1] == b'i':
        e = d.index(b'e', i); return int(d[i+1:e]), e+1
    else:
        c = d.index(b':', i); n = int(d[i:c]); return d[c+1:c+1+n], c+1+n

def parse_torrent(path):
    raw = open(path, 'rb').read()
    meta, _ = bdecode(raw)
    info_start = raw.index(b'4:infod') + 6
    info_dict, info_end = bdecode(raw, info_start)
    info_raw = raw[info_start:info_end]
    info_hash = hashlib.sha1(info_raw).hexdigest()

    pieces_raw = info_dict[b'pieces']
    num_pieces = len(pieces_raw) // 20
    piece_hashes = [pieces_raw[i*20:(i+1)*20] for i in range(num_pieces)]
    piece_len = info_dict[b'piece length']

    total_size = 0
    if b'length' in info_dict:
        total_size = info_dict[b'length']
    elif b'files' in info_dict:
        for f in info_dict[b'files']:
            total_size += f[b'length']

    tracker = meta.get(b'announce', b'').decode()
    trackers = ["https://tracker.opentrackr.org:443/announce"]
    if b'announce-list' in meta:
        for tier in meta[b'announce-list']:
            for t in tier:
                u = t.decode()
                if u.startswith('http:') or u.startswith('https:'):
                    trackers.append(u)
    if tracker and tracker.startswith('http'):
        trackers.append(tracker)

    return {
        'name': info_dict.get(b'name', b'?').decode(),
        'info_hash': info_hash,
        'info_hash_bytes': bytes.fromhex(info_hash),
        'piece_len': piece_len,
        'num_pieces': num_pieces,
        'piece_hashes': piece_hashes,
        'total_size': total_size,
        'trackers': trackers,
    }

def make_peer_id():
    suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    return b'-PY0001-' + suffix.encode()

def make_bitfield(num_pieces, have_pieces):
    num_bytes = (num_pieces + 7) // 8
    bf = bytearray(num_bytes)
    for p in have_pieces:
        byte_idx = p // 8
        bit_idx = 7 - (p % 8)
        bf[byte_idx] |= (1 << bit_idx)
    return bytes(bf)

def fetch_piece(piece_index):
    url = f"{BASE_URL}/piece_{piece_index}.bin"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception as e:
        log(f"  HTTP error piece {piece_index}: {e}")
        return None

def recv_exact(sock, n):
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data

def send_msg(sock, msg):
    sock.sendall(msg)

def recv_msg(sock):
    length_bytes = recv_exact(sock, 4)
    if not length_bytes:
        return None, None
    length = struct.unpack('>I', length_bytes)[0]
    if length == 0:
        return 0, b''
    payload = recv_exact(sock, length)
    if not payload:
        return None, None
    return payload[0], payload[1:]

def get_public_ip():
    import subprocess
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "5", "https://icanhazip.com"],
                           capture_output=True, text=True, timeout=8)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except:
        pass
    for url in ["https://api.ipify.org", "https://ifconfig.me/ip"]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode().strip()
                if data and not data.startswith("<"):
                    return data
        except:
            continue
    return None

def tracker_announce(info, peer_id):
    peers_found = []
    seen = set()

    for tracker in info['trackers']:
        if not tracker or tracker.startswith('udp:'):
            continue

        parts = []
        for k, v in [('info_hash', info['info_hash_bytes']),
                      ('peer_id', peer_id),
                      ('port', ANNOUNCE_PORT),
                      ('uploaded', 0),
                      ('downloaded', 0),
                      ('left', info['total_size']),
                      ('compact', 1),
                      ('numwant', 50),
                      ('event', 'started')]:
            if isinstance(v, bytes):
                encoded = urllib.parse.quote(v, safe='')
            else:
                encoded = str(v)
            parts.append(f"{k}={encoded}")

        url = f"{tracker}?{'&'.join(parts)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            result, _ = bdecode(data)
            if b'peers' in result:
                peers_data = result[b'peers']
                if isinstance(peers_data, bytes):
                    count = 0
                    for i in range(0, len(peers_data), 6):
                        ip = f"{peers_data[i]}.{peers_data[i+1]}.{peers_data[i+2]}.{peers_data[i+3]}"
                        port = struct.unpack('>H', peers_data[i+4:i+6])[0]
                        key = (ip, port)
                        if port > 0 and key not in seen:
                            seen.add(key)
                            peers_found.append(key)
                            count += 1
                    log(f"  Tracker {tracker}: +{count} new ({len(peers_found)} total)")
        except Exception as e:
            log(f"  Tracker {tracker}: {e}")
    return peers_found

stats_lock = threading.Lock()
stats = {'incoming': 0, 'outgoing': 0, 'handshakes_ok': 0, 'requests': 0, 'served': 0}

def handle_peer(sock, addr, info, peer_id):
    try:
        sock.settimeout(15)
        handshake = recv_exact(sock, 68)
        if not handshake or len(handshake) < 68:
            return
        remote_info_hash = handshake[28:48]
        if remote_info_hash != info['info_hash_bytes']:
            return

        reserved = b'\x00' * 8
        my_handshake = b'\x13BitTorrent protocol' + reserved + info['info_hash_bytes'] + peer_id
        send_msg(sock, my_handshake)

        bf = make_bitfield(info['num_pieces'], TARGET_PIECES)
        send_msg(sock, struct.pack('>I', 1 + len(bf)) + b'\x05' + bf)

        with stats_lock:
            stats['handshakes_ok'] += 1
        log(f"  <-- Incoming {addr[0]}:{addr[1]} handshake OK")

        choked = True
        piece_cache = {}
        while True:
            msg_id, payload = recv_msg(sock)
            if msg_id is None:
                break
            if msg_id == 0:
                choked = True
            elif msg_id == 1:
                choked = False
            elif msg_id == 2:
                send_msg(sock, struct.pack('>I', 1) + b'\x01')
                log(f"  <-- {addr[0]}:{addr[1]} interested -> unchoked")
            elif msg_id == 6:
                idx, begin, length = struct.unpack('>III', payload)
                with stats_lock:
                    stats['requests'] += 1
                if idx in TARGET_PIECES:
                    if idx not in piece_cache:
                        piece_cache[idx] = fetch_piece(idx)
                    data = piece_cache[idx]
                    if data and len(data) >= begin + length:
                        chunk = data[begin:begin+length]
                        msg = struct.pack('>I', 9 + length) + b'\x07' + struct.pack('>II', idx, begin) + chunk
                        send_msg(sock, msg)
                        with stats_lock:
                            stats['served'] += 1
                        log(f"  --> Served piece {idx} [{begin}:{begin+length}] to {addr[0]}:{addr[1]}")
    except Exception as e:
        pass
    finally:
        sock.close()

def peer_listener(info, peer_id):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', LISTEN_PORT))
    srv.listen(50)
    log(f"Listening on port {LISTEN_PORT}")

    while True:
        try:
            sock, addr = srv.accept()
            with stats_lock:
                stats['incoming'] += 1
            t = threading.Thread(target=handle_peer, args=(sock, addr, info, peer_id), daemon=True)
            t.start()
        except Exception:
            pass

def outgoing_connect(ip, port, info, peer_id):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))

        reserved = b'\x00' * 8
        my_handshake = b'\x13BitTorrent protocol' + reserved + info['info_hash_bytes'] + peer_id
        send_msg(sock, my_handshake)

        handshake = recv_exact(sock, 68)
        if not handshake or len(handshake) < 68:
            sock.close()
            return
        remote_info_hash = handshake[28:48]
        if remote_info_hash != info['info_hash_bytes']:
            sock.close()
            return

        bf_msg_id, bf_payload = recv_msg(sock)

        bf = make_bitfield(info['num_pieces'], TARGET_PIECES)
        send_msg(sock, struct.pack('>I', 1 + len(bf)) + b'\x05' + bf)
        send_msg(sock, struct.pack('>I', 1) + b'\x02')

        with stats_lock:
            stats['handshakes_ok'] += 1
        log(f"  --> Outgoing {ip}:{port} handshake OK")

        choked = True
        piece_cache = {}
        while True:
            msg_id, payload = recv_msg(sock)
            if msg_id is None:
                break
            if msg_id == 1:
                choked = False
                log(f"  <-- {ip}:{port} unchoked us")
            elif msg_id == 6:
                idx, begin, length = struct.unpack('>III', payload)
                with stats_lock:
                    stats['requests'] += 1
                if idx in TARGET_PIECES:
                    if idx not in piece_cache:
                        piece_cache[idx] = fetch_piece(idx)
                    data = piece_cache[idx]
                    if data and len(data) >= begin + length:
                        chunk = data[begin:begin+length]
                        msg = struct.pack('>I', 9 + length) + b'\x07' + struct.pack('>II', idx, begin) + chunk
                        send_msg(sock, msg)
                        with stats_lock:
                            stats['served'] += 1
                        log(f"  --> Served piece {idx} [{begin}:{begin+length}] to {ip}:{port}")
    except Exception as e:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass

def stats_loop():
    while True:
        time.sleep(30)
        with stats_lock:
            log(f"  STATS: in={stats['incoming']} out={stats['outgoing']} "
                f"handshakes={stats['handshakes_ok']} requests={stats['requests']} served={stats['served']}")

def shutdown_timer(minutes):
    time.sleep(minutes * 60)
    log(f"  Timer expired ({minutes} min). Shutting down.")
    with stats_lock:
        log(f"  FINAL: in={stats['incoming']} out={stats['outgoing']} "
            f"handshakes={stats['handshakes_ok']} requests={stats['requests']} served={stats['served']}")
    os._exit(0)

def main():
    log("=" * 60)
    log("  Raw BT Seeder — Zero Storage On-Demand Proxy")
    log("  GitHub Actions Edition")
    log("=" * 60)

    public_ip = get_public_ip()
    log(f"Public IP: {public_ip or 'unknown'}")

    info = parse_torrent(TORRENT_FILE)
    peer_id = make_peer_id()

    log(f"Torrent  : {info['name']}")
    log(f"InfoHash : {info['info_hash']}")
    log(f"Size     : {info['total_size']/1024/1024/1024:.2f} GB")
    log(f"Pieces   : {info['num_pieces']} x {info['piece_len']/1024:.0f} KB")
    log(f"Claiming : pieces {TARGET_PIECES}")
    log(f"HTTP src : {BASE_URL}")
    log(f"Storage  : ZERO")
    log(f"PeerID   : {peer_id.decode()}")
    log(f"Timeout  : {RUN_MINUTES} minutes")
    log("")

    timer = threading.Thread(target=shutdown_timer, args=(RUN_MINUTES,), daemon=True)
    timer.start()

    listener = threading.Thread(target=peer_listener, args=(info, peer_id), daemon=True)
    listener.start()

    stats_thread = threading.Thread(target=stats_loop, daemon=True)
    stats_thread.start()

    log("Announcing to trackers...")
    peers = tracker_announce(info, peer_id)
    log(f"Total unique peers: {len(peers)}")
    log("")

    for ip, port in peers:
        t = threading.Thread(target=outgoing_connect, args=(ip, port, info, peer_id), daemon=True)
        t.start()
        time.sleep(0.1)

    def reannounce_loop():
        while True:
            time.sleep(90)
            try:
                new_peers = tracker_announce(info, peer_id)
                for ip, port in new_peers:
                    t = threading.Thread(target=outgoing_connect, args=(ip, port, info, peer_id), daemon=True)
                    t.start()
            except Exception:
                pass

    reannouncer = threading.Thread(target=reannounce_loop, daemon=True)
    reannouncer.start()

    log("Running. Waiting for peer connections...")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        log("Done.")

if __name__ == "__main__":
    main()
