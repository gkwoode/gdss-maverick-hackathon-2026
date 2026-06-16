# Environment Configuration Guide

This guide explains all environment variables used in the IMDB Product Management System.

## Quick Start

1. Copy the example files to create your environment files:
   ```bash
   # Backend
   cp backend/.env.example backend/.env
   
   # Frontend
   cp frontend/.env.example frontend/.env.local
   ```

2. Update the values in the `.env` files with your actual configuration.

3. **Important**: Update the `OPENAI_API_KEY` in `backend/.env` for image analysis features to work.

---

## Backend Configuration (backend/.env)

### Django Core Settings

#### `SECRET_KEY`
- **Default**: `django-insecure-change-this-in-production-use-random-string-here`
- **Description**: Django's secret key for cryptographic signing
- **Production**: Generate a secure random string (50+ characters)
- **Generate**: `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`

#### `DEBUG`
- **Default**: `True`
- **Description**: Enables Django debug mode
- **Values**: `True` or `False`
- **Production**: **MUST** be `False`

#### `ALLOWED_HOSTS`
- **Default**: `localhost,127.0.0.1,backend`
- **Description**: Comma-separated list of host/domain names
- **Production**: Add your actual domain (e.g., `example.com,www.example.com`)

---

### Database Configuration

#### `DB_ENGINE`
- **Default**: `django.db.backends.postgresql`
- **Description**: Database backend engine
- **Options**: 
  - `django.db.backends.postgresql` (recommended for production)
  - `django.db.backends.sqlite3` (for local dev only)
  - `django.db.backends.mysql`

#### `DB_NAME`
- **Default**: `imdb`
- **Description**: Database name
- **Docker**: Should match `POSTGRES_DB` in docker-compose.yml

#### `DB_USER`
- **Default**: `postgres`
- **Description**: Database username
- **Docker**: Should match `POSTGRES_USER` in docker-compose.yml

#### `DB_PASSWORD`
- **Default**: `postgres`
- **Description**: Database password
- **Production**: Use a strong, unique password
- **Docker**: Should match `POSTGRES_PASSWORD` in docker-compose.yml

#### `DB_HOST`
- **Default**: `db`
- **Description**: Database host
- **Docker**: Use `db` (service name)
- **Local**: Use `localhost` or `127.0.0.1`

#### `DB_PORT`
- **Default**: `5432`
- **Description**: Database port
- **PostgreSQL**: `5432` (default)
- **MySQL**: `3306`

---

### CORS Configuration

#### `CORS_ALLOWED_ORIGINS`
- **Default**: `http://localhost:3000,http://127.0.0.1:3000`
- **Description**: Comma-separated list of allowed frontend origins
- **Production**: Add your frontend domain (e.g., `https://example.com`)
- **Note**: When `DEBUG=True`, all origins are allowed automatically

---

### OpenAI Configuration

#### `OPENAI_API_KEY`
- **Default**: `your-openai-api-key-here`
- **Description**: OpenAI API key for image analysis features
- **Required**: Yes (for image analysis to work)
- **Get Key**: https://platform.openai.com/api-keys
- **Usage**: Used by the image analyzer service to extract product details from images

---

### Media Files Configuration

#### `MEDIA_URL`
- **Default**: `/media/`
- **Description**: URL prefix for media files

#### `MEDIA_ROOT`
- **Default**: `media`
- **Description**: Directory where uploaded files are stored

---

### AWS S3 Configuration (Optional - Production)

#### `USE_S3`
- **Default**: `False` (commented out)
- **Description**: Enable AWS S3 for media storage
- **Values**: `True` or `False`

#### `AWS_ACCESS_KEY_ID`
- **Description**: AWS access key ID
- **Required**: If `USE_S3=True`

#### `AWS_SECRET_ACCESS_KEY`
- **Description**: AWS secret access key
- **Required**: If `USE_S3=True`

#### `AWS_STORAGE_BUCKET_NAME`
- **Description**: S3 bucket name for storing media files
- **Required**: If `USE_S3=True`

#### `AWS_S3_REGION_NAME`
- **Default**: `us-east-1`
- **Description**: AWS region where your S3 bucket is located

