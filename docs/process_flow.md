# PDF Extraction Process Flow

## Introduction
This document describes the PDF extraction workflow designed to enhance extraction capabilities using DeepSeek AI.

## Steps in the Process Flow:
1. **PDF Upload**: User uploads a PDF document to the system.
2. **Document Parsing**: The system uses libraries such as PyPDF2 to parse the document content.
3. **OCR Processing**: If the document is scanned, OCR processing is initiated using DeepSeek OCR to extract text.
4. **Data Storage**: Extracted text and data are stored in a structured format in a database.
5. **Redis Caching**: Results are cached using Redis for quick retrieval on subsequent requests.
6. **User Retrieval**: Users can retrieve the extracted data as needed.

## Implementation

The following backend files implement this document:

| Component | File |
|-----------|------|
| PyPDF2 document parsing | `backend/app/services/pdf_parser.py` |
| DeepSeek OCR client | `backend/app/core/deepseek.py` |
| Upload + OCR + storage route | `backend/app/api/routes/deepseek_pdf.py` |
| User retrieval route | `backend/app/api/routes/deepseek_pdf.py` |
| Redis caching service | `backend/app/core/redis_cache.py` |
| Config (DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL) | `backend/app/core/config.py` |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/deepseek/upload-pdf` | Upload PDF → parse → OCR → store → cache |
| `GET`  | `/api/v1/deepseek/retrieve/{pdf_hash}` | Retrieve extraction by SHA-256 hash |
