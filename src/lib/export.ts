import { jsPDF } from "jspdf";
import type { Note, NoteSections } from "./store";

const SECTION_ORDER: { key: keyof NoteSections; label: string }[] = [
  { key: "chiefComplaint", label: "Chief Complaint" },
  { key: "hpi", label: "History of Present Illness" },
  { key: "examination", label: "Examination Findings" },
  { key: "diagnosis", label: "Diagnosis" },
  { key: "treatment", label: "Treatment / Plan" },
  { key: "followUp", label: "Follow-up" },
];

function safeFile(name: string) {
  return name.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "");
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 500);
}

export function exportMarkdown(note: Note, signedByName?: string) {
  const date = new Date(note.signedAt ?? note.consultTime).toLocaleString();
  const signerLabel = signedByName ?? "Dr. Raman";
  const lines: string[] = [];
  lines.push(`# ${note.type} — ${note.patientName}`);
  lines.push("");
  lines.push(`**MRN:** ${note.mrn}  `);
  lines.push(`**Consultation Date:** ${date}  `);
  lines.push(`**Status:** ${note.status}${note.status === "signed" ? ` (Approved & Locked by ${signerLabel})` : ""}`);
  lines.push("");
  
  if (note.icd10Codes && note.icd10Codes.length > 0) {
    lines.push("### Attached ICD-10 Disease Codes");
    for (const c of note.icd10Codes) {
      lines.push(`- **${c.code}**: ${c.title} (${c.category})`);
    }
    lines.push("");
  }

  if (note.prescriptions && note.prescriptions.length > 0) {
    lines.push("### Prescribed Medications & Rx");
    for (const rx of note.prescriptions) {
      lines.push(`- **${rx.name}** (${rx.brand || "Generic"}) — ${rx.dosage}, ${rx.frequency}, ${rx.route}, ${rx.duration}`);
    }
    lines.push("");
  }

  lines.push("---");
  lines.push("");
  for (const { key, label } of SECTION_ORDER) {
    lines.push(`## ${label}`);
    lines.push("");
    lines.push(note.sections[key] || "None recorded");
    lines.push("");
  }
  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  triggerDownload(blob, `${safeFile(note.patientName)}_${safeFile(note.type)}.md`);
}

export function exportPdf(note: Note, signedByName?: string) {
  const signerLabel = signedByName ?? "Dr. Raman";
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 50;
  const contentW = pageW - margin * 2;
  let y = margin;

  const ensureSpace = (needed: number) => {
    if (y + needed > pageH - margin - 30) {
      doc.addPage();
      y = margin;
    }
  };

  // Header Banner
  doc.setFillColor(245, 247, 250);
  doc.rect(margin, y, contentW, 40, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(14);
  doc.setTextColor(30, 41, 59);
  doc.text("VERIFACT CLINICAL DISCHARGE SUMMARY", margin + 12, y + 25);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(100, 116, 139);
  doc.text("100% LOCAL & DPDP COMPLIANT", pageW - margin - 140, y + 25);
  y += 55;

  // Metadata Table Box
  doc.setDrawColor(226, 232, 240);
  doc.rect(margin, y, contentW, 55);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(30, 41, 59);
  doc.text(`Patient Name: ${note.patientName}`, margin + 12, y + 20);
  doc.text(`MRN: ${note.mrn}`, margin + 250, y + 20);

  const dateStr = new Date(note.signedAt ?? note.consultTime).toLocaleDateString([], {
    year: "numeric", month: "short", day: "numeric"
  });
  doc.setFont("helvetica", "normal");
  doc.text(`Consult Type: ${note.type}`, margin + 12, y + 40);
  doc.text(`Date: ${dateStr}`, margin + 250, y + 40);
  y += 70;

  // ICD-10 Section
  if (note.icd10Codes && note.icd10Codes.length > 0) {
    ensureSpace(35);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.setTextColor(15, 23, 42);
    doc.setFillColor(241, 245, 249);
    doc.rect(margin, y, contentW, 18, "F");
    doc.text("ATTACHED ICD-10 CODES", margin + 8, y + 13);
    y += 24;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(51, 65, 85);
    for (const c of note.icd10Codes) {
      const lineStr = `${c.code} - ${c.title} (${c.category})`;
      const wrapped = doc.splitTextToSize(lineStr, contentW - 16);
      for (const line of wrapped) {
        ensureSpace(14);
        doc.text(line, margin + 8, y);
        y += 14;
      }
    }
    y += 10;
  }

  // Prescriptions Section
  if (note.prescriptions && note.prescriptions.length > 0) {
    ensureSpace(35);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.setTextColor(15, 23, 42);
    doc.setFillColor(241, 245, 249);
    doc.rect(margin, y, contentW, 18, "F");
    doc.text("PRESCRIBED MEDICATIONS & RX", margin + 8, y + 13);
    y += 24;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(51, 65, 85);
    for (const rx of note.prescriptions) {
      const lineStr = `${rx.name} (${rx.brand || "Generic"}) - ${rx.dosage}, ${rx.frequency}, ${rx.route}, ${rx.duration}`;
      const wrapped = doc.splitTextToSize(lineStr, contentW - 16);
      for (const line of wrapped) {
        ensureSpace(14);
        doc.text(line, margin + 8, y);
        y += 14;
      }
    }
    y += 10;
  }

  // Sections
  for (const { key, label } of SECTION_ORDER) {
    const textVal = note.sections[key] || "No findings reported.";
    const paragraphs = textVal.split("\n");

    ensureSpace(35);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.setTextColor(15, 23, 42);
    doc.setFillColor(241, 245, 249);
    doc.rect(margin, y, contentW, 18, "F");
    doc.text(label.toUpperCase(), margin + 8, y + 13);
    y += 24;

    doc.setFont("times", "normal");
    doc.setFontSize(11);
    doc.setTextColor(51, 65, 85);

    for (const para of paragraphs) {
      const wrapped = doc.splitTextToSize(para || " ", contentW - 16);
      for (const line of wrapped) {
        ensureSpace(14);
        doc.text(line, margin + 8, y);
        y += 14;
      }
    }
    y += 10;
  }

  // Sign-off Block
  ensureSpace(50);
  y += 10;
  doc.setDrawColor(203, 213, 225);
  doc.line(margin, y, pageW - margin, y);
  y += 20;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(30, 41, 59);
  doc.text(`Attending Clinician: ${signerLabel}`, margin, y);

  if (note.status === "signed") {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(16, 185, 129);
    doc.text(`[APPROVED & LOCKED] - Time-to-Review: ${note.reviewSeconds ?? 0}s`, margin + 250, y);
  }
  y += 30;

  // Footer on every page
  const pageCount = doc.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(148, 163, 184);
    doc.text(
      `Verifact Local · DPDP Compliant · Page ${i} of ${pageCount}`,
      margin,
      pageH - 20,
    );
  }

  doc.save(`${safeFile(note.patientName)}_${safeFile(note.type)}.pdf`);
}
