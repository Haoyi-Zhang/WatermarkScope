const stages = {
  codemarkbench: {
    kind: "shared benchmark support",
    title: "CodeMarkBench",
    summary: "Executable benchmark support for fixed source-code watermark evaluation surfaces.",
    denominator: "140 canonical run-completion records",
    observed: "140/140 canonical runs completed",
    allowed: "Benchmark support for the released executable stress matrix.",
    boundary: "Not a universal result over all watermarking methods."
  },
  semcodebook: {
    kind: "white-box provenance recovery",
    title: "SemCodebook",
    summary: "Structured provenance recovery in admitted white-box model and scale cells.",
    denominator: "31,200 positives; 62,400 fixed controls; 62,400 blind replay rows",
    observed: "30,330/31,200 positives; 0/62,400 fixed controls; 0/62,400 blind replay",
    allowed: "Structured provenance recovery within the admitted white-box family.",
    boundary: "Not a universal semantic watermarking or first-sample natural-generation guarantee."
  },
  codedye: {
    kind: "black-box null-audit",
    title: "CodeDye",
    summary: "Conservative curator-side audit surface with role-separated controls.",
    denominator: "3,600 DeepSeek live rows over 1,200 pre-separated memory-probe triads",
    observed: "0/300 fresh live signal; 272/300 positive memory calibration; 0/300 negative controls; 0/300 retrieval-confound controls",
    allowed: "Active audit/calibration surface with preserved null-audit evidence.",
    boundary: "Not contamination prevalence, provider accusation, high-recall detection, or proof of absence."
  },
  probetrace: {
    kind: "active-owner verification",
    title: "ProbeTrace",
    summary: "Source-bound commitment and witness verification with false-owner controls.",
    denominator: "6,000 DeepSeek five-owner commitment/witness rows",
    observed: "750/750 true-owner positives; 0/5,250 wrong/null/random/same-provider controls",
    allowed: "Scoped DeepSeek-only active-owner verification under the evaluated registry and split.",
    boundary: "Not provider-general authorship proof, cross-provider attribution, or unbounded transfer."
  },
  sealaudit: {
    kind: "security triage",
    title: "SealAudit",
    summary: "Marker-hidden security-relevant selective triage with explicit abstention.",
    denominator: "960 marker-hidden claim rows over 320 cases",
    observed: "320/960 decisive rows; 0/960 provider-flag unsafe-pass rows",
    allowed: "Conservative marker-hidden selective triage and coverage-risk frontier.",
    boundary: "Not an automatic safety classifier, harmlessness certificate, or security certificate."
  }
};

document.documentElement.classList.add("motion-ready");

const buttons = Array.from(document.querySelectorAll(".stage"));
const fields = {
  kind: document.getElementById("stageKind"),
  title: document.getElementById("stageTitle"),
  summary: document.getElementById("stageSummary"),
  denominator: document.getElementById("stageDenominator"),
  observed: document.getElementById("stageObserved"),
  allowed: document.getElementById("stageAllowed"),
  boundary: document.getElementById("stageBoundary")
};

function setStage(key) {
  const data = stages[key];
  if (!data) return;

  buttons.forEach((button) => {
    const active = button.dataset.stage === key;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });

  fields.kind.textContent = data.kind;
  fields.title.textContent = data.title;
  fields.summary.textContent = data.summary;
  fields.denominator.textContent = data.denominator;
  fields.observed.textContent = data.observed;
  fields.allowed.textContent = data.allowed;
  fields.boundary.textContent = data.boundary;
}

buttons.forEach((button) => {
  button.setAttribute("aria-pressed", button.classList.contains("active") ? "true" : "false");
  button.addEventListener("click", () => setStage(button.dataset.stage));
});

const revealItems = Array.from(document.querySelectorAll(".reveal"));

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  revealItems.forEach((item) => observer.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("visible"));
}
