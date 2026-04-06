"""
#!/bin/bash
# =========================================================================
# Defensive Triage & Attacker Neutralization Script
# Description: Isolate malicious IP, kill processes, and lockdown files.
# WARNING: Run with caution. Test in safe environment.
# =========================================================================

# Configuration
MALICIOUS_IP="x.x.x.x"  # Attacker IP to block
LOG_FILE="/var/log/defense_script.log"
SAFE_LIST="/etc/safe_ips.txt" # IPs never to block

# Ensure script is run as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root." 
   exit 1
fi

echo "--- Defense Action Initiated: $(date) ---" >> $LOG_FILE

# 1. Isolate Malicious Agent (Network Level)
echo "[+] Blocking IP: $MALICIOUS_IP"
iptables -A INPUT -s $MALICIOUS_IP -j DROP
iptables -A OUTPUT -d $MALICIOUS_IP -j DROP
echo "$(date) - Blocked $MALICIOUS_IP" >> $LOG_FILE

# 2. Kill Active Malicious Processes
echo "[+] Killing processes associated with malicious agent..."
# Finds processes connected to the bad IP and kills them
PIDS=$(netstat -anp | grep $MALICIOUS_IP | awk '{print $7}' | cut -d/ -f1 | sort | uniq)
if [ -n "$PIDS" ]; then
    kill -9 $PIDS
    echo "Killed PIDs: $PIDS" >> $LOG_FILE
else
    echo "No direct active PID found for IP, searching for common malicious activity."
fi

# 3. Secure Persistence Points (Cron jobs/SSH keys)
echo "[+] Securing SSH Keys and Crontabs..."
# Lock down authorized keys, preventing attacker from regaining access
chattr +ia /home/*/.ssh/authorized_keys 2>/dev/null
chattr +ia /root/.ssh/authorized_keys 2>/dev/null
# Clean crontabs
crontab -r 2>/dev/null
rm -rf /var/spool/cron/* 2>/dev/null
echo "$(date) - Persistence points secured." >> $LOG_FILE

# 4. Remove Common Backdoors
echo "[+] Cleaning temporary files..."
rm -rf /tmp/*
rm -rf /var/tmp/*

echo "--- Defense Action Completed: $(date) ---" >> $LOG_FILE
echo "[!] Malicious agent neutralized and isolated."
