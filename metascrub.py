#!/usr/bin/env python3
"""MetaScrub engine: audit, scrub (copy-only) and re-verify hidden
metadata in JPEG photos, Office files (docx/xlsx/pptx) and PDFs.

Everything runs locally. Inputs are never modified: scrubbed copies are
written to a separate output folder. Digitally signed PDFs are detected
(by signature flags and/or a /Type /Sig or /FT /Sig marker in the file
bytes) and SKIPPED, never scrubbed, because changing the file would
break the signature. Detection is signature-field/marker detection only
— it is not a cryptographic signature validation, and a scrubbed file is
never claimed to be legally certified or compliant with any standard.

Usage:
    python metascrub.py scan  <folder>
    python metascrub.py scrub <folder> --out <dir>
"""
import hashlib
import io
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

import piexif
from PIL import Image

try:
    import pymupdf
except ImportError:  # older PyMuPDF installs expose `fitz`
    import fitz as pymupdf

SIGNED_SKIP_NOTE = ("skipped — digitally signed, scrubbing would "
                    "break the signature")

JPEG_EXTS = {".jpg", ".jpeg"}
OFFICE_EXTS = {".docx", ".xlsx", ".pptx"}
PDF_EXTS = {".pdf"}

# ---------------------------------------------------------------- findings


class Finding:
    """One discovered metadata item: (category, field, value preview)."""

    def __init__(self, category, field, preview):
        self.category = category
        self.field = field
        self.preview = preview

    def as_tuple(self):
        return (self.category, self.field, self.preview)

    def __repr__(self):
        return "Finding(%r, %r, %r)" % (self.category, self.field,
                                         self.preview)


def _preview(value, limit=60):
    if isinstance(value, bytes):
        s = value.decode("utf-8", "ignore")
    else:
        s = str(value)
    return s if len(s) <= limit else s[:limit] + "…"


# ---------------------------------------------------------------- JPEG


def _dms_to_degrees(dms, ref):
    try:
        vals = [v[0] / v[1] if v[1] else 0 for v in dms]
        deg = vals[0] + vals[1] / 60.0 + vals[2] / 3600.0
        return -deg if ref in (b"S", b"W", "S", "W") else deg
    except Exception:
        return None


def audit_jpeg(path):
    findings = []
    try:
        data = piexif.load(path)
    except Exception as e:
        return [Finding("JPEG", "unreadable EXIF", "error: %s" % e)]
    ifd0 = data.get("0th", {})
    exif = data.get("Exif", {})
    gps = data.get("GPS", {})
    tag_names_0th = {
        piexif.ImageIFD.Make: "Make",
        piexif.ImageIFD.Model: "Model",
        piexif.ImageIFD.Software: "Software",
        piexif.ImageIFD.Artist: "Artist",
        piexif.ImageIFD.DateTime: "DateTime",
    }
    for tag, name in tag_names_0th.items():
        if tag in ifd0 and ifd0[tag] not in (b"", ""):
            findings.append(Finding("EXIF", name, _preview(ifd0[tag])))
    tag_names_exif = {
        piexif.ExifIFD.DateTimeOriginal: "DateTimeOriginal",
        piexif.ExifIFD.DateTimeDigitized: "DateTimeDigitized",
        piexif.ExifIFD.BodySerialNumber: "BodySerialNumber",
        piexif.ExifIFD.LensSerialNumber: "LensSerialNumber",
        piexif.ExifIFD.LensMake: "LensMake",
        piexif.ExifIFD.LensModel: "LensModel",
    }
    for tag, name in tag_names_exif.items():
        if tag in exif and exif[tag] not in (b"", ""):
            findings.append(Finding("EXIF", name, _preview(exif[tag])))
    if gps:
        lat = _dms_to_degrees(gps.get(piexif.GPSIFD.GPSLatitude),
                              gps.get(piexif.GPSIFD.GPSLatitudeRef))
        lon = _dms_to_degrees(gps.get(piexif.GPSIFD.GPSLongitude),
                              gps.get(piexif.GPSIFD.GPSLongitudeRef))
        if lat is not None and lon is not None:
            findings.append(Finding("GPS", "GPS coordinates",
                                    "%.5f, %.5f" % (lat, lon)))
        else:
            findings.append(Finding("GPS", "GPS data present",
                                    _preview(sorted(gps.keys()))))
    thumb = data.get("thumbnail")
    if thumb:
        findings.append(Finding("EXIF thumbnail", "EXIF thumbnail",
                                "%d bytes embedded" % len(thumb)))
    return findings


def scrub_jpeg(src, dst):
    """Strip the whole EXIF block at byte level (pixel data untouched)."""
    piexif.remove(src, dst)


def pixel_hash(path):
    with Image.open(path) as img:
        img.load()
        raw = img.tobytes()
        return hashlib.sha256(
            ("%s|%s|%s" % (img.mode, img.size, len(raw))).encode()
            + raw).hexdigest()


# ---------------------------------------------------------------- Office


def _xml_text_of(element):
    return (element.text or "").strip() if element is not None else ""


def audit_office(path):
    findings = []
    try:
        zf = zipfile.ZipFile(path)
    except Exception as e:
        return [Finding("Office", "unreadable file", "error: %s" % e)]
    names = set(zf.namelist())
    try:
        if "docProps/core.xml" in names:
            root = ET.fromstring(zf.read("docProps/core.xml"))
            ns = {"dc": "http://purl.org/dc/elements/1.1/",
                  "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"}
            for tag, name in (("dc:creator", "dc:creator (author)"),
                              ("cp:lastModifiedBy", "cp:lastModifiedBy"),
                              ("cp:revision", "cp:revision")):
                el = root.find(tag, ns)
                val = _xml_text_of(el)
                if tag == "cp:revision":
                    if val not in ("", "0"):
                        findings.append(Finding("core properties", name,
                                                _preview(val)))
                elif val:
                    findings.append(Finding("core properties", name,
                                            _preview(val)))
        if "docProps/app.xml" in names:
            root = ET.fromstring(zf.read("docProps/app.xml"))
            for el in root.iter():
                if el.tag.endswith("}Company") or el.tag == "Company":
                    val = _xml_text_of(el)
                    if val:
                        findings.append(Finding("app properties", "Company",
                                                _preview(val)))
        if "docProps/custom.xml" in names:
            findings.append(Finding("custom properties",
                                    "docProps/custom.xml present",
                                    "custom properties block present"))
        # Revision traces: w:rsid* attributes in document parts.
        doc_parts = [n for n in names
                     if n.endswith(".xml")
                     and not n.startswith("docProps/")]
        rsid_total = 0
        for part in doc_parts:
            try:
                text = zf.read(part).decode("utf-8", "ignore")
            except Exception:
                continue
            rsid_total += len(re.findall(r"w:rsid\w*=", text))
        if rsid_total:
            findings.append(Finding(
                "revision traces",
                "revision traces (w:rsid attributes)",
                "%d rsid attribute(s) across document XML" % rsid_total))
    finally:
        zf.close()
    return findings


def _rewrite_core_xml(data):
    root = ET.fromstring(data)
    ns_cp = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    ns_dc = "http://purl.org/dc/elements/1.1/"
    ET.register_namespace("cp", ns_cp)
    ET.register_namespace("dc", ns_dc)
    ET.register_namespace("dcterms", "http://purl.org/dc/terms/")
    ET.register_namespace("dcmitype", "http://purl.org/dc/dcmitype/")
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    for tag in ("{%s}creator" % ns_dc,):
        el = root.find(tag)
        if el is not None:
            el.text = ""
    for tag in ("{%s}lastModifiedBy" % ns_cp, "{%s}revision" % ns_cp):
        el = root.find(tag)
        if el is not None:
            el.text = "0" if tag.endswith("}revision") else ""
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _rewrite_app_xml(data):
    root = ET.fromstring(data)
    for el in root.iter():
        if el.tag.endswith("}Company") or el.tag == "Company":
            el.text = ""
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def scrub_office(src, dst):
    """Rewrite docProps, strip rsid attributes; body text untouched."""
    zin = zipfile.ZipFile(src)
    try:
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "docProps/custom.xml":
                    continue  # custom properties removed
                data = zin.read(item.filename)
                if item.filename == "docProps/core.xml":
                    data = _rewrite_core_xml(data)
                elif item.filename == "docProps/app.xml":
                    data = _rewrite_app_xml(data)
                elif (item.filename.endswith(".xml")
                      and not item.filename.startswith("docProps/")):
                    text = data.decode("utf-8", "ignore")
                    text = re.sub(r"\s+w:rsid\w*=\"[^\"]*\"", "", text)
                    data = text.encode("utf-8")
                zout.writestr(item, data)
    finally:
        zin.close()


