# Question extraction from JEE / NEET PDFs

`backend/app/services/extraction` turns an uploaded paper (two-column or single-column, typed or scanned) into questions students can take online, with every figure cropped and every solution matched.

## Pipeline

```
PDF ──► layout.py      columns, text lines, images, vector drawings,
                       watermark / header / footer / page-number removal
    ──► segmenter.py   question bands, option cells, solution split, figures
    ──► pipeline.py    solution matching, answer keys, PNG crops
    ──► transcriber.py OpenAI vision: one isolated crop -> Markdown + LaTeX
    ──► Question rows  content / solution_content JSON + legacy text fields
```

1. **Layout (free, deterministic).** PyMuPDF gives every text line, image and vector drawing with its coordinates. The column divider line, or the empty gutter, splits the page into columns. Diagonal watermarks, running headers and footers, page numbers and the title block (Subject / Standard / Paper Set ...) are removed. Vector drawings are clustered into figures; boxes and tables around text stay text.
2. **Questions.** A question starts at its number (`(12)`, `12.`, `Q12`) at the column's left margin. Each question owns the vertical band of the column down to the next number, and continues into the next column or page. Content is assigned by geometry (its centre point), not reading order, so tightly packed questions and horizontal neighbours never mix. Stacked chemistry/fractions printed a line above the number are pulled into the right question. Numbering is validated as a sequence, so list items like "(1) Imbricate" inside a question are not mistaken for questions.
3. **Options.** Option labels `(A)`...`(D)` are grouped into grid columns (A/C and B/D in a 2×2 layout). Each option owns a cell, so a picture printed under or beside "(B)" belongs to option B. Structures printed around the label (label on the middle line) are included.
4. **Figures.** Images, vector diagrams (circuits, graphs, biology diagrams) and typed structural formulas (`CH3−CH−...` with `|`/`||` bonds) are cropped at 216 dpi with their labels. They are tagged as stem, option or solution figures. Stem figures are referenced from the text as `[[F1]]`, option figures as `A1`, `B1`, ..., and solution figures as `[[S1]]`.
5. **Solutions & answers.** Solutions are recognised in these forms:
   - a solution copy in the same PDF (`Solution:(Correct Answer:C)` and the explanation that follows);
   - the correct option highlighted in green;
   - answer lines (`➠ (D)`, `Ans. B`);
   - answer-key tables (`33. | B | ...`);
   - a separately uploaded solutions PDF;
   - a key typed by the teacher (`1-B, 2-C, 21-12.5`).

   Each solution is matched to its question by number and text similarity.
6. **Transcription.** The pipeline renders each question's crop with other questions' content erased and figures masked by labelled boxes (`[[F1]]`, `OPTION FIGURE`), then sends it with the text layer as a hint. The model returns stem, options, solution and any printed answer as strict JSON. Plain single-font prose (most biology) is taken from the text layer and costs nothing. Several crops share one request, results are cached on disk, and requests run in parallel.
7. **Fallbacks.** Without an API key, or if a request fails:
   - text-only questions use the text layer;
   - maths-heavy questions show their original crop, so nothing is garbled;
   - scanned pages are segmented by hanging indent and shown as crops.

   Every question keeps a "view original" crop, and anything uncertain is flagged with a reason for teacher review.

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `EXTRACTION_ENGINE` | `layout` | `gemini` switches back to the legacy whole-page extractor |
| `OPENAI_API_KEY` | – | Needed for LaTeX transcription of maths/chemistry |
| `OPENAI_EXTRACTION_MODEL` | `gpt-4.1-mini` | Any OpenAI-compatible vision model |
| `OPENAI_BASE_URL` | – | For OpenAI-compatible gateways |
| `EXTRACTION_CACHE_DIR` | `data/extraction_cache` | Re-uploading a paper costs nothing |
| `EXTRACTION_MAX_WORKERS` / `EXTRACTION_BATCH_SIZE` | `4` / `6` | Parallel requests / crops per request |

Cost with `gpt-4.1-mini` is roughly $0.05–0.15 for a 180-question paper including solutions. Layout and cropping take about 10–20 s per paper on a laptop.

## Teacher workflow

1. Upload the paper in *Omega Go*. Optionally add a separate solutions PDF or paste an answer key, and set the question ranges per subject and section.
2. The success screen shows the counts: answers found, solutions, figures cropped, and questions needing review.
3. *View Questions* on the test shows every question exactly as students will see it, with the correct option and solution. Flagged questions list the reason, and a missing or wrong answer can be fixed inline.

## Students

- Questions render with KaTeX and cropped figures, including side-by-side and option figures. Any figure can be tapped to enlarge, and the original crop is one tap away.
- Time is tracked per question, including skipped ones.
- After submission the analysis shows:
  - each question with the student's answer, the correct answer and the full solution;
  - time per question, per subject and by outcome;
  - the slowest questions, plus filters by outcome and subject.

## Developing

To run the extractor on a PDF without the web app:

```python
from app.services.extraction import extract_paper, build_transcriber
res = extract_paper("paper.pdf", asset_dir="out", asset_url="/out", transcriber=build_transcriber())
print(res.report)
```

`tests/services/test_extraction.py` covers the geometry rules on synthetic PDFs.
