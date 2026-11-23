# Persistent system log (journald)

Raspberry Pi OS keeps the journal in RAM only
(`/usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf`: `Storage=volatile`,
to spare SD cards), so every reboot wipes it. forrest-jr boots from an SSD, so
`90-forrest.conf` overrides that: the log goes to `/var/log/journal`, older than
3 months is deleted, 2 GB cap. Installed 2026-11-23.

Install (needs sudo; run on the Pi):

    sudo mkdir -p /etc/systemd/journald.conf.d
    sudo cp pi/journald/90-forrest.conf /etc/systemd/journald.conf.d/
    sudo systemctl restart systemd-journald
    sudo journalctl --flush

Check: `journalctl --header | grep 'File path'` shows `/var/log/journal/...`.
Useful: `journalctl -b -1 -k | grep -i usb`, `journalctl --user -u forrest-lidar --since today`.
