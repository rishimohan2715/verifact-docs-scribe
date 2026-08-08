import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Stethoscope, Lock, Sparkles, UserCheck } from "lucide-react";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Clinician Sign In — Verifact Local" },
      { name: "description", content: "Local DPDP-compliant sign-in for Verifact clinical documentation." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { signInLocally } = useAuth();
  const [name, setName] = useState("Dr. Raman");
  const [email, setEmail] = useState("dr.raman@verifact.local");

  function handleLocalSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    signInLocally(name.trim(), email.trim());
    toast.success(`Logged in as ${name.trim()} (Local DPDP Mode)`);
    navigate({ to: "/" });
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Left — branding panel */}
      <div className="hidden w-1/2 flex-col justify-between bg-sidebar border-r border-border p-12 lg:flex">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-accent text-accent-foreground">
            <Stethoscope className="h-5 w-5" />
          </div>
          <span className="font-serif text-xl tracking-tight text-foreground">Verifact</span>
        </div>

        <div>
          <blockquote className="font-serif text-3xl leading-snug text-foreground">
            "100% Local. Zero Cloud Data. Fully DPDP Compliant."
          </blockquote>
          <p className="mt-4 text-sm text-muted-foreground">
            Ambient AI clinical documentation running completely on your workstation.
            Audio, transcripts, and clinical summaries never leave your machine.
          </p>
        </div>

        <div className="space-y-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-accent" />
            <span>faster-whisper STT & Pyannote Diarization</span>
          </div>
          <div className="flex items-center gap-2">
            <Lock className="h-3.5 w-3.5 text-accent" />
            <span>Presidio PII Redaction Engine</span>
          </div>
          <div className="flex items-center gap-2">
            <UserCheck className="h-3.5 w-3.5 text-accent" />
            <span>Ollama MedGemma Local Discharge Summarizer</span>
          </div>
        </div>
      </div>

      {/* Right — auth form */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-16">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex items-center gap-2.5">
            <div className="grid h-9 w-9 place-items-center rounded-md bg-accent text-accent-foreground">
              <Stethoscope className="h-5 w-5" />
            </div>
            <span className="font-serif text-2xl tracking-tight text-foreground">Verifact Local</span>
          </div>

          <h1 className="font-serif text-2xl text-foreground">Clinician Access</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Enter your credentials to access your local consultation workspace.
          </p>

          <form onSubmit={handleLocalSubmit} className="mt-6 space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Clinician Name
              </span>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Dr. Raman"
                className="w-full rounded-lg border border-input bg-card px-3 py-2.5 text-sm outline-none focus:border-accent"
              />
            </label>

            <label className="block">
              <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Local Email
              </span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="dr.raman@verifact.local"
                className="w-full rounded-lg border border-input bg-card px-3 py-2.5 text-sm outline-none focus:border-accent"
              />
            </label>

            <button
              type="submit"
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent py-2.5 text-sm font-medium text-accent-foreground shadow-sm transition hover:opacity-90"
            >
              Start Local Session
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
