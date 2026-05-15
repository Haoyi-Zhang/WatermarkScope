const repoBase = "https://github.com/Haoyi-Zhang/WatermarkScope";
const submittedRef = "e0851409c3fe14d1813b714ff9b2d1fa2da965cb";
const repoTree = `${repoBase}/tree/${submittedRef}`;
const repoBlob = `${repoBase}/blob/${submittedRef}`;

const contractFacts = {
  denominator: {
    label: "What is counted?",
    title: "A result only means something after the denominator is fixed.",
    text: "For example, SemCodebook reports 30,330 recoveries over 31,200 admitted positive rows. I keep the misses inside the denominator, so the result is easier to defend."
  },
  controls: {
    label: "What would fail?",
    title: "Controls decide whether a signal is evidence or a shortcut.",
    text: "The main results are paired with negative controls, false-owner controls, or unsafe-pass tracking. Zero observed events are reported as finite-sample evidence, not as zero risk."
  },
  artifact: {
    label: "Can it be inspected?",
    title: "A viva claim should point to code, manifests, and preserved result files.",
    text: "The repository route is README, claim boundaries, traceability matrix, result manifest, and viva_check.py. This lets me show the work live without pretending I can rerun every expensive experiment in the room."
  },
  access: {
    label: "What access is assumed?",
    title: "Changing access changes the claim.",
    text: "White-box provenance recovery, black-box null audit, active-owner verification, and marker-hidden triage are different evidence questions. They should not be collapsed into one detector score."
  },
  boundary: {
    label: "What is forbidden?",
    title: "The boundary prevents the result from becoming broader than the evidence.",
    text: "The framework explicitly says what I cannot claim: no universal watermarking claim, no provider accusation, no general authorship proof, and no safety certificate unless a new admitted surface supports it."
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
    oral: "I use this first because code watermark evaluation must start from executable rows, not only text similarity.",
    accent: "blue"
  },
  {
    name: "SemCodebook",
    tag: "White-box provenance",
    result: "30.3k/31.2k",
    denominator: "31,200 positive rows; 62,400 fixed negatives; 62,400 blind replay negatives",
    controls: "0/62,400 fixed negative-control hits and 0/62,400 blind replay hits",
    claim: "Structured provenance recovery within admitted white-box cells.",
    boundary: "Not universal natural-generation watermarking.",
    oral: "This is the main method contribution. The key defense is that recoveries, misses, and two negative surfaces are all reported together.",
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
    oral: "A sparse signal is not a failed story; it tells us the honest claim is conservative audit evidence, not contamination prevalence.",
    accent: "violet"
  },
  {
    name: "ProbeTrace",
    tag: "Active-owner attribution",
    result: "750/750",
    denominator: "Five-owner DeepSeek commitment/witness surface",
    controls: "750/750 true-owner positives and 0/5,250 false-attribution controls",
    claim: "Scoped active-owner commitment and witness verification.",
    boundary: "Not provider-general or cross-provider authorship proof.",
    oral: "The strong positive result is only safe because it is paired with false-owner controls and a fixed owner registry.",
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
    oral: "For security-facing evidence, abstention is part of the design because forced labels would overstate what the evidence supports.",
    accent: "green"
  }
];

const problemFacts = {
  execution: {
    title: "The original prompt session is not enough.",
    text: "This is why I treat provenance as an evidence problem: after code is copied or edited, I need an artifact and a boundary, not just a detector score."
  },
  access: {
    title: "Executable rows protect the denominator.",
    text: "For code, the benchmark row must be runnable and countable before I interpret any watermark signal."
  },
  abstention: {
    title: "Different access models need different claims.",
    text: "White-box recovery, black-box audit, active-owner attribution, and security triage answer different questions, so I keep their claims separate."
  }
};

