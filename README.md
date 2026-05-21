# Exam Generator

AI-powered exam builder for teachers and students. Upload course documents (PDFs),
configure exam specs (difficulty, question types, number of exercises, total points,
per-exercise points, export format), refine the request with chat, and download the
generated exam as DOCX or PDF.

## Stack

- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Backend**: FastAPI (Python)
- **Auth + DB + Storage**: Supabase (Postgres + Google OAuth + Storage)
- **LLM**: OpenRouter (free models, default `meta-llama/llama-3.3-70b-instruct:free`)
- **Exports**: `python-docx` (DOCX), `reportlab` (PDF)

## Project layout

```
frontend/   # Vite + React + TS SPA
backend/    # FastAPI service
supabase/   # SQL migrations
```

## 1. Supabase setup

1. Create a project at https://supabase.com.
2. **Authentication → Providers → Google**: enable, set client ID/secret from Google Cloud Console, add `http://localhost:5173` as a redirect.
3. **Storage**: create two private buckets named `documents` and `exports`.
4. **SQL Editor**: run [supabase/migrations/0001_init.sql](supabase/migrations/0001_init.sql) to create tables, RLS policies, and storage policies.
5. **Project Settings → API**: copy
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `VITE_SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_KEY`
   - **Project Settings → API → JWT Settings → JWT Secret** → `SUPABASE_JWT_SECRET`

## 2. OpenRouter

Sign up at https://openrouter.ai, create an API key, and put it in the backend `.env`. The default model is a free Llama 3.3 70B model; you can switch via `OPENROUTER_MODEL`.

## 3. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env  # edit values
uvicorn app.main:app --reload
```
if that doesn't work

```powershell
cd backend
irm https://astral.sh/uv/install.ps1 | iex
$env:Path = "C:\Users\yourfolder\.local\bin;$env:Path"
uv venv --python 3.12 .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env  # edit values
uvicorn app.main:app --reload
```


Backend runs at http://localhost:8000 (`/docs` for the Swagger UI).

## 4. Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env  # edit values
npm run dev
```

Frontend runs at http://localhost:5173.

## Using the app

1. Click **Sign in with Google**.
2. Upload a PDF on the dashboard.
3. Click the document to preview it and chat about its contents.
4. Click **Build exam from this document** to open the spec form:
   - Difficulty
   - Question types (MCQ, open, or both)
   - Number of exercises
   - **Total points** + per-exercise distribution (must sum to total)
   - Export format (PDF or DOCX)
   - Extra instructions
   - Side chat lets you add refinements before generating.
5. Hit **Generate exam** → preview appears with all questions, points, and an answer key.
6. Click **Download** to fetch the rendered DOCX or PDF.

## Notes

- Free OpenRouter models can sometimes return malformed JSON. The generator does one retry with an explicit correction prompt before failing.
- Document text is cached on the `documents` row at upload time. Large PDFs (>~18k chars after extraction) are truncated when sent to the LLM.
- RLS enforces per-user isolation — different Google accounts cannot see each other's data.
