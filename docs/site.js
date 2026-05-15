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

const continuationTracks = [
  {
    name: "CodeMarkBench",
    route: "Software-engineering venue",
    repo: "https://github.com/Haoyi-Zhang/CodeMarkBench",
    commit: "3252ca4",
    snapshot: "140/140 canonical runs",
    progress: "Public benchmark infrastructure",
    next: "External reruns and broader stress taxonomy",
    value: 100,
    accent: "blue"
  },
  {
    name: "SemCodebook",
    route: "EMNLP-oriented paper",
    repo: "https://github.com/Haoyi-Zhang/SemCodebook",
    commit: "69efebc",
    snapshot: "23,342/24,000 recoveries",
    progress: "30,330/31,200; 0/62,400 x2 controls",
    next: "New admitted cells, ablations, and positioning",
    value: 97,
    accent: "cyan"
  },
  {
    name: "CodeDye",
    route: "EMNLP-oriented paper",
    repo: "https://github.com/Haoyi-Zhang/CodeDye",
    commit: "e8f9df3",
    snapshot: "6/300 live signals",
    progress: "0/300 fresh; 272/300 calibration",
    next: "Provider-specific frozen surfaces",
    value: 1,
    accent: "violet"
  },
  {
    name: "ProbeTrace",
    route: "EMNLP-oriented paper",
    repo: "https://github.com/Haoyi-Zhang/ProbeTrace",
    commit: "9e459d4",
    snapshot: "300/300 scoped decisions",
    progress: "750/750 true; 0/5,250 false",
    next: "Registry expansion and margin evidence",
    value: 100,
    accent: "amber"
  },
  {
    name: "SealAudit",
    route: "EMNLP-oriented paper",
    repo: "https://github.com/Haoyi-Zhang/SealAudit",
    commit: "039275d",
    snapshot: "81/960 decisive rows",
    progress: "320/960 decisive; 0/960 unsafe",
    next: "Second-stage coverage with unsafe-pass accounting",
    value: 33,
    accent: "green"
  }
];

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

const trackGrid = document.getElementById("continuationTracks");

if (trackGrid) {
  continuationTracks.forEach((track) => {
    const article = document.createElement("article");
    article.className = `track-card ${track.accent}`;
    article.innerHTML = `
      <div class="track-head">
        <span>${track.route}</span>
        <a href="${track.repo}" aria-label="Open ${track.name} repository">${track.commit}</a>
      </div>
      <h3>${track.name}</h3>
      <div class="track-bars" aria-label="${track.name} submitted and continuation status">
        <div>
          <span>Submitted snapshot</span>
          <strong>${track.snapshot}</strong>
        </div>
        <div class="meter"><i style="width: ${track.value}%"></i></div>
        <div>
          <span>Continuation progress</span>
          <strong>${track.progress}</strong>
        </div>
      </div>
      <p>${track.next}</p>
      <a class="track-link" href="${track.repo}">Repository</a>
    `;
    trackGrid.appendChild(article);
  });
}

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
