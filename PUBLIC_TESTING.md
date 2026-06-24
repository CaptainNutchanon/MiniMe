# MiniMe Public Testing

Use this when you want friends to test the local MiniMe chatbot through a public URL.

## Quick Share

From the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_public_tunnel.ps1 -DownloadCloudflared
```

The script will:

- start the MiniMe server on `127.0.0.1`
- create an access key
- run a Cloudflare quick tunnel
- print the URL suffix to share with friends

When `cloudflared` prints a URL like:

```text
https://example.trycloudflare.com
```

share it with the key suffix shown by the script:

```text
https://example.trycloudflare.com/?key=YOUR_ACCESS_KEY
```

Keep the terminal window open while friends are testing.

## Background Share

Start the public tunnel in the background:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_public_tunnel.ps1 -DownloadCloudflared -Background
```

Stop the public tunnel:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_public_tunnel.ps1
```

## Local Server Only

Run without public tunnel:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_server.ps1
```

Run with an access key:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_server.ps1 -AccessKey "friend-test"
```

Open:

```text
http://127.0.0.1:8000/?key=friend-test
```

## Notes

- The public link works only while your computer and terminal are running.
- The app loads the local LoRA adapter from `output/captain-lora` by default.
- Keep the access key private. Anyone with the public URL and key can use your local model while the tunnel is open.
- If the model is busy, requests are serialized and another user may need to wait.
