# Zoho Catalyst fit for ArthaCommerce (F-03 and platform)

Status: research note, 2026-10-08. Sources are the public Catalyst docs. Items marked [UNVERIFIED] were not confirmed
(the pricing page could not be read; India data centre availability per service is not confirmed).

## 1. Verdict for the PDF worker (ERD 6.5)

Catalyst can host part of it, not all of it as designed.

| Need (ERD 6.5) | Catalyst option | Fit |
| --- | --- | --- |
| Always-on poller (`run_worker`) | AppSail, Job Pool | No. AppSail is an HTTP service: 30 s per request, instances spawn on traffic and idle out after 5 min, max 5 instances (support can raise it), must listen within 10 s. No documented always-on instance |
| Tesseract 5 (`eng`, `hin`), pikepdf, pypdfium2, ClamAV | AppSail custom runtime (OCI image, linux/amd64) | Can be baked into the image, but max 2048 MB RAM, 256 MB default disk (configurable), 30 s per request. ClamAV needs about 1 GB and a slow signature load, which risks the 10 s listen rule |
| Long jobs (OCR chunk at 300 dpi, export up to 3 min, extract) | Cron/Event Functions (15 min limit); Job Pool targets: Job Functions, Circuits, AppSail, URLs | Functions run Java/Node/Python managed runtimes with no system binaries, so no Tesseract. Pure-wheel work (pypdfium2, pikepdf, pypdf, reportlab) may fit [UNVERIFIED package size] |
| Light jobs (`internal/tick`) | Cron / Job Scheduling | Yes, good fit (section 2, row 1) |

**Recommendation:** keep the Docker worker from the PRD on a host that runs long-lived processes (Fly, Railway, Render), and use
Catalyst for scheduling and optional services. If you want everything on Catalyst, run a 2-day spike: chunked jobs
(OCR 3 to 5 pages, extract 20 pages, export per page range) driven by a Job Pool that calls an AppSail endpoint
(`POST /worker/run-one` replacing the poll loop). Our handlers are already chunked, so this is a thin adapter, but every chunk must
finish inside 30 s and ClamAV would have to be replaced (see Stratus malware scanning).

## 2. Features we can use Catalyst for

| # | Catalyst feature | Use in ArthaCommerce | Priority |
| --- | --- | --- | --- |
| 1 | Cron / Job Scheduling | Call `POST /api/v1/notes/internal/tick/` every 5 min (purge, thin versions, reconcile usage, expire reservations) with the `NOTES_TICK_SECRET` header. The Vercel free plan only allows daily crons, and notes needs sub-hourly ticks | High, low risk |
| 2 | Job Pool + Circuits | Retry and branch workflow for the upload pipeline (scan, inspect, extract, OCR) and export, instead of hand-written retries | Medium, only if the worker moves to Catalyst |
| 3 | AppSail custom runtime | Host the PDF worker as chunked HTTP jobs (section 1), or a small export/OCR microservice | Medium, spike first |
| 4 | Stratus object storage | Multipart upload for R3 resumable uploads, byte-range download, versioning, built-in malware scanning (could replace ClamAV). Would sit beside Supabase Storage, so only if we accept two stores | Low for R2, evaluate for R3 |
| 5 | Zia OCR | PDF and image input, 21 languages including Hindi, handwriting if legible. No word boxes are documented, so it cannot replace Tesseract's text layer. Candidate for the R3 "Improve page" tier instead of Gemini [UNVERIFIED limits and price]. Files leave our stack, so it needs consent wording | Low, R3 |
| 6 | SmartBrowz (headless browser, PDF from HTML templates) | "Download my notes" PDF and appendix pages, shared digests as PDF. Not suitable for burning marks onto an existing PDF | Low |
| 7 | Cache | Shared throttle and flag cache across instances (audit AUD-008). Redis or Postgres does the same today | Low |
| 8 | Push Notifications, Mail | X-01.1 already uses pywebpush and SMTP | Skip |
| 9 | Logging/APM, Security rules, API Gateway | Overlap Sentry, DRF and Vercel | Skip |
| 10 | Data Store, Search, User Authentication, Filestore, Web client hosting | Overlap Supabase Postgres/Auth/Storage and Vercel; Django is the only writer by design | Skip |
| 11 | Event Functions (Signals) | Only react to Catalyst-internal resources; our data lives in Supabase | Skip |

## 3. Constraints to remember

- AppSail and Basic/Advanced I/O functions: 30 s hard limit. Event and Cron functions: 15 min. Job Pool runs at most 10 AppSail, circuit or URL targets in parallel.
- Integration Functions are not available in the IN, EU, AU and CA data centres.
- Images must be OCI, linux/amd64.
- Data residency: pick the India data centre if student PDFs are processed there [UNVERIFIED which services exist in IN].
- Pricing and free tier: not read. Send the pricing page link and I will check it.

## 4. Decision needed (affects R2 slices 9, 17, 18)

A. Container-host worker as in the PRD (recommended). B. Catalyst AppSail + Job Pool chunked adapter (spike first).
Cron (row 1) is independent and can be adopted either way.

Sources: docs.catalyst.zoho.com (AppSail limits, custom runtimes, Job Pool key concepts, serverless FAQ, Stratus intro, SmartBrowz, Zia OCR key concepts), catalyst.zoho.com/features.