#### `AWS_S3_CUSTOM_DOMAIN`
- **Description**: CloudFront domain for serving media files
- **Optional**: For better performance with CDN

---

### Email Configuration (Optional - Production)

#### `EMAIL_BACKEND`
- **Default**: `django.core.mail.backends.smtp.EmailBackend`
- **Description**: Django email backend

#### `EMAIL_HOST`
- **Example**: `smtp.gmail.com`
- **Description**: SMTP server hostname

#### `EMAIL_PORT`
- **Default**: `587`
- **Description**: SMTP server port

#### `EMAIL_USE_TLS`
- **Default**: `True`
- **Description**: Use TLS encryption

#### `EMAIL_HOST_USER`
- **Description**: Email address for sending emails

#### `EMAIL_HOST_PASSWORD`
- **Description**: Email account password or app-specific password

---

## Frontend Configuration (frontend/.env.local)

### API Configuration

#### `NEXT_PUBLIC_API_URL`
- **Default**: `http://localhost:8000/api`
- **Description**: Backend API base URL
- **Docker**: Use `http://backend:8000/api`
- **Production**: Use your actual backend URL (e.g., `https://api.example.com/api`)
- **Note**: Must start with `NEXT_PUBLIC_` to be accessible in browser

---

### Analytics (Optional)

#### `NEXT_PUBLIC_GA_ID`
- **Description**: Google Analytics tracking ID
- **Format**: `G-XXXXXXXXXX` or `UA-XXXXXXXXX-X`
- **Optional**: Only if using Google Analytics

---

### Error Tracking (Optional)

#### `NEXT_PUBLIC_SENTRY_DSN`
- **Description**: Sentry DSN for error tracking
- **Get DSN**: https://sentry.io
- **Optional**: Only if using Sentry

---

## Docker Compose Environment

The `docker-compose.yml` file also defines PostgreSQL environment variables:

```yaml
POSTGRES_DB=imdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

These should match your backend database configuration.

---

## Environment-Specific Configurations

### Local Development (without Docker)

**Backend (.env)**:
```env
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
DB_HOST=
DB_PORT=
```

**Frontend (.env.local)**:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

### Docker Development

**Backend (.env)**:
```env
DB_ENGINE=django.db.backends.postgresql
DB_HOST=db
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

**Frontend (.env.local)**:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

### Production

**Backend (.env)**:
```env
SECRET_KEY=<strong-random-key>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DB_PASSWORD=<strong-password>
CORS_ALLOWED_ORIGINS=https://yourdomain.com
USE_S3=True
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
```

**Frontend (.env.local)**:
```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api
```

---

## Security Best Practices

1. **Never commit `.env` files** to version control (already in `.gitignore`)
2. **Always commit `.env.example` files** as templates
3. **Use strong passwords** in production
4. **Rotate secrets regularly** (SECRET_KEY, DB_PASSWORD, API keys)
5. **Set DEBUG=False** in production
6. **Use HTTPS** in production for all URLs
7. **Restrict ALLOWED_HOSTS** to specific domains in production
8. **Use environment-specific values** - don't share the same credentials across environments

---

## Troubleshooting

### Backend can't connect to database
- Check `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` match your database setup
- For Docker: ensure `DB_HOST=db` (the service name)
- Verify PostgreSQL is running: `docker-compose ps`

### Frontend can't reach backend API
- Check `NEXT_PUBLIC_API_URL` is correct
- For Docker: backend should be `http://backend:8000/api`
- For local dev: backend should be `http://localhost:8000/api`
- Verify CORS settings in backend allow your frontend origin

### Image analysis not working
- Ensure `OPENAI_API_KEY` is set correctly
- Verify you have credits in your OpenAI account
- Check backend logs for API errors

### Static/Media files not loading
- Check `MEDIA_URL` and `MEDIA_ROOT` settings
- Run `python manage.py collectstatic` for static files
- Ensure the `media/` directory has write permissions

---

## Additional Resources

- [Django Settings Documentation](https://docs.djangoproject.com/en/4.2/ref/settings/)
- [Next.js Environment Variables](https://nextjs.org/docs/basic-features/environment-variables)
- [Docker Compose Environment Variables](https://docs.docker.com/compose/environment-variables/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
