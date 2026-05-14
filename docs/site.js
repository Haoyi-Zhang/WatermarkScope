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
    summary: "Structured provenance recovery in the submitted FYP snapshot.",
    denominator: "24,000 positive recovery rows and 48,000 negative-control rows",
    observed: "23,342/24,000 positive recoveries; 0/48,000 negative-control hits",
    allowed: "Structured provenance recovery within the admitted white-box family.",
    boundary: "Not a universal semantic watermarking or first-sample natural-generation guarantee."
  },
  codedye: {
    kind: "black-box null-audit",
    title: "CodeDye",
    summary: "Conservative black-box audit surface with positive and negative controls.",
    denominator: "300 live audit samples, 300 positive controls, and 300 negative controls",
    observed: "6/300 sparse live signals; 170/300 positive controls; 0/300 negative controls",
    allowed: "Preserved null-audit evidence under a finite black-box surface.",
    boundary: "Not contamination prevalence, provider accusation, high-recall detection, or proof of absence."
  },
  probetrace: {
    kind: "active-owner verification",
    title: "ProbeTrace",
    summary: "Source-bound commitment and witness verification with false-owner controls.",
    denominator: "300 scoped owner decisions and 1,200 false-owner controls",
    observed: "300/300 scoped decisions; 0/1,200 false-owner controls",
    allowed: "Scoped active-owner attribution under the evaluated registry and split.",
    boundary: "Not provider-general authorship proof, cross-provider attribution, or unbounded transfer."
  },
  sealaudit: {
    kind: "security triage",
    title: "SealAudit",
    summary: "Marker-hidden security-relevant selective triage with explicit abstention.",
    denominator: "960 marker-hidden triage rows in the submitted FYP snapshot",
    observed: "81/960 decisive outcomes; 0 observed unsafe passes",
    allowed: "Conservative marker-hidden selective triage with explicit abstention.",
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
