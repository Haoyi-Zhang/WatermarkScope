const repoBase = "https://github.com/Haoyi-Zhang/WatermarkScope";
const submittedRef = "e0851409c3fe14d1813b714ff9b2d1fa2da965cb";
const repoTree = `${repoBase}/tree/${submittedRef}`;
const repoBlob = `${repoBase}/blob/${submittedRef}`;

const contractFacts = {
  denominator: {
    label: "What is counted?",
    title: "A result only means something after the denominator is fixed.",
    text: "For example, SemCodebook reports 30,330 recoveries over 31,200 admitted positive rows. Misses remain inside the denominator; they are not hidden by the aggregate."
  },
  controls: {
    label: "What would fail?",
    title: "Controls decide whether a signal is evidence or a shortcut.",
    text: "The main results are paired with negative controls, false-owner controls, or unsafe-pass tracking. Zero observed events are reported as finite-sample evidence, not as zero risk."
  },
  artifact: {
    label: "Can it be inspected?",
    title: "A viva claim should point to code, manifests, and preserved result files.",
    text: "The repository route is README, claim boundaries, traceability matrix, result manifest, and viva_check.py. This makes the work inspectable without rerunning all expensive experiments live."
  },
  access: {
    label: "What access is assumed?",
    title: "Changing access changes the claim.",
    text: "White-box provenance recovery, black-box null audit, active-owner verification, and marker-hidden triage are different evidence questions. They should not be collapsed into one detector score."
  },
  boundary: {
    label: "What is forbidden?",
    title: "The boundary prevents the result from becoming broader than the evidence.",
    text: "The framework explicitly forbids universal watermarking, provider accusation, general authorship proof, and safety certification unless a new admitted surface supports those claims."
  }
};

const submittedResults = [
  {
    name: "CodeMarkBench",
    tag: "Executable benchmark",
    result: "140/140",
    denominator: "4 baselines x 5 local code models x 7 source groups",
    controls: "Canonical run-completion inventory before interpretation",
    claim: "The benchmark foundation is executable and countable.",
    boundary: "This is benchmark support, not watermark success.",
    accent: "blue"
  },
  {
    name: "SemCodebook",
    tag: "White-box provenance",
    result: "30,330/31,200",
    denominator: "31,200 positive rows; 62,400 fixed negatives; 62,400 blind replay negatives",
    controls: "0/62,400 fixed negative-control hits and 0/62,400 blind replay hits",
    claim: "Structured provenance recovery within admitted white-box cells.",
    boundary: "Not universal natural-generation watermarking.",
    accent: "cyan"
  },
  {
    name: "CodeDye",
    tag: "Black-box null audit",
    result: "4/300",
    denominator: "300 live audit samples, 300 positive controls, 300 negative controls",
    controls: "170/300 positive controls and 0/300 negative controls",
    claim: "Conservative sparse black-box audit evidence.",
    boundary: "Not prevalence, provider accusation, high-recall detection, or proof of absence.",
    accent: "violet"
  },
  {
    name: "ProbeTrace",
    tag: "Active-owner attribution",
    result: "6,000 rows",
    denominator: "Five-owner DeepSeek commitment/witness surface",
    controls: "750/750 true-owner positives and 0/5,250 false-attribution controls",
    claim: "Scoped active-owner commitment and witness verification.",
    boundary: "Not provider-general or cross-provider authorship proof.",
    accent: "amber"
  },
  {
    name: "SealAudit",
    tag: "Security triage",
    result: "320/960",
    denominator: "960 marker-hidden triage rows",
    controls: "0/960 observed unsafe passes; nondecisive rows retained as review load",
    claim: "Selective marker-hidden triage with explicit abstention.",
    boundary: "Not an automatic safety classifier or harmlessness certificate.",
    accent: "green"
  }
];

