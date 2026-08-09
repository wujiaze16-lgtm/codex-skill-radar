const urlParams = new URLSearchParams(window.location.search);
const state = {
  catalog: null,
  items: [],
  query: urlParams.get("q") || "",
  category: urlParams.get("category") || "all",
  type: "all",
  risks: new Set(),
  licensedOnly: false,
  recentOnly: false,
  sort: "trending",
};

const elements = {
  search: document.querySelector("#searchInput"),
  sort: document.querySelector("#sortSelect"),
  category: document.querySelector("#categorySelect"),
  list: document.querySelector("#resultList"),
  status: document.querySelector("#statusMessage"),
  count: document.querySelector("#resultCount"),
  subtitle: document.querySelector("#pageSubtitle"),
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

function categoryFor(item) {
  return item.category?.id || "general";
}

function matches(item) {
  if (state.type !== "all" && !item.types.includes(state.type)) return false;
  if (state.category !== "all" && categoryFor(item) !== state.category) return false;
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
    item.category?.label,
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
  document.querySelector("#skillCount").textContent = formatNumber(state.items.length);
  document.querySelector("#repoCount").textContent = formatNumber(new Set(state.items.map((item) => item.repository.full_name)).size);
  document.querySelector("#pluginCount").textContent = formatNumber(state.items.filter((item) => item.types.includes("plugin")).length);
  document.querySelector("#mcpCount").textContent = formatNumber(state.items.filter((item) => item.types.includes("mcp")).length);
}

function createResult(item) {
  const link = node("a", "result-row");
  link.href = `./skill.html?id=${encodeURIComponent(item.id)}`;
  link.setAttribute("aria-label", `查看 ${item.name} 的详情`);

  const main = node("div", "result-main");
  const avatar = node("img", "avatar");
  avatar.src = item.repository.owner_avatar || "";
  avatar.alt = "";
  avatar.loading = "lazy";
  const content = node("div");
  const titleLine = node("div", "result-titleline");
  titleLine.append(node("strong", "", item.name));
  item.types.forEach((type) => titleLine.append(node("span", "tag", type.toUpperCase())));
  titleLine.append(node("span", "category-chip", item.category?.label || "通用工作流"));
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
  link.append(main, score);
  return link;
}

function updateUrl() {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.category !== "all") params.set("category", state.category);
  const query = params.toString();
  window.history.replaceState({}, "", query ? `?${query}` : "./catalog.html");
}

function renderHeading() {
  const category = (state.catalog?.categories || []).find((candidate) => candidate.id === state.category);
  elements.subtitle.textContent = category
    ? `${category.description} · 当前查看 ${category.label}`
    : "搜索并比较热度、活跃度与安装风险。";
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
  renderHeading();
}

function populateCategories() {
  const categories = state.catalog.categories || [];
  elements.category.replaceChildren(new Option("全部类别", "all"));
  categories.forEach((category) => elements.category.add(new Option(category.label, category.id)));
  if (!categories.some((category) => category.id === state.category)) state.category = "all";
  elements.category.value = state.category;
}

function resetFilters() {
  state.query = "";
  state.category = "all";
  state.type = "all";
  state.risks.clear();
  state.licensedOnly = false;
  state.recentOnly = false;
  elements.search.value = "";
  elements.category.value = "all";
  document.querySelectorAll('input[name="risk"]').forEach((input) => { input.checked = false; });
  document.querySelector("#licensedOnly").checked = false;
  document.querySelector("#recentOnly").checked = false;
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.type === "all"));
  updateUrl();
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
  elements.search.addEventListener("input", (event) => { state.query = event.target.value; updateUrl(); render(); });
  elements.sort.addEventListener("change", (event) => { state.sort = event.target.value; render(); });
  elements.category.addEventListener("change", (event) => { state.category = event.target.value; updateUrl(); render(); });
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
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement !== elements.search) {
      event.preventDefault();
      elements.search.focus();
    }
  });
}

async function loadCatalog() {
  wireEvents();
  elements.search.value = state.query;
  try {
    const response = await fetch("./catalog.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.catalog = await response.json();
    state.items = Array.isArray(state.catalog.items) ? state.catalog.items : [];
    populateCategories();
    renderMetrics();
    render();
  } catch (error) {
    elements.status.textContent = `无法读取 catalog.json：${error.message}`;
  }
}

loadCatalog();
