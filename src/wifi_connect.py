import subprocess



ssid = "IDMind"
password = "df%645;A"

print("Connecting to WiFi network %s. Password: %s" % (ssid, password))
subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password], check=True)
result = subprocess.run(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"], capture_output=True, text=True)
for line in result.stdout.splitlines():
        if line.startswith("yes:"):
            connected_ssid = line.split(":")[1]
            print(connected_ssid)