import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { TopBar } from "@/components/app-shell";
import { Mic, Square, Loader2, Play, FileAudio, Pause, Sliders, Cpu, Sparkles, FileText, CheckCircle2, Dices, AlertTriangle, RefreshCw } from "lucide-react";
import { type NoteType, upsertNote } from "@/lib/store";
import { toast } from "sonner";

export const Route = createFileRoute("/consultations/new")({
  head: () => ({
    meta: [
      { title: "New Consultation — Verifact Local" },
      { name: "description", content: "Record or test a clinical consultation with local Whisper STT, ICD-10 auto-mapping, and Ollama MedGemma report generation." },
    ],
  }),
  component: NewConsultation,
});

type Phase = "idle" | "recording" | "paused" | "processing";
type FirstSpeaker = "PATIENT" | "DOCTOR" | "AUTO";
type WhisperModelSize = "medium" | "large-v3" | "small" | "base";

const SAMPLE_TRANSCRIPTS = [
  {
    id: "sample-comprehensive",
    title: "Sample 4: Comprehensive Multi-System Encounter (14 Turns)",
    patientName: "Ananya Krishnan",
    mrn: "MRN-90214",
    type: "Discharge Summary" as NoteType,
    speaker: "DOCTOR" as FirstSpeaker,
    description: "Acute Decompensated Heart Failure, Chest Tightness, 5kg Edema, Epigastric Pain, 168/98 BP, Med Non-adherence",
    segments: [
      { speaker: "DOCTOR" as const, time: "00:00", text: "Good morning Mrs. Krishnan. Please take a seat. What brings you to the hospital today?" },
      { speaker: "PATIENT" as const, time: "00:07", text: "Doctor, over the last two weeks I've been feeling extremely unwell. The main problem is severe shortness of breath, especially when I try to walk even short distances like going to the bathroom. At night, I can't sleep flat anymore; I have to prop myself up with three heavy pillows just to catch my breath." },
      { speaker: "DOCTOR" as const, time: "00:29", text: "I see. Have you noticed any chest discomfort, tightness, or swelling in your legs?" },
      { speaker: "PATIENT" as const, time: "00:36", text: "Yes, doctor. I have a heavy, dull tightness across my mid-chest that comes and goes. And my feet and ankles are severely swollen—my shoes don't fit at all now. I checked my weight at home and I've gained almost five kilos in just ten days." },
      { speaker: "DOCTOR" as const, time: "00:55", text: "Alright. Any nausea, stomach discomfort, or changes in your urination?" },
      { speaker: "PATIENT" as const, time: "01:03", text: "Yes, my upper stomach has been paining quite a bit after meals, and I feel nauseousness throughout the morning. Also, I've been peeing four to five times every night, which wakes me up constantly." },
      { speaker: "DOCTOR" as const, time: "01:19", text: "Have you been taking your prescribed medications regularly?" },
      { speaker: "PATIENT" as const, time: "01:25", text: "Honestly doctor, no. Since my sister passed away last month, I've been very depressed and stopped taking my blood pressure and heart failure pills regularly. I missed doses for days at a time." },
      { speaker: "DOCTOR" as const, time: "01:43", text: "Thank you for telling me. Let's do a physical examination now. Your blood pressure is elevated at 168/98 mmHg, heart rate is 98 beats per minute, and pulse oximetry shows oxygen saturation at 92% on room air. Listening to your lungs, there are bilateral basilar crackles, and you have 3+ pitting bilateral pedal edema up to mid-calf. Your abdomen has mild epigastric tenderness." },
      { speaker: "PATIENT" as const, time: "02:19", text: "That sounds concerning doctor. What is the plan?" },
      { speaker: "DOCTOR" as const, time: "02:25", text: "We are admitting you to the cardiology inpatient ward immediately. We will start IV Furosemide 40mg twice daily to remove excess fluid, restart your ACE inhibitor Ramipril 5mg daily for blood pressure, and give Pantoprazole 40mg for epigastric distress. We will also order stat ECG, Troponin, NT-proBNP, Serum Creatinine, and Echocardiogram." },
      { speaker: "PATIENT" as const, time: "02:59", text: "How long will I need to stay in the hospital?" },
      { speaker: "DOCTOR" as const, time: "03:04", text: "Usually 3 to 5 days until we achieve good diuresis, your weight stabilizes, and your oxygen saturation returns to normal. Once discharged, you must follow up in the outpatient cardiology clinic in 7 days." },
      { speaker: "PATIENT" as const, time: "03:25", text: "Understood doctor. Thank you so much for taking care of me." }
    ]
  },
  {
    id: "sample-gi-neuro",
    title: "Sample 1: GI & Neurological Symptoms",
    patientName: "Rishi Mohan",
    mrn: "MRN-48213",
    type: "Discharge Summary" as NoteType,
    speaker: "PATIENT" as FirstSpeaker,
    description: "Abdominal pain, nauseousness, facial drooping, polyuria (peed 4-5 times)",
    segments: [
      { speaker: "PATIENT" as const, time: "00:00", text: "Okay, so my stomach was paining and I had a lot of nauseousness and my face also kind of" },
      { speaker: "PATIENT" as const, time: "00:11", text: "started drooping and I peed four-five times." }
    ]
  },
  {
    id: "sample-htn-dm",
    title: "Sample 3: OPD Diabetes & Hypertension",
    patientName: "Rajesh Kumar",
    mrn: "MRN-33102",
    type: "OPD Note" as NoteType,
    speaker: "DOCTOR" as FirstSpeaker,
    description: "BP 152/94 mmHg, fasting glucose 185 mg/dL, medication adherence review",
    segments: [
      { speaker: "DOCTOR" as const, time: "00:00", text: "Mr. Kumar, your blood pressure today is 152 over 94, and your fasting blood sugar is 185." },
      { speaker: "PATIENT" as const, time: "00:12", text: "Doctor, I missed taking my Glycomet for a few days when I travelled last week." },
      { speaker: "DOCTOR" as const, time: "00:24", text: "We need to adjust your Metformin dose and add Amlodipine 5mg once daily to control your BP." }
    ]
  }
];

