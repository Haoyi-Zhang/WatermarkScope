const repoBase = "https://github.com/Haoyi-Zhang/WatermarkScope";
const submittedRef = "main";
const repoTree = `${repoBase}/tree/${submittedRef}`;
const repoBlob = `${repoBase}/blob/${submittedRef}`;

const contractFacts = {
  denominator: {
    label: "What is counted?",
    title: "A result only means something after the denominator is fixed.",
    text: "For example, the submitted SemCodebook surface reports 23,342 recoveries over 24,000 admitted positive rows. The misses remain inside the denominator, so the result is easier to inspect."
  },
  controls: {
    label: "What would fail?",
    title: "Controls decide whether a signal is evidence or a shortcut.",
    text: "The main results are paired with negative controls, false-owner controls, or unsafe-pass tracking. Zero observed events are reported as finite-sample evidence, not as zero risk."
  },
  artifact: {
    label: "Can it be inspected?",
    title: "A defended claim should point to code, manifests, and preserved result files.",
    text: "The repository route is README, claim boundaries, traceability matrix, result manifest, and viva_check.py. It supports live inspection without requiring an expensive full experimental rerun in the room."
  },
  access: {
    label: "What access is assumed?",
    title: "Changing access changes the claim.",
    text: "White-box provenance recovery, black-box null audit, active-owner verification, and marker-hidden triage are different evidence questions. They should not be collapsed into one detector score."
  },
  boundary: {
    label: "What is forbidden?",
    title: "The boundary prevents the result from becoming broader than the evidence.",
    text: "The framework explicitly blocks unsupported claims: no universal watermarking claim, no provider accusation, no general authorship proof, and no safety certificate unless a new admitted surface supports it."
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
    oral: "This comes first because code watermark evaluation must start from executable rows, not only text similarity.",
    meter: 100,
    meterLabel: "completed",
    controlLabel: "inventory locked",
    accent: "blue"
  },
  {
    name: "SemCodebook",
    tag: "White-box provenance",
    result: "23.3k/24k",
    exact: "23,342/24,000",
    denominator: "24,000 positive rows and 48,000 negative-control rows",
    controls: "0/48,000 negative-control hits",
    claim: "Structured provenance recovery within admitted white-box cells.",
    boundary: "Not universal natural-generation watermarking.",
    oral: "This is the main method contribution: recoveries, misses, and two negative surfaces are reported together.",
    meter: 97.3,
    meterLabel: "recovered",
    controlLabel: "0 fixed / 0 blind hits",
    accent: "cyan"
  },
  {
    name: "CodeDye",
    tag: "Black-box null audit",
    result: "6/300",
    denominator: "300 live audit samples, 300 positive controls, 300 negative controls",
    controls: "170/300 positive controls and 0/300 negative controls",
    claim: "Conservative sparse black-box audit evidence.",
    boundary: "Not prevalence, provider accusation, high-recall detection, or proof of absence.",
    oral: "The sparse signal supports a conservative audit claim, not a contamination-prevalence claim.",
    meter: 2,
    meterLabel: "sparse signal",
    controlLabel: "0/300 negative controls",
    accent: "violet"
  },
  {
    name: "ProbeTrace",
    tag: "Active-owner attribution",
    result: "300/300",
    denominator: "300 scoped active-owner decisions and 1,200 false-owner controls",
    controls: "300/300 scoped decisions and 0/1,200 false-owner controls",
    claim: "Scoped active-owner commitment and witness verification.",
    boundary: "Not provider-general or cross-provider authorship proof.",
    oral: "The strong positive result is bounded by false-owner controls and a fixed owner registry.",
    meter: 100,
    meterLabel: "true owner",
    controlLabel: "0 false-attribution hits",
    accent: "amber"
  },
  {
    name: "SealAudit",
    tag: "Security triage",
    result: "81/960",
    denominator: "960 marker-hidden triage rows",
    controls: "0 observed unsafe passes; nondecisive rows retained as review load",
    claim: "Selective marker-hidden triage with explicit abstention.",
    boundary: "Not an automatic safety classifier or harmlessness certificate.",
    oral: "For security-facing evidence, abstention is part of the design because forced labels would overstate the evidence.",
    meter: 8.4,
    meterLabel: "decisive",
    controlLabel: "0 unsafe passes",
    accent: "green"
  }
];

const problemFacts = {
  execution: {
    title: "The original prompt session is not enough.",
    text: "This is why provenance is treated as an evidence problem: after code is copied or edited, the claim needs an artifact and a boundary, not just a detector score."
  },
  access: {
    title: "Executable rows protect the denominator.",
    text: "For code, the benchmark row must be runnable and countable before any watermark signal is interpreted."
  },
  abstention: {
    title: "Different access models need different claims.",
    text: "White-box recovery, black-box audit, active-owner attribution, and security triage answer different questions, so their claims stay separate."
  }
};