def office_body_text(path):
    """Concatenated document text (docx word/document.xml; other Office
    parts fall back to all w:t-like text nodes)."""
    zf = zipfile.ZipFile(path)
    try:
        texts = []
        for name in zf.namelist():
            if name in ("word/document.xml",) or (
                    name.endswith(".xml")
                    and "/slides/slide" in name):
                try:
                    root = ET.fromstring(zf.read(name))
                except Exception:
                    continue
                for el in root.iter():
                    if el.tag.endswith("}t") and el.text:
                        texts.append(el.text)
        return "".join(texts)
    finally:
        zf.close()


def office_opens(path):
    try:
        zf = zipfile.ZipFile(path)
        names = zf.namelist()
        for name in ("word/document.xml", "docProps/core.xml"):
            if name in names:
                ET.fromstring(zf.read(name))
        zf.close()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- PDF


def _pdf_is_signed(path, doc):
    try:
        # get_sigflags() returns -1 when the file has no AcroForm at all,
        # so only a positive value means a signature is actually declared.
        flags = doc.get_sigflags()
        if flags is not None and flags > 0:
            return True
    except Exception:
        pass
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        if re.search(rb"/Type\s*/Sig", raw) or re.search(rb"/FT\s*/Sig", raw):
            return True
    except Exception:
        pass
    return False


def audit_pdf(path):
    doc = pymupdf.open(path)
    try:
        findings = []
        meta = doc.metadata or {}
        for key, name in (("author", "Author"), ("creator", "Creator"),
                          ("producer", "Producer"), ("title", "Title"),
                          ("subject", "Subject"), ("keywords", "Keywords")):
            val = (meta.get(key) or "").strip()
            if val:
                findings.append(Finding("PDF info dictionary", name,
                                        _preview(val)))
        try:
            if doc.xref_xml_metadata():
                findings.append(Finding("XMP metadata", "XMP metadata",
                                        "XMP metadata stream present"))
        except Exception:
            pass
        return findings, _pdf_is_signed(path, doc)
    finally:
        doc.close()


def scrub_pdf(src, dst):
    doc = pymupdf.open(src)
    try:
        doc.set_metadata({k: "" for k in
                          ("title", "author", "subject", "keywords",
                           "creator", "producer", "trapped")})
        try:
            doc.del_xml_metadata()
        except Exception:
            pass
        doc.save(dst, garbage=4, deflate=True)
    finally:
        doc.close()


def pdf_page_text(path):
    doc = pymupdf.open(path)
    try:
        return "".join(page.get_text() for page in doc)
    finally:
        doc.close()


def pdf_opens(path):
    try:
        doc = pymupdf.open(path)
        ok = doc.page_count >= 0
        doc.close()
        return ok
    except Exception:
        return False


# ---------------------------------------------------------------- driver


def kind_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in JPEG_EXTS:
        return "JPEG"
    if ext in OFFICE_EXTS:
        return "Office"
    if ext in PDF_EXTS:
        return "PDF"
    return "unsupported"


def audit_file(path):
    """Returns dict: kind, findings, signed."""
    kind = kind_of(path)
    if kind == "JPEG":
        return {"kind": kind, "findings": audit_jpeg(path), "signed": False}
    if kind == "Office":
        return {"kind": kind, "findings": audit_office(path),
                "signed": False}
    if kind == "PDF":
        findings, signed = audit_pdf(path)
        return {"kind": kind, "findings": findings, "signed": signed}
    return {"kind": kind, "findings": [], "signed": False}


def scan_folder(folder):
    """Audit every supported file in folder (non-recursive, sorted)."""
    files = sorted(
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f)))
    results = []
    for name in files:
        path = os.path.join(folder, name)
        info = audit_file(path)
        info["name"] = name
        info["path"] = path
        results.append(info)
    return results


def run_scan(folder):
    results = scan_folder(folder)
    return {"mode": "scan", "folder": folder, "files": results}