const stages = {
  codemarkbench: {
    question: "Can we evaluate code watermarking on executable benchmark rows?",
    plain: "CodeMarkBench fixes the benchmark denominator before any detector interpretation.",
    contribution: "Executable benchmark denominator.",
    denominator: "4 baselines x 5 local code models x 7 source groups = 140 canonical runs.",
    observed: "140/140 canonical runs completed.",
    boundary: "Run completion is benchmark support, not watermark success.",
    speak: "This stage is the foundation: before comparing watermark methods, I first make the benchmark rows executable and countable.",
    links: [
      ["Code snapshot", `${repoTree}/projects/CodeMarkBench`],
      ["Result tables", `${repoTree}/projects/CodeMarkBench/results/tables/suite_all_models_methods`],
      ["Dissertation appendix", `${repoTree}/dissertation/latex/appendix`]
    ]
  },
  semcodebook: {
    question: "Can we recover provenance when local white-box carrier evidence exists?",
    plain: "SemCodebook is the main method contribution: structured carriers over program representations, with recovery and controls reported separately.",
    contribution: "Typed carriers over AST, CFG, and SSA structure, with keyed scheduling and recovery logic.",
    denominator: "31,200 positives, 62,400 fixed negatives, and 62,400 blind replay negatives.",
    observed: "30,330/31,200 recoveries; 0/62,400 fixed hits; 0/62,400 blind replay hits.",
    boundary: "White-box admitted-cell provenance, not universal semantic watermarking.",
    speak: "The important point is not just a high recovery rate. The important point is that the misses and the negative controls stay inside the admitted evidence surface.",
    links: [
      ["Implementation", `${repoTree}/projects/SemCodebook`],
      ["Result artifacts", `${repoTree}/results/SemCodebook/artifacts/generated`],
      ["Method index", `${repoBlob}/docs/METHOD_INDEX.md`]
    ]
  },
  codedye: {
    question: "What can still be claimed when only black-box audit transcripts exist?",
    plain: "CodeDye keeps a conservative null-audit surface instead of turning sparse evidence into a provider accusation.",
    contribution: "Hash-bound black-box audit evidence with positive and negative controls.",
    denominator: "300 live audit samples, 300 positive controls, and 300 negative controls.",
    observed: "4/300 sparse live signals; 170/300 positive controls; 0/300 negative controls.",
    boundary: "Not contamination prevalence, high-recall detection, provider accusation, or proof of absence.",
    speak: "A sparse signal is still useful if it tells us what not to claim. Here the correct claim is conservative audit evidence, not prevalence.",
    links: [
      ["Implementation", `${repoTree}/projects/CodeDye`],
      ["Result artifacts", `${repoTree}/results/CodeDye/artifacts/generated`],
      ["Claim boundaries", `${repoBlob}/CLAIM_BOUNDARIES.md`]
    ]
  },
  probetrace: {
    question: "Can an active owner make a scoped source claim under a fixed registry?",
    plain: "ProbeTrace treats attribution as commitment and witness verification, not as open-ended authorship inference.",
    contribution: "Five-owner source-bound commitment/witness verification with false-owner controls.",
    denominator: "6,000 five-owner rows with 5,250 false-attribution controls.",
    observed: "750/750 true-owner positives and 0/5,250 false-attribution controls.",
    boundary: "Scoped DeepSeek-only owner evidence, not provider-general authorship proof.",
    speak: "The perfect-looking true-owner result is not presented as universal authorship. It is read together with the false-owner controls and the fixed registry.",
    links: [
      ["Implementation", `${repoTree}/projects/ProbeTrace`],
      ["Result artifacts", `${repoTree}/results/ProbeTrace/artifacts/generated`],
      ["Traceability", `${repoBlob}/docs/TRACEABILITY_MATRIX.md`]
    ]
  },
  sealaudit: {
    question: "Should watermark evidence trigger security review instead of automatic acceptance?",
    plain: "SealAudit treats marker-hidden evidence as a triage problem and keeps ambiguous rows as review load.",
    contribution: "Marker-hidden selective triage with abstention and unsafe-pass accounting.",
    denominator: "960 marker-hidden triage rows.",
    observed: "320/960 decisive outcomes and 0/960 unsafe passes.",
    boundary: "Selective triage, not an automatic safety classifier or security certificate.",
    speak: "For this stage, abstention is not a failure of presentation. It is part of the design because forced labels would make the claim less honest.",
    links: [
      ["Implementation", `${repoTree}/projects/SealAudit`],
      ["Result artifacts", `${repoTree}/results/SealAudit/artifacts/generated`],
      ["Results summary", `${repoBlob}/docs/RESULTS_SUMMARY.md`]
    ]
  }
};