const demoFacts = {
  readme: {
    title: "Start with the repository README.",
    text: "The README defines the submitted FYP surface and the route into deeper artifacts."
  },
  boundaries: {
    title: "Then show the claim boundaries.",
    text: "This document states both the allowed claim and the forbidden interpretation."
  },
  traceability: {
    title: "Traceability connects claims to files.",
    text: "Each module is connected to code paths, result paths, and a safe interpretation."
  },
  manifest: {
    title: "The manifest preserves evidence records.",
    text: "This shows the evidence is not just prose on the page; rows are recorded and hash-addressed for inspection."
  },
  check: {
    title: "Finish with the lightweight evidence check.",
    text: "This verifies repository consistency and artifact presence; it is not a replacement for the full GPU/API experiments."
  }
};

const evidenceDemoTimeline = [
  {
    key: "readme",
    at: 0,
    line: "[demo] Open README: submitted FYP surface and inspection route."
  },
  {
    key: "boundaries",
    at: 2.4,
    line: "[demo] Check CLAIM_BOUNDARIES.md: allowed claim and forbidden wording."
  },
  {
    key: "traceability",
    at: 4.8,
    line: "[demo] Check TRACEABILITY_MATRIX.md: claim -> code -> artifact."
  },
  {
    key: "manifest",
    at: 7.2,
    line: "[demo] Inspect RESULT_MANIFEST.jsonl: hash-addressed evidence rows."
  },
  {
    key: "check",
    at: 9.6,
    line: "[demo] Run viva_check.py: lightweight repository consistency check."
  },
  {
    key: "check",
    at: 11.6,
    line: "[OK] Evidence check passed. Full experiments are not rerun live."
  }
];

const evidenceDemoDuration = 12;

const autoDemoPlan = [
  {
    id: "top",
    duration: 45,
    title: "Opening",
    cue: "Start with the one-sentence story: watermarking is evidence, not one detector score.",
    next: "Problem"
  },
  {
    id: "problem",
    duration: 75,
    title: "Problem",
    cue: "Explain why generated code loses context after reuse, and why code has to remain executable.",
    next: "Method",
    actions: [
      { at: 10, type: "problem", key: "execution" },
      { at: 34, type: "problem", key: "access" },
      { at: 58, type: "problem", key: "abstention" }
    ]
  },
  {
    id: "contract",
    duration: 105,
    title: "Method",
    cue: "Use the contract: denominator, controls, artifact, access model, and boundary.",
    next: "Results",
    actions: [
      { at: 8, type: "contract", key: "denominator" },
      { at: 28, type: "contract", key: "controls" },
      { at: 48, type: "contract", key: "artifact" },
      { at: 68, type: "contract", key: "access" },
      { at: 88, type: "contract", key: "boundary" }
    ]
  },
  {
    id: "snapshot",
    duration: 120,
    title: "Submitted results",
    cue: "Do not read every table. Say what each number can safely support.",
    next: "Evidence demo",
    actions: [
      { at: 4, type: "result", index: 0 },
      { at: 28, type: "result", index: 1 },
      { at: 56, type: "result", index: 2 },
      { at: 80, type: "result", index: 3 },
      { at: 102, type: "result", index: 4 }
    ]
  },
  {
    id: "demo",
    duration: 90,
    title: "Evidence demo",
    cue: "This is an inspectability demo, not a full rerun. Follow the evidence route.",
    next: "Future",
    actions: [
      { at: 0, type: "demo", key: "readme" },
      { at: 18, type: "demo", key: "boundaries" },
      { at: 36, type: "demo", key: "traceability" },
      { at: 54, type: "demo", key: "manifest" },
      { at: 72, type: "demo", key: "check" },
      { at: 84, type: "terminal-final" }
    ]
  },
  {
    id: "future",
    duration: 45,
    title: "Future work",
    cue: "Keep this short: future repositories are separate paper tracks, not changes to the submitted FYP.",
    next: "Q&A",
    actions: [
      { at: 2, type: "future", index: 0 },
      { at: 10, type: "future", index: 1 },
      { at: 18, type: "future", index: 2 },
      { at: 26, type: "future", index: 3 },
      { at: 34, type: "future", index: 4 }
    ]
  },
  {
    id: "qa",
    duration: 15,
    title: "Q&A landing",
    cue: "Stop here. Answer directly, give one evidence number, then state the boundary.",
    next: "Q&A hold",
    actions: [
      { at: 2, type: "qa", key: "broad" },
      { at: 7, type: "qa", key: "rerun" }
    ]
  },
  {
    id: "qa",
    duration: 105,
    title: "Q&A hold",
    cue: "Stay on this page. Use the answer rule and let the examiner lead.",
    next: "Finished"
  }
];

const qaFacts = {
  broad: {
    title: "Is this too broad for one FYP?",
    answer: "It is broad in modules, but narrow in principle: every stage follows the same evidence contract. The defended surface is the submitted FYP, not five final papers."
  },
  stages: {
    title: "Why do you need five stages?",
    answer: "Because access changes the claim. White-box recovery, black-box audit, owner attribution, and triage cannot honestly share one accuracy score."
  },
  rerun: {
    title: "Why not rerun everything live?",
    answer: "A full rerun needs GPUs, model weights, or provider APIs. The defensible live evidence is inspectability: repository, claim boundaries, traceability, manifest, and the quick check."
  },
  generalize: {
    title: "Can the result generalize?",
    answer: "Possibly, but a broader claim needs a new admitted surface. The correct next step is to add model cells and report them separately."
  },
  sparse: {
    title: "Is CodeDye too sparse?",
    answer: "It would be too sparse for a high-recall detector claim. My claim is conservative black-box audit evidence: 6/300 live signals with 0/300 negative controls."
  },
  code: {
    title: "Where is the code evidence?",
    answer: "The submitted repository is the defended artifact. The strongest live route is README, CLAIM_BOUNDARIES.md, TRACEABILITY_MATRIX.md, RESULT_MANIFEST.jsonl, then viva_check.py."
  }
};

