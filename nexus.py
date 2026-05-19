#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import sys
import ipaddress
import socket
import json
from datetime import datetime

INPUT_FILE = "ips.txt"
MAX_MS = 1500
RESULTS_DIR = "results"
TCP_TIMEOUT = 3
MAX_IPS_PER_CIDR = 10000

CONFIG_DIR = ".config"
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

default_settings = {
    "concurrent": 100,
    "port": 443,
    "test_mode": "both"
}

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return default_settings.copy()

def save_settings(settings):
    with open(CONFIG_FILE, "w") as f:
        json.dump(settings, f, indent=4)

settings = load_settings()
concurrent = settings["concurrent"]
port = settings["port"]
test_mode = settings["test_mode"]

all_results = {}
all_failed = {}
all_slow = {}
semaphore = None
os.makedirs(RESULTS_DIR, exist_ok=True)

# ============ القائمة والوظائف الأساسية ============
def show_menu():
    print("\n" + "="*50)
    print("      IP CONNECTIVITY TESTER v2.8")
    print("="*50)
    print(f" 1. Port              : {port}")
    print(f" 2. Test mode         : {test_mode} (tcp/http/both)")
    print(f" 3. Concurrent        : {concurrent}")
    print("="*50)
    print(" 4. START TEST (from ips.txt)")
    print(" 5. Test single IP/CIDR")
    print(" 6. Save settings & EXIT")
    print(" 7. EXIT without saving")
    print("="*50)

def change_port():
    global port
    try:
        new_port = int(input(f"Enter new port (current: {port}): "))
        port = new_port
        print(f"✅ Port changed to: {port}")
    except:
        print("❌ Invalid port number.")

def change_test_mode():
    global test_mode
    print(f"Current test mode: {test_mode}")
    print("   (t)cp only")
    print("   (h)ttp only")
    print("   (b)oth")
    choice = input("Your choice (t/h/b): ").strip().lower()
    if choice == 't':
        test_mode = "tcp"
    elif choice == 'h':
        test_mode = "http"
    elif choice == 'b':
        test_mode = "both"
    else:
        print("❌ Invalid choice. Keeping current.")
    print(f"✅ Test mode changed to: {test_mode}")

def change_concurrent():
    global concurrent
    try:
        new_concurrent = int(input(f"Enter concurrent connections (current: {concurrent}): "))
        concurrent = new_concurrent
        print(f"✅ Concurrent changed to: {concurrent}")
    except:
        print("❌ Invalid number.")

def save_and_exit():
    settings = {
        "concurrent": concurrent,
        "port": port,
        "test_mode": test_mode
    }
    save_settings(settings)
    print("✅ Settings saved permanently.")
    print("👋 Exiting. Goodbye!")
    sys.exit(0)

def create_sample_ips_file():
    sample_content = """# Example IPs and CIDRs - Add your own below
# Single IPs:
1.1.1.1
8.8.8.8
# CIDR ranges:
203.198.20.0/24
104.16.0.0/12
"""
    with open(INPUT_FILE, "w") as f:
        f.write(sample_content)
    print(f"📝 Created sample '{INPUT_FILE}' file.")
    print("💡 Please edit it and add your own IPs or CIDR ranges, then run the script again.")

def expand_cidr(line, limit=MAX_IPS_PER_CIDR):
    line = line.strip()
    if '/' in line:
        try:
            network = ipaddress.ip_network(line, strict=False)
            hosts = list(network.hosts())
            if len(hosts) > limit:
                print(f"⚠️ WARNING: CIDR {line} has {len(hosts)} IPs, limiting to {limit} IPs")
                hosts = hosts[:limit]
            return [(str(ip), line, True) for ip in hosts]
        except ValueError:
            print(f"❌ INVALID CIDR: {line}")
            return []
    else:
        return [(line, line, False)]

def expand_single_cidr(cidr):
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        return [str(ip) for ip in network.hosts()[:MAX_IPS_PER_CIDR]]
    except ValueError:
        return [cidr]

def get_url(ip, port):
    if port in [443, 8443, 2096, 2053, 465, 993, 995]:
        return f"https://{ip}:{port}" if port != 443 else f"https://{ip}"
    elif port in [80, 8080, 8000, 8888, 81, 3000, 5000]:
        return f"http://{ip}:{port}" if port != 80 else f"http://{ip}"
    else:
        return f"https://{ip}:{port}"

# ============ دوال الاختبار ============
async def test_tcp(ip, port):
    try:
        loop = asyncio.get_event_loop()
        def tcp_connect():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(TCP_TIMEOUT)
            try:
                start = datetime.now()
                sock.connect((ip, port))
                elapsed = (datetime.now() - start).total_seconds() * 1000
                sock.close()
                return elapsed
            except:
                return None
        return await loop.run_in_executor(None, tcp_connect)
    except:
        return None