def run_scrub(folder, outdir):
    """Scrub every supported file into outdir (copy-only). Signed PDFs
    are skipped: no output copy is claimed for them."""
    os.makedirs(outdir, exist_ok=True)
    results = []
    for info in scan_folder(folder):
        entry = dict(info)
        entry["output"] = None
        entry["recheck"] = None
        entry["verify"] = {}
        if info["kind"] == "unsupported":
            entry["status"] = "unsupported — left untouched"
            results.append(entry)
            continue
        if info["signed"]:
            entry["status"] = SIGNED_SKIP_NOTE
            results.append(entry)
            continue
        dst = os.path.join(outdir, info["name"])
        if info["kind"] == "JPEG":
            before = pixel_hash(info["path"])
            scrub_jpeg(info["path"], dst)
            after = pixel_hash(dst)
            entry["verify"]["pixel_hash_unchanged"] = (before == after)
        elif info["kind"] == "Office":
            before = hashlib.sha256(
                office_body_text(info["path"]).encode("utf-8")).hexdigest()
            scrub_office(info["path"], dst)
            after = hashlib.sha256(
                office_body_text(dst).encode("utf-8")).hexdigest()
            entry["verify"]["body_text_hash_unchanged"] = (before == after)
            entry["verify"]["opens"] = office_opens(dst)
        elif info["kind"] == "PDF":
            before = hashlib.sha256(
                pdf_page_text(info["path"]).encode("utf-8")).hexdigest()
            scrub_pdf(info["path"], dst)
            after = hashlib.sha256(
                pdf_page_text(dst).encode("utf-8")).hexdigest()
            entry["verify"]["page_text_hash_unchanged"] = (before == after)
            entry["verify"]["opens"] = pdf_opens(dst)
        entry["output"] = dst
        entry["recheck"] = audit_file(dst)
        entry["status"] = "scrubbed"
        results.append(entry)
    return {"mode": "scrub", "folder": folder, "outdir": outdir,
            "files": results}


def render_report(result):
    lines = ["# MetaScrub Report", ""]
    lines.append("- Mode: %s" % result["mode"])
    lines.append("- Input folder: %s" % result["folder"])
    if result["mode"] == "scrub":
        lines.append("- Output folder: %s" % result["outdir"])
    lines.append("")
    for info in result["files"]:
        lines.append("## %s (%s)" % (info["name"], info["kind"]))
        if info["kind"] == "unsupported":
            lines.append("- Unsupported file type — left untouched.")
            lines.append("")
            continue
        found = info["findings"]
        lines.append("- Found: %d item(s)" % len(found))
        for f in found:
            lines.append("  - [%s] %s: %s" % (f.category, f.field,
                                              f.preview))
        if result["mode"] == "scrub":
            if info.get("status") == SIGNED_SKIP_NOTE:
                lines.append("- %s" % SIGNED_SKIP_NOTE)
                lines.append("- No scrubbed copy was produced for this file.")
            else:
                removed = len(found)
                recheck = info["recheck"]["findings"] if info["recheck"] \
                    else []
                lines.append("- Removed: %d item(s)" % removed)
                lines.append("- Recheck: %d target item(s) remaining"
                             % len(recheck))
                for f in recheck:
                    lines.append("  - still present: [%s] %s"
                                 % (f.category, f.field))
                for key, val in sorted(info["verify"].items()):
                    lines.append("- Verify %s: %s"
                                 % (key, "OK" if val else "FAILED"))
                lines.append("- Scrubbed copy: %s" % info["output"])
        lines.append("")
    lines.append("100% local — nothing was uploaded. Original files were "
                 "never modified; scrubbed copies are separate files.")
    lines.append("Note: a scrubbed file is not legally certified or "
                 "compliant with any standard; signed PDFs are detected "
                 "by signature-field/marker detection and skipped, not "
                 "cryptographically validated.")
    return "\n".join(lines) + "\n"


def main(argv):
    if len(argv) < 3 or argv[1] not in ("scan", "scrub"):
        print("Usage: metascrub.py scan <folder> | "
              "metascrub.py scrub <folder> --out <dir>")
        return 2
    folder = argv[2]
    if argv[1] == "scan":
        print(render_report(run_scan(folder)))
        return 0
    if "--out" not in argv:
        print("scrub requires --out <dir>")
        return 2
    outdir = argv[argv.index("--out") + 1]
    print(render_report(run_scrub(folder, outdir)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
