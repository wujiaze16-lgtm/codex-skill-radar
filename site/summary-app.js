const summaryElements = {
  categories: document.querySelector("#categoryGrid"),
  popular: document.querySelector("#popularList"),
  status: document.querySelector("#summaryStatus"),
  updated: document.querySelector("#updatedAt"),
};

function summaryNode(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function summaryNumber(value) {
  return new Intl.NumberFormat("zh-CN", { notation: value >= 10000 ? "compact" : "standard" }).format(value || 0);
}

function categoryItems(items, categoryId) {
  return items
    .filter((item) => (item.category?.id || "general") === categoryId)
    .sort((a, b) => (b.score?.total || 0) - (a.score?.total || 0));
}

function categoryCard(category, items) {
  const categorySkills = categoryItems(items, category.id);
  const card = summaryNode("article", `category-card tone-${category.tone}`);
  const link = summaryNode("a", "category-card-link");
  link.href = `./catalog.html?category=${encodeURIComponent(category.id)}`;
  link.setAttribute("aria-label", `查看 ${category.label} 类别的全部 skills`);
  const heading = summaryNode("div", "category-heading");
  heading.append(summaryNode("span", "category-marker", String(categorySkills.length)), summaryNode("h3", "", category.label));
  link.append(heading, summaryNode("p", "", category.description));
  const count = summaryNode("span", "category-count", `${categorySkills.length} 个 Skills`);
  link.append(count);

  const topList = summaryNode("div", "category-top-list");
  categorySkills.slice(0, 3).forEach((item) => {
    const skillLink = summaryNode("a", "category-top-skill", item.name);
    skillLink.href = `./skill.html?id=${encodeURIComponent(item.id)}`;
    skillLink.title = item.description;
    topList.append(skillLink);
  });
  if (!categorySkills.length) topList.append(summaryNode("span", "empty-skill", "暂无条目"));
  card.append(link, topList);
  return card;
}

function popularRow(item) {
  const link = summaryNode("a", "popular-row");
  link.href = `./skill.html?id=${encodeURIComponent(item.id)}`;
  const avatar = summaryNode("img", "avatar");
  avatar.src = item.repository.owner_avatar || "";
  avatar.alt = "";
  avatar.loading = "lazy";
  const identity = summaryNode("div", "popular-identity");
  identity.append(summaryNode("strong", "", item.name), summaryNode("span", "", item.category?.label || "通用工作流"));
  const meta = summaryNode("span", "popular-meta", `★ ${summaryNumber(item.repository.stars)} · 热度 ${item.score?.total || 0}`);
  link.append(avatar, identity, meta, summaryNode("span", "arrow", "→"));
  return link;
}

function summaryMetrics(items, categories) {
  document.querySelector("#skillCount").textContent = summaryNumber(items.length);
  document.querySelector("#repoCount").textContent = summaryNumber(new Set(items.map((item) => item.repository.full_name)).size);
  document.querySelector("#categoryCount").textContent = String(categories.length);
  document.querySelector("#activeCount").textContent = summaryNumber(items.filter((item) => {
    const pushed = new Date(item.repository.pushed_at || 0).getTime();
    return Date.now() - pushed <= 90 * 86400000;
  }).length);
}

async function loadSummary() {
  try {
    const response = await fetch("./catalog.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const catalog = await response.json();
    const items = Array.isArray(catalog.items) ? catalog.items : [];
    const categories = Array.isArray(catalog.categories) ? catalog.categories : [];
    summaryMetrics(items, categories);
    summaryElements.categories.replaceChildren(...categories.map((category) => categoryCard(category, items)));
    const popular = [...items].sort((a, b) => (b.score?.total || 0) - (a.score?.total || 0)).slice(0, 6);
    summaryElements.popular.replaceChildren(...popular.map(popularRow));
    summaryElements.status.hidden = true;
    const generated = new Date(catalog.generated_at);
    summaryElements.updated.textContent = Number.isNaN(generated.getTime())
      ? "更新时间未知"
      : `更新于 ${generated.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`;
  } catch (error) {
    summaryElements.status.textContent = `无法读取 catalog.json：${error.message}`;
  }
}

loadSummary();
