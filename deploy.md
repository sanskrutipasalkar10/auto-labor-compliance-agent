# Deployment Guide for Oracle VM

This project is now ready for deployment using Docker Compose. Follow these steps to get it running on your Oracle VM:

## 1. Prerequisites
- Docker and Docker Compose installed on the Oracle VM.
- Ports `80` (Frontend) and `8000` (Backend API) allowed in the VM's security list (Ingress rules).

## 2. Setup
1. Clone or copy this repository to your VM.
2. Navigate to the project root:
   ```bash
   cd auto-labor-compliance-agent
   ```
3. Create your `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
4. Edit the `.env` file and fill in your API keys:
   ```bash
   nano .env
   ```
   **Crucial**: Update `VITE_API_BASE_URL` and `VITE_WS_BASE_URL` to point to your VM's public IP address:
   ```env
   VITE_API_BASE_URL=http://<YOUR_VM_PUBLIC_IP>:8000/api
   VITE_WS_BASE_URL=ws://<YOUR_VM_PUBLIC_IP>:8000/ws
   ```

## 3. Run with Docker Compose
Build and start the services in detached mode:
```bash
docker-compose up -d --build
```

## 4. Verification
- **Frontend**: Open `http://<YOUR_VM_PUBLIC_IP>` in your browser.
- **Backend API**: Check `http://<YOUR_VM_PUBLIC_IP>:8000/` to see the "System Online" message.

## Troubleshooting
- If the frontend cannot communicate with the backend, ensure that port `8000` is open in both the VM's OS firewall (e.g., `ufw` or `firewalld`) and the Oracle Cloud security list.
- Check logs: `docker-compose logs -f`
