# Enterprise Network Setup & Connectivity

This document explains how the Smart Table Analyzer connects to services within the enterprise network.

## Network Architecture

### Connection Overview

The Smart Table Analyzer connects to three main services within the Dell enterprise network:

1. **IOMETE Platform** - Iceberg data lakehouse platform
2. **Dell AIA Gateway** - LLM API gateway for AI model access
3. **Alation Catalog** (optional) - Data catalog for metadata enrichment

### Network Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Enterprise Network                        │
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │   Developer  │         │   IOMETE     │                 │
│  │   Workstation│◄───────►│   Platform   │                 │
│  │              │ Spark   │  (Data Lake) │                 │
│  └──────────────┘ Connect │              │                 │
│         │                └──────────────┘                 │
│         │                                                   │
│         │ HTTPS                                            │
│         ▼                                                   │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ Dell AIA     │◄───────►│   Alation    │                 │
│  │ Gateway      │ HTTPS   │   Catalog    │                 │
│  │  (LLM API)   │         │ (Optional)   │                 │
│  └──────────────┘         └──────────────┘                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## IOMETE Connection

### Connection Details

**Host:** `cp.iomete-a2-np.kob.dell.com`
**Protocol:** HTTPS (SSL/TLS)
**Port:** 443

### Spark Connect Endpoint

The system uses Spark Connect to execute queries against IOMETE:

```
sc://cp.iomete-a2-np.kob.dell.com:443/;cluster=lh-eds-it-lakehouse;data_plane=dp-1007399-edsit-a2np-dev02;use_ssl=true
```

**Components:**
- **Host:** `cp.iomete-a2-np.kob.dell.com`
- **Cluster:** `lh-eds-it-lakehouse` (Lakehouse name)
- **Data Plane:** `dp-1007399-edsit-a2np-dev02` (Data plane ID)
- **SSL:** Enabled (requires certificate)

### SSL Certificate

IOMETE requires SSL certificate validation:

**Certificate File:** `certs/CertificateAuthoritykob.cer`
**Verification:** Enabled by default (`IOMETE_VERIFY_SSL=true`)

**Setup:**
1. Obtain the IOMETE CA certificate from your IOMETE administrator
2. Save to `certs/CertificateAuthoritykob.cer`
3. Configure `IOMETE_CERT_FILE` in `.env`

### Authentication

IOMETE uses API token authentication:

**Environment Variables:**
```bash
IOMETE_USER_ID=your_user_id
IOMETE_API_TOKEN=your_api_token
```

**Token Format:** Base64-encoded token obtained from IOMETE UI

### Infrastructure Settings

```bash
IOMETE_DATA_PLANE=dp-1007399-edsit-a2np-dev02
IOMETE_LAKEHOUSE=lh-eds-it-lakehouse
IOMETE_CATALOG=eds_it_dev
IOMETE_NAMESPACE=elh_comn
```

## Dell AIA Gateway Connection

### Connection Details

**Base URL:** `https://aia.gateway.dell.com/genai/dev/v1`
**Protocol:** HTTPS
**Authentication:** OAuth2 with client credentials

### Authentication Flow

1. **Client Credentials:**
   ```bash
   CLIENT_ID=your_client_id
   CLIENT_SECRET=your_client_secret
   ```

2. **Token Exchange:**
   - System exchanges client credentials for access token
   - Token refresh handled automatically if `ENABLE_TOKEN_REFRESH_AT_SERVER_SIDE=true`

3. **API Calls:**
   - All LLM requests include Bearer token in Authorization header
   - Tokens have limited lifespan (typically 1 hour)

### Model Configuration

```bash
LLM_PROVIDER=custom
LLM_MODEL=gpt-oss-120b
LLM_BASE_URL=https://aia.gateway.dell.com/genai/dev/v1
```

### Generation Parameters

```bash
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4000
LLM_TIMEOUT=120
LLM_TOP_P=0.95
```

## Alation Catalog Connection (Optional)

### Connection Details

**Base URL:** `https://alation.dell.com`
**Protocol:** HTTPS
**Authentication:** API access token with refresh token

### Authentication

```bash
ALATION_BASE_URL=https://alation.dell.com
ALATION_ACCESS_TOKEN=your_access_token
ALATION_REFRESH_TOKEN=your_refresh_token
ALATION_USER_ID=your_user_id
ALATION_VERIFY_SSL=false
```