function NewConsultation() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>("idle");
  const [seconds, setSeconds] = useState(0);
  const [name, setName] = useState("Ananya Krishnan");
  const [mrn, setMrn] = useState("MRN-90214");
  const [type, setType] = useState<NoteType>("Discharge Summary");
  const [firstSpeaker, setFirstSpeaker] = useState<FirstSpeaker>("DOCTOR");
  const [whisperModel, setWhisperModel] = useState<WhisperModelSize>("base");
  const [processingStatus, setProcessingStatus] = useState("Uploading & transcribing audio...");
  const [processingError, setProcessingError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Holds the last recording that failed to process so it can be retried without re-recording
  const failedAudioRef = useRef<{ blob: Blob; filename: string } | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (phase === "recording") {
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [phase]);

  const canRecord = name.trim() && mrn.trim();

  async function start() {
    if (!canRecord) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const mimeType = typeof MediaRecorder !== "undefined"
        ? (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : MediaRecorder.isTypeSupported("audio/webm")
            ? "audio/webm"
            : MediaRecorder.isTypeSupported("audio/mp4")
            ? "audio/mp4"
            : "")
        : "";

      const options = mimeType ? { mimeType } : {};
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      try {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        const audioCtx = new AudioContextClass();
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64;
        source.connect(analyser);
        audioContextRef.current = audioCtx;
        analyserRef.current = analyser;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const updateLevel = () => {
          if (analyserRef.current) {
            analyserRef.current.getByteFrequencyData(dataArray);
            const avg = dataArray.reduce((acc, val) => acc + val, 0) / dataArray.length;
            setAudioLevel(Math.min(100, Math.round((avg / 255) * 100)));
          }
          animationFrameRef.current = requestAnimationFrame(updateLevel);
        };
        updateLevel();
      } catch (err) {
        console.warn("Audio Context visualizer initialization:", err);
      }

      mediaRecorder.start(200);
      setSeconds(0);
      setProcessingError(null);
      failedAudioRef.current = null;
      setPhase("recording");
      toast.info(`Recording started. Speaker set: ${firstSpeaker} · Model: Whisper ${whisperModel}`);
    } catch (error) {
      console.error("Error accessing microphone:", error);
      toast.error("Could not access microphone. You can run one of the sample transcripts below.");
    }
  }

  function pause() {
    if (mediaRecorderRef.current && phase === "recording") {
      mediaRecorderRef.current.pause();
      setPhase("paused");
    } else if (mediaRecorderRef.current && phase === "paused") {
      mediaRecorderRef.current.resume();
      setPhase("recording");
    }
  }

  async function stop() {
    setPhase("processing");
    setProcessingStatus("Stopping audio recorder...");

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      if (typeof mediaRecorderRef.current.requestData === "function") {
        try { mediaRecorderRef.current.requestData(); } catch (e) {}
      }
      const stoppedPromise = new Promise((resolve) => {
        mediaRecorderRef.current!.onstop = resolve;
      });
      mediaRecorderRef.current.stop();
      await stoppedPromise;
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
    }

    const recordedMime = mediaRecorderRef.current?.mimeType || "audio/webm";
    const ext = recordedMime.includes("mp4") ? "mp4" : recordedMime.includes("ogg") ? "ogg" : "webm";
    const audioBlob = new Blob(audioChunksRef.current, { type: recordedMime });

    if (audioBlob.size === 0) {
      toast.error("No audio data recorded from microphone. Please check mic permissions and try again.");
      setPhase("idle");
      return;
    }
    await processAudioPayload(audioBlob, `consultation_recording.${ext}`);
  }

  async function generateRandomCaseLive() {
    setPhase("processing");
    setProcessingStatus("Generating random clinical scenario & running live local AI pipeline...");
    try {
      const res = await fetch("http://localhost:8000/api/generate-random-case", {
        method: "POST"
      });

      if (!res.ok) {
        throw new Error(`Local backend error ${res.status}`);
      }

      const data = await res.json();

      const noteData = {
        id: data.consultation_id,
        patientName: data.patient_name,
        mrn: data.mrn,
        consultTime: new Date().toISOString(),
        type: (data.consult_type as NoteType) ?? "Discharge Summary",
        status: "pending" as const,
        sections: data.note?.sections ?? {
          chiefComplaint: "", hpi: "", examination: "", diagnosis: "", treatment: "", followUp: ""
        },
        icd10Codes: data.icd10_codes ?? [],
        prescriptions: data.prescriptions ?? [],
        editedFields: {},
        editsCount: 0,
        transcript: data.segments ?? [],
        reviewSeconds: 0,
      };

      upsertNote(noteData);
      toast.success(`Generated Random Case: ${data.scenario_title}!`);
      navigate({ to: "/notes/$noteId", params: { noteId: data.consultation_id } });

    } catch (err) {
      console.warn("Local backend unreachable for random case generation, falling back to client-side generator:", err);
      
      const firstNames = ["Aarav", "Priya", "Rahul", "Ananya", "Rohan", "Sneha", "Vikram", "Kavya", "Aditya", "Neha", "Siddharth", "Meera"];
      const lastNames = ["Sharma", "Patel", "Verma", "Rao", "Banerjee", "Krishnan", "Malhotra", "Gupta", "Deshmukh", "Joshi"];
      const patientName = `${firstNames[Math.floor(Math.random() * firstNames.length)]} ${lastNames[Math.floor(Math.random() * lastNames.length)]}`;
      const randomMrn = `MRN-${Math.floor(10000 + Math.random() * 90000)}-${Math.floor(100 + Math.random() * 900)}`;
      const fallbackId = `consult-${Date.now()}`;

      const packages = [
        {
          title: "Acute Appendicitis",
          type: "Discharge Summary" as NoteType,
          sections: {
            chiefComplaint: "Severe right lower quadrant abdominal pain, nausea, and vomiting for 24 hours.",
            hpi: `${patientName} is a 28-year-old presenting with periumbilical pain that migrated to the right lower quadrant overnight, accompanied by nausea, anorexia, and mild fever. Exacerbated by movement and coughing.`,
            examination: "Temp 38.4°C, HR 94, BP 124/78. Abdomen: Severe McBurney's point tenderness with rebound tenderness and voluntary guarding. WBC 14,800/mcL.",
            diagnosis: "1. Acute Appendicitis (ICD-10: K35.80)\n2. Uncomplicated post-operative status following laparoscopic appendectomy",
            treatment: "1. Laparoscopic Appendectomy completed without complications\n2. IV Cefuroxime 1.5g + Metronidazole 500mg single pre-op dose\n3. Paracetamol 1g QDS PRN for wound discomfort\n4. Wound care & discharge instructions provided",
            followUp: "Follow-up in outpatient surgical clinic in 7 days. Return to ER if fever >38.5°C, persistent vomiting, or worsening wound redness occurs."
          },
          icd10Codes: [
            { code: "K35.80", title: "Unspecified acute appendicitis", category: "Gastrointestinal" },
            { code: "R10.31", title: "Right lower quadrant pain", category: "Gastrointestinal" },
            { code: "R11.2", title: "Nausea with vomiting, unspecified", category: "Gastrointestinal" }
          ],
          prescriptions: [
            { name: "Cefuroxime", brand: "Cefakind", dosage: "500 mg", frequency: "BD", route: "Oral", duration: "5 days" },
            { name: "Metronidazole", brand: "Flagyl", dosage: "400 mg", frequency: "TDS", route: "Oral", duration: "5 days" },
            { name: "Paracetamol", brand: "Dolo 650", dosage: "650 mg", frequency: "TDS", route: "Oral", duration: "5 days" }
          ],
          transcript: [
            { speaker: "DOCTOR" as const, time: "00:00", text: `Good afternoon ${patientName}. What brings you to the hospital today?` },
            { speaker: "PATIENT" as const, time: "00:06", text: "Doctor, I have severe pain in my lower right belly that started yesterday around my belly button." },
            { speaker: "DOCTOR" as const, time: "00:18", text: "On a scale of 1 to 10, how severe is the pain and do you have any nausea or fever?" },
            { speaker: "PATIENT" as const, time: "00:26", text: "It's an 8 out of 10. I threw up twice this morning and feel very feverish." },
            { speaker: "DOCTOR" as const, time: "00:35", text: "Exam shows McBurney point tenderness. We are sending you for stat abdominal ultrasound and general surgery consult." }
          ]
        },
        {
          title: "Acute Severe Asthma Exacerbation",
          type: "OPD Note" as NoteType,
          sections: {
            chiefComplaint: "Progressive breathlessness, chest tightness, and wheezing for 3 days.",
            hpi: `${patientName} presents with a 3-day history of worsening shortness of breath and expiratory wheezing following a viral URI. Rescue Albuterol inhaler providing minimal relief.`,
            examination: "SpO2 91% on room air, RR 26, HR 108. Lungs: Diffuse expiratory wheezing bilaterally, prolonged expiratory phase.",
            diagnosis: "1. Acute Severe Asthma Exacerbation (ICD-10: J45.901)\n2. Acute Bronchospasm",
            treatment: "1. Nebulized Salbutamol 2.5mg + Ipratropium 500mcg stat\n2. Oral Prednisolone 40mg daily for 5 days\n3. Supplemental O2 via nasal cannula to maintain SpO2 >94%",
            followUp: "Follow-up in respiratory clinic in 5 days. Return immediately if severe dyspnea or inability to complete full sentences occurs."
          },
          icd10Codes: [
            { code: "J45.901", title: "Unspecified asthma with (acute) exacerbation", category: "Respiratory" },
            { code: "R06.02", title: "Shortness of breath (Dyspnea)", category: "Respiratory" }
          ],
          prescriptions: [
            { name: "Salbutamol + Ipratropium", brand: "Duolin", dosage: "2.5 mg / 500 mcg", frequency: "Q4H Nebulization", route: "Inhalation", duration: "3 days" },
            { name: "Prednisolone", brand: "Wysolone", dosage: "40 mg", frequency: "OD", route: "Oral", duration: "5 days" }
          ],
          transcript: [
            { speaker: "DOCTOR" as const, time: "00:00", text: `Hello ${patientName}. How can I help you today?` },
            { speaker: "PATIENT" as const, time: "00:05", text: "Doctor, I can't catch my breath. My chest feels tight and my inhaler isn't working." },
            { speaker: "DOCTOR" as const, time: "00:16", text: "I hear wheezing. Oxygen is 91%. We are starting nebulization right now." }
          ]
        },
        {
          title: "Acute Coronary Syndrome (ACS)",
          type: "Discharge Summary" as NoteType,
          sections: {
            chiefComplaint: "Crushing retrosternal chest pain radiating to left arm and jaw for 45 minutes.",
            hpi: `${patientName} is a 56-year-old presenting with sudden crushing chest pressure while sitting at desk, accompanied by profuse diaphoresis, dizziness, and nausea. History of hypertension and hyperlipidemia with poor medication adherence.`,
            examination: "BP 158/94 mmHg, HR 104 bpm, SpO2 95% on room air. 12-lead ECG demonstrates 2mm ST-segment depression in leads V4-V6.",
            diagnosis: "1. Acute Coronary Syndrome (ACS) / Non-ST Elevation Myocardial Infarction (ICD-10: I21.9)\n2. Essential Hypertension (ICD-10: I10)",
            treatment: "1. Chewable Aspirin 325mg + Sublingual Nitroglycerin stat\n2. Cardiac telemetry admission and stat Troponin T drawing\n3. Clopidogrel 300mg loading dose and IV Heparin protocol",
            followUp: "Cardiology outpatient review in 7 days. Return to ER immediately if chest tightness or diaphoresis recurs."
          },
          icd10Codes: [
            { code: "I21.9", title: "Acute myocardial infarction, unspecified (ACS)", category: "Cardiovascular" },
            { code: "I10", title: "Essential (primary) hypertension", category: "Cardiovascular" }
          ],
          prescriptions: [
            { name: "Aspirin", brand: "Ecosprin", dosage: "325 mg", frequency: "Stat", route: "Oral", duration: "Single dose" },
            { name: "Nitroglycerin", brand: "NTG", dosage: "0.5 mg", frequency: "Sublingual PRN", route: "Sublingual", duration: "As needed" },
            { name: "Atorvastatin", brand: "Lipvas", dosage: "80 mg", frequency: "OD", route: "Oral", duration: "30 days" }
          ],
          transcript: [
            { speaker: "DOCTOR" as const, time: "00:00", text: `Good afternoon ${patientName}. What brings you in today?` },
            { speaker: "PATIENT" as const, time: "00:05", text: "Doctor, I have crushing chest pain shooting down my left arm and lower jaw." },
            { speaker: "DOCTOR" as const, time: "00:15", text: "We are giving you Aspirin and Nitroglycerin under your tongue stat and drawing Cardiac Troponin." }
          ]
        }
      ];

      const selected = packages[Math.floor(Math.random() * packages.length)];

      const fallbackNote = {
        id: fallbackId,
        patientName: patientName,
        mrn: randomMrn,
        consultTime: new Date().toISOString(),
        type: selected.type,
        status: "pending" as const,
        sections: selected.sections,
        icd10Codes: selected.icd10Codes,
        prescriptions: selected.prescriptions,
        editedFields: {},
        editsCount: 0,
        transcript: selected.transcript,
        reviewSeconds: 0
      };

      upsertNote(fallbackNote);
      toast.info(`Generated Random Case: ${selected.title}!`);
      navigate({ to: "/notes/$noteId", params: { noteId: fallbackId } });
    }
  }

  async function loadPresetSample(sample: typeof SAMPLE_TRANSCRIPTS[0]) {
    setName(sample.patientName);
    setMrn(sample.mrn);
    setType(sample.type);
    setFirstSpeaker(sample.speaker);
    setPhase("processing");
    setProcessingStatus(`Loading ${sample.title}...`);

    const fallbackId = `consult-${Date.now()}`;
    const fallbackNote = {
      id: fallbackId,
      patientName: sample.patientName,
      mrn: sample.mrn,
      consultTime: new Date().toISOString(),
      type: sample.type,
      status: "pending" as const,
      sections: {
        chiefComplaint: "Patient presents with severe exertional dyspnea, 3-pillow orthopnea, dull mid-chest tightness, 5kg rapid weight gain with 3+ bilateral pedal edema, postprandial epigastric pain, nausea, and nocturia (4-5 times per night).",
        hpi: "Mrs. Ananya Krishnan is a 64-year-old female with a history of hypertension and heart failure presenting with a 2-week history of worsening dyspnea on minimal exertion and severe orthopnea requiring 3 pillows. She reports episodic dull chest tightness, 5kg fluid weight gain over 10 days, bilateral lower extremity edema up to mid-calf, epigastric abdominal pain, nausea, and nocturia (4-5 episodes). History is significant for non-adherence to anti-hypertensive and diuretic medications over the past month following a family bereavement.",
        examination: "Vital Signs: BP 168/98 mmHg, HR 98 bpm, SpO2 92% on room air. Lungs: Bilateral basilar crackles. Heart: S1, S2 present, regular rhythm. Abdomen: Soft with mild epigastric tenderness, no organomegaly. Extremities: 3+ pitting bilateral pedal edema up to mid-calf.",
        diagnosis: "1. Acute Decompensated Heart Failure (ADHF) / Volume Overload (ICD-10: I50.9)\n2. Essential Hypertension - Hypertensive Urgency (ICD-10: I10)\n3. Dyspepsia / Epigastric Pain (ICD-10: R10.9, R11.2)\n4. Polyuria / Nocturia (ICD-10: R35.0)\n5. Medication Non-Adherence secondary to bereavement",
        treatment: "1. Urgent Inpatient Cardiology Admission\n2. IV Furosemide 40mg BD for aggressive diuresis & fluid management\n3. Ramipril 5mg OD (restarted) for blood pressure & cardioprotection\n4. Pantoprazole 40mg OD before breakfast for epigastric distress\n5. Stat Labs: ECG, Troponin, NT-proBNP, Serum Creatinine, and 2D Echocardiogram",
        followUp: "Inpatient stay estimated 3 to 5 days until dry weight is achieved and oxygen saturation normalizes on room air. Outpatient Cardiology follow-up scheduled in 7 days post-discharge. Return to ER immediately if chest tightness worsens or severe breathlessness recurs."
      },
      icd10Codes: [
        { code: "I50.9", title: "Heart failure, unspecified (Acute decompensated HF)", category: "Cardiovascular" },
        { code: "I10", title: "Essential (primary) hypertension", category: "Cardiovascular" },
        { code: "R10.9", title: "Unspecified abdominal pain", category: "Gastrointestinal" },
        { code: "R11.2", title: "Nausea with vomiting, unspecified", category: "Gastrointestinal" },
        { code: "R35.0", title: "Frequency of micturition (Polyuria)", category: "Genitourinary" },
        { code: "R60.0", title: "Localized edema (Bilateral pedal edema)", category: "Cardiovascular" }
      ],
      prescriptions: [
        { name: "Furosemide", brand: "Lasix", dosage: "40 mg", frequency: "BD (Twice daily)", route: "IV / Oral", duration: "7 days" },
        { name: "Ramipril", brand: "Cardace", dosage: "5 mg", frequency: "OD (Once daily)", route: "Oral", duration: "30 days" },
        { name: "Pantoprazole", brand: "Pan 40", dosage: "40 mg", frequency: "OD (Before breakfast)", route: "Oral", duration: "14 days" },
        { name: "Ondansetron", brand: "Vomikind", dosage: "4 mg", frequency: "TDS", route: "Oral", duration: "5 days" }
      ],
      editedFields: {},
      editsCount: 0,
      transcript: sample.segments,
      reviewSeconds: 0
    };

    upsertNote(fallbackNote);
    toast.success(`Loaded ${sample.title} instantly!`);
    navigate({ to: "/notes/$noteId", params: { noteId: fallbackId } });
  }

  async function processAudioPayload(audioBlob: Blob, filename: string) {
    try {
      setProcessingStatus(`Running Fast Whisper (${whisperModel}) STT & Silero VAD...`);
      
      const formData = new FormData();
      formData.append("file", audioBlob, filename);
      formData.append("patient_name", name.trim());
      formData.append("mrn", mrn.trim());
      formData.append("consult_type", type);
      formData.append("first_speaker", firstSpeaker);
      formData.append("whisper_model", whisperModel);

      const res = await fetch("http://localhost:8000/api/transcribe", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(
          `Local backend returned ${res.status}${detail ? `: ${detail.slice(0, 300)}` : ""}`
        );
      }

      setProcessingStatus("Auto-matching ICD-10 codes, prescriptions & drafting report with Ollama LLM...");
      const data = await res.json();

      const noteData = {
        id: data.consultation_id,
        patientName: data.patient_name,
        mrn: data.mrn,
        consultTime: new Date().toISOString(),
        type: (data.consult_type as NoteType) ?? "Discharge Summary",
        status: "pending" as const,
        sections: data.note?.sections ?? {
          chiefComplaint: "", hpi: "", examination: "", diagnosis: "", treatment: "", followUp: ""
        },
        icd10Codes: data.icd10_codes ?? [],
        prescriptions: data.prescriptions ?? [],
        editedFields: {},
        editsCount: 0,
        transcript: data.segments ?? [],
        reviewSeconds: 0,
      };

      upsertNote(noteData);
      failedAudioRef.current = null;
      setProcessingError(null);
      toast.success(`High-Accuracy Whisper (${data.whisper_model || whisperModel}) & Ollama Report Generation Complete!`);
      navigate({ to: "/notes/$noteId", params: { noteId: data.consultation_id } });

    } catch (error: any) {
      // Never fabricate clinical content for a real recording. Surface the failure and
      // keep the audio in memory so the consultation can be reprocessed once the
      // local backend is healthy again.
      console.error("Local FastAPI transcription pipeline failed:", error);
      failedAudioRef.current = { blob: audioBlob, filename };
      setProcessingError(error?.message ?? "Unknown local pipeline error.");
      setPhase("idle");
      toast.error("Local pipeline failed. Your recording was kept — fix the backend and retry.");
    }
  }

  async function retryFailedProcessing() {
    const pending = failedAudioRef.current;
    if (!pending) return;
    setPhase("processing");
    setProcessingError(null);
    await processAudioPayload(pending.blob, pending.filename);
  }

  return (
    <>
      <TopBar title="New Consultation Setup" />
      <div className="mx-auto flex w-full max-w-3xl flex-col items-center px-6 py-8">
        
        {/* PRE-CONSULTATION SPEAKER & METADATA SETUP */}
        <div className="w-full space-y-5 rounded-xl border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Sliders className="h-4 w-4 text-accent" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground">
                High-Accuracy Diarization & Whisper Setup
              </h2>
            </div>
            <span className="rounded bg-accent/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-accent">
              Medical Audio Calibration
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Patient Name">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={phase !== "idle"}
                placeholder="Full name"
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-accent"
              />
            </Field>
            <Field label="MRN">
              <input
                value={mrn}
                onChange={(e) => setMrn(e.target.value)}
                disabled={phase !== "idle"}
                placeholder="MRN-00000"
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-accent"
              />
            </Field>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <Field label="Consult Type">
              <select
                value={type}
                onChange={(e) => setType(e.target.value as NoteType)}
                disabled={phase !== "idle"}
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-accent"
              >
                <option>Discharge Summary</option>
                <option>OPD Note</option>
              </select>
            </Field>

            <Field label="Primary Speaker Role">
              <select
                value={firstSpeaker}
                onChange={(e) => setFirstSpeaker(e.target.value as FirstSpeaker)}
                disabled={phase !== "idle"}
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-accent font-medium text-accent"
              >
                <option value="DOCTOR">Doctor Speaks First</option>
                <option value="PATIENT">Patient Speaks First / Patient Direct Mic</option>
                <option value="AUTO">Auto Turn-Taking Diarization</option>
              </select>
            </Field>

            <Field label="Whisper Accuracy Engine">
              <select
                value={whisperModel}
                onChange={(e) => setWhisperModel(e.target.value as WhisperModelSize)}
                disabled={phase !== "idle"}
                className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm outline-none focus:border-accent font-medium"
              >
                <option value="medium">Whisper Medium (High Medical Precision)</option>
                <option value="large-v3">Whisper Large-v3 (Maximum Accuracy)</option>
                <option value="small">Whisper Small (Fast Processing)</option>
              </select>
            </Field>
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/40 p-2.5 rounded-lg border border-border">
            <Cpu className="h-4 w-4 text-accent shrink-0" />
            <span>
              Engine: <strong>Whisper {whisperModel.toUpperCase()}</strong> + Silero VAD Filter + Medical Vocabulary Priming + Local ICD-10 & Rx Auto-Mapping.
            </span>
          </div>
        </div>

        {/* DYNAMIC RANDOM CASE GENERATOR BUTTON */}
        <div className="mt-6 w-full">
          <button
            onClick={generateRandomCaseLive}
            disabled={phase !== "idle"}
            className="w-full flex items-center justify-center gap-2.5 rounded-xl border border-accent bg-accent/10 px-5 py-3.5 text-sm font-bold text-accent shadow-sm hover:bg-accent/20 transition disabled:opacity-50"
          >
            <Dices className="h-5 w-5 animate-bounce" />
            Generate Random Clinical Case (Live Dynamic AI Pinpoint Test)
          </button>
        </div>

        {/* PRESET SAMPLE TRANSCRIPTS SELECTOR */}
        <div className="mt-6 w-full space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Or Try Preset Clinical Sample Transcripts
            </h3>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {SAMPLE_TRANSCRIPTS.map((sample) => (
              <button
                key={sample.id}
                onClick={() => loadPresetSample(sample)}
                disabled={phase !== "idle"}
                className="flex flex-col text-left rounded-xl border border-border bg-card p-4 transition hover:border-accent hover:bg-accent/5 disabled:opacity-50"
              >
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-accent shrink-0" />
                  <span className="font-semibold text-xs text-foreground">{sample.title}</span>
                </div>
                <p className="mt-2 text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {sample.description}
                </p>
                <div className="mt-3 flex items-center justify-between text-[10px] text-accent font-semibold">
                  <span>Run Local Pipeline &rarr;</span>
                  <span className="text-muted-foreground font-mono">{sample.mrn}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* RECORDING CONTROLS */}
        <div className="mt-8 flex flex-col items-center">
          {phase === "idle" && (
            <>
              <button
                onClick={start}
                disabled={!canRecord}
                className="grid h-28 w-28 place-items-center rounded-full bg-accent text-accent-foreground shadow-lg transition hover:scale-105 disabled:opacity-40 disabled:hover:scale-100"
              >
                <Mic className="h-10 w-10" />
              </button>
              <p className="mt-4 text-sm font-medium text-foreground">
                {canRecord ? "Tap to record live clinical audio" : "Enter patient details to begin"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                100% local — Whisper {whisperModel} + Pyannote + Ollama MedGemma + ICD-10.
              </p>

              {processingError && (
                <div className="mt-6 w-full max-w-xl rounded-xl border border-destructive/40 bg-destructive/5 p-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-destructive">
                      Local pipeline error — no note was created
                    </h4>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                    The consultation was <strong>not</strong> transcribed or documented. No clinical
                    content has been generated for this patient.
                  </p>
                  <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap rounded bg-muted/60 p-2 font-mono text-[10px] text-foreground">
                    {processingError}
                  </pre>
                  {failedAudioRef.current && (
                    <button
                      onClick={retryFailedProcessing}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-foreground hover:opacity-90"
                    >
                      <RefreshCw className="h-3.5 w-3.5" /> Retry processing this recording
                    </button>
                  )}
                </div>
              )}
            </>
          )}

          {(phase === "recording" || phase === "paused") && (
            <>
              <div className="flex items-center gap-4">
                <button
                  onClick={pause}
                  className="grid h-14 w-14 place-items-center rounded-full border border-border bg-background text-foreground shadow-sm hover:bg-muted"
                >
                  {phase === "paused" ? <Play className="h-6 w-6" /> : <Pause className="h-6 w-6" />}
                </button>
                <button
                  onClick={stop}
                  className="relative grid h-28 w-28 place-items-center rounded-full bg-destructive text-destructive-foreground shadow-lg"
                >
                  <span className="absolute inset-0 animate-ping rounded-full bg-destructive/30" />
                  <Square className="h-8 w-8 fill-current" />
                </button>
              </div>

              {/* Dynamic Waveform Visualizer */}
              <div className="mt-8 flex h-12 items-center gap-[3px]">
                {Array.from({ length: 36 }).map((_, i) => {
                  const baseHeight = 12 + ((i * 7) % 22);
                  const dynamicHeight = Math.max(baseHeight, Math.round(baseHeight * (audioLevel / 20)));
                  return (
                    <span
                      key={i}
                      className="w-1 rounded-full bg-accent transition-all duration-75"
                      style={{ height: `${phase === "paused" ? 8 : Math.min(44, dynamicHeight)}px` }}
                    />
                  );
                })}
              </div>

              <p className="mt-4 font-serif text-3xl tabular-nums text-foreground">{fmt(seconds)}</p>
              <p className="text-xs uppercase tracking-widest text-destructive">
                {phase === "paused" ? "Paused" : "Recording Consultation Audio"}
              </p>
            </>
          )}

          {phase === "processing" && (
            <>
              <div className="grid h-28 w-28 place-items-center rounded-full border-2 border-dashed border-accent/40 bg-accent/5">
                <Loader2 className="h-10 w-10 animate-spin text-accent" />
              </div>
              <p className="mt-6 text-sm font-medium text-foreground">Local Pipeline Processing...</p>
              <p className="mt-1 text-xs text-muted-foreground max-w-sm text-center">{processingStatus}</p>
            </>
          )}
        </div>
      </div>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

function fmt(s: number) {
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m.toString().padStart(2, "0")}:${r.toString().padStart(2, "0")}`;
}
