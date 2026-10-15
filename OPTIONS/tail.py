import time
import sys
import os

def tail(filepath, n_lines=30):
    if not os.path.exists(filepath):
        print(f"Waiting for {filepath} to be created...")
        while not os.path.exists(filepath):
            time.sleep(1)
            
    with open(filepath, 'rb') as f:
        # Print the last n lines
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        block_size = 1024
        blocks = -1
        data = b""
        while len(data.splitlines()) < n_lines and file_size + (blocks * block_size) > 0:
            f.seek(blocks * block_size, os.SEEK_END)
            data = f.read(block_size) + data
            blocks -= 1
            
        data_str = data.decode('utf-8', errors='replace')
        lines = data_str.splitlines()[-n_lines:]
        for line in lines:
            print(line)
            
        f.seek(0, os.SEEK_END)
        
        # Continuously print new lines (no screen flashing)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            sys.stdout.write(line.decode('utf-8', errors='replace'))
            sys.stdout.flush()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python tail.py <logfile>")
        sys.exit(1)
    try:
        tail(sys.argv[1])
    except KeyboardInterrupt:
        sys.exit(0)
