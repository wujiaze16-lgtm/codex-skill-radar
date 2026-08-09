const state = {
  catalog: null,
  items: [],
  query: "",
  type: "all",
  risks: new Set(),
  licensedOnly: false,
  recentOnly: false,
  sort: "trending",
  selected: null,
};

const elements = {
  search: document.querySelector("#searchInput"),
  sort: document.querySelector("#sortSelect"),
  list: document.querySelector("#resultList"),
  status: document.querySelector("#statusMessage"),
  count: document.querySelector("#resultCount"),
  updated: document.querySelector("#updatedAt"),
  dialog: document.querySelector("#detailDialog"),
  dialogIdentity: document.querySelector("#dialogIdentity"),
  dialogBody: document.querySelector("#dialogBody"),
  sourceLink: document.querySelector("#sourceLink"),
  copyInstall: document.querySelector("#copyInstall"),
  toast: document.querySelector("#toast"),
};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN", { notation: value >= 10000 ? "compact" : "standard" }).format(value || 0);
}

function relativeDate(value) {
  if (!value) return "时间未知";
  const days = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86400000));
  if (days === 0) return "今天活跃";
  if (days < 30) return `${days} 天前活跃`;
  if (days < 365) return `${Math.floor(days / 30)} 个月前活跃`;
  return `${Math.floor(days / 365)} 年前活跃`;
}

function riskLabel(level) {
  return { low: "低风险", medium: "中风险", high: "高风险" }[level] || "未评估";
}

function matches(item) {
  if (state.type !== "all" && !item.types.includes(state.type)) return false;
  if (state.risks.size && !state.risks.has(item.risk.level)) return false;
  if (state.licensedOnly && !item.repository.license) return false;
  if (state.recentOnly) {
    const pushedAt = new Date(item.repository.pushed_at || 0).getTime();
    if (Date.now() - pushedAt > 90 * 86400000) return false;
  }
  const terms = state.query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const haystack = [
    item.name,
    item.description,
    item.repository.full_name,
    ...(item.repository.topics || []),
  ].join(" ").toLowerCase();
  return terms.every((term) => haystack.includes(term));
}

function sortItems(items) {
  const sorted = [...items];
  const score = (item, key) => item.score?.[key] || 0;
  if (state.sort === "stars") sorted.sort((a, b) => b.repository.stars - a.repository.stars);
  else if (state.sort === "momentum") sorted.sort((a, b) => score(b, "momentum") - score(a, "momentum"));
  else if (state.sort === "updated") sorted.sort((a, b) => new Date(b.repository.pushed_at || 0) - new Date(a.repository.pushed_at || 0));
  else sorted.sort((a, b) => score(b, "total") - score(a, "total"));
  return sorted;
}

function renderMetrics() {
  const items = state.items;
  document.querySelector("#skillCount").textContent = formatNumber(items.length);
  document.querySelector("#repoCount").textContent = formatNumber(new Set(items.map((item) => item.repository.full_name)).size);
  document.querySelector("#pluginCount").textContent = formatNumber(items.filter((item) => item.types.includes("plugin")).length);
  document.querySelector("#mcpCount").textContent = formatNumber(items.filter((item) => item.types.includes("mcp")).length);
}

function createResult(item) {
  const button = node("button", "result-row");
  button.type = "button";
  button.addEventListener("click", () => openDetail(item));

  const main = node("div", "result-main");
  const avatar = node("img", "avatar");
  avatar.src = item.repository.owner_avatar || "";
  avatar.alt = `${item.repository.owner} GitHub 头像`;
  avatar.loading = "lazy";
  const content = node("div");
  const titleLine = node("div", "result-titleline");
  titleLine.append(node("strong", "", item.name));
  item.types.forEach((type) => titleLine.append(node("span", "tag", type.toUpperCase())));
  titleLine.append(node("span", "repo-name", item.repository.full_name));
  content.append(titleLine, node("p", "description", item.description));

  const meta = node("div", "meta");
  meta.append(
    node("span", "", `★ ${formatNumber(item.repository.stars)}`),
    node("span", "", `7 天 +${item.score.star_delta_7d || 0}`),
    node("span", "", relativeDate(item.repository.pushed_at)),
    node("span", "", item.repository.license || "无许可证")
  );
  content.append(meta);
  main.append(avatar, content);

  const score = node("div", "result-score");
  const scoreValue = node("div", "score", String(item.score.total || 0));
  scoreValue.append(node("small", "", "热度分"));
  score.append(scoreValue, node("span", `risk ${item.risk.level}`, riskLabel(item.risk.level)));
  button.append(main, score);
  return button;
}

function render() {
  const items = sortItems(state.items.filter(matches));
  elements.count.textContent = `${items.length} 项`;
  elements.list.replaceChildren(...items.map(createResult));
  elements.status.hidden = items.length > 0;
  if (!items.length) {
    elements.status.textContent = state.items.length
      ? "没有符合当前筛选条件的项目。"
      : "目录尚未生成，请运行 GitHub Actions 的 catalog-and-pages 工作流。";
  }
}

