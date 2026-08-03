# WiPcam Bridge

WiPcam Bridge discovers and manages WiPcam/OMGuard cameras on a trusted LAN
and republishes each enabled camera through MediaMTX as RTSP. It includes an
authenticated management interface, persistent camera configuration, and
independent supervision for up to four cameras.

## Before starting

Set these required options in the Configuration tab:

- `lan_bind_ip`: the IPv4 address of the Home Assistant host on the same LAN as
  the cameras. Do not use `0.0.0.0`, a Docker address, or a loopback address.
- `basic_username`: the management interface username.
- `basic_password`: a strong management interface password.

The add-on uses host networking because camera discovery broadcasts from UDP
port 7200 and the camera protocol calls back to a LAN address over a managed
UDP worker-port range. No privileged mode, hardware mapping, Docker API, or
Home Assistant/Supervisor API access is requested.

## Use

1. Start the add-on and open its web interface at port `8080`.
2. Sign in with the configured management credentials.
3. Select **Add camera**, scan the LAN, and enter the camera security code.
4. Enable a configured camera.
5. Use the displayed recording or low-stream RTSP URL in Home Assistant.

The default RTSP paths are:

```text
rtsp://<home-assistant-host>:8554/<stream-key>
rtsp://<home-assistant-host>:8554/<stream-key>-sub
```

Set both `rtsp_read_username` and `rtsp_read_password` to protect RTSP readers.
If both are omitted, RTSP playback is available without authentication to
clients that can reach the Home Assistant host. Publishing and the MediaMTX API
remain restricted to loopback clients.

Camera definitions and retained diagnostics are stored in
`/data/wipcam.sqlite3` and are included in cold add-on backups.

## Ports and security

WiPcam Bridge listens on TCP `8080` for its authenticated management interface
and TCP `8554` for RTSP. It also uses UDP `7200` for discovery, UDP `32100`
for local rendezvous, and UDP `13000-13099` for camera workers. Check for port
conflicts before starting another service on the Home Assistant host.

Unused MediaMTX RTMP, HLS, WebRTC, SRT, and UDP/multicast RTSP listeners are
disabled to keep the host-network surface limited to the features this add-on
uses.

Camera Telnet operations use cleartext traffic on the trusted camera LAN and
retained camera files can contain credentials. Keep the camera network trusted,
use strong management and optional RTSP credentials, and protect backups.

Experimental camera writes can modify camera flash and may require manual
recovery. Leave `experimental_camera_writes_enabled` disabled unless you have
reviewed the upstream documentation and accept that risk.

## Packaged versions

- WiPcam Bridge `0.1.0`, pinned to commit
  `aedd25bf1fc48f34972de56b3c1d856eb6a25e18`
- MediaMTX `1.18.2`

For protocol and operational details, see the
[upstream WiPcam Bridge repository](https://github.com/iuginP/wipcam-bridge).