const stages = {
  codemarkbench: {
    question: "Can we evaluate code watermarking on executable benchmark rows?",
    plain: "CodeMarkBench fixes the benchmark denominator before any detector interpretation.",
    contribution: "Executable benchmark denominator.",
    denominator: "4 baselines x 5 local code models x 7 source groups = 140 canonical runs.",
    observed: "140/140 canonical runs completed.",
    boundary: "Run completion is benchmark support, not watermark success.",
    speak: "This stage is the foundation: before comparing watermark methods, the benchmark rows are made executable and countable.",
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
    denominator: "24,000 positives and 48,000 negative-control rows.",
    observed: "23,342/24,000 recoveries and 0/48,000 negative-control hits.",
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
    observed: "6/300 sparse live signals; 170/300 positive controls; 0/300 negative controls.",
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
    denominator: "300 scoped active-owner decisions with 1,200 false-owner controls.",
    observed: "300/300 scoped decisions and 0/1,200 false-owner controls.",
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
    observed: "81/960 decisive outcomes and 0 observed unsafe passes.",
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
    key: "codemarkbench",
    name: "CodeMarkBench",
    route: "Benchmark foundation",
    venue: "EMNLP Findings / ARR resource track",
    repo: "https://github.com/Haoyi-Zhang/CodeMarkBench",
    visibility: "Continuation artifact",
    status: "Benchmark expansion with separately admitted denominators.",
    focus: "Task suites, release metadata, and admitted benchmark surfaces.",
    boundary: "Any new benchmark cell must be admitted as a new surface; it does not change the 140/140 submitted FYP denominator.",
    review: ["Repository", "Task suites", "New denominator rule"]
  },
  {
    key: "semcodebook",
    name: "SemCodebook",
    route: "White-box method",
    venue: "EMNLP Main / ACL Main",
    repo: "https://github.com/Haoyi-Zhang/SemCodebook",
    visibility: "Continuation artifact",
    status: "Structured provenance recovery beyond the submitted FYP slice.",
    focus: "Carrier/recovery pipeline and negative-control replay gates.",
    boundary: "Extra cells are future evidence. They should be reported separately from the submitted 23,342/24,000 FYP recovery surface.",
    review: ["Repository", "Carrier pipeline", "Negative controls"]
  },
  {
    key: "codedye",
    name: "CodeDye",
    route: "Black-box audit",
    venue: "Findings / audit workshop",
    repo: "https://github.com/Haoyi-Zhang/CodeDye",
    visibility: "Continuation artifact",
    status: "Conservative black-box null-audit evidence.",
    focus: "Audit scripts, role-separated controls, and non-accusation boundary.",
    boundary: "The claim remains null-audit evidence, not prevalence, wrongdoing proof, or absence proof.",
    review: ["Repository", "Audit scripts", "Control design"]
  },
  {
    key: "probetrace",
    name: "ProbeTrace",
    route: "Owner attribution",
    venue: "EMNLP / USENIX-style crossover",
    repo: "https://github.com/Haoyi-Zhang/ProbeTrace",
    visibility: "Continuation artifact",
    status: "Scoped owner verification with commitment/witness evidence.",
    focus: "Owner registry, split, and false-owner controls.",
    boundary: "It is scoped owner verification, not universal authorship proof or cross-provider attribution.",
    review: ["Repository", "Owner registry", "False-owner controls"]
  },
  {
    key: "sealaudit",
    name: "SealAudit",
    route: "Security triage",
    venue: "Responsible NLP / safety track",
    repo: "https://github.com/Haoyi-Zhang/SealAudit",
    visibility: "Continuation artifact",
    status: "Marker-hidden selective security triage.",
    focus: "Decision packets, abstention, and unsafe-pass accounting.",
    boundary: "It is selective triage, not a classifier, safety certificate, or automatic harmlessness guarantee.",
    review: ["Repository", "Triage pipeline", "Abstention rule"]
  }
];

const resultLedger = document.getElementById("resultLedger");

if (resultLedger) {
  resultLedger.innerHTML = submittedResults.map((item, index) => `
    <article class="result-card ${item.accent}" data-result="${index}" tabindex="0" role="button" aria-pressed="false">
      <div class="result-main">
        <span>${item.tag}</span>
        <h3>${item.name}</h3>
        <strong>${item.result}</strong>
      </div>
      <div class="result-meter" aria-label="${item.name} ${item.meterLabel}">
        <i style="--value: ${item.meter}%"></i>
      </div>
      <div class="result-badges">
        <b>${item.meterLabel}</b>
        <b>${item.controlLabel}</b>
      </div>
      <p class="result-claim">${item.claim}</p>
    </article>
  `).join("");
}

const resultFocus = document.getElementById("resultFocus");
const resultCards = Array.from(document.querySelectorAll(".result-card"));

