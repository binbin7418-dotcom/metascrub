# MetaScrub — Metadata Audit & Scrub: Find, Remove & Verify Hidden Data in Photos, Office & PDF Files

Before you send a file out, MetaScrub shows you what is hiding inside
it — the GPS coordinates and camera serial number in a photo, the
author, company and revision history in a Word document, the author and
producer data in a PDF — then removes it and re-checks the cleaned copy
until the report reads zero. The differentiator is the report itself:
every file gets a **found → removed → rechecked zero** triple, instead
of a bare "done" list.

100% local — your files never leave your computer. Originals are never
modified: scrubbed copies are written to a separate folder, and the
report proves the result per file (photo pixels unchanged, document
text unchanged).

## What it audits

- **JPEG photos** (EXIF via piexif): GPS coordinates, Make/Model,
  Software, Artist, DateTime/DateTimeOriginal, BodySerialNumber and
  LensSerialNumber, plus whether an EXIF thumbnail is embedded (the
  cropped-out part of a photo can survive inside its own thumbnail).
- **Office files** (docx/xlsx/pptx, handled as zip + XML, never
  unzipped to disk): docProps/core.xml author (dc:creator),
  lastModifiedBy and revision; docProps/app.xml Company;
  docProps/custom.xml presence; revision traces (w:rsid attributes) in
  document XML.
- **PDFs** (PyMuPDF): info-dictionary Author, Creator, Producer, Title,
  Subject, Keywords, plus XMP metadata presence.

## What scrubbing does (copy-only)

- JPEG: the whole EXIF block is stripped at byte level, so GPS, serial
  numbers and the embedded thumbnail go together. Pixel data is not
  re-encoded — the decoded-pixel hash is verified unchanged.
- Office: core.xml author/lastModifiedBy are emptied and revision is
  reset, app.xml Company is emptied, custom.xml is removed, and rsid
  attributes are stripped from document XML. Body text is verified
  unchanged and the file is verified to still open.
- PDF: info-dictionary fields and XMP metadata are emptied via
  PyMuPDF and saved to a new file. Page text is verified unchanged and
  the file is verified to still open.

## Verified behaviour

Seeded acceptance test with known ground truth (harness:
dev/test_acceptance.py; seeds built programmatically, no real
cryptographic signature anywhere): **35/35 checks passed**.

- JPEG planted with GPS (37.77500, -122.41944), BodySerialNumber
  SN-TEST-12345, an embedded EXIF thumbnail and Make/Model: audit hit
  all 9 planted items; after scrub, recheck GPS/serial/thumbnail/total
  all 0; decoded-pixel hash unchanged.
- DOCX planted with author Jane Author, lastModifiedBy John Editor,
  revision 7, Company Acme Corp, a custom-properties block and 4 rsid
  attributes: audit hit all 6 finding groups; after scrub, recheck 0;
  file still opens; body-text hash unchanged.
- PDF planted with Author, Creator, Producer, Title, Subject, Keywords
  and XMP metadata: audit hit all 7 items; after scrub, recheck 0;
  file still opens; page-text hash unchanged.
- A PDF carrying a signature field (real /FT /Sig marker in the file
  bytes, plus signature flags = 3): detected, skipped, no scrubbed copy
  produced, and the report states the skip explicitly.
- All 4 original seed files byte-identical (SHA-256) before and after;
  scan-only mode wrote nothing.

Full log: TEST-RESULTS.txt. Example report: sample_report.md.

## Run from source

```
python metascrub.py scan  <folder>
python metascrub.py scrub <folder> --out <cleaned_folder>
```

Dependencies: Pillow, piexif, PyMuPDF (see requirements.txt). The
Windows app (`gui.py`, packaged with PyInstaller) wraps the same engine.

## Scope & honest limits

- Signed PDFs are detected by signature flags and/or a /Type /Sig or
  /FT /Sig marker in the file bytes, and are skipped — scrubbing would
  break the signature. Detection is signature-field/marker detection
  only: it is not a cryptographic signature validation, and it cannot
  tell you whether a signature is valid, trusted, or legally binding.
- A scrubbed file is not certified or compliant with any law, standard
  or platform policy. Scrubbing removes metadata; it does not make a
  document legally "clean", and it does not remove tracked-change
  content itself — only the rsid revision-trace attributes. Review the
  report before sending anything sensitive.
- JPEG is the only image format in v1. PNG, HEIC, TIFF and RAW metadata
  are not scrubbed in this version and are reported as unsupported,
  never force-converted. Video and audio metadata are out of scope.
- Office revision history beyond rsid attributes (comments, tracked
  insertions/deletions as content) is not removed; the report lists
  exactly what was found and removed, nothing more.
