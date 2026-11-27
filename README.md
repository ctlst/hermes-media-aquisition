# Hermes media workflow

```mermaid
flowchart TD
    A["Someone asks Hermes for a movie"] --> B{"Is it already in Plex?"}
    B -- Yes --> C["Done: it is already in the library"]
    B -- No --> D["Hermes picks a healthy release"]
    D --> E["Over a restricted SSH key, the media helper checks the VPN and adds the download paused"]
    E --> F["Helper rechecks the VPN, then starts that exact download"]
    F --> G["qBittorrent downloads only through the Gluetun VPN"]
    G --> H["Helper links the finished file into Plex and asks Plex to scan"]
```

A systemd service on the media host starts the VPN and download containers once storage is mounted, and restarts them if either one stops.