const futureTracks = [
  {
    name: "WatermarkScope",
    route: "Submitted FYP marking surface",
    repo: "https://github.com/Haoyi-Zhang/WatermarkScope",
    status: "Use for viva and dissertation alignment.",
    note: "This page is the main presentation interface."
  },
  {
    name: "CodeMarkBench",
    route: "TOSEM-oriented benchmark track",
    repo: "https://github.com/Haoyi-Zhang/CodeMarkBench",
    status: "Continuation benchmark infrastructure.",
    note: "Future expansion must create new admitted benchmark surfaces."
  },
  {
    name: "SemCodebook",
    route: "EMNLP-oriented method track",
    repo: "https://github.com/Haoyi-Zhang/SemCodebook",
    status: "Continuation commit 69efebc.",
    note: "New cells should not rewrite the submitted denominator."
  },
  {
    name: "CodeDye",
    route: "EMNLP-oriented audit track",
    repo: "https://github.com/Haoyi-Zhang/CodeDye",
    status: "Continuation commit e8f9df3.",
    note: "Provider-specific black-box surfaces remain separately admitted."
  },
  {
    name: "ProbeTrace",
    route: "EMNLP-oriented attribution track",
    repo: "https://github.com/Haoyi-Zhang/ProbeTrace",
    status: "Continuation commit 9e459d4.",
    note: "Registry expansion needs new owner and control gates."
  },
  {
    name: "SealAudit",
    route: "EMNLP-oriented triage track",
    repo: "https://github.com/Haoyi-Zhang/SealAudit",
    status: "Continuation commit 039275d.",
    note: "Coverage updates require preserving unsafe-pass accounting."
  }
];

const resultLedger = document.getElementById("resultLedger");

if (resultLedger) {
  resultLedger.innerHTML = submittedResults.map((item, index) => `
    <article class="result-card ${item.accent}" data-result="${index}">
      <div class="result-main">
        <span>${item.tag}</span>
        <h3>${item.name}</h3>
        <strong>${item.result}</strong>
      </div>
      <dl>
        <div>
          <dt>Submitted denominator</dt>
          <dd>${item.denominator}</dd>
        </div>
        <div>
          <dt>Controls / accounting</dt>
          <dd>${item.controls}</dd>
        </div>
        <div>
          <dt>Allowed claim</dt>
          <dd>${item.claim}</dd>
        </div>
        <div>
          <dt>Boundary</dt>
          <dd>${item.boundary}</dd>
        </div>
      </dl>
    </article>
  `).join("");
}

const contractButtons = Array.from(document.querySelectorAll(".contract-chip"));
const contractLabel = document.getElementById("contractLabel");
const contractTitle = document.getElementById("contractTitle");
const contractText = document.getElementById("contractText");