function detailMetric(label, value) {
  const wrapper = node("div");
  wrapper.append(node("span", "", label), node("strong", "", value));
  return wrapper;
}

function openDetail(item) {
  state.selected = item;
  const heading = node("h2", "", item.name);
  const repo = node("p", "", `${item.repository.full_name} · ${item.skill_path}`);
  elements.dialogIdentity.replaceChildren(heading, repo);

  const description = node("p", "dialog-description", item.description);
  const grid = node("div", "detail-grid");
  grid.append(
    detailMetric("综合热度", String(item.score.total || 0)),
    detailMetric("GitHub Stars", formatNumber(item.repository.stars)),
    detailMetric("30 天增长", `+${item.score.star_delta_30d || 0}`),
    detailMetric("安装类型", item.install.mode === "plugin" ? "Codex Plugin" : "Standalone Skill"),
    detailMetric("许可证", item.repository.license || "未声明"),
    detailMetric("最近活跃", relativeDate(item.repository.pushed_at))
  );
  const risk = node("section", "risk-section");
  risk.append(node("h3", "", `权限信号 · ${riskLabel(item.risk.level)}`));
  const signals = node("ul");
  (item.risk.signals || []).forEach((signal) => signals.append(node("li", "", signal)));
  risk.append(signals);
  const prompt = node("div", "prompt-box", item.install.codex_prompt);
  elements.dialogBody.replaceChildren(description, grid, risk, prompt);
  elements.sourceLink.href = item.source_url;
  elements.dialog.showModal();
}

let toastTimer;
function showToast(message) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  toastTimer = setTimeout(() => elements.toast.classList.remove("visible"), 2200);
}

async function copyInstallPrompt() {
  const prompt = state.selected?.install?.codex_prompt;
  if (!prompt) return;
  try {
    await navigator.clipboard.writeText(prompt);
    showToast("安装指令已复制");
  } catch {
    const area = document.createElement("textarea");
    area.value = prompt;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    showToast("安装指令已复制");
  }
}

function resetFilters() {
  state.query = "";
  state.type = "all";
  state.risks.clear();
  state.licensedOnly = false;
  state.recentOnly = false;
  elements.search.value = "";
  document.querySelectorAll('input[name="risk"]').forEach((input) => { input.checked = false; });
  document.querySelector("#licensedOnly").checked = false;
  document.querySelector("#recentOnly").checked = false;
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.type === "all"));
  render();
}

function toggleMobileFilters() {
  const filters = document.querySelector(".filters");
  const toggle = document.querySelector("#filterToggle");
  const expanded = filters.classList.toggle("expanded");
  toggle.setAttribute("aria-expanded", String(expanded));
  toggle.textContent = expanded ? "收起" : "展开";
}

function wireEvents() {
  elements.search.addEventListener("input", (event) => { state.query = event.target.value; render(); });
  elements.sort.addEventListener("change", (event) => { state.sort = event.target.value; render(); });
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
    state.type = tab.dataset.type;
    document.querySelectorAll(".tab").forEach((candidate) => candidate.classList.toggle("active", candidate === tab));
    render();
  }));
  document.querySelectorAll('input[name="risk"]').forEach((input) => input.addEventListener("change", () => {
    if (input.checked) state.risks.add(input.value); else state.risks.delete(input.value);
    render();
  }));
  document.querySelector("#licensedOnly").addEventListener("change", (event) => { state.licensedOnly = event.target.checked; render(); });
  document.querySelector("#recentOnly").addEventListener("change", (event) => { state.recentOnly = event.target.checked; render(); });
  document.querySelector("#clearFilters").addEventListener("click", resetFilters);
  document.querySelector("#filterToggle").addEventListener("click", toggleMobileFilters);
  document.querySelector("#closeDialog").addEventListener("click", () => elements.dialog.close());
  elements.dialog.addEventListener("click", (event) => { if (event.target === elements.dialog) elements.dialog.close(); });
  elements.copyInstall.addEventListener("click", copyInstallPrompt);
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement !== elements.search) {
      event.preventDefault();
      elements.search.focus();
    }
  });
}

async function loadCatalog() {
  wireEvents();
  try {
    const response = await fetch("./catalog.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.catalog = await response.json();
    state.items = Array.isArray(state.catalog.items) ? state.catalog.items : [];
    const generated = new Date(state.catalog.generated_at);
    elements.updated.textContent = Number.isNaN(generated.getTime())
      ? "更新时间未知"
      : `更新于 ${generated.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`;
    renderMetrics();
    render();
  } catch (error) {
    elements.updated.textContent = "目录加载失败";
    elements.status.textContent = `无法读取 catalog.json：${error.message}`;
  }
}

loadCatalog();