async def test_http(ip, port):
    try:
        url = get_url(ip, port)
        proc = await asyncio.create_subprocess_exec(
            "curl", "-o", "/dev/null", "-s", "-w", "%{time_total}",
            "--max-time", "5", "--connect-timeout", "3", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode().strip()
        if output:
            return float(output) * 1000
        return None
    except:
        return None

async def test_ip(ip, source, is_cidr, port, test_mode, is_retest=False):
    global semaphore, all_results, all_failed, all_slow
    async with semaphore:
        try:
            tcp_ms = None
            http_ms = None
            
            if test_mode in ["tcp", "both"]:
                tcp_ms = await test_tcp(ip, port)
                if tcp_ms is None:
                    print(f"❌ FAIL (TCP): {ip}:{port}")
                    if not is_retest:
                        if port not in all_failed:
                            all_failed[port] = []
                        all_failed[port].append((ip, source, is_cidr))
                    return False
            
            if test_mode in ["http", "both"]:
                http_ms = await test_http(ip, port)
                if http_ms is None and test_mode != "tcp":
                    print(f"❌ FAIL (HTTP): {ip}:{port}")
                    if not is_retest:
                        if port not in all_failed:
                            all_failed[port] = []
                        all_failed[port].append((ip, source, is_cidr))
                    return False
            
            if test_mode == "tcp":
                final_ms = tcp_ms
                detail = f"TCP:{int(tcp_ms)}ms"
            elif test_mode == "http":
                final_ms = http_ms
                detail = f"HTTP:{int(http_ms)}ms"
            else:
                final_ms = max(tcp_ms, http_ms)
                detail = f"TCP:{int(tcp_ms)}ms | HTTP:{int(http_ms)}ms"
            
            if final_ms <= MAX_MS:
                if not is_retest:
                    if port not in all_results:
                        all_results[port] = []
                    all_results[port].append((ip, final_ms, source, is_cidr, port))
                print(f"✅ WORKING: {ip}:{port} ({detail})")
                if is_cidr:
                    print(f"   └─ from CIDR: {source}")
                return True
            else:
                print(f"⏱️ SLOW: {ip}:{port} ({detail})")
                if not is_retest:
                    if port not in all_slow:
                        all_slow[port] = []
                    all_slow[port].append((ip, source, is_cidr))
                return False
        except Exception as e:
            print(f"❌ FAIL: {ip}:{port}")
            if not is_retest:
                if port not in all_failed:
                    all_failed[port] = []
                all_failed[port].append((ip, source, is_cidr))
            return False

def save_results(port, results_list, concurrent, test_mode):
    if not results_list:
        return None
    
    counter = 1
    while os.path.exists(os.path.join(RESULTS_DIR, f"ips_successful_port{port}({counter}).txt")):
        counter += 1
    output_file = os.path.join(RESULTS_DIR, f"ips_successful_port{port}({counter}).txt")
    
    with open(output_file, "w") as f:
        f.write(f"Tested on port: {port}\n")
        f.write(f"Test mode: {test_mode}\n")
        f.write(f"Concurrent connections: {concurrent}\n")
        f.write(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*50 + "\n")
        
        single_ips = [(ip, ms) for ip, ms, source, is_cidr, p in results_list if not is_cidr]
        cidr_ips = [(ip, ms, source) for ip, ms, source, is_cidr, p in results_list if is_cidr]
        
        f.write("========== Single IPs ==========\n")
        for ip, _ in single_ips:
            f.write(f"{ip}\n")
        
        if cidr_ips:
            f.write("\n========== CIDR IPs ==========\n")
            current_source = None
            for ip, _, source in cidr_ips:
                if source != current_source:
                    f.write(f"\nFrom CIDR: {source}\n")
                    current_source = source
                f.write(f"{ip}\n")
        
        f.write("\n========== All IPs with ping ==========\n")
        for ip, ms, source, is_cidr, p in results_list:
            if is_cidr:
                f.write(f"{ip} - Ping: {int(ms)}ms  [from CIDR: {source}]\n")
            else:
                f.write(f"{ip} - Ping: {int(ms)}ms\n")
    
    return output_file

# ============ اختبار IP/CIDR واحد ============
async def test_single_target(target, test_port, test_mode):
    global semaphore, all_results, all_failed, all_slow
    
    all_results = {}
    all_failed = {}
    all_slow = {}
    semaphore = asyncio.Semaphore(concurrent)
    
    if '/' in target:
        ips = expand_single_cidr(target)
        print(f"🔍 Testing CIDR {target} ({len(ips)} IPs) on port {test_port}")
        print("-" * 40)
        
        all_ips = [(ip, target, True) for ip in ips]
        tasks = [test_ip(ip, source, is_cidr, test_port, test_mode) for ip, source, is_cidr in all_ips]
        await asyncio.gather(*tasks)
        
        if test_port in all_results and all_results[test_port]:
            print(f"\n✅ Working IPs from CIDR {target}:")
            for ip, ms, source, is_cidr, p in all_results[test_port]:
                print(f"   {ip}:{test_port} ({int(ms)}ms)")
        else:
            print(f"\n❌ No working IPs found in CIDR {target} on port {test_port}")
    else:
        print(f"🔍 Testing single IP: {target} on port {test_port}")
        print("-" * 40)
        await test_ip(target, target, False, test_port, test_mode)
        
        if test_port in all_results and all_results[test_port]:
            ip, ms, _, _, _ = all_results[test_port][0]
            print(f"\n🎉 IP {target} is WORKING ({int(ms)}ms) on port {test_port}")
        else:
            print(f"\n❌ IP {target} is NOT WORKING on port {test_port}")
    
    if test_port in all_results and all_results[test_port]:
        save_results(test_port, all_results[test_port], concurrent, test_mode)

# ============ إعادة الاختبار للفاشلة والبطيئة ============
async def retest_failed_ips(original_port):
    global semaphore, all_results, all_failed, all_slow, port, test_mode, concurrent
    
    current_port = original_port
    retest_round = 1
    
    while retest_round <= 5:
        current_failed = all_failed.get(current_port, [])
        current_slow = all_slow.get(current_port, [])
        
        if not current_failed and not current_slow:
            print(f"\n✨ No failed or slow IPs from port {current_port}. Exiting retest.")
            break
        
        print("\n" + "="*50)
        print(f"📊 Summary for port {current_port}:")
        print(f"   ✅ Working: {len(all_results.get(current_port, []))}")
        print(f"   ⏱️ Slow: {len(current_slow)}")
        print(f"   ❌ Failed: {len(current_failed)}")
        print("="*50)
        
        print("\n🔁 Would you like to test the FAILED/SLOW IPs on another port?")
        choice = input("   (y)es / (n)o : ").strip().lower()
        
        if choice != 'y':
            print("✅ Retest completed. Exiting.")
            break
        
        try:
            new_port = int(input("   Enter new port number (e.g., 80, 8080, 8443): "))
            print("")
            
            ips_to_retest = list(set(current_failed + current_slow))
            total_ips = len(ips_to_retest)
            print(f"🔄 Retest round {retest_round}: Testing {total_ips} IPs on port {new_port}...")
            print(f"   ⚙️ Using {concurrent} concurrent connections (PARALLEL mode)")
            
            start_time = datetime.now()
            temp_results = []
            temp_failed = []
            temp_slow = []
            
            retest_semaphore = asyncio.Semaphore(concurrent)
            
            async def test_retest_ip(ip, source, is_cidr):
                async with retest_semaphore:
                    try:
                        tcp_ms = None
                        http_ms = None
                        
                        if test_mode in ["tcp", "both"]:
                            tcp_ms = await test_tcp(ip, new_port)
                            if tcp_ms is None:
                                return ('failed', ip, source, is_cidr)
                        
                        if test_mode in ["http", "both"]:
                            http_ms = await test_http(ip, new_port)
                            if http_ms is None and test_mode != "tcp":
                                return ('failed', ip, source, is_cidr)
                        
                        if test_mode == "tcp":
                            final_ms = tcp_ms
                        elif test_mode == "http":
                            final_ms = http_ms
                        else:
                            final_ms = max(tcp_ms, http_ms)
                        
                        if final_ms <= MAX_MS:
                            return ('working', ip, final_ms, source, is_cidr, new_port)
                        else:
                            return ('slow', ip, source, is_cidr)
                    except:
                        return ('failed', ip, source, is_cidr)
            
            tasks = [test_retest_ip(ip, source, is_cidr) for ip, source, is_cidr in ips_to_retest]
            results = await asyncio.gather(*tasks)
            
            working_count = 0
            slow_count = 0
            failed_count = 0
            
            for result in results:
                if result[0] == 'working':
                    _, ip, ms, source, is_cidr, p = result
                    temp_results.append((ip, ms, source, is_cidr, p))
                    working_count += 1
                    if working_count <= 20 or working_count % 50 == 0:
                        print(f"✅ WORKING: {ip}:{new_port} ({int(ms)}ms)")
                elif result[0] == 'slow':
                    _, ip, source, is_cidr = result
                    temp_slow.append((ip, source, is_cidr))
                    slow_count += 1
                else:
                    _, ip, source, is_cidr = result
                    temp_failed.append((ip, source, is_cidr))
                    failed_count += 1
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            print(f"\n   📈 Progress: {working_count} working, {slow_count} slow, {failed_count} failed")
            print(f"   ⚡ Completed in {elapsed:.1f} seconds (≈ {total_ips/elapsed:.1f} IPs/sec)")
            
            if temp_results:
                all_results[new_port] = temp_results
                output_file = save_results(new_port, temp_results, concurrent, test_mode)
                print(f"\n💾 Retest results saved in: {output_file}")
            
            all_failed[new_port] = temp_failed
            all_slow[new_port] = temp_slow
            
            print("\n" + "="*50)
            print(f"✨ Retest Results (Round {retest_round}) on port {new_port}:")
            print("="*50)
            print(f"   ✅ Working: {len(temp_results)}")
            print(f"   ⏱️ Slow: {len(temp_slow)}")
            print(f"   ❌ Failed: {len(temp_failed)}")
            print(f"   ⚡ Time: {elapsed:.1f} seconds")
            
            current_port = new_port
            retest_round += 1
            
        except ValueError:
            print("❌ Invalid port number. Skipping retest.")
            break

# ============ الاختبار الرئيسي من الملف ============
async def start_test():
    global semaphore, concurrent, port, test_mode, all_results, all_failed, all_slow
    
    print("\n" + "="*50)
    print("🚀 STARTING TEST...")
    print("="*50)
    print(f"📡 Port: {port}")
    print(f"🧪 Test mode: {test_mode}")
    print(f"⚙️ Concurrent connections: {concurrent}")
    print("="*50)
    
    all_results = {}
    all_failed = {}
    all_slow = {}
    semaphore = asyncio.Semaphore(concurrent)
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found.")
        create_sample_ips_file()
        return
    
    all_ips = []
    print("\n📖 Reading and expanding IPs/CIDRs from file...")
    with open(INPUT_FILE, "r") as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        expanded = expand_cidr(line)
        all_ips.extend(expanded)
    
    total_ips = len(all_ips)
    print(f"📊 Total IPs to test: {total_ips:,}")
    
    if total_ips == 0:
        print("❌ No valid IPs or CIDRs found in file.")
        return
    
    if total_ips > 50000:
        print(f"⚠️ WARNING: You are about to test {total_ips:,} IPs. This may take a long time.")
        response = input("Continue? (y/n): ").strip().lower()
        if response != 'y':
            print("❌ Aborted by user.")
            return
    
    print(f"\n🚀 Testing {total_ips:,} IPs on port {port}...")
    print(f"   ⚙️ Using {concurrent} concurrent connections")
    
    start_time = datetime.now()
    batch_size = 10000
    
    for i in range(0, len(all_ips), batch_size):
        batch = all_ips[i:i+batch_size]
        tasks = [test_ip(ip, source, is_cidr, port, test_mode) for ip, source, is_cidr in batch]
        await asyncio.gather(*tasks)
        print(f"📈 Progress: {min(i+batch_size, total_ips):,}/{total_ips:,} IPs tested")
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    if port in all_results and all_results[port]:
        output_file = save_results(port, all_results[port], concurrent, test_mode)
        print(f"\n💾 Results saved in: {output_file}")
    else:
        print(f"\n❌ No working IPs found on port {port}")
    
    print(f"\n⚡ Main test completed in {elapsed:.1f} seconds (≈ {total_ips/elapsed:.1f} IPs/sec)")
    
    # ✅ إعادة الاختبار
    await retest_failed_ips(port)

# ============ الوظيفة الرئيسية ============
async def main():
    while True:
        show_menu()
        choice = input("Your choice (1-7): ").strip()
        
        if choice == '1':
            change_port()
        elif choice == '2':
            change_test_mode()
        elif choice == '3':
            change_concurrent()
        elif choice == '4':
            await start_test()
            input("\nPress Enter to continue...")
        elif choice == '5':
            target = input("Enter IP or CIDR (e.g., 1.1.1.1 or 203.198.20.0/24): ").strip()
            if target:
                await test_single_target(target, port, test_mode)
            input("\nPress Enter to continue...")
        elif choice == '6':
            save_and_exit()
        elif choice == '7':
            print("👋 Exiting without saving. Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-7.")

if __name__ == "__main__":
    asyncio.run(main())
