# Adding tourism sites

JSON files in this folder are the curated knowledge base.

## Rules

1. Add a new object in the regional `sites.json` (do not invent a region).
2. Every factual sentence must have a source (`title`, `organization`, `url` if it exists, `publication_date` if known, `verification_status`).
3. Prefer MINTOUL, UNESCO, official museums, official parks.
4. If a price, timetable, phone number, address, GPS point or historical date is not in that source, store `null`.
5. Never copy random blogs.
6. Rebuild the index:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m scripts.build_knowledge_base
```
