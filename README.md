## Setup
1) python -m venv .venv
2) .venv\Scripts\activate
3) pip install -r requirements.txt
4) copy .env.example .env og udfyld

## Kør pipeline
Del A: hent mails + pdf + tekst -> tasks.json
  python -m src.pipeline.a_ingest_mail

Del B: analyse + preview til tømrere
  python -m src.pipeline.b_analyze_and_notify

Del C: lav plan (tekst)
  python -m src.pipeline.c_plan_schedule

Outputs:
- data/state/tasks.json
- data/out/carpenter_email_preview.txt
- data/out/plan_preview.txt
