# NEXUS Prime Frontend

Angular 21 SPA for the NEXUS Prime manufacturing operations system.

## Local Development

Use the root script so the frontend runtime API address is written automatically:

```powershell
..\scripts\dev.ps1
```

Direct frontend commands:

```powershell
npm install
npm start -- --host 127.0.0.1 --port 4200
```

## Runtime API

Production builds read `NEXUS_API_BASE_URL` and generate `public/runtime-config.js` before build.

```env
NEXUS_API_BASE_URL=https://<backend-project>.vercel.app/api/v1
```

Do not put backend secrets, Supabase connection strings, AI keys, or Cloudinary secrets in this project.

## Verification

```powershell
npm test -- --watch=false
npm run build
npm run audit:charts
npm run audit:layout
```

## Deploy

Vercel project settings:

```text
Project Root: frontend
Framework Preset: Angular
Build Command: npm run build
Output Directory: dist/frontend/browser
```

Full deployment instructions are in `../docs/deployment-supabase-vercel.md`.
