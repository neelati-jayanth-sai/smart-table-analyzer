# Environment Configuration Quick Start

This guide helps you configure the `.env` file with your credentials.

## Step 1: IOMETE Connection

Fill in **either** OAuth credentials **OR** API token credentials:

### Option A: OAuth2 Authentication

```env
IOMETE_CLIENT_ID=your_actual_client_id
IOMETE_CLIENT_SECRET=your_actual_client_secret
```

### Option B: API Token Authentication

```env
IOMETE_USER_ID=your_actual_user_id
IOMETE_API_TOKEN=your_actual_api_token
```

### IOMETE Infrastructure

These are pre-configured but verify they match your environment:

```env
IOMETE_HOST=cp.iomete-a2-np.kob.dell.com
IOMETE_DATA_PLANE=dp-1007399-edsit-a2np-dev02
IOMETE_LAKEHOUSE=lh-eds-it-lakehouse
IOMETE_CATALOG=eds_it_dev
IOMETE_NAMESPACE=elh_comn
```

### SSL Certificate

If you have a custom SSL certificate file, update:

```env
IOMETE_CERT_FILE=path/to/your/certificate.cer
IOMETE_VERIFY_SSL=true
```

## Step 2: LLM Model Connection

You mentioned you need `CLIENT_ID`, `CLIENT_SECRET`, and `BASE_URL` for LLM.
Fill in these values:

```env
LLM_CLIENT_ID=your_llm_client_id
LLM_CLIENT_SECRET=your_llm_client_secret
LLM_BASE_URL=https://your-llm-endpoint.com/v1
LLM_PROVIDER=custom
```

If your LLM requires OAuth token endpoint:

```env
LLM_TOKEN_ENDPOINT=https://your-auth-server.com/oauth/token
```

### Alternative: Using Standard LLM Providers

If you're using OpenAI, Anthropic, or Azure instead:

**OpenAI:**

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4
```

**Anthropic (Claude):**

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

**Azure OpenAI:**

```env
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
```

## Step 3: Test Your Configuration

After filling in the credentials, test the connection:

```bash
python scripts/test_env.py
```

This will verify:

- ✅ All required environment variables are set
- ✅ IOMETE connection is working
- ✅ LLM API is accessible
- ✅ SSL certificates are valid (if applicable)

## Step 4: Common Configuration Tweaks

### Development vs Production

**Development:**

```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
VERBOSE=true
```

**Production:**

```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
VERBOSE=false
ENABLE_METRICS=true
```

### Performance Tuning

For faster processing:

```env
WORKER_THREADS=8
ENABLE_CACHING=true
CACHE_TTL_SECONDS=7200
CONNECTION_POOL_SIZE=10
```

### Security Hardening

For production deployments:

```env
ENFORCE_READ_ONLY=true
ENABLE_QUERY_VALIDATION=true
BLOCK_DANGEROUS_QUERIES=true
MAX_QUERY_RESULT_ROWS=5000
```

## Troubleshooting

### SSL Certificate Issues

If you get SSL errors:

1. Download the certificate from your IOMETE instance
2. Save it as `CertificateAuthoritykob.cer` in project root
3. Update `.env`:

   ```env
   IOMETE_CERT_FILE=CertificateAuthoritykob.cer
   IOMETE_VERIFY_SSL=true
   ```

4. Alternative: Disable SSL verification (NOT recommended for production):

   ```env
   IOMETE_VERIFY_SSL=false
   ```

### LLM Authentication Errors

If your LLM endpoint uses OAuth2 flow:

1. Ensure `LLM_TOKEN_ENDPOINT` is set correctly
2. Verify `LLM_CLIENT_ID` and `LLM_CLIENT_SECRET` are valid
3. Check if `LLM_BASE_URL` includes the correct API version path

### Connection Timeouts

If experiencing timeouts:

```env
QUERY_TIMEOUT_SECONDS=60
REQUEST_TIMEOUT=120
LLM_TIMEOUT=180
```

### Database/Directory Issues

Ensure data directories exist:

```bash
mkdir -p data logs
```

Or enable auto-creation:

```env
AUTO_CREATE_DB_DIRS=true
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IOMETE_CLIENT_ID` | Yes* | - | IOMETE OAuth client ID |
| `IOMETE_CLIENT_SECRET` | Yes* | - | IOMETE OAuth client secret |
| `IOMETE_USER_ID` | Yes** | - | IOMETE user ID (alt auth) |
| `IOMETE_API_TOKEN` | Yes** | - | IOMETE API token (alt auth) |
| `LLM_CLIENT_ID` | Yes | - | LLM OAuth client ID |
| `LLM_CLIENT_SECRET` | Yes | - | LLM OAuth client secret |
| `LLM_BASE_URL` | Yes | - | LLM API endpoint URL |
| `LLM_PROVIDER` | Yes | `custom` | LLM provider type |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `ENVIRONMENT` | No | `development` | Runtime environment |

*Required if using OAuth authentication  
**Required if using API token authentication

## Security Best Practices

1. ✅ **NEVER commit `.env` to version control** (already in `.gitignore`)
2. ✅ **Use environment-specific .env files** (`.env.dev`, `.env.prod`)
3. ✅ **Rotate credentials regularly** (CLIENT_SECRET, API_TOKEN)
4. ✅ **Use least-privilege access** (read-only for analyzer)
5. ✅ **Enable SSL verification** in production (`IOMETE_VERIFY_SSL=true`)
6. ✅ **Set short cache TTLs** for sensitive data
7. ✅ **Enable query validation** (`ENABLE_QUERY_VALIDATION=true`)
8. ✅ **Monitor access logs** (check `./logs/analyzer.log`)

## Next Steps

After configuring `.env`:

1. Run `python scripts/test_env.py` to validate configuration
2. Check logs in `./logs/analyzer.log` for any warnings
3. Review <ref_file file="C:/Users/JayanthSai_Neelati/OneDrive - Dell Technologies/EDS/smart-table-analyzer-demo/Architecture.md" /> for system overview
4. See `CONTEXT.md` for domain model and terminology
5. Start analyzing tables! 🚀

## Support

If you encounter issues:

- Check `./logs/analyzer.log` for error details
- Verify credentials with your IOMETE/LLM administrator
- Review the IOMETE and LLM provider documentation
- Ensure network connectivity to endpoints