function setResultFocus(index) {
  const data = submittedResults[index];
  if (!data || !resultFocus) return;
  resultFocus.classList.remove("content-refresh");
  resultCards.forEach((card) => {
    const active = Number(card.dataset.result) === index;
    card.classList.toggle("active", active);
    card.setAttribute("aria-pressed", String(active));
  });
  resultFocus.innerHTML = `
    <div class="result-focus-lead">
      <span>${data.tag}</span>
      <strong>${data.name}: ${data.exact || data.result}</strong>
      <p>${data.oral}</p>
    </div>
    <div class="result-focus-grid">
      <div><b>Denominator</b><em>${data.denominator}</em></div>
      <div><b>Controls</b><em>${data.controls}</em></div>
      <div><b>Boundary</b><em>${data.boundary}</em></div>
    </div>
  `;
  requestAnimationFrame(() => resultFocus.classList.add("content-refresh"));
}

resultCards.forEach((card) => {
  const index = Number(card.dataset.result);
  card.addEventListener("click", (event) => {
    handleManualInteraction(event);
    setResultFocus(index);
  });
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleManualInteraction(event);
      setResultFocus(index);
    }
  });
});

if (resultCards.length) setResultFocus(0);

const contractButtons = Array.from(document.querySelectorAll(".contract-chip"));
const contractLabel = document.getElementById("contractLabel");
const contractTitle = document.getElementById("contractTitle");
const contractText = document.getElementById("contractText");

function setContract(key) {
  const data = contractFacts[key];
  if (!data) return;
  const detail = contractTitle?.closest(".contract-detail");
  detail?.classList.remove("content-refresh");
  contractButtons.forEach((button) => {
    const active = button.dataset.contract === key;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  contractLabel.textContent = data.label;
  contractTitle.textContent = data.title;
  contractText.textContent = data.text;
  requestAnimationFrame(() => detail?.classList.add("content-refresh"));
}

contractButtons.forEach((button) => {
  button.setAttribute("aria-pressed", button.classList.contains("active") ? "true" : "false");
  button.addEventListener("click", (event) => {
    handleManualInteraction(event);
    setContract(button.dataset.contract);
  });
});

const problemCards = Array.from(document.querySelectorAll(".problem-card"));
const problemPanelTitle = document.getElementById("problemPanelTitle");
const problemPanelText = document.getElementById("problemPanelText");

function setProblem(key) {
  const data = problemFacts[key];
  if (!data) return;
  const panel = problemPanelTitle?.closest(".interaction-panel");
  panel?.classList.remove("content-refresh");
  problemCards.forEach((card) => card.classList.toggle("active", card.dataset.problem === key));
  if (problemPanelTitle) problemPanelTitle.textContent = data.title;
  if (problemPanelText) problemPanelText.textContent = data.text;
  requestAnimationFrame(() => panel?.classList.add("content-refresh"));
}

problemCards.forEach((card) => {
  card.addEventListener("click", (event) => {
    handleManualInteraction(event);
    setProblem(card.dataset.problem);
  });
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleManualInteraction(event);
      setProblem(card.dataset.problem);
    }
  });
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
  const detail = stageFields.question?.closest(".stage-detail");
  detail?.classList.remove("content-refresh");
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
  requestAnimationFrame(() => detail?.classList.add("content-refresh"));
}

stageButtons.forEach((button) => {
  button.setAttribute("aria-pressed", button.classList.contains("active") ? "true" : "false");
  button.addEventListener("click", (event) => {
    handleManualInteraction(event);
    setStage(button.dataset.stage);
  });
});

const futureGrid = document.getElementById("futureGrid");
const futureNote = document.getElementById("futureNote");

if (futureGrid) {
  futureGrid.innerHTML = futureTracks.map((track, index) => `
    <article class="future-track ${index === 0 ? "active" : ""}" data-future="${index}" tabindex="0" role="button" aria-pressed="${index === 0 ? "true" : "false"}">
      <span>${track.venue}</span>
      <h3>${track.name}</h3>
      <p>${track.route}</p>
      <em>${track.visibility}</em>
      <a href="${track.repo}" target="_blank" rel="noopener" aria-label="Open ${track.name} repository">Open repo</a>
    </article>
  `).join("");
}

const futureCards = Array.from(document.querySelectorAll(".future-track"));

function setFutureTrack(index) {
  const track = futureTracks[index];
  if (!track) return;
  futureNote?.classList.remove("content-refresh");
  futureCards.forEach((card) => {
    const active = Number(card.dataset.future) === index;
    card.classList.toggle("active", active);
    card.setAttribute("aria-pressed", String(active));
  });
  if (futureNote) {
    futureNote.innerHTML = `
      <div class="future-note-main">
        <strong>${track.name}</strong>
        <span>${track.status}</span>
        <em>${track.focus}</em>
      </div>
      <div class="future-review">
        ${track.review.map((item) => `<b>${item}</b>`).join("")}
      </div>
      <p>${track.boundary}</p>
    `;
  }
  requestAnimationFrame(() => futureNote?.classList.add("content-refresh"));
}

futureCards.forEach((card) => {
  const index = Number(card.dataset.future);
  card.addEventListener("click", (event) => {
    handleManualInteraction(event);
    setFutureTrack(index);
  });
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleManualInteraction(event);
      setFutureTrack(index);
    }
  });
});

