# MetaScrub Report

- Mode: scrub
- Input folder: seed input folder
- Output folder: seed output folder

## document.pdf (PDF)
- Found: 7 item(s)
  - [PDF info dictionary] Author: Jane Author
  - [PDF info dictionary] Creator: MetaScrub Test Creator
  - [PDF info dictionary] Producer: TestProducer 1.0
  - [PDF info dictionary] Title: Quarterly Report
  - [PDF info dictionary] Subject: Internal draft
  - [PDF info dictionary] Keywords: draft
  - [XMP metadata] XMP metadata: XMP metadata stream present
- Removed: 7 item(s)
- Recheck: 0 target item(s) remaining
- Verify opens: OK
- Verify page_text_hash_unchanged: OK
- Scrubbed copy: seed output folder/document.pdf

## photo.jpg (JPEG)
- Found: 9 item(s)
  - [EXIF] Make: TestCamera
  - [EXIF] Model: TestCam X100
  - [EXIF] Software: TestSoft 1.0
  - [EXIF] Artist: Jane Photographer
  - [EXIF] DateTime: 2024:03:15 14:30:45
  - [EXIF] DateTimeOriginal: 2024:03:15 14:30:45
  - [EXIF] BodySerialNumber: SN-TEST-12345
  - [GPS] GPS coordinates: 37.77500, -122.41944
  - [EXIF thumbnail] EXIF thumbnail: 615 bytes embedded
- Removed: 9 item(s)
- Recheck: 0 target item(s) remaining
- Verify pixel_hash_unchanged: OK
- Scrubbed copy: seed output folder/photo.jpg

## report.docx (Office)
- Found: 6 item(s)
  - [core properties] dc:creator (author): Jane Author
  - [core properties] cp:lastModifiedBy: John Editor
  - [core properties] cp:revision: 7
  - [app properties] Company: Acme Corp
  - [custom properties] docProps/custom.xml present: custom properties block present
  - [revision traces] revision traces (w:rsid attributes): 4 rsid attribute(s) across document XML
- Removed: 6 item(s)
- Recheck: 0 target item(s) remaining
- Verify body_text_hash_unchanged: OK
- Verify opens: OK
- Scrubbed copy: seed output folder/report.docx

## signed.pdf (PDF)
- Found: 4 item(s)
  - [PDF info dictionary] Author: Jane Author
  - [PDF info dictionary] Creator: Test Creator
  - [PDF info dictionary] Producer: TestProducer
  - [PDF info dictionary] Title: Agreement
- skipped — digitally signed, scrubbing would break the signature
- No scrubbed copy was produced for this file.

100% local — nothing was uploaded. Original files were never modified; scrubbed copies are separate files.
Note: a scrubbed file is not legally certified or compliant with any standard; signed PDFs are detected by signature-field/marker detection and skipped, not cryptographically validated.
