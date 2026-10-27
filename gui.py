#!/usr/bin/env python3
"""MetaScrub desktop shell (tkinter). Pick a folder -> scan for hidden
metadata, or scrub: write cleaned copies to a new folder (originals are
never modified) and a find -> remove -> verify-zero report.

Digitally signed PDFs are detected and skipped, never scrubbed."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metascrub import run_scan, run_scrub, SIGNED_SKIP_NOTE


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MetaScrub — Metadata Audit & Scrub "
                   "(Originals Never Modified)")
        self.geometry("780x600")
        self.folder = tk.StringVar()
        tk.Label(self, text="Folder of photos, Office files (docx/xlsx/"
                            "pptx) and PDFs to audit:").pack(
            anchor="w", padx=12, pady=(12, 2))
        row = tk.Frame(self)
        row.pack(fill="x", padx=12)
        tk.Entry(row, textvariable=self.folder).pack(side="left", fill="x",
                                                     expand=True)
        tk.Button(row, text="Browse…", command=self.pick).pack(side="left",
                                                               padx=6)
        btns = tk.Frame(self)
        btns.pack(pady=12)
        self.btn_scan = tk.Button(btns, text="Scan Only — Report, "
                                            "Write Nothing",
                                  command=lambda: self.run(False), height=2)
        self.btn_scan.pack(side="left", padx=6)
        self.btn_fix = tk.Button(btns, text="Scrub — Clean, Verify & "
                                            "Report",
                                 command=lambda: self.run(True), height=2)
        self.btn_fix.pack(side="left", padx=6)
        self.log = scrolledtext.ScrolledText(self, wrap="word")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.write(
            "MetaScrub finds the hidden data inside your files before you "
            "send them out: GPS coordinates and camera serial numbers in "
            "photos, author/company/revision history in Office documents, "
            "author/producer data and XMP metadata in PDFs — then removes "
            "it and re-checks the cleaned copies until the report reads "
            "zero.\n"
            "SAFETY PROMISE: your original files are never modified — "
            "scrubbed copies go to a new folder, and the report shows a "
            "per-file find -> remove -> verify-zero triple. Photos keep "
            "their exact pixels; documents keep their exact text.\n"
            "Digitally signed PDFs are detected and skipped, never "
            "scrubbed, because changing the file would break the "
            "signature.\n"
            "Everything runs locally — your files never leave this "
            "computer.\n")

    def write(self, s):
        self.log.insert("end", s)
        self.log.see("end")

    def pick(self):
        p = filedialog.askdirectory()
        if p:
            self.folder.set(p)

    def run(self, scrub):
        path = self.folder.get().strip()
        if not path or not os.path.isdir(path):
            messagebox.showerror("MetaScrub", "Choose a folder first.")
            return
        self.btn_scan.config(state="disabled")
        self.btn_fix.config(state="disabled")
        threading.Thread(target=self._work, args=(path, scrub),
                         daemon=True).start()

    def _work(self, path, scrub):
        try:
            if scrub:
                outdir = os.path.join(
                    os.path.dirname(os.path.abspath(path.rstrip("/\\"))),
                    os.path.basename(os.path.abspath(path.rstrip("/\\")))
                    + "_metascrubbed")
                s = run_scrub(path, outdir)
                for f in s["files"]:
                    if f["kind"] == "unsupported":
                        self.write("\n%s: unsupported — left untouched."
                                   % f["name"])
                        continue
                    if f.get("status") == SIGNED_SKIP_NOTE:
                        self.write("\n%s: %s." % (f["name"],
                                                  SIGNED_SKIP_NOTE))
                        continue
                    re_n = len(f["recheck"]["findings"])
                    ver = ", ".join(
                        "%s: %s" % (k, "OK" if v else "FAILED")
                        for k, v in sorted(f["verify"].items()))
                    self.write(
                        "\n%s: found %d -> removed %d -> recheck %d "
                        "remaining. %s\n  Cleaned copy: %s"
                        % (f["name"], len(f["findings"]), len(f["findings"]),
                           re_n, ver, f["output"]))
                self.write("\n\nDone. Cleaned copies in: %s\n"
                           "Your original files were not touched.\n"
                           % outdir)
            else:
                s = run_scan(path)
                total = sum(len(f["findings"]) for f in s["files"])
                for f in s["files"]:
                    if f["kind"] == "unsupported":
                        continue
                    note = (" — SIGNED, would be skipped"
                            if f["signed"] else "")
                    self.write("\n%s: %d hidden item(s)%s"
                               % (f["name"], len(f["findings"]), note))
                    for item in f["findings"]:
                        self.write("\n  - [%s] %s: %s"
                                   % (item.category, item.field,
                                      item.preview))
                self.write("\n\nScan done. %d hidden item(s) across %d "
                           "file(s).\nScan only — nothing was written.\n"
                           % (total, len(s["files"])))
        except Exception as e:  # surface, never crash silently
            self.write("\nError: %s\n" % e)
        finally:
            self.btn_scan.config(state="normal")
            self.btn_fix.config(state="normal")


if __name__ == "__main__":
    App().mainloop()
