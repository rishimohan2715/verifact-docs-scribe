import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect } from "react";
import { TopBar } from "@/components/app-shell";
import { ensureSeeded } from "@/lib/mock-data";
import { useStore, fetchLocalConsultations, type Note } from "@/lib/store";
import { Plus, ChevronRight, Lock, Clock, FileText, CheckCircle2 } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard — Verifact Local" },
      { name: "description", content: "Your local consultation queue: pending notes, review times, and recent sign-offs." },
    ],
  }),
  component: Dashboard,
});

function fmtTime(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

function StatCard({ label, value, sub, icon: Icon }: { label: string; value: string; sub?: string; icon: any }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
        <Icon className="h-4 w-4 text-accent" />
      </div>
      <div className="mt-2 font-serif text-3xl text-foreground">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function StatusPill({ status }: { status: Note["status"] }) {
  const map = {
    draft: "bg-muted text-muted-foreground border-border",
    pending: "bg-accent/10 text-accent border-accent/30",
    signed: "bg-primary/5 text-primary border-primary/20",
  } as const;
  const label = { draft: "Draft", pending: "Pending Review", signed: "Signed & Locked" }[status];
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${map[status]}`}>
      {label}
    </span>
  );
}

function Dashboard() {
  useEffect(() => {
    ensureSeeded();
    fetchLocalConsultations();
  }, []);

  const notes = useStore((s) => s.notes);
  const pending = notes.filter((n) => n.status === "pending" || n.status === "draft");
  const signed = notes.filter((n) => n.status === "signed");
  const reviewedToday = signed.length;
  const avgTime = signed.length
    ? Math.round(signed.reduce((a, n) => a + (n.reviewSeconds ?? 0), 0) / signed.length)
    : 0;

  return (
    <>
      <TopBar title="Dashboard" />
      <div className="mx-auto w-full max-w-6xl px-6 py-8">
        {/* PRIVACY BADGE */}
        <div className="mb-6 flex items-center justify-between rounded-xl border border-accent/20 bg-accent/5 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <Lock className="h-4 w-4 text-accent" />
            <span className="text-xs font-medium text-foreground">
              100% Local Processing Active · Zero Cloud Data Transmission (DPDP Compliant)
            </span>
          </div>
          <span className="text-[11px] font-mono text-muted-foreground">SQLite: verifact_local.db</span>
        </div>

        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Good morning, Dr. Raman.</p>
            <p className="mt-1 font-serif text-2xl text-foreground">You have {pending.length} notes pending review.</p>
          </div>
          <Link
            to="/consultations/new"
            className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-accent-foreground shadow-sm transition hover:opacity-90"
          >
            <Plus className="h-4 w-4" /> New Consultation
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard label="Notes Reviewed" value={String(reviewedToday)} sub="Approved & Locked" icon={CheckCircle2} />
          <StatCard
            label="Average Review Time"
            value={avgTime ? `${Math.floor(avgTime / 60)}m ${avgTime % 60}s` : "—"}
            sub="Per note (Invisible Tracker)"
            icon={Clock}
          />
          <StatCard label="Pending Queue" value={String(pending.length)} sub="Ready for Clinician Sign-off" icon={FileText} />
        </div>

        {/* PENDING QUEUE TABLE */}
        <section className="mt-10">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="font-serif text-xl text-foreground">Pending Consultation Queue</h2>
            <span className="text-xs text-muted-foreground">Click a row to review draft note</span>
          </div>
          <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30 text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Patient Name</th>
                  <th className="px-4 py-3 font-medium">MRN</th>
                  <th className="px-4 py-3 font-medium">Consult Time</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {pending.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      No pending consultations. All notes are signed off!
                    </td>
                  </tr>
                )}
                {pending.map((n) => (
                  <tr key={n.id} className="group border-b border-border/60 last:border-0 hover:bg-muted/40 transition">
                    <td className="px-4 py-3.5">
                      <Link to="/notes/$noteId" params={{ noteId: n.id }} className="font-medium text-foreground hover:underline">
                        {n.patientName}
                      </Link>
                    </td>
                    <td className="px-4 py-3.5 text-muted-foreground">{n.mrn}</td>
                    <td className="px-4 py-3.5 text-muted-foreground">{fmtTime(n.consultTime)}</td>
                    <td className="px-4 py-3.5 text-muted-foreground">{n.type}</td>
                    <td className="px-4 py-3.5"><StatusPill status={n.status} /></td>
                    <td className="px-4 py-3.5 text-right">
                      <Link
                        to="/notes/$noteId"
                        params={{ noteId: n.id }}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-accent opacity-90 transition group-hover:opacity-100"
                      >
                        Review & Sign <ChevronRight className="h-4 w-4" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* RECENTLY SIGNED */}
        <section className="mt-10">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Recently Signed & Locked</h2>
            <Link to="/notes" className="text-xs text-muted-foreground hover:text-foreground">View all notes</Link>
          </div>
          <div className="divide-y divide-border rounded-xl border border-border bg-card/60 shadow-sm">
            {signed.slice(0, 5).map((n) => (
              <Link
                key={n.id}
                to="/notes/$noteId"
                params={{ noteId: n.id }}
                className="flex items-center justify-between px-4 py-3.5 text-sm hover:bg-muted/40 transition"
              >
                <div className="flex items-center gap-3">
                  <span className="font-medium text-foreground">{n.patientName}</span>
                  <span className="text-xs text-muted-foreground">{n.mrn}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>{n.type}</span>
                  <span>{fmtDate(n.signedAt ?? n.consultTime)}</span>
                  <span>Reviewed in {n.reviewSeconds ?? 0}s</span>
                  <StatusPill status="signed" />
                </div>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