**Token Lifecycle:**
- Access token: 24-hour lifespan
- Refresh token: 60-day lifespan
- System uses refresh token to obtain new access tokens

### Usage

Alation provides:
- Table metadata enrichment
- Popular columns
- Usage patterns
- Catalog context for investigations

## Network Requirements

### Firewall Rules

Ensure the following outbound connections are allowed:

| Service | Host | Port | Protocol |
|---------|------|------|----------|
| IOMETE | cp.iomete-a2-np.kob.dell.com | 443 | HTTPS |
| Dell AIA | aia.gateway.dell.com | 443 | HTTPS |
| Alation | alation.dell.com | 443 | HTTPS |

### DNS Resolution

The following hostnames must resolve:
- `cp.iomete-a2-np.kob.dell.com`
- `aia.gateway.dell.com`
- `alation.dell.com`

### Proxy Configuration

If your enterprise network uses a proxy, configure in `.env`:

```bash
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=https://proxy.example.com:8080
NO_PROXY=localhost,127.0.0.1
```

## SSL/TLS Configuration

### Certificate Trust

The system validates SSL certificates by default. For self-signed certificates:

**Option 1: Disable verification (not recommended for production):**
```bash
IOMETE_VERIFY_SSL=false
ALATION_VERIFY_SSL=false
```

**Option 2: Use custom CA bundle:**
```bash
REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
```

### IOMETE Certificate

IOMETE uses a custom CA certificate. Setup steps:

1. Request certificate from IOMETE administrator
2. Save to project directory: `certs/CertificateAuthoritykob.cer`
3. Configure in `.env`:
   ```bash
   IOMETE_CERT_FILE=certs/CertificateAuthoritykob.cer
   ```

## Troubleshooting Network Issues

### Connection Timeout

**Symptom:** Timeout when connecting to IOMETE or AIA Gateway

**Solutions:**
1. Check network connectivity: `ping cp.iomete-a2-np.kob.dell.com`
2. Verify firewall rules allow outbound HTTPS
3. Check if proxy is required
4. Verify DNS resolution

### SSL Certificate Errors

**Symptom:** SSL certificate validation failed

**Solutions:**
1. Verify IOMETE certificate file exists and is valid
2. Check certificate hasn't expired
3. Try disabling SSL verification for testing (not production)
4. Use custom CA bundle if using corporate proxy

### Authentication Failures

**Symptom:** 401 Unauthorized or token errors

**Solutions:**
1. Verify API tokens are correct and not expired
2. Check client credentials for AIA Gateway
3. Ensure user ID matches token owner
4. Regenerate tokens if expired

### Spark Connection Issues

**Symptom:** Spark Connect connection refused

**Solutions:**
1. Verify Spark Connect URL format is correct
2. Check data plane and cluster names
3. Ensure SSL certificate is properly configured
4. Verify IOMETE platform is accessible

## Security Considerations

### Credential Management

**Best Practices:**
1. Never commit `.env` to version control
2. Use `.env.example` as template
3. Rotate API tokens regularly
4. Use separate tokens for dev/staging/production
5. Limit token permissions to minimum required

### Network Security

**Recommendations:**
1. Use SSL/TLS for all connections
2. Validate certificates in production
3. Use VPN when accessing from outside enterprise network
4. Follow enterprise security policies for API access

### Data Security

**Considerations:**
1. Investigations access sensitive table metadata
2. Query results may contain sensitive data
3. Store investigation databases securely
4. Follow data governance policies for your organization

## Development vs Production

### Development Environment

- Uses non-production IOMETE catalog (`eds_it_dev`)
- Development AIA Gateway endpoint
- Test tables and data
- Lower timeout values for faster iteration

### Production Environment

- Uses production IOMETE catalog
- Production AIA Gateway endpoint
- Real production tables
- Higher timeout values for large tables
- Stricter security settings

## Monitoring & Logging

### Connection Logging

The system logs connection attempts and errors:

```bash
LOG_LEVEL=DEBUG
LOG_FILE=./logs/analyzer.log
```

### Health Checks

Monitor service availability:

```bash
# Test IOMETE connection
python scripts/test_iomete_connection.py

# Test AIA Gateway connection
python scripts/test_aia_connection.py
```

## Contact & Support

For network connectivity issues:

1. **IOMETE Support:** Contact IOMETE platform administrator
2. **AIA Gateway Support:** Contact Dell AI platform team
3. **Alation Support:** Contact data catalog administrator
4. **Network Team:** Contact enterprise network operations for firewall/proxy issues
