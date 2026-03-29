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