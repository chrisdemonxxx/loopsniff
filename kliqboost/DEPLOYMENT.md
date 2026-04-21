# Kliqboost Professional Deployment

This guide automates upgrading all Kliqboost services to Render Professional plan for 24/7 availability.

## 🚀 Quick Deploy

```bash
# Run automated deployment
./deploy-professional.sh

# Check deployment status
./check-deployment.sh
```

## 📋 What Gets Deployed

| Service | Description | URL |
|---------|-------------|-----|
| **kliqboost-api** | FastAPI backend with database | `https://kliqboost-api.onrender.com` |
| **kliqboost-admin** | Admin dashboard (Next.js) | `https://kliqboost-admin.onrender.com` |
| **kliqboost-portal** | Client portal (Next.js) | `https://kliqboost-portal.onrender.com` |
| **kliqboost-website** | Marketing website (Next.js) | `https://kliqboost-website.onrender.com` |
| **kliqboost-vectordb** | ChromaDB vector database | `https://kliqboost-vectordb.onrender.com` |
| **kliqboost-autoresponder** | AI Telegram userbot | `https://kliqboost-autoresponder.onrender.com` |
| **kliqboost-bot** | Telegram bot service | `https://kliqboost-bot.onrender.com` |
| **kliqboost-db** | PostgreSQL database | Managed by Render |

## 🔧 Manual Steps (if needed)

### 1. Push Configuration Changes

```bash
git add .
git commit -m "Upgrade all services to Professional plan"
git push origin main
```

### 2. Monitor Deployment

Go to [Render Dashboard](https://dashboard.render.com) and watch each service redeploy.

### 3. Create Admin User

```bash
curl -X POST "https://kliqboost-api.onrender.com/bot-stats/bootstrap-admin?email=<admin-email>&password=<strong-password>&name=Kliqboost%20Admin" \
  -H "X-Sync-Key: <STATS_SYNC_KEY>"
```

### 4. Test Login

- **Admin Panel:** https://kliqboost-admin.onrender.com
- **Client Portal:** https://kliqboost-portal.onrender.com
- **Credentials:** use the admin account and password configured in your secret manager.

## ⚙️ Configuration Details

### Environment Variables to Set in Render Dashboard

#### API Service (`kliqboost-api`)
- `JWT_SECRET` (auto-generated)
- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `NOWPAY_API_KEY`
- `NOWPAY_IPN_SECRET`
- `SENDGRID_API_KEY`
- `OLLAMA_CLOUD_KEY`
- `TG_BOT_TOKEN`
- `TG_ALERT_CHAT_ID`

#### Autoresponder (`kliqboost-autoresponder`)
- `TG_SESSION_B64` (base64 encoded session file)
- `ADMIN_BOT_TOKEN`
- `ADMIN_CHAT_ID`

#### Bot Service (`kliqboost-bot`)
- `BOT_TOKEN`
- `ADMIN_ID`
- `WEBHOOK_URL`

## 🔍 Troubleshooting

### Service Still Sleeping?
- Check if `render.yaml` has `plan: professional`
- Verify Professional plan is active in Render dashboard
- Restart service manually

### Deployment Failed?
- Check build logs in Render dashboard
- Verify all required environment variables are set
- Check if database migrations ran successfully

### Login Not Working?
- Ensure admin user was created successfully
- Check API service is responding
- Verify CORS settings allow your domain

## 📊 Monitoring

Run the status checker regularly:

```bash
# Every 5 minutes during deployment
watch -n 300 ./check-deployment.sh

# Or manually
./check-deployment.sh
```

## 🎯 Expected Results

After successful deployment:
- ✅ No more "SERVICE WAKING UP" messages
- ✅ All services respond instantly
- ✅ 24/7 availability
- ✅ Professional performance (more CPU/RAM)
- ✅ Admin and client portals fully functional

## 💡 Pro Tips

1. **Monitor Costs:** Professional plan costs ~$25/month per service
2. **Backup Config:** Save environment variables securely
3. **Domain Setup:** Point custom domains to Render services
4. **SSL:** All services get free SSL certificates
5. **Scaling:** Professional plan supports higher traffic

---

**Need Help?** Check the [Render Documentation](https://docs.render.com) or run `./check-deployment.sh` for diagnostics.