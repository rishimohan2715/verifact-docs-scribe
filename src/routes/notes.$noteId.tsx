import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { TopBar } from "@/components/app-shell";
import { ensureSeeded } from "@/lib/mock-data";
import {
  useStore,
  editSection,
  editTranscriptLine,
  signNote,
  updateNote,
  fetchAndUpsertConsultation,
  addIcd10Code,
  removeIcd10Code,
  addSnomedCode,
  removeSnomedCode,
  addPrescription,
  removePrescription,
  type NoteSections,
  type TranscriptLine,
  type ICD10Code,
  type SnomedCode,
  type Prescription,
  type ClinicalRiskAnalysis,
  type DifferentialPinpoint,
} from "@/lib/store";
import { useAuth } from "@/lib/auth";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { exportMarkdown, exportPdf } from "@/lib/export";
import {
  ChevronDown,
  ChevronRight,
  Lock,
  Play,
  Check,
  Download,
  FileText,
  FileType,
  Edit3,
  Stethoscope,
  User,
  Sparkles,
  ArrowLeftRight,
  Pill,
  Tag,
  Plus,
  X,
  Search,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Award,
  Info,
  Activity,
  FlameKindling,
  Microscope,
  UserCheck,
  ActivitySquare,
} from "lucide-react";

export const Route = createFileRoute("/notes/$noteId")({
  head: () => ({
    meta: [
      { title: "Review & Sign-Off — Verifact Local" },
      {
        name: "description",
        content:
          "Review note, clinical risk alerts, differentials, ICD-10, and prescriptions, edit inline, then sign off.",
      },
    ],
  }),
  component: ReviewScreen,
});

const SECTIONS: { key: keyof NoteSections; label: string }[] = [
  { key: "chiefComplaint", label: "Chief Complaint" },
  { key: "hpi", label: "History of Present Illness" },
  { key: "examination", label: "Examination Findings" },
  { key: "diagnosis", label: "Diagnosis" },
  { key: "treatment", label: "Treatment / Plan" },
  { key: "followUp", label: "Follow-up" },
];

