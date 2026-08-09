const detailElements = {
  status: document.querySelector("#detailStatus"),
  detail: document.querySelector("#skillDetail"),
  breadcrumb: document.querySelector("#breadcrumb"),
  avatar: document.querySelector("#ownerAvatar"),
  repository: document.querySelector("#repositoryName"),
  name: document.querySelector("#skillName"),
  tags: document.querySelector("#skillTags"),
  description: document.querySelector("#skillDescription"),
  confidence: document.querySelector("#categoryConfidence"),
  categoryLink: document.querySelector("#categoryLink"),
  categoryMarker: document.querySelector("#categoryMarker"),
  categoryLabel: document.querySelector("#categoryLabel"),
  categoryDescription: document.querySelector("#categoryDescription"),
  categorySignals: document.querySelector("#categorySignals"),
  metrics: document.querySelector("#detailMetrics"),
  riskBadge: document.querySelector("#riskBadge"),
  riskSignals: document.querySelector("#riskSignals"),
  prompt: document.querySelector("#installPrompt"),
  copyInstall: document.querySelector("#copyInstall"),
  sourceLink: document.querySelector("#sourceLink"),
  installMode: document.querySelector("#installMode"),
  license: document.querySelector("#licenseName"),
  path: document.querySelector("#skillPath"),
  toast: document.querySelector("#toast"),
};

function detailNode(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function detailNumber(value) {
  return new Intl.NumberFormat("zh-CN", { notation: value >= 10000 ? "compact" : "standard" }).format(value || 0);
}

function detailDate(value) {
  if (!value) return "时间未知";
  const days = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86400000));
  return days < 1 ? "今天活跃" : days < 30 ? `${days} 天前活跃` : `${Math.floor(days / 30)} 个月前活跃`;
}

function detailRisk(level) {
  return { low: "低风险", medium: "中风险", high: "高风险" }[level] || "未评估";
}

function metric(label, value) {
  const wrapper = detailNode("div");
  wrapper.append(detailNode("span", "", label), detailNode("strong", "", value));
  return wrapper;
}

function breadcrumb(category, item) {
  const home = detailNode("a", "", "分类总览");
  home.href = "./index.html";
  const categoryLink = detailNode("a", "", category.label);
  categoryLink.href = `./catalog.html?category=${encodeURIComponent(category.id)}`;
  detailElements.breadcrumb.replaceChildren(home, detailNode("span", "", "/"), categoryLink, detailNode("span", "", "/"), detailNode("span", "", item.name));
}

let toastTimer;
function showToast(message) {
  clearTimeout(toastTimer);
  detailElements.toast.textContent = message;
  detailElements.toast.classList.add("visible");
  toastTimer = setTimeout(() => detailElements.toast.classList.remove("visible"), 2200);
}

async function copyPrompt() {
  const prompt = detailElements.prompt.textContent;
  try {
    await navigator.clipboard.writeText(prompt);
    showToast("安装提示词已复制");
  } catch {
    const area = document.createElement("textarea");
    area.value = prompt;
    area.setAttribute("readonly", "");
    area.className = "clipboard-fallback";
    document.body.append(area);
    area.select();
    const copied = document.execCommand("copy");
    area.remove();
    showToast(copied ? "安装提示词已复制" : "复制失败，请手动复制上方提示词");
  }
}

function renderDetail(item, categories) {
  const category = categories.find((candidate) => candidate.id === item.category?.id) || {
    id: "general", label: "通用工作流", description: "规划、协作、方法论与跨领域辅助能力", tone: "gray",
  };
  document.title = `${item.name} · Codex Skill Radar`;
  breadcrumb(category, item);
  detailElements.avatar.src = item.repository.owner_avatar || "";
  detailElements.avatar.alt = `${item.repository.owner} 的 GitHub 头像`;
  detailElements.repository.textContent = item.repository.full_name;
  detailElements.name.textContent = item.name;
  detailElements.tags.replaceChildren(...item.types.map((type) => detailNode("span", "tag", type.toUpperCase())));
  detailElements.description.textContent = item.description;
  detailElements.confidence.textContent = `分类置信度 ${item.category?.confidence || 0}%`;
  detailElements.categoryLink.href = `./catalog.html?category=${encodeURIComponent(category.id)}`;
  detailElements.categoryMarker.className = `category-marker tone-${category.tone}`;
  detailElements.categoryMarker.textContent = String(item.category?.confidence || 0);
  detailElements.categoryLabel.textContent = category.label;
  detailElements.categoryDescription.textContent = category.description;
  detailElements.categorySignals.replaceChildren(...(item.category?.signals || []).map((signal) => detailNode("span", "signal", signal)));
  detailElements.metrics.replaceChildren(
    metric("综合热度", String(item.score?.total || 0)),
    metric("GitHub Stars", detailNumber(item.repository.stars)),
    metric("30 天增长", `+${item.score?.star_delta_30d || 0}`),
    metric("最近活跃", detailDate(item.repository.pushed_at)),
    metric("Forks", detailNumber(item.repository.forks)),
    metric("主要语言", item.repository.language || "未声明")
  );
  detailElements.riskBadge.className = `risk ${item.risk?.level || "medium"}`;
  detailElements.riskBadge.textContent = detailRisk(item.risk?.level);
  const riskSignals = item.risk?.signals || [];
  detailElements.riskSignals.replaceChildren(...(riskSignals.length ? riskSignals : ["未发现额外静态权限信号"]).map((signal) => detailNode("li", "", signal)));
  detailElements.prompt.textContent = item.install?.codex_prompt || "暂无安装提示词";
  detailElements.sourceLink.href = item.source_url;
  detailElements.installMode.textContent = item.install?.mode === "plugin" ? "Codex Plugin" : "Standalone Skill";
  detailElements.license.textContent = item.repository.license || "未声明";
  detailElements.path.textContent = item.skill_path;
  detailElements.detail.hidden = false;
  detailElements.status.hidden = true;
}

async function loadDetail() {
  const itemId = new URLSearchParams(window.location.search).get("id");
  if (!itemId) {
    detailElements.status.textContent = "缺少 Skill ID。请从分类总览或完整目录打开详情。";
    return;
  }
  try {
    const response = await fetch("./catalog.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const catalog = await response.json();
    const item = (catalog.items || []).find((candidate) => candidate.id === itemId);
    if (!item) {
      detailElements.status.textContent = "这个 Skill 不在当前目录中，可能已在最近一次更新中移除。";
      return;
    }
    renderDetail(item, catalog.categories || []);
  } catch (error) {
    detailElements.status.textContent = `无法读取 catalog.json：${error.message}`;
  }
}

detailElements.copyInstall.addEventListener("click", copyPrompt);
loadDetail();
