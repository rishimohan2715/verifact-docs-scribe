import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface DoctorSession {
  user: {
    id: string;
    email: string;
    user_metadata: {
      full_name: string;
    };
  };
  displayName: string;
  initials: string;
}

interface AuthContextValue {
  doctor: DoctorSession | null;
  loading: boolean;
  signOut: () => Promise<void>;
  signInLocally: (name: string, email: string) => void;
}

// Default local clinician profile (100% DPDP compliant offline session)
const DEFAULT_DOCTOR: DoctorSession = {
  user: {
    id: "local-doctor-001",
    email: "dr.raman@verifact.local",
    user_metadata: {
      full_name: "Dr. Raman",
    },
  },
  displayName: "Dr. Raman",
  initials: "DR",
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [doctor, setDoctor] = useState<DoctorSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check localStorage for a custom local clinician session, or use DEFAULT_DOCTOR
    const stored = localStorage.getItem("verifact_local_doctor");
    if (stored) {
      try {
        setDoctor(JSON.parse(stored));
      } catch {
        setDoctor(DEFAULT_DOCTOR);
      }
    } else {
      setDoctor(DEFAULT_DOCTOR);
    }
    setLoading(false);
  }, []);

  async function signOut() {
    localStorage.removeItem("verifact_local_doctor");
    setDoctor(null);
  }

  function signInLocally(name: string, email: string) {
    const initials = name
      .trim()
      .split(/\s+/)
      .map((p) => p[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "DR";

    const session: DoctorSession = {
      user: {
        id: `local-doc-${Date.now()}`,
        email: email || "clinician@verifact.local",
        user_metadata: { full_name: name || "Dr. Clinician" },
      },
      displayName: name || "Dr. Clinician",
      initials,
    };
    localStorage.setItem("verifact_local_doctor", JSON.stringify(session));
    setDoctor(session);
  }

  return (
    <AuthContext.Provider value={{ doctor, loading, signOut, signInLocally }}>
      {children}
    </AuthContext.Provider>
  );
}