function setContract(key) {
  const data = contractFacts[key];
  if (!data) return;
  contractButtons.forEach((button) => {
    const active = button.dataset.contract === key;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  contractLabel.textContent = data.label;
  contractTitle.textContent = data.title;
  contractText.textContent = data.text;
}

contractButtons.forEach((button) => {
  button.setAttribute("aria-pressed", button.classList.contains("active") ? "true" : "false");
  button.addEventListener("click", () => setContract(button.dataset.contract));
});

const stageButtons = Array.from(document.querySelectorAll(".stage-tab"));
const stageFields = {
  question: document.getElementById("stageQuestion"),
  plain: document.getElementById("stagePlain"),
  contribution: document.getElementById("stageContribution"),
  denominator: document.getElementById("stageDenominator"),
  observed: document.getElementById("stageObserved"),
  boundary: document.getElementById("stageBoundary"),
  speak: document.getElementById("stageSpeak"),
  links: document.getElementById("stageLinks")
};

function setStage(key) {
  const data = stages[key];
  if (!data) return;
  stageButtons.forEach((button) => {
    const active = button.dataset.stage === key;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  stageFields.question.textContent = data.question;
  stageFields.plain.textContent = data.plain;
  stageFields.contribution.textContent = data.contribution;
  stageFields.denominator.textContent = data.denominator;
  stageFields.observed.textContent = data.observed;
  stageFields.boundary.textContent = data.boundary;
  stageFields.speak.textContent = data.speak;
  stageFields.links.innerHTML = data.links.map(([label, href]) => `<a href="${href}">${label}</a>`).join("");
}

stageButtons.forEach((button) => {
  button.setAttribute("aria-pressed", button.classList.contains("active") ? "true" : "false");
  button.addEventListener("click", () => setStage(button.dataset.stage));
});

const futureGrid = document.getElementById("futureGrid");

if (futureGrid) {
  futureGrid.innerHTML = futureTracks.map((track) => `
    <article>
      <span>${track.route}</span>
      <h3>${track.name}</h3>
      <p>${track.status}</p>
      <em>${track.note}</em>
      <a href="${track.repo}">Open repository</a>
    </article>
  `).join("");
}

const steps = Array.from(document.querySelectorAll(".viva-step"));
const currentStep = document.getElementById("currentStep");
const routeLinks = Array.from(document.querySelectorAll(".route-nav a"));

function updateCurrentStep(id) {
  const step = steps.find((section) => section.id === id);
  if (step && currentStep) currentStep.textContent = step.dataset.step || step.id;
  routeLinks.forEach((link) => link.classList.toggle("active", link.getAttribute("href") === `#${id}`));
}

if ("IntersectionObserver" in window) {
  const sectionObserver = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (visible) updateCurrentStep(visible.target.id);
  }, { threshold: [0.32, 0.5, 0.68] });
  steps.forEach((section) => sectionObserver.observe(section));
}

const scrollMeter = document.getElementById("scrollMeter");

function updateScrollMeter() {
  if (!scrollMeter) return;
  const max = document.documentElement.scrollHeight - window.innerHeight;
  const progress = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
  scrollMeter.style.transform = `scaleX(${progress})`;
}

window.addEventListener("scroll", updateScrollMeter, { passive: true });
window.addEventListener("resize", updateScrollMeter);
updateScrollMeter();

window.addEventListener("load", () => {
  if (!window.location.hash) return;
  const target = document.querySelector(window.location.hash);
  if (target) {
    requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
  }
});

function scrollToRelativeStep(direction) {
  const offsets = steps.map((section) => ({
    id: section.id,
    top: Math.abs(section.getBoundingClientRect().top)
  }));
  const current = offsets.sort((a, b) => a.top - b.top)[0];
  const index = steps.findIndex((section) => section.id === current.id);
  const target = steps[Math.min(steps.length - 1, Math.max(0, index + direction))];
  if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
}

document.getElementById("nextStep")?.addEventListener("click", () => scrollToRelativeStep(1));
document.getElementById("prevStep")?.addEventListener("click", () => scrollToRelativeStep(-1));

const presenterButton = document.getElementById("presenterMode");

presenterButton?.addEventListener("click", () => {
  const active = document.body.classList.toggle("presenter");
  presenterButton.setAttribute("aria-pressed", String(active));
  presenterButton.textContent = active ? "Exit presenter" : "Presenter mode";
});

document.addEventListener("keydown", (event) => {
  if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
  if (event.key.toLowerCase() === "n" || event.key === "ArrowDown") scrollToRelativeStep(1);
  if (event.key.toLowerCase() === "p" || event.key === "ArrowUp") scrollToRelativeStep(-1);
});

document.getElementById("copyCommand")?.addEventListener("click", async (event) => {
  const command = document.getElementById("checkCommand")?.textContent?.trim();
  if (!command || !navigator.clipboard) return;
  await navigator.clipboard.writeText(command);
  event.currentTarget.textContent = "Copied";
  setTimeout(() => {
    event.currentTarget.textContent = "Copy command";
  }, 1500);
});