setFutureTrack(0);

const steps = Array.from(document.querySelectorAll(".viva-step"));
const currentStep = document.getElementById("currentStep");
const routeLinks = Array.from(document.querySelectorAll(".route-nav a, .cover-route a"));
const startupParams = new URLSearchParams(window.location.search);
const stepDots = document.createElement("div");

stepDots.className = "step-dots";
stepDots.setAttribute("aria-label", "Presentation section dots");
steps.forEach((section, index) => {
  const button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-label", `${index + 1}. ${section.dataset.step || section.id}`);
  button.addEventListener("click", () => scrollToStep(section));
  stepDots.appendChild(button);
});

if (steps.length) document.body.appendChild(stepDots);

if (startupParams.get("presenter") === "1") {
  document.body.classList.add("presenter");
  document.documentElement.classList.add("presenter");
}

function updateCurrentStep(id) {
  const step = steps.find((section) => section.id === id);
  if (step && currentStep) currentStep.textContent = step.dataset.step || step.id;
  document.body.dataset.activeStep = id;
  steps.forEach((section) => section.classList.toggle("active-step", section.id === id));
  routeLinks.forEach((link) => link.classList.toggle("active", link.getAttribute("href") === `#${id}`));
  Array.from(stepDots.children).forEach((button, index) => {
    button.classList.toggle("active", steps[index]?.id === id);
  });
}

if (steps.length) updateCurrentStep(steps[0].id);

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
const cueTitle = document.getElementById("cueTitle");
const cueText = document.getElementById("cueText");
const cueStatus = document.getElementById("cueStatus");
const cueClock = document.getElementById("cueClock");
const cueNext = document.getElementById("cueNext");
const cueProgress = document.getElementById("cueProgress");
const demoCue = document.getElementById("demoCue");
const autoDemoButton = document.getElementById("autoDemo");
let autoDemoState = null;
let autoDemoTick = null;
let lastPresenterWheelAt = 0;

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
  const requestedStep = startupParams.get("step") || window.location.hash.slice(1);
  if (!requestedStep) return;
  const target = document.getElementById(requestedStep);
  if (target) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        scrollToStep(target, "auto");
        updateCurrentStep(target.id);
      });
    });
  }
});

function scrollToStep(target, behavior = "smooth") {
  const topbarOffset = document.body.classList.contains("presenter") ? 0 : 62;
  const targetTop = target.getBoundingClientRect().top + window.scrollY - topbarOffset;
  const top = Math.max(0, targetTop);
  if (behavior === "auto") {
    const root = document.documentElement;
    const previousBehavior = root.style.scrollBehavior;
    const previousSnap = root.style.scrollSnapType;
    root.style.scrollBehavior = "auto";
    root.style.scrollSnapType = "none";
    window.scrollTo({ left: 0, top, behavior: "auto" });
    document.documentElement.scrollTop = top;
    document.body.scrollTop = top;
    requestAnimationFrame(() => {
      root.style.scrollBehavior = previousBehavior;
      root.style.scrollSnapType = previousSnap;
    });
    return;
  }
  window.scrollTo({ top, behavior });
}

function formatTime(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function getElapsedBefore(planIndex) {
  return autoDemoPlan.slice(0, planIndex).reduce((sum, step) => sum + step.duration, 0);
}

function getPlanTotal() {
  return autoDemoPlan.reduce((sum, step) => sum + step.duration, 0);
}

function setAutoDemoButton(label, pressed) {
  if (!autoDemoButton) return;
  autoDemoButton.textContent = label;
  autoDemoButton.setAttribute("aria-pressed", String(pressed));
  autoDemoButton.dataset.state = label.toLowerCase().replace(/\s+/g, "-");
}

function setCueVisible(visible) {
  if (demoCue) demoCue.setAttribute("aria-hidden", String(!visible));
}

function setCue(planIndex, elapsedInStep, paused = false) {
  const item = autoDemoPlan[planIndex] || autoDemoPlan[autoDemoPlan.length - 1];
  const totalElapsed = getElapsedBefore(planIndex) + elapsedInStep;
  const total = getPlanTotal();
  document.documentElement.style.setProperty("--cue-progress", total ? String(Math.min(1, totalElapsed / total)) : "0");
  if (cueStatus) cueStatus.textContent = paused ? "Paused" : "Auto demo";
  if (cueTitle) cueTitle.textContent = item.title;
  if (cueText) cueText.textContent = item.cue;
  if (cueClock) cueClock.textContent = `${formatTime(totalElapsed)} / ${formatTime(total)}`;
  if (cueNext) cueNext.textContent = `Next: ${item.next}`;
  cueProgress?.style.setProperty("--cue-progress", total ? String(Math.min(1, totalElapsed / total)) : "0");
}

function runAutoAction(action) {
  if (!action) return;
  if (action.type === "problem") setProblem(action.key);
  if (action.type === "contract") setContract(action.key);
  if (action.type === "result") setResultFocus(action.index);
  if (action.type === "demo") setDemo(action.key);
  if (action.type === "future") setFutureTrack(action.index);
  if (action.type === "qa") setQaAnswer(action.key);
  if (action.type === "terminal-final") {
    document.querySelector(".terminal-card")?.classList.add("demo-final");
  }
}

function enterAutoStep(planIndex, behavior = "smooth") {
  const item = autoDemoPlan[planIndex];
  if (!item) return;
  const target = document.getElementById(item.id);
  if (target) {
    const scrollBehavior = document.body.classList.contains("presenter") ? "auto" : behavior;
    scrollToStep(target, scrollBehavior);
    updateCurrentStep(target.id);
    if (scrollBehavior === "auto") requestAnimationFrame(() => scrollToStep(target, "auto"));
  }
  if (item.id !== "demo") document.querySelector(".terminal-card")?.classList.remove("demo-final");
  (item.actions || []).forEach((action, actionIndex) => {
    if (action.at !== 0) return;
    autoDemoState?.fired.add(`${planIndex}:${actionIndex}`);
    runAutoAction(action);
  });
  setCue(planIndex, 0, false);
}

function clearAutoTimer() {
  if (autoDemoTick) window.clearInterval(autoDemoTick);
  autoDemoTick = null;
}

function stopAutoDemo(holdCue = false) {
  clearAutoTimer();
  if (!autoDemoState) return;
  autoDemoState = null;
  document.body.classList.remove("auto-demo", "demo-paused", "demo-complete");
  if (holdCue) {
    document.body.classList.add("demo-complete");
    document.documentElement.style.setProperty("--cue-progress", "1");
    cueProgress?.style.setProperty("--cue-progress", "1");
    if (cueStatus) cueStatus.textContent = "Finished";
    if (cueTitle) cueTitle.textContent = "Q&A";
    if (cueText) cueText.textContent = "Stay here. Answer directly, give one evidence number, then state the boundary.";
    if (cueClock) cueClock.textContent = `${formatTime(getPlanTotal())} / ${formatTime(getPlanTotal())}`;
    if (cueNext) cueNext.textContent = "Next: examiner questions";
    setAutoDemoButton("Restart demo", false);
    setCueVisible(true);
  } else {
    setAutoDemoButton("Auto demo", false);
    document.documentElement.style.setProperty("--cue-progress", "0");
    cueProgress?.style.setProperty("--cue-progress", "0");
    if (cueStatus) cueStatus.textContent = "Manual mode";
    setCueVisible(false);
  }
}

function pauseAutoDemo(reason = "manual") {
  if (!autoDemoState || autoDemoState.paused) return;
  const now = performance.now();
  autoDemoState.elapsed += (now - autoDemoState.startedAt) / 1000;
  autoDemoState.paused = true;
  autoDemoState.pauseReason = reason;
  clearAutoTimer();
  document.body.classList.remove("auto-demo");
  document.body.classList.remove("demo-complete");
  document.body.classList.add("demo-paused");
  setAutoDemoButton("Resume", true);
  setCue(autoDemoState.index, autoDemoState.elapsed, true);
  if (cueNext) cueNext.textContent = "Next: resume or continue manually";
  setCueVisible(true);
}

function resumeAutoDemo() {
  if (!autoDemoState || !autoDemoState.paused) return;
  autoDemoState.paused = false;
  autoDemoState.startedAt = performance.now();
  document.body.classList.add("auto-demo");
  document.body.classList.remove("demo-paused", "demo-complete");
  setAutoDemoButton("Pause", true);
  setCueVisible(true);
  autoDemoTick = window.setInterval(updateAutoDemo, 250);
}

function startAutoDemo() {
  clearAutoTimer();
  document.body.classList.add("presenter", "auto-demo");
  document.documentElement.classList.add("presenter");
  document.body.classList.remove("demo-paused", "demo-complete");
  if (presenterButton) {
    presenterButton.setAttribute("aria-pressed", "true");
    presenterButton.textContent = "Exit presenter";
  }
  autoDemoState = {
    index: 0,
    startedAt: performance.now(),
    elapsed: 0,
    fired: new Set(),
    paused: false
  };
  setAutoDemoButton("Pause", true);
  setCueVisible(true);
  enterAutoStep(0, "auto");
  autoDemoTick = window.setInterval(updateAutoDemo, 250);
}

function updateAutoDemo() {
  if (!autoDemoState || autoDemoState.paused) return;
  const item = autoDemoPlan[autoDemoState.index];
  if (!item) {
    stopAutoDemo(true);
    return;
  }
  const elapsed = autoDemoState.elapsed + (performance.now() - autoDemoState.startedAt) / 1000;
  (item.actions || []).forEach((action, actionIndex) => {
    const key = `${autoDemoState.index}:${actionIndex}`;
    if (elapsed >= action.at && !autoDemoState.fired.has(key)) {
      autoDemoState.fired.add(key);
      runAutoAction(action);
    }
  });
  setCue(autoDemoState.index, Math.min(elapsed, item.duration), false);
  if (elapsed < item.duration) return;
  autoDemoState.index += 1;
  if (autoDemoState.index >= autoDemoPlan.length) {
    setCue(autoDemoPlan.length - 1, autoDemoPlan[autoDemoPlan.length - 1].duration, false);
    stopAutoDemo(true);
    return;
  }
  autoDemoState.elapsed = 0;
  autoDemoState.startedAt = performance.now();
  autoDemoState.fired = new Set();
  enterAutoStep(autoDemoState.index);
}

function handleManualInteraction(event) {
  if (!autoDemoState) {
    if (document.body.classList.contains("demo-complete")) {
      document.body.classList.remove("demo-complete");
      setCueVisible(false);
      setAutoDemoButton("Auto demo", false);
    }
    return;
  }
  if (autoDemoState.paused) return;
  const target = event.target;
  if (target?.closest?.("#autoDemo, #copyCommand")) return;
  pauseAutoDemo("manual");
}

routeLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    handleManualInteraction(event);
    const id = link.getAttribute("href")?.replace("#", "");
    const target = id ? document.getElementById(id) : null;
    if (!target) return;
    event.preventDefault();
    history.replaceState(null, "", `#${id}`);
    scrollToStep(target);
    updateCurrentStep(id);
  });
});

function getCurrentStepIndex() {
  const topbarOffset = document.body.classList.contains("presenter") ? 0 : 62;
  const anchor = window.scrollY + topbarOffset + 4;
  let currentIndex = 0;
  steps.forEach((section, index) => {
    if (section.offsetTop <= anchor) currentIndex = index;
  });
  return currentIndex;
}

function scrollToRelativeStep(direction) {
  const index = getCurrentStepIndex();
  const target = steps[Math.min(steps.length - 1, Math.max(0, index + direction))];
  if (target) scrollToStep(target);
}

document.getElementById("nextStep")?.addEventListener("click", (event) => {
  handleManualInteraction(event);
  scrollToRelativeStep(1);
});
document.getElementById("prevStep")?.addEventListener("click", (event) => {
  handleManualInteraction(event);
  scrollToRelativeStep(-1);
});

function handleWheelNavigation(event) {
  if (!document.body.classList.contains("presenter")) {
    handleManualInteraction(event);
    return;
  }
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  event.preventDefault();
  handleManualInteraction(event);
  if (Math.abs(event.deltaY) < 38) return;
  const now = performance.now();
  if (now - lastPresenterWheelAt < 620) return;
  lastPresenterWheelAt = now;
  scrollToRelativeStep(event.deltaY > 0 ? 1 : -1);
}

window.addEventListener("wheel", handleWheelNavigation, { passive: false });
window.addEventListener("touchstart", handleManualInteraction, { passive: true });

autoDemoButton?.addEventListener("click", () => {
  if (!autoDemoState) {
    startAutoDemo();
    return;
  }
  if (autoDemoState.paused) {
    resumeAutoDemo();
  } else {
    pauseAutoDemo("button");
  }
});

const presenterButton = document.getElementById("presenterMode");

if (presenterButton && document.body.classList.contains("presenter")) {
  presenterButton.setAttribute("aria-pressed", "true");
  presenterButton.textContent = "Exit presenter";
}

presenterButton?.addEventListener("click", () => {
  if (autoDemoState) pauseAutoDemo("presenter-toggle");
  const active = document.body.classList.toggle("presenter");
  document.documentElement.classList.toggle("presenter", active);
  presenterButton.setAttribute("aria-pressed", String(active));
  presenterButton.textContent = active ? "Exit presenter" : "Presenter mode";
});