function fmt(s: number) {
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}m ${r}s`;
}

function ReviewScreen() {
  const { noteId } = Route.useParams();
  const { doctor } = useAuth();
  const doctorName = doctor?.displayName ?? "Dr. Raman";

  const [clinicalRisks, setClinicalRisks] = useState<ClinicalRiskAnalysis | null>(null);
  const [differentials, setDifferentials] = useState<DifferentialPinpoint[]>([]);
  const [patientMeta, setPatientMeta] = useState<{ age?: number; pmh?: string }>({});

  useEffect(() => {
    ensureSeeded();
    fetchAndUpsertConsultation(noteId);

    // Fetch clinical decision support and differential pinpoint analysis
    fetch(`http://localhost:8000/api/consultations/${noteId}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.clinicalRiskAnalysis) {
          setClinicalRisks(data.clinicalRiskAnalysis);
        }
        if (data.differentialPinpoints) {
          setDifferentials(data.differentialPinpoints);
        }
        if (data.age || data.pmh) {
          setPatientMeta({ age: data.age, pmh: data.pmh });
        }
      })
      .catch(() => {});
  }, [noteId]);

  const note = useStore((s) => s.notes.find((n) => n.id === noteId));
  const [transcriptOpen, setTranscriptOpen] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [showIcd10Modal, setShowIcd10Modal] = useState(false);
  const [showSnomedModal, setShowSnomedModal] = useState(false);
  const [showRxModal, setShowRxModal] = useState(false);
  const startRef = useRef<number>(Date.now());
  const finalRef = useRef<number | null>(null);

  useEffect(() => {
    startRef.current = Date.now();
    finalRef.current = null;
    setElapsed(0);
    const t = setInterval(() => {
      if (finalRef.current !== null) return;
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(t);
  }, [noteId]);

  if (!note) {
    return (
      <>
        <TopBar title="Consultation Note" />
        <div className="p-8 text-sm text-muted-foreground">
          Loading local consultation...{" "}
          <Link to="/" className="text-accent underline">
            Back to Dashboard
          </Link>
          .
        </div>
      </>
    );
  }

  const isSigned = note.status === "signed";

  function statusPill() {
    const s = note!.status;
    const map = {
      draft: "bg-muted text-muted-foreground border-border",
      pending: "bg-accent/10 text-accent border-accent/30",
      signed: "bg-primary/5 text-primary border-primary/20",
    } as const;
    const label = { draft: "Draft", pending: "Pending Review", signed: "Signed & Locked" }[s];
    return (
      <span
        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${map[s]}`}
      >
        {s === "signed" && <Check className="h-3 w-3" />}
        {label}
      </span>
    );
  }

  async function handleSign() {
    finalRef.current = elapsed;
    await signNote(note!.id, elapsed);
    toast.success("Note Approved & Locked! Review duration saved to local database.");
  }

  async function handleRegenerateNote() {
    setIsRegenerating(true);
    toast.info("Regenerating clinical report with local LLM...");
    try {
      const res = await fetch("http://localhost:8000/api/generate-note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consultation_id: note!.id }),
      });
      if (res.ok) {
        const data = await res.json();
        updateNote(note!.id, (n) => ({
          ...n,
          sections: data.sections,
          icd10Codes: data.icd10_codes || n.icd10Codes,
          snomedCodes: data.snomed_codes || n.snomedCodes,
          prescriptions: data.prescriptions || n.prescriptions,
          editsCount: n.editsCount + 1,
          generationStatus: data.generationStatus,
          llmModel: data.llm_model,
        }));
        if (data.clinical_risk_analysis) setClinicalRisks(data.clinical_risk_analysis);
        if (data.differential_pinpoints) setDifferentials(data.differential_pinpoints);
        if (data.generationStatus === "success") {
          toast.success(`Report regenerated using local ${data.llm_model || "LLM"}!`);
        } else {
          toast.warning(
            "Local AI model was unavailable — report was auto-extracted from the transcript instead. Every section needs review.",
          );
        }
      } else {
        const detail = await res.text().catch(() => "");
        throw new Error(
          `Local backend returned ${res.status}${detail ? `: ${detail.slice(0, 200)}` : ""}`,
        );
      }
    } catch (err) {
      console.error("Regeneration failed:", err);
      toast.error(
        err instanceof Error
          ? `Regeneration failed: ${err.message}`
          : "Regeneration failed — the report was not changed.",
      );
    } finally {
      setIsRegenerating(false);
    }
  }

  function swapAllSpeakers() {
    if (isSigned) return;
    updateNote(note!.id, (n) => ({
      ...n,
      transcript: n.transcript.map((line) => ({
        ...line,
        speaker: line.speaker === "DOCTOR" ? "PATIENT" : "DOCTOR",
      })),
    }));
    toast.info("Swapped speaker labels for all segments.");
  }

  return (
    <>
      <TopBar title={`${note.patientName} · ${note.mrn}`} extras={statusPill()} />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* LEFT: Diarized Transcript View */}
        <section
          className={`flex shrink-0 flex-col border-r border-border bg-card/50 transition-all duration-300 ${
            transcriptOpen ? "w-[42%]" : "w-14"
          }`}
        >
          <header className="flex h-12 items-center justify-between border-b border-border px-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setTranscriptOpen((v) => !v)}
                className="grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-muted"
                aria-label="Toggle transcript"
              >
                {transcriptOpen ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </button>
              {transcriptOpen && (
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Local Diarized Transcript
                </span>
              )}
            </div>

            {transcriptOpen && !isSigned && (
              <div className="flex items-center gap-1">
                <button
                  onClick={swapAllSpeakers}
                  className="inline-flex items-center gap-1 rounded bg-muted/60 px-2 py-1 text-[10px] font-medium text-foreground hover:bg-muted"
                  title="Swap Doctor and Patient labels for all lines"
                >
                  <ArrowLeftRight className="h-3 w-3" /> Swap Roles
                </button>
              </div>
            )}
          </header>

          {transcriptOpen && (
            <>
              <div className="border-b border-border p-3 bg-muted/20">
                <div className="flex items-center gap-2">
                  <button className="grid h-7 w-7 place-items-center rounded-full bg-accent text-accent-foreground">
                    <Play className="h-3 w-3 fill-current" />
                  </button>
                  <div className="flex h-8 flex-1 items-center gap-[2px] overflow-hidden rounded bg-muted/60 px-1">
                    {Array.from({ length: 70 }).map((_, i) => (
                      <span
                        key={i}
                        className="w-[3px] shrink-0 rounded-full bg-accent/50"
                        style={{ height: `${8 + ((i * 13) % 22)}px` }}
                      />
                    ))}
                  </div>
                  <span className="text-xs tabular-nums text-muted-foreground">Local Audio</span>
                </div>
              </div>

              {/* Speaker-separated Transcript list */}
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                <ul className="space-y-3">
                  {note.transcript.map((line, i) => (
                    <TranscriptBlock
                      key={i}
                      index={i}
                      line={line}
                      locked={isSigned}
                      onUpdate={(speaker, text) => editTranscriptLine(note.id, i, speaker, text)}
                    />
                  ))}
                </ul>
              </div>
            </>
          )}
        </section>

        {/* RIGHT: Structured Note Editor + Clinical Risk Alerts + Differential Diagnosis + ICD-10 & Rx */}
        <section className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-12 shrink-0 items-center justify-between border-b border-border px-6">
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {note.type}
              </span>
              <span className="text-xs text-muted-foreground">·</span>
              <span className="text-xs text-muted-foreground">
                Consultation{" "}
                {new Date(note.consultTime).toLocaleString([], {
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </span>
            </div>
            <div className="flex items-center gap-3">
              {!isSigned && (
                <button
                  onClick={handleRegenerateNote}
                  disabled={isRegenerating}
                  className="inline-flex items-center gap-1.5 rounded-md border border-accent/40 bg-accent/10 px-2.5 py-1.5 text-xs font-semibold text-accent hover:bg-accent/20 transition disabled:opacity-50"
                >
                  <Sparkles className={`h-3.5 w-3.5 ${isRegenerating ? "animate-spin" : ""}`} />
                  {isRegenerating ? "Generating..." : "Regenerate Report"}
                </button>
              )}

              <DropdownMenu>
                <DropdownMenuTrigger className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-muted">
                  <Download className="h-3.5 w-3.5" /> Export
                  <ChevronDown className="h-3 w-3" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52">
                  <DropdownMenuItem
                    onSelect={() => {
                      exportPdf(note, doctorName);
                      toast.success("Clinical PDF downloaded");
                    }}
                  >
                    <FileType className="mr-2 h-4 w-4" /> Download Clinical PDF
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={() => {
                      exportMarkdown(note, doctorName);
                      toast.success("Markdown downloaded");
                    }}
                  >
                    <FileText className="mr-2 h-4 w-4" /> Download Markdown
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto max-w-3xl px-8 py-8">
              {/* PATIENT DEMOGRAPHICS & PMH BANNER */}
              <div className="mb-6 border-b border-border pb-4 font-serif">
                <div className="flex items-center justify-between">
                  <h2 className="text-3xl leading-tight text-foreground">{note.patientName}</h2>
                  <span className="font-mono text-xs font-bold text-accent bg-accent/10 px-3 py-1 rounded-full">
                    {note.mrn}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-4 font-sans text-xs text-muted-foreground">
                  <span>{note.type}</span>
                  <span>·</span>
                  {patientMeta.age && (
                    <span>
                      Age: <strong>{patientMeta.age} yrs</strong>
                    </span>
                  )}
                  {patientMeta.pmh && (
                    <>
                      <span>·</span>
                      <span className="flex items-center gap-1 text-foreground">
                        <ActivitySquare className="h-3.5 w-3.5 text-accent" />
                        Prior Illnesses (PMH): <strong>{patientMeta.pmh}</strong>
                      </span>
                    </>
                  )}
                </div>
              </div>

              {/* PROVENANCE BANNER: only shown when the note was NOT LLM-generated */}
              {note.generationStatus && note.generationStatus !== "success" && (
                <div className="mb-6 flex items-start gap-2.5 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3.5 text-xs">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
                  <div className="text-amber-900 dark:text-amber-200">
                    <strong>Auto-extracted note — not written by the local AI model.</strong>{" "}
                    {note.generationStatus === "extracted_fallback"
                      ? "The local Ollama model was unavailable when this note was generated, so every section below was pulled directly from the transcript's own sentences. Diagnosis, treatment, and follow-up were intentionally left blank for the clinician to complete."
                      : "This is a synthetic demo case generated for testing — sections were extracted directly from the scripted transcript, not drafted by the AI model."}
                  </div>
                </div>
              )}

              {/* CLINICAL DECISION SUPPORT & RISK ALERTS BANNER */}
              <div className="mb-8 rounded-xl border border-amber-500/30 bg-amber-500/5 p-5 shadow-sm">
                <div className="flex items-center justify-between border-b border-amber-500/20 pb-3 mb-3">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-amber-900 dark:text-amber-200">
                      Clinical Risk Detection & Decision Support
                    </h3>
                  </div>
                  {clinicalRisks ? (
                    <span className="inline-flex items-center gap-1 rounded bg-amber-500/20 px-2.5 py-1 text-xs font-bold text-amber-800 dark:text-amber-300">
                      <Award className="h-3.5 w-3.5" /> Score: {clinicalRisks.qualityScore ?? 0}/100
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded bg-muted px-2.5 py-1 text-xs font-bold text-muted-foreground">
                      Not analysed
                    </span>
                  )}
                </div>

                {clinicalRisks?.alerts && clinicalRisks.alerts.length > 0 ? (
                  <div className="space-y-3">
                    {clinicalRisks.alerts.map((alert, idx) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-amber-500/20 bg-background/80 p-3 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-foreground flex items-center gap-1.5">
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                            {alert.title}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              alert.severity === "HIGH"
                                ? "bg-red-500/10 text-red-600"
                                : alert.severity === "MEDIUM"
                                  ? "bg-amber-500/10 text-amber-600"
                                  : "bg-blue-500/10 text-blue-600"
                            }`}
                          >
                            {alert.severity} RISK
                          </span>
                        </div>
                        <p className="mt-1 text-muted-foreground">{alert.description}</p>
                        <div className="mt-2 text-foreground font-medium bg-amber-500/10 p-2 rounded">
                          💡 <strong>Recommended Action:</strong> {alert.recommendedAction}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : clinicalRisks ? (
                  <div className="text-xs text-muted-foreground flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    <span>
                      No urgent clinical red flags detected. Transcript matches standard clinical
                      documentation parameters.
                    </span>
                  </div>
                ) : (
                  <div className="text-xs text-muted-foreground flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>
                      Clinical risk analysis did not run for this note — the local backend returned
                      no analysis. Absence of alerts here does <strong>not</strong> mean the
                      consultation is low risk.
                    </span>
                  </div>
                )}
              </div>

              {/* DIFFERENTIAL DIAGNOSIS & PATHOPHYSIOLOGY PINPOINT */}
              {differentials && differentials.length > 0 && (
                <div className="mb-8 rounded-xl border border-border bg-card p-5 shadow-sm">
                  <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
                    <div className="flex items-center gap-2">
                      <Activity className="h-4 w-4 text-accent animate-pulse" />
                      <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                        AI Clinical Pinpoint & Pathophysiology Analysis
                      </h3>
                    </div>
                    <span className="rounded bg-accent/10 px-2 py-0.5 text-[9px] font-bold uppercase text-accent">
                      Evidence-Grounded Insights
                    </span>
                  </div>

                  <div className="space-y-4">
                    {differentials.map((diff, idx) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-border bg-background p-4 text-xs"
                      >
                        <div className="flex items-center justify-between border-b border-border pb-2 mb-2.5">
                          <div className="flex items-center gap-1.5">
                            <span className="rounded bg-accent/15 px-2 py-0.5 font-bold text-accent font-mono text-[10px]">
                              {diff.icd10}
                            </span>
                            <span className="font-semibold text-foreground text-sm">
                              {diff.diagnosis}
                            </span>
                          </div>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              diff.severity === "CRITICAL" || diff.severity === "HIGH"
                                ? "bg-red-500/10 text-red-600"
                                : diff.severity === "MEDIUM"
                                  ? "bg-amber-500/10 text-amber-600"
                                  : "bg-blue-500/10 text-blue-600"
                            }`}
                          >
                            {diff.severity}
                          </span>
                        </div>

                        {/* Pathophysiology */}
                        <div className="mb-3">
                          <div className="font-bold text-muted-foreground flex items-center gap-1 mb-1">
                            <Info className="h-3.5 w-3.5 text-accent" /> Pathophysiology Mechanism:
                          </div>
                          <p className="text-foreground leading-relaxed pl-4 border-l border-accent/20">
                            {diff.pathophysiology}
                          </p>
                        </div>

                        {/* Evidence Quotes */}
                        <div className="mb-3">
                          <div className="font-bold text-muted-foreground flex items-center gap-1 mb-1">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> Supporting
                            Dialogue Evidence:
                          </div>
                          <ul className="list-disc pl-5 space-y-1 text-muted-foreground italic">
                            {diff.evidence.map((quote: string, qIdx: number) => (
                              <li key={qIdx}>"{quote}"</li>
                            ))}
                          </ul>
                        </div>

                        {/* Confirmatory Tests */}
                        <div>
                          <div className="font-bold text-muted-foreground flex items-center gap-1 mb-1">
                            <Microscope className="h-3.5 w-3.5 text-blue-500" /> Suggested
                            Confirmatory Tests:
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1.5 pl-1">
                            {diff.confirmatoryTests.map((test: string, tIdx: number) => (
                              <div
                                key={tIdx}
                                className="rounded bg-muted/50 p-2 text-foreground flex items-start gap-1"
                              >
                                <span className="text-accent font-bold">&middot;</span>
                                <span>{test}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ICD-10 DISEASE CODES SECTION */}
              <div className="mb-8 rounded-xl border border-border bg-card p-5 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Tag className="h-4 w-4 text-accent" />
                    <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Attached ICD-10 Disease Codes
                    </h3>
                  </div>
                  {!isSigned && (
                    <button
                      onClick={() => setShowIcd10Modal(true)}
                      className="inline-flex items-center gap-1 rounded bg-accent/10 px-2 py-1 text-xs font-semibold text-accent hover:bg-accent/20"
                    >
                      <Plus className="h-3 w-3" /> Add Code
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {note.icd10Codes && note.icd10Codes.length > 0 ? (
                    note.icd10Codes.map((c) => (
                      <span
                        key={c.code}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent/5 px-2.5 py-1.5 text-xs font-medium text-foreground"
                      >
                        <span className="font-mono font-bold text-accent">{c.code}</span>
                        <span>·</span>
                        <span>{c.title}</span>
                        {!isSigned && (
                          <button
                            onClick={() => removeIcd10Code(note.id, c.code)}
                            className="ml-1 text-muted-foreground hover:text-destructive"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </span>
                    ))
                  ) : (
                    <p className="text-xs text-muted-foreground">No ICD-10 codes attached yet.</p>
                  )}
                </div>
              </div>

              {/* SNOMED CT CODES SECTION */}
              <div className="mb-8 rounded-xl border border-border bg-card p-5 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Tag className="h-4 w-4 text-accent" />
                    <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Attached SNOMED CT Codes
                    </h3>
                  </div>
                  {!isSigned && (
                    <button
                      onClick={() => setShowSnomedModal(true)}
                      className="inline-flex items-center gap-1 rounded bg-accent/10 px-2 py-1 text-xs font-semibold text-accent hover:bg-accent/20"
                    >
                      <Plus className="h-3 w-3" /> Add Code
                    </button>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {note.snomedCodes && note.snomedCodes.length > 0 ? (
                    note.snomedCodes.map((c) => (
                      <span
                        key={c.conceptId}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent/5 px-2.5 py-1.5 text-xs font-medium text-foreground"
                      >
                        <span className="font-mono font-bold text-accent">{c.conceptId}</span>
                        <span>·</span>
                        <span>{c.term}</span>
                        {c.icd10Map && (
                          <span className="text-muted-foreground">(ICD-10: {c.icd10Map})</span>
                        )}
                        {!isSigned && (
                          <button
                            onClick={() => removeSnomedCode(note.id, c.conceptId)}
                            className="ml-1 text-muted-foreground hover:text-destructive"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </span>
                    ))
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      No SNOMED CT codes attached yet.
                    </p>
                  )}
                </div>
              </div>

              {/* PRESCRIPTION BUILDER SECTION */}
              <div className="mb-8 rounded-xl border border-border bg-card p-5 shadow-sm">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Pill className="h-4 w-4 text-accent" />
                    <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Prescribed Medications & Rx
                    </h3>
                  </div>
                  {!isSigned && (
                    <button
                      onClick={() => setShowRxModal(true)}
                      className="inline-flex items-center gap-1 rounded bg-accent/10 px-2 py-1 text-xs font-semibold text-accent hover:bg-accent/20"
                    >
                      <Plus className="h-3 w-3" /> Add Medication
                    </button>
                  )}
                </div>

                <div className="divide-y divide-border border rounded-lg overflow-hidden bg-background">
                  {note.prescriptions && note.prescriptions.length > 0 ? (
                    note.prescriptions.map((rx, idx) => (
                      <div
                        key={rx.id || idx}
                        className="flex items-center justify-between p-3 text-xs"
                      >
                        <div>
                          <div className="font-semibold text-foreground text-sm">
                            {rx.name}{" "}
                            <span className="text-muted-foreground font-normal">
                              ({rx.brand || "Generic"})
                            </span>
                          </div>
                          <div className="mt-1 flex gap-3 text-muted-foreground">
                            <span>
                              Dose: <strong>{rx.dosage}</strong>
                            </span>
                            <span>
                              Freq: <strong>{rx.frequency}</strong>
                            </span>
                            <span>
                              Route: <strong>{rx.route}</strong>
                            </span>
                            <span>
                              Duration: <strong>{rx.duration}</strong>
                            </span>
                          </div>
                        </div>
                        {!isSigned && (
                          <button
                            onClick={() => removePrescription(note.id, rx.id || `rx-${idx}`)}
                            className="text-muted-foreground hover:text-destructive p-1"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="p-4 text-xs text-muted-foreground text-center">
                      No prescriptions added yet. Click 'Add Medication' to prescribe.
                    </div>
                  )}
                </div>
              </div>

              {/* 6 STRUCTURED SECTIONS */}
              {SECTIONS.map(({ key, label }) => (
                <SectionBlock
                  key={key}
                  label={label}
                  value={note.sections[key]}
                  edited={!!note.editedFields[key]}
                  locked={isSigned}
                  onChange={(v) => editSection(note.id, key, v)}
                />
              ))}
            </div>
          </div>

          {/* STICKY ACTION BAR */}
          <footer className="shrink-0 border-t border-border bg-card px-6 py-3 shadow-lg">
            {isSigned ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm">
                  <Lock className="h-4 w-4 text-accent" />
                  <span className="text-foreground">
                    Reviewed & Signed in{" "}
                    <span className="tabular-nums font-semibold">
                      {fmt(note.reviewSeconds ?? 0)}
                    </span>
                  </span>
                  <span className="text-muted-foreground">·</span>
                  <span className="text-muted-foreground">Clinician: {doctorName}</span>
                </div>
                <button
                  onClick={() => {
                    if (window.confirm("Unlock this signed note for editing?")) {
                      updateNote(note!.id, (n) => ({ ...n, status: "pending" }));
                      finalRef.current = null;
                      startRef.current = Date.now();
                      setElapsed(0);
                      toast.success("Note unlocked for editing");
                    }
                  }}
                  className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
                >
                  Request Unlock
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm text-muted-foreground">
                  Time-to-Review:{" "}
                  <span className="tabular-nums font-semibold text-foreground">{fmt(elapsed)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toast.success("Draft saved to local SQLite database")}
                    className="rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
                  >
                    Save Draft
                  </button>
                  <button
                    onClick={handleSign}
                    className="inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-accent-foreground shadow-md hover:opacity-90 transition"
                  >
                    <Check className="h-4 w-4" /> Approve & Lock Note
                  </button>
                </div>
              </div>
            )}
          </footer>
        </section>
      </div>

      {/* ICD-10 SEARCH MODAL */}
      {showIcd10Modal && (
        <Icd10SearchModal
          onClose={() => setShowIcd10Modal(false)}
          onSelect={(c) => {
            addIcd10Code(note.id, c);
            setShowIcd10Modal(false);
            toast.success(`Attached ICD-10: ${c.code} - ${c.title}`);
          }}
        />
      )}

      {/* SNOMED CT SEARCH MODAL */}
      {showSnomedModal && (
        <SnomedSearchModal
          onClose={() => setShowSnomedModal(false)}
          onSelect={(c) => {
            addSnomedCode(note.id, c);
            setShowSnomedModal(false);
            toast.success(`Attached SNOMED CT: ${c.conceptId} - ${c.term}`);
          }}
        />
      )}

      {/* PRESCRIPTION MODAL */}
      {showRxModal && (
        <PrescriptionModal
          onClose={() => setShowRxModal(false)}
          onAdd={(rx) => {
            addPrescription(note.id, rx);
            setShowRxModal(false);
            toast.success(`Prescribed: ${rx.name} ${rx.dosage}`);
          }}
        />
      )}
    </>
  );
}

function TranscriptBlock({
  index,
  line,
  locked,
  onUpdate,
}: {
  index: number;
  line: TranscriptLine;
  locked: boolean;
  onUpdate: (speaker: "DOCTOR" | "PATIENT", text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(line.text);

  useEffect(() => {
    setText(line.text);
  }, [line.text]);

  const toggleSpeaker = () => {
    if (locked) return;
    const newSpeaker = line.speaker === "DOCTOR" ? "PATIENT" : "DOCTOR";
    onUpdate(newSpeaker, text);
  };

  return (
    <li
      className={`group rounded-lg border-l-4 p-3 transition ${
        line.speaker === "DOCTOR"
          ? "border-accent bg-accent/5"
          : "border-emerald-500 bg-emerald-500/5"
      }`}
    >
      <div className="mb-1 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={toggleSpeaker}
            disabled={locked}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition ${
              line.speaker === "DOCTOR"
                ? "bg-accent/20 text-accent hover:bg-accent/30"
                : "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/30"
            }`}
            title="Click to toggle speaker between DOCTOR and PATIENT"
          >
            {line.speaker === "DOCTOR" ? (
              <Stethoscope className="h-3 w-3" />
            ) : (
              <User className="h-3 w-3" />
            )}
            {line.speaker}
          </button>
          <span className="text-[10px] tabular-nums text-muted-foreground opacity-70">
            {line.time}
          </span>
        </div>

        {!locked && !editing && (
          <button
            onClick={() => setEditing(true)}
            className="opacity-0 group-hover:opacity-100 text-[10px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            <Edit3 className="h-3 w-3" /> Edit
          </button>
        )}
      </div>

      {editing && !locked ? (
        <div className="mt-1 space-y-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full rounded border border-accent bg-background p-2 text-sm outline-none"
            rows={2}
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => {
                setEditing(false);
                setText(line.text);
              }}
              className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                setEditing(false);
                onUpdate(line.speaker, text);
              }}
              className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-foreground"
            >
              Save
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm leading-relaxed text-foreground">{line.text}</p>
      )}
    </li>
  );
}

function SectionBlock({
  label,
  value,
  edited,
  locked,
  onChange,
}: {
  label: string;
  value: string;
  edited: boolean;
  locked: boolean;
  onChange: (v: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  return (
    <section className="mb-6">
      <h3 className="mb-2 flex items-center gap-2 font-sans text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        <span>{label}</span>
        {edited && (
          <span className="h-1.5 w-1.5 rounded-full bg-accent" title="Edited by clinician" />
        )}
      </h3>
      {editing && !locked ? (
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => {
            setEditing(false);
            if (draft !== value) onChange(draft);
          }}
          rows={Math.max(3, draft.split("\n").length + 1)}
          className="w-full resize-none rounded-md border border-accent bg-background p-3.5 font-sans text-[15px] leading-relaxed text-foreground outline-none shadow-sm font-normal"
        />
      ) : (
        <div
          onClick={() => !locked && setEditing(true)}
          className={`whitespace-pre-wrap rounded-md p-3.5 font-sans text-[15px] leading-relaxed text-foreground font-normal transition ${
            locked
              ? "cursor-default"
              : "cursor-text hover:bg-muted/30 border border-transparent hover:border-border"
          } ${edited ? "border-l-2 border-accent pl-3 bg-accent/5" : ""}`}
        >
          {value}
        </div>
      )}
    </section>
  );
}

function Icd10SearchModal({
  onClose,
  onSelect,
}: {
  onClose: () => void;
  onSelect: (code: ICD10Code) => void;
}) {
  const [q, setQ] = useState("");
  const [codes, setCodes] = useState<ICD10Code[]>([]);

  useEffect(() => {
    fetch(`http://localhost:8000/api/icd10?q=${encodeURIComponent(q)}`)
      .then((res) => res.json())
      .then((data) => setCodes(data))
      .catch(() => {
        setCodes([
          { code: "R10.9", title: "Unspecified abdominal pain", category: "Gastrointestinal" },
          {
            code: "R11.2",
            title: "Nausea with vomiting, unspecified",
            category: "Gastrointestinal",
          },
          {
            code: "G51.0",
            title: "Bell's palsy / Facial nerve paralysis",
            category: "Neurological",
          },
          {
            code: "R35.0",
            title: "Frequency of micturition (Polyuria)",
            category: "Genitourinary",
          },
          { code: "I50.9", title: "Heart failure, unspecified", category: "Cardiovascular" },
          { code: "I10", title: "Essential hypertension", category: "Cardiovascular" },
        ]);
      });
  }, [q]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-xl">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <Tag className="h-4 w-4 text-accent" /> Search & Attach ICD-10 Codes
          </h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="my-4 relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search disease by code, name or symptom (e.g., Bell's palsy, pain, I10)..."
            className="w-full rounded-lg border border-input bg-background py-2.5 pl-9 pr-3 text-xs outline-none focus:border-accent"
          />
        </div>

        <div className="max-h-60 overflow-y-auto divide-y divide-border border rounded-lg bg-background">
          {codes.map((c) => (
            <button
              key={c.code}
              onClick={() => onSelect(c)}
              className="w-full text-left p-3 hover:bg-muted/40 transition flex items-center justify-between text-xs"
            >
              <div>
                <span className="font-mono font-bold text-accent">{c.code}</span>
                <span className="ml-2 font-medium text-foreground">{c.title}</span>
              </div>
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                {c.category}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function SnomedSearchModal({
  onClose,
  onSelect,
}: {
  onClose: () => void;
  onSelect: (code: SnomedCode) => void;
}) {
  const [q, setQ] = useState("");
  const [codes, setCodes] = useState<SnomedCode[]>([]);

  useEffect(() => {
    fetch(`http://localhost:8000/api/snomed?q=${encodeURIComponent(q)}`)
      .then((res) => res.json())
      .then((data) =>
        setCodes(
          data.map(
            (item: {
              conceptId: string;
              preferredTerm: string;
              category: string;
              icd10Map?: string;
            }) => ({
              conceptId: item.conceptId,
              term: item.preferredTerm,
              category: item.category,
              icd10Map: item.icd10Map,
            }),
          ),
        ),
      )
      .catch(() => setCodes([]));
  }, [q]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-xl">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <Tag className="h-4 w-4 text-accent" /> Search & Attach SNOMED CT Codes
          </h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="my-4 relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by concept, term or symptom (e.g., asthma, reflux, dizziness)..."
            className="w-full rounded-lg border border-input bg-background py-2.5 pl-9 pr-3 text-xs outline-none focus:border-accent"
          />
        </div>

        <div className="max-h-60 overflow-y-auto divide-y divide-border border rounded-lg bg-background">
          {codes.map((c) => (
            <button
              key={c.conceptId}
              onClick={() => onSelect(c)}
              className="w-full text-left p-3 hover:bg-muted/40 transition flex items-center justify-between text-xs"
            >
              <div>
                <span className="font-mono font-bold text-accent">{c.conceptId}</span>
                <span className="ml-2 font-medium text-foreground">{c.term}</span>
              </div>
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                {c.category}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function PrescriptionModal({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (rx: Prescription) => void;
}) {
  const [name, setName] = useState("Ondansetron");
  const [brand, setBrand] = useState("Vomikind");
  const [dosage, setDosage] = useState("4 mg");
  const [frequency, setFrequency] = useState("TDS (3 times daily)");
  const [route, setRoute] = useState("Oral");
  const [duration, setDuration] = useState("5 days");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    onAdd({
      name: name.trim(),
      brand: brand.trim(),
      dosage: dosage.trim(),
      frequency: frequency.trim(),
      route: route.trim(),
      duration: duration.trim(),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <Pill className="h-4 w-4 text-accent" /> Add Clinical Prescription / Medication
          </h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block font-semibold text-muted-foreground uppercase">
                Generic Name
              </span>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ondansetron"
                className="w-full rounded border border-input bg-background p-2 outline-none focus:border-accent"
              />
            </label>
            <label className="block">
              <span className="mb-1 block font-semibold text-muted-foreground uppercase">
                Brand Name
              </span>
              <input
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                placeholder="Vomikind / Zofran"
                className="w-full rounded border border-input bg-background p-2 outline-none focus:border-accent"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block font-semibold text-muted-foreground uppercase">
                Dosage
              </span>
              <input
                required
                value={dosage}
                onChange={(e) => setDosage(e.target.value)}
                placeholder="4 mg"
                className="w-full rounded border border-input bg-background p-2 outline-none focus:border-accent"
              />
            </label>
            <label className="block">
              <span className="mb-1 block font-semibold text-muted-foreground uppercase">
                Route
              </span>
              <select
                value={route}
                onChange={(e) => setRoute(e.target.value)}
                className="w-full rounded border border-input bg-background p-2 outline-none focus:border-accent"
              >
                <option>Oral</option>
                <option>IV (Intravenous)</option>
                <option>SC (Subcutaneous)</option>
                <option>IM (Intramuscular)</option>
                <option>Topical</option>
              </select>
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block font-semibold text-muted-foreground uppercase">
                Frequency
              </span>
              <input
                required
                value={frequency}
                onChange={(e) => setFrequency(e.target.value)}
                placeholder="TDS / BD / OD"
                className="w-full rounded border border-input bg-background p-2 outline-none focus:border-accent"
              />
            </label>
            <label className="block">
              <span className="mb-1 block font-semibold text-muted-foreground uppercase">
                Duration
              </span>
              <input
                required
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                placeholder="5 days / 2 weeks"
                className="w-full rounded border border-input bg-background p-2 outline-none focus:border-accent"
              />
            </label>
          </div>

          <div className="mt-5 flex justify-end gap-2 pt-3 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 rounded bg-accent text-accent-foreground font-semibold"
            >
              Add Prescription
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