const demoFacts = {
  readme: {
    title: "Start with the repository README.",
    text: "Use it to show the examiner the submitted FYP surface and the exact page route before opening deeper artifacts."
  },
  boundaries: {
    title: "Then show the claim boundaries.",
    text: "This is the strongest defense document: it states both the allowed claim and the forbidden interpretation."
  },
  traceability: {
    title: "Traceability connects claims to files.",
    text: "Use this to show that each module has code paths, result paths, and a safe interpretation."
  },
  manifest: {
    title: "The manifest preserves evidence records.",
    text: "This shows the evidence is not just prose on the page; rows are recorded and hash-addressed for inspection."
  },
  check: {
    title: "Finish with the lightweight viva check.",
    text: "Say clearly that this verifies inspectability, not a full GPU/API rerun."
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
    key: "codemarkbench",
    name: "CodeMarkBench",
    route: "Benchmark foundation",
    venue: "ACM TOSEM",
    repo: "https://github.com/Haoyi-Zhang/CodeMarkBench",
    commit: "2db2630",
    visibility: "Public repository",
    status: "Benchmark expansion with separately admitted denominators.",
    focus: "Review: task suites, release metadata, and admitted benchmark surfaces.",
    boundary: "Any new benchmark cell must be admitted as a new surface; it does not change the 140/140 submitted FYP denominator.",
    review: ["Open the benchmark repository", "Show task and suite organization", "Explain how new benchmark surfaces would be admitted"]
  },
  {
    key: "semcodebook",
    name: "SemCodebook",
    route: "White-box method",
    venue: "EMNLP",
    repo: "https://github.com/Haoyi-Zhang/SemCodebook",
    commit: "f243416",
    visibility: "Private continuation repository",
    status: "Structured provenance recovery beyond the submitted FYP slice.",
    focus: "Review: carrier/recovery pipeline and negative-control replay gates.",
    boundary: "Extra cells are future evidence. They should be reported separately from the submitted 30,330/31,200 FYP recovery surface.",
    review: ["Open implementation modules", "Show carrier and recovery pipeline", "Explain negative-control and replay gates"]
  },
  {
    key: "codedye",
    name: "CodeDye",
    route: "Black-box audit",
    venue: "EMNLP",
    repo: "https://github.com/Haoyi-Zhang/CodeDye",
    commit: "6aa5d8c",
    visibility: "Private continuation repository",
    status: "Conservative black-box null-audit evidence.",
    focus: "Review: audit scripts, role-separated controls, and non-accusation boundary.",
    boundary: "The claim remains null-audit evidence, not prevalence, wrongdoing proof, or absence proof.",
    review: ["Open audit scripts", "Show role-separated control design", "Explain why sparse signals are not accusations"]
  },
  {
    key: "probetrace",
    name: "ProbeTrace",
    route: "Owner attribution",
    venue: "EMNLP",
    repo: "https://github.com/Haoyi-Zhang/ProbeTrace",
    commit: "a6e53b2",
    visibility: "Private continuation repository",
    status: "Scoped owner verification with commitment/witness evidence.",
    focus: "Review: owner registry, split, and false-owner controls.",
    boundary: "It is scoped owner verification, not universal authorship proof or cross-provider attribution.",
    review: ["Open commitment and witness code", "Show owner registry and split", "Explain false-owner controls"]
  },
  {
    key: "sealaudit",
    name: "SealAudit",
    route: "Security triage",
    venue: "EMNLP",
    repo: "https://github.com/Haoyi-Zhang/SealAudit",
    commit: "5203c62",
    visibility: "Private continuation repository",
    status: "Marker-hidden selective security triage.",
    focus: "Review: decision packets, abstention, and unsafe-pass accounting.",
    boundary: "It is selective triage, not a classifier, safety certificate, or automatic harmlessness guarantee.",
    review: ["Open triage pipeline", "Show marker-hidden decision packets", "Explain abstention and unsafe-pass accounting"]
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
      <p class="result-claim">${item.claim}</p>
      <small>${item.boundary}</small>
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
    <span>${data.tag}</span>
    <strong>${data.name}: ${data.result}</strong>
    <p>${data.oral}</p>
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
  card.addEventListener("click", () => setResultFocus(index));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
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
  button.addEventListener("click", () => setContract(button.dataset.contract));
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
  card.addEventListener("click", () => setProblem(card.dataset.problem));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
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
  button.addEventListener("click", () => setStage(button.dataset.stage));
});

const futureGrid = document.getElementById("futureGrid");
const futureNote = document.getElementById("futureNote");

if (futureGrid) {
  futureGrid.innerHTML = futureTracks.map((track, index) => `
    <article class="future-track ${index === 0 ? "active" : ""}" data-future="${index}" tabindex="0" role="button" aria-pressed="${index === 0 ? "true" : "false"}">
      <span>Target: ${track.venue}</span>
      <h3>${track.name}</h3>
      <p>${track.route}</p>
      <em>${track.visibility} / ${track.commit}</em>
      <a href="${track.repo}" target="_blank" rel="noopener" aria-label="Review ${track.name} repository">Review repo</a>
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
      <strong>${track.name}</strong>
      <span>${track.status}</span>
      <em>${track.focus}</em>
    `;
  }
  requestAnimationFrame(() => futureNote?.classList.add("content-refresh"));
}

futureCards.forEach((card) => {
  const index = Number(card.dataset.future);
  card.addEventListener("click", () => setFutureTrack(index));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setFutureTrack(index);
    }
  });
});

setFutureTrack(0);

const steps = Array.from(document.querySelectorAll(".viva-step"));
const currentStep = document.getElementById("currentStep");
const routeLinks = Array.from(document.querySelectorAll(".route-nav a"));

function updateCurrentStep(id) {
  const step = steps.find((section) => section.id === id);
  if (step && currentStep) currentStep.textContent = step.dataset.step || step.id;
  steps.forEach((section) => section.classList.toggle("active-step", section.id === id));
  routeLinks.forEach((link) => link.classList.toggle("active", link.getAttribute("href") === `#${id}`));
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
    requestAnimationFrame(() => scrollToStep(target, "auto"));
  }
});

function scrollToStep(target, behavior = "smooth") {
  const topbarOffset = document.body.classList.contains("presenter") ? 0 : 62;
  const targetTop = target.getBoundingClientRect().top + window.scrollY - topbarOffset;
  window.scrollTo({ top: Math.max(0, targetTop), behavior });
}

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
  if (event.metaKey || event.ctrlKey || event.altKey) return;
  if (event.key.toLowerCase() === "n" || event.key === "ArrowDown") {
    event.preventDefault();
    scrollToRelativeStep(1);
  }
  if (event.key.toLowerCase() === "p" || event.key === "ArrowUp") {
    event.preventDefault();
    scrollToRelativeStep(-1);
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

demoLinks.forEach((link) => {
  link.addEventListener("mouseenter", () => setDemo(link.dataset.demo));
  link.addEventListener("focus", () => setDemo(link.dataset.demo));
  link.addEventListener("click", () => setDemo(link.dataset.demo));
});