document.addEventListener("keydown", (event) => {
  if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
  const interactiveTarget = event.target?.closest?.("button, a, summary");
  if (interactiveTarget && [" ", "Enter", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  if (event.key.toLowerCase() === "a") {
    event.preventDefault();
    if (!autoDemoState) startAutoDemo();
    else if (autoDemoState.paused) resumeAutoDemo();
    else pauseAutoDemo("keyboard");
    return;
  }
  if (event.key.toLowerCase() === "k" && autoDemoState) {
    event.preventDefault();
    if (autoDemoState.paused) resumeAutoDemo();
    else pauseAutoDemo("keyboard");
    return;
  }
  if (event.key.toLowerCase() === "n" || event.key === "ArrowDown" || event.key === "ArrowRight" || event.key === "PageDown" || event.key === " ") {
    event.preventDefault();
    handleManualInteraction(event);
    scrollToRelativeStep(1);
  }
  if (event.key.toLowerCase() === "p" || event.key === "ArrowUp" || event.key === "ArrowLeft" || event.key === "PageUp") {
    event.preventDefault();
    handleManualInteraction(event);
    scrollToRelativeStep(-1);
  }
  if (event.key === "Home") {
    event.preventDefault();
    handleManualInteraction(event);
    if (steps[0]) scrollToStep(steps[0]);
  }
  if (event.key === "End") {
    event.preventDefault();
    handleManualInteraction(event);
    if (steps[steps.length - 1]) scrollToStep(steps[steps.length - 1]);
  }
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

const demoLinks = Array.from(document.querySelectorAll("[data-demo]"));
const demoPanelTitle = document.getElementById("demoPanelTitle");
const demoPanelText = document.getElementById("demoPanelText");
const demoOutput = document.getElementById("demoOutput");
const playEvidenceDemoButton = document.getElementById("playEvidenceDemo");
const resetEvidenceDemoButton = document.getElementById("resetEvidenceDemo");
const demoProgressBar = document.getElementById("demoProgressBar");
const demoPlaybackStatus = document.getElementById("demoPlaybackStatus");
let evidenceDemoTimer = null;
let evidenceDemoStartedAt = 0;
let evidenceDemoFired = new Set();

function setDemo(key) {
  const data = demoFacts[key];
  if (!data) return;
  let activeIndex = -1;
  demoLinks.forEach((link, index) => {
    const active = link.dataset.demo === key;
    link.classList.toggle("active", active);
    if (active) activeIndex = index;
  });
  const routeItems = Array.from(document.querySelectorAll(".demo-route > *"));
  routeItems.forEach((item, index) => {
    const routeIndex = Math.floor(index / 2);
    item.classList.toggle("passed", item.tagName === "SPAN" && routeIndex < activeIndex);
  });
  const panel = demoPanelTitle?.closest(".interaction-panel");
  panel?.classList.remove("content-refresh");
  if (demoPanelTitle) demoPanelTitle.textContent = data.title;
  if (demoPanelText) demoPanelText.textContent = data.text;
  requestAnimationFrame(() => panel?.classList.add("content-refresh"));
}

function formatShortClock(seconds) {
  return `00:${String(Math.max(0, Math.round(seconds))).padStart(2, "0")}`;
}

function setEvidenceDemoProgress(seconds) {
  const clamped = Math.max(0, Math.min(evidenceDemoDuration, seconds));
  const ratio = clamped / evidenceDemoDuration;
  demoProgressBar?.style.setProperty("--demo-progress", String(ratio));
  if (demoPlaybackStatus) {
    demoPlaybackStatus.textContent = `${formatShortClock(clamped)} / ${formatShortClock(evidenceDemoDuration)}`;
  }
}

function resetEvidenceDemo() {
  if (evidenceDemoTimer) window.clearInterval(evidenceDemoTimer);
  evidenceDemoTimer = null;
  evidenceDemoFired = new Set();
  document.querySelector(".terminal-card")?.classList.remove("demo-final");
  if (demoOutput) demoOutput.textContent = "[ready] Click Play demo to run the viva evidence route.";
  if (playEvidenceDemoButton) {
    playEvidenceDemoButton.textContent = "Play demo";
    playEvidenceDemoButton.setAttribute("aria-pressed", "false");
  }
  setEvidenceDemoProgress(0);
  setDemo("readme");
}

function appendDemoOutput(line) {
  if (!demoOutput) return;
  const current = demoOutput.textContent || "";
  demoOutput.textContent = current.startsWith("[ready]")
    ? line
    : `${current}\n${line}`;
}

function startEvidenceDemo() {
  resetEvidenceDemo();
  evidenceDemoStartedAt = performance.now();
  document.querySelector(".terminal-card")?.classList.remove("demo-final");
  if (playEvidenceDemoButton) {
    playEvidenceDemoButton.textContent = "Playing";
    playEvidenceDemoButton.setAttribute("aria-pressed", "true");
  }
  evidenceDemoTimer = window.setInterval(() => {
    const elapsed = (performance.now() - evidenceDemoStartedAt) / 1000;
    setEvidenceDemoProgress(elapsed);
    evidenceDemoTimeline.forEach((item, index) => {
      if (elapsed < item.at || evidenceDemoFired.has(index)) return;
      evidenceDemoFired.add(index);
      setDemo(item.key);
      appendDemoOutput(item.line);
    });
    if (elapsed < evidenceDemoDuration) return;
    if (evidenceDemoTimer) window.clearInterval(evidenceDemoTimer);
    evidenceDemoTimer = null;
    setEvidenceDemoProgress(evidenceDemoDuration);
    document.querySelector(".terminal-card")?.classList.add("demo-final");
    if (playEvidenceDemoButton) {
      playEvidenceDemoButton.textContent = "Replay demo";
      playEvidenceDemoButton.setAttribute("aria-pressed", "false");
    }
  }, 120);
}

playEvidenceDemoButton?.addEventListener("click", (event) => {
  handleManualInteraction(event);
  startEvidenceDemo();
});

resetEvidenceDemoButton?.addEventListener("click", (event) => {
  handleManualInteraction(event);
  resetEvidenceDemo();
});

demoLinks.forEach((link) => {
  link.addEventListener("mouseenter", () => setDemo(link.dataset.demo));
  link.addEventListener("focus", () => setDemo(link.dataset.demo));
  link.addEventListener("click", (event) => {
    handleManualInteraction(event);
    setDemo(link.dataset.demo);
  });
});

const qaButtons = Array.from(document.querySelectorAll("[data-qa]"));
const qaAnswer = document.getElementById("qaAnswer");

function setQaAnswer(key) {
  const data = qaFacts[key];
  if (!data || !qaAnswer) return;
  qaAnswer.classList.remove("content-refresh");
  qaButtons.forEach((button) => {
    const active = button.dataset.qa === key;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  qaAnswer.innerHTML = `
    <span>Evidence-based response</span>
    <strong>${data.title}</strong>
    <p>${data.answer}</p>
  `;
  requestAnimationFrame(() => qaAnswer.classList.add("content-refresh"));
}

qaButtons.forEach((button) => {
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", (event) => {
    handleManualInteraction(event);
    setQaAnswer(button.dataset.qa);
  });
});

if (qaButtons.length) setQaAnswer(qaButtons[0].dataset.qa);
