# Fabric MCP Server - Production Deployment Guide

This guide covers deploying Fabric MCP Server to production, including PostgreSQL setup, monitoring, and OVHcloud deployment.

## Quick Start with Docker Compose

The easiest way to deploy is using Docker Compose with PostgreSQL:

```bash
# Clone the repository
git clone <your-repo>
cd a2a-mcp

# Copy environment file
cp .env.example .env

# Edit .env with your settings
nano .env

# Start services
docker-compose up -d

# View logs
docker-compose logs -f fabric-gateway
```

## Configuration

### Environment Variables

Create a `.env` file with your production settings:

```bash
# Server
FABRIC_PORT=8000
FABRIC_PSK=your-secure-production-key

# Database
USE_POSTGRES=true
DATABASE_URL=postgresql://fabric:password@postgres:5432/fabric_registry

# Monitoring
ENABLE_METRICS=true
LOG_LEVEL=INFO

# Security
ALLOWED_HOSTS=fabric.yourdomain.com
CORS_ORIGINS=https://yourdomain.com
```

### Using PostgreSQL

PostgreSQL is recommended for production. Benefits:
- Persistent storage
- Horizontal scaling support
- Better query performance
- Built-in observability data

#### Database Migration from YAML

When you first start with PostgreSQL, Fabric will automatically migrate agents from `agents.yaml` to the database:

```bash
# 1. Start PostgreSQL first
docker-compose up -d postgres

# 2. Wait for database to be ready
sleep 10

# 3. Start Fabric (will auto-migrate)
docker-compose up -d fabric-gateway

# 4. Check logs
docker-compose logs fabric-gateway
```

## OVHcloud Deployment

### Step 1: Create a VM

1. Log into OVHcloud Manager
2. Create a new Public Cloud instance
3. Recommended: **B2-15** (4 vCPU, 15 GB RAM) or larger
4. Operating System: Ubuntu 22.04 LTS

### Step 2: Initial Setup

```bash
# SSH into your VM
ssh ubuntu@your-vm-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in for group changes to take effect
exit
ssh ubuntu@your-vm-ip
```

### Step 3: Deploy Fabric

```bash
# Create directory
mkdir ~/fabric && cd ~/fabric

# Copy your project files
# Option 1: Clone from GitHub
git clone https://github.com/yourusername/a2a-mcp.git .

# Option 2: SCP files from local machine
# (from your local machine)
# scp -r a2a-mcp/* ubuntu@your-vm-ip:~/fabric/

# Create production environment
cp .env.example .env
nano .env
```

Edit `.env`:

```bash
FABRIC_PORT=80
FABRIC_PSK=your-super-secret-production-key
USE_POSTGRES=true
DATABASE_URL=postgresql://fabric:strong-password@postgres:5432/fabric_registry
ENABLE_METRICS=true
LOG_LEVEL=INFO
ALLOWED_HOSTS=your-vm-ip,fabric.yourdomain.com
```

### Step 4: Start Services

```bash
# Start everything
docker-compose up -d

# Verify services are running
docker-compose ps

# View logs
docker-compose logs -f fabric-gateway
```

### Step 5: Configure Firewall

```bash
# Allow HTTP traffic
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp  # If using HTTPS
sudo ufw allow 22/tcp   # SSH
sudo ufw enable
```

### Step 6: (Optional) Set up HTTPS with Nginx

```bash
# Install Nginx
sudo apt install nginx certbot python3-certbot-nginx -y

# Create Nginx config
sudo nano /etc/nginx/sites-available/fabric
```

Add:

```nginx
server {
    listen 80;
    server_name fabric.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable and get SSL:

```bash
sudo ln -s /etc/nginx/sites-available/fabric /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Get SSL certificate
sudo certbot --nginx -d fabric.yourdomain.com
```

## Monitoring Setup

### Option 1: Basic Monitoring (Included)

Fabric includes built-in monitoring endpoints:

```
GET /monitoring/dashboard      # Human-readable dashboard
GET /monitoring/metrics        # JSON metrics for AI agents
GET /monitoring/health         # Health check
GET /monitoring/status         # AI-optimized status
GET /metrics                   # Prometheus metrics
```

### Option 2: Full Monitoring Stack

Start with monitoring profile:

```bash
docker-compose --profile monitoring up -d
```

This starts:
- **Prometheus** (port 9090) - Metrics collection
- **Grafana** (port 3000) - Visualization dashboards

Access:
- Prometheus: http://your-vm-ip:9090
- Grafana: http://your-vm-ip:3000 (admin/admin)

### Setting Up Grafana

1. Log into Grafana (default: admin/admin)
2. Add Prometheus data source: http://prometheus:9090
3. Import dashboard from `observability/grafana/dashboards/`

## Public Registry Setup

To enable public agent registration (like npm for agents):

### 1. Enable Public Mode

```bash
# In .env
PUBLIC_REGISTRY=true
REGISTRY_REQUIRES_AUTH=true
ALLOW_EXTERNAL_REGISTRATION=true
```

### 2. Registration API

Users can register agents via:

```bash
curl -X POST https://fabric.yourdomain.com/mcp/call \
  -H "Authorization: Bearer $REGISTRY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "fabric.agent.register",
    "arguments": {
      "agent_id": "my-awesome-agent",
      "display_name": "My Awesome Agent",
      "endpoint": "https://my-agent.example.com/mcp",
      "capabilities": [...]
    }
  }'
```

### 3. API Keys

Generate API keys for agent developers:

```bash
# Add to database or config
REGISTRY_API_KEYS=key1,key2,key3
```

## Backup and Recovery

### Database Backup

```bash
# Backup PostgreSQL
docker exec fabric-postgres pg_dump -U fabric fabric_registry > backup.sql

# Automated daily backup
crontab -e
# Add: 0 2 * * * docker exec fabric-postgres pg_dump -U fabric fabric_registry > /backups/fabric-$(date +\%Y\%m\%d).sql
```

### Restore

```bash
# Restore from backup
docker exec -i fabric-postgres psql -U fabric fabric_registry < backup.sql
```

## Scaling

### Vertical Scaling

Increase VM resources:
- CPU: 4+ cores
- RAM: 8+ GB
- Disk: 50+ GB SSD

### Horizontal Scaling (Future)

For multiple Fabric instances:

1. Use external PostgreSQL (OVHcloud Database)
2. Deploy multiple Fabric instances behind load balancer
3. Use shared Redis for session state

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  fabric-gateway-1:
    build: .
    environment:
      - DATABASE_URL=postgresql://user:pass@external-db.ovh.net:5432/fabric
  
  fabric-gateway-2:
    build: .
    environment:
      - DATABASE_URL=postgresql://user:pass@external-db.ovh.net:5432/fabric
  
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"
```

## Troubleshooting

### Check Service Status

```bash
# View all services
docker-compose ps

# View logs
docker-compose logs fabric-gateway
docker-compose logs postgres

# Check database connection
docker exec -it fabric-postgres psql -U fabric -d fabric_registry -c "\dt"
```

### Common Issues

**1. Database connection failed**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Verify connection string in .env
```

**2. Port already in use**
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Change port in .env
FABRIC_PORT=8080
```

**3. Permission denied**
```bash
# Fix permissions
sudo chown -R ubuntu:ubuntu ~/fabric
```

### Health Check

```bash
# Check server health
curl http://localhost:8000/health

# Check metrics
curl http://localhost:8000/monitoring/health

# Check Prometheus metrics
curl http://localhost:8000/metrics
```

## Security Checklist

- [ ] Change default PSK in production
- [ ] Use strong PostgreSQL password
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Restrict CORS origins (don't use *)
- [ ] Set up firewall rules
- [ ] Enable rate limiting
- [ ] Regular security updates
- [ ] Database backups
- [ ] Log monitoring
- [ ] Access logging

## Updating

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Database migrations (if needed)
docker exec -it fabric-postgres psql -U fabric -d fabric_registry -f /migrations/update.sql
```

## Support

For issues or questions:
- Check logs: `docker-compose logs`
- Review documentation: [README.md](README.md)
- Open issue on GitHub

---

**Your Fabric MCP Server is now production-ready! 🚀**