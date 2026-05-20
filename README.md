```markdown
# ⚡ NexuS – IP Connectivity Tester

**NexuS** is a command-line tool for testing the connectivity and response time of IPv4 addresses and CIDR ranges. It supports **TCP**, **HTTP**, and **Both** modes, making it useful for scanning CDN networks, proxy servers, and general network diagnostics.

---

t Ps or CIDR ranges (e.g., `203.198.20.0/24`)
- Three test modes: `tcp` (TCP only), `http` (HTTP/HTTPS), `both` (TCP+HTTP)
- Concurrent connections for high-speed scanning
- Auto-retest failed/slow IPs on other ports (up to 5 rounds)
- Persistent settings Create isavd---

## 📦 Requirements

- Python 3.7 or higher
- `curl` (for HTTP/HTTPS tests)

---

## 🚀 How to Use

### 1. Prepare `ips.txt`
Create a file named `ips.txt` in the same directory as `Nexus.py`. Add one IP or CIDR per line:


```

> **Note:** CIDR ranges are automatically expanded. Very large ranges (e.g., `/8`) are limited to 10,000 IPs for performance.

### 2. Run the tool
```bash
python Nexus.py
```

3. Main menu

You will see this interactive menu:

```
==================================================
      IP CONNECTIVITY TESTER v1.0.0
==================================================
 1. Port              : 443
 2. Test mode         : both (tcp/http/both)
 3. Concurrent        : 100
==================================================
 4. START TEST (from ips.txt)
 5. Test single IP/CIDR
 6. Save settings & EXIT
 7. EXIT without saving
==================================================
```

4. Start testing

· Press 4 to test all IPs in ips.txt
· Press 5 to test a single IP or CIDR directly
· Use options 1, 2, or 3 to change settings before testing

5. Retest failed/slow IPs

After the main test finishes, you will be asked if you want to retest failed/slow IPs on another port. Enter a new port number (e.g., 80, 8080, 8443) to continue testing only the problematic IPs.

6. View results

Results are saved in the results/ folder with filenames like ips_successful_port443(1).txt. Each file contains:

· A list of IPs only (for easy copying)
· A list of IPs with ping times (for analysis)
· For CIDR ranges, the source range is also shown

---

📁 Project Structure

```
cdn-ip-tester/
├── Nexus.py               # Main script
├── ips.txt                # Input file (auto-created if missing)
├── results/               # Test results (one file per port)
└── .config/               # Persistent settings (auto-created)
    └── settings.json
```

---

🧪 Test Modes

Mode Description
tcp TCP handshake only – fast, low‑level check to see if the port is open
http Full HTTP/HTTPS request using curl – simulates real web traffic
both Runs both TCP and HTTP tests, using the slower (more accurate) time

---

📊 Example Output

```
✅ WORKING: 203.198.20.15:443 (TCP:45ms | HTTP:67ms)
✅ WORKING: 1.1.1.1:443 (TCP:12ms | HTTP:15ms)
⏱️ SLOW: 8.8.8.8:443 (TCP:300ms | HTTP:310ms)
❌ FAIL: 203.198.20.99:443
```

---

📄 License

This project is licensed under the MIT License – free to use, modify, and distribute.

---

🤝 Contributing

Issues, suggestions, and pull requests are welcome!
Feel free to open an issue or contact the maintainer.
