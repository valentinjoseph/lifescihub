const industrySectorSelect = document.getElementById("industrySectorSelect");
const companySelect = document.getElementById("companySelect");
const periodSelect = document.getElementById("periodSelect");
const topicSelect = document.getElementById("topicSelect");
const refreshButton = document.getElementById("refreshButton");
const runTokenInput = document.getElementById("runToken");
const articleCount = document.getElementById("articleCount");
const companyCount = document.getElementById("companyCount");
const avgPriority = document.getElementById("avgPriority");
const topTopics = document.getElementById("topTopics");
const companyBars = document.getElementById("companyBars");
const topicPulse = document.getElementById("topicPulse");
const newsFeedPanel = document.getElementById("newsFeedPanel");
const newsFeedToggle = document.getElementById("newsFeedToggle");
const newsRows = document.getElementById("newsRows");
const newsMeta = document.getElementById("newsMeta");
const chatButton = document.getElementById("chatButton");
const chatQuestion = document.getElementById("chatQuestion");
const chatMeta = document.getElementById("chatMeta");
const chatAnswer = document.getElementById("chatAnswer");
const chatSources = document.getElementById("chatSources");
const TOKEN_STORAGE_KEY = "gtm_advisor_access_token";
const NEWS_FEED_VISIBLE_STORAGE_KEY = "gtm_advisor_news_feed_visible";
const defaultPeriods = [
  { value: "week", label: "Last 7 days" },
  { value: "month", label: "This month" },
  { value: "6_months", label: "Last 6 months" },
  { value: "all", label: "All available" },
];

const companyColors = {
  "SANOFI": "#0f5fa8",
  "SERVIER": "#1d4ed8",
  "PFIZER": "#0891b2",
  "MODERNA": "#4338ca",
  "VIATRIS": "#2563eb",
  "OPELLA": "#0369a1",
  "IPSEN": "#0f766e",
  "GALDERMA": "#4f46e5",
  "ALLIANCE HEALTHCARE": "#475569",
  "CEVA SANTE": "#0284c7",
};

function getRunToken() {
  return runTokenInput.value.trim();
}

function authHeaders() {
  const token = getRunToken();
  return token
    ? {
        "X-Viewer-Token": token,
        "X-Api-Key": token,
      }
    : {};
}

function populateSelect(select, values, selectedValue) {
  select.innerHTML = "";
  values.forEach((item) => {
    const option = document.createElement("option");
    if (typeof item === "string") {
      option.value = item;
      option.textContent = item;
    } else {
      option.value = item.value;
      option.textContent = item.label;
    }
    if (option.value === selectedValue) {
      option.selected = true;
    }
    select.appendChild(option);
  });
}

function initializeFilters() {
  populateSelect(industrySectorSelect, ["ALL"], "ALL");
  populateSelect(companySelect, ["ALL"], "ALL");
  populateSelect(periodSelect, defaultPeriods, "week");
  populateSelect(topicSelect, ["ALL"], "ALL");
}

function restoreToken() {
  const savedToken = readStorage(window.sessionStorage, TOKEN_STORAGE_KEY);
  if (savedToken) {
    runTokenInput.value = savedToken;
  }
}

function persistToken() {
  const token = getRunToken();
  if (token) {
    writeStorage(window.sessionStorage, TOKEN_STORAGE_KEY, token);
  } else {
    removeStorage(window.sessionStorage, TOKEN_STORAGE_KEY);
  }
}

function readStorage(storage, key) {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(storage, key, value) {
  try {
    storage.setItem(key, value);
  } catch {
    // Some managed browsers restrict storage; the dashboard still works without saved preferences.
  }
}

function removeStorage(storage, key) {
  try {
    storage.removeItem(key);
  } catch {
    // Some managed browsers restrict storage; clearing saved preferences is best-effort.
  }
}

function newsFeedIsVisible() {
  return !newsFeedPanel.classList.contains("news-feed-collapsed");
}

function setNewsFeedVisibility(isVisible) {
  newsFeedPanel.classList.toggle("news-feed-collapsed", !isVisible);
  newsFeedToggle.textContent = isVisible ? "Hide" : "Show";
  newsFeedToggle.setAttribute("aria-expanded", String(isVisible));
  writeStorage(window.localStorage, NEWS_FEED_VISIBLE_STORAGE_KEY, String(isVisible));
}

function restoreNewsFeedVisibility() {
  setNewsFeedVisibility(readStorage(window.localStorage, NEWS_FEED_VISIBLE_STORAGE_KEY) !== "false");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeUrl(value) {
  const url = String(value ?? "");
  return url.startsWith("http://") || url.startsWith("https://") ? url : "";
}

function renderRows(rows) {
  newsRows.innerHTML = "";
  if (!rows.length) {
    newsRows.innerHTML = "<div class='news-row'><p class='meta-line'>No articles match the current filters.</p></div>";
    return;
  }

  rows.forEach((row) => {
    const item = document.createElement("article");
    item.className = "news-row";
    item.style.borderLeftColor = companyColors[row.company_name] || "#8d99ae";
    const rowUrl = safeUrl(row.url);
    item.innerHTML = `
      <div class="news-row-head">
        <div>
          <h3>${escapeHtml(row.title || "Untitled article")}</h3>
          <p class="meta-line">${escapeHtml(row.industry_sector || "No sector")} | ${escapeHtml(row.company_name)} | ${escapeHtml(row.published_date || "No date")} | Priority ${escapeHtml(row.priority_score ?? "")}</p>
        </div>
      </div>
      <p>${escapeHtml(row.article_summary || "")}</p>
      <div class="tag-row">
        ${row.key_topic ? `<span class="tag">${escapeHtml(row.key_topic)}</span>` : ""}
        ${row.signal_type ? `<span class="tag">${escapeHtml(row.signal_type)}</span>` : ""}
        ${row.geography ? `<span class="tag">${escapeHtml(row.geography)}</span>` : ""}
      </div>
      ${row.business_impact ? `<p><strong>Impact:</strong> ${escapeHtml(row.business_impact)}</p>` : ""}
      ${rowUrl ? `<a class="news-link" href="${escapeHtml(rowUrl)}" target="_blank" rel="noreferrer">Open source</a>` : ""}
    `;
    newsRows.appendChild(item);
  });
}

function renderOverview(rows) {
  const companyCounts = new Map();
  const topicCounts = new Map();

  rows.forEach((row) => {
    if (row.company_name) {
      companyCounts.set(row.company_name, (companyCounts.get(row.company_name) || 0) + 1);
    }
    if (row.key_topic) {
      topicCounts.set(row.key_topic, (topicCounts.get(row.key_topic) || 0) + 1);
    }
  });

  const topCompanies = [...companyCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const maxCompanyCount = topCompanies[0]?.[1] || 1;
  companyBars.innerHTML = topCompanies.length
    ? topCompanies.map(([company, count]) => `
        <div class="bar-row">
          <div class="bar-meta">
            <span>${escapeHtml(company)}</span>
            <strong>${escapeHtml(count)}</strong>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${Math.max((count / maxCompanyCount) * 100, 8)}%; background:${companyColors[company] || "#1d4ed8"}"></div>
          </div>
        </div>
      `).join("")
    : "<p class='helper'>No company activity to show yet.</p>";

  const topTopicItems = [...topicCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  topicPulse.innerHTML = topTopicItems.length
    ? topTopicItems.map(([topic, count]) => `
        <div class="pulse-chip">
          <span>${escapeHtml(topic)}</span>
          <strong>${escapeHtml(count)}</strong>
        </div>
      `).join("")
    : "<p class='helper'>No dominant topic detected for the current filter.</p>";
}

function renderChatSources(sources) {
  chatSources.innerHTML = "";
  if (!sources || !sources.length) {
    return;
  }

  const title = document.createElement("h3");
  title.textContent = "Articles used";
  chatSources.appendChild(title);

  sources.forEach((source, index) => {
    const item = document.createElement("article");
    item.className = "source-card";
    const sourceUrl = safeUrl(source.url);
    item.innerHTML = `
      <div class="source-head">
        <strong>${index + 1}. ${escapeHtml(source.company_name || "Unknown company")}</strong>
        <span>${escapeHtml(source.published_date || "No date")} | Priority ${escapeHtml(source.priority_score ?? "")}</span>
      </div>
      <p class="source-title">${escapeHtml(source.title || "Untitled article")}</p>
      ${source.article_summary ? `<p>${escapeHtml(source.article_summary)}</p>` : ""}
      ${source.business_impact ? `<p><strong>Impact:</strong> ${escapeHtml(source.business_impact)}</p>` : ""}
      ${sourceUrl ? `<a class="news-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">Open source article</a>` : ""}
    `;
    chatSources.appendChild(item);
  });
}

async function loadDashboard() {
  const industrySector = industrySectorSelect.value || "ALL";
  const company = companySelect.value || "ALL";
  const period = periodSelect.value || "week";
  const topic = topicSelect.value || "ALL";
  const response = await fetch(`/api/dashboard/news?industry_sector=${encodeURIComponent(industrySector)}&company=${encodeURIComponent(company)}&period=${encodeURIComponent(period)}&topic=${encodeURIComponent(topic)}`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) {
      initializeFilters();
      newsMeta.textContent = "Paste a viewer or admin token, or sign in through /viewer to enter viewer mode.";
      newsRows.innerHTML = "<div class='news-row'><p class='meta-line'>Dashboard access requires a viewer or admin token.</p></div>";
      articleCount.textContent = "0";
      companyCount.textContent = "0";
      avgPriority.textContent = "0";
      topTopics.textContent = "None";
      companyBars.innerHTML = "<p class='helper'>Sign in to unlock company activity.</p>";
      topicPulse.innerHTML = "<p class='helper'>Sign in to unlock topic pulse.</p>";
      return;
    }
    throw new Error(payload.detail || "Unable to load dashboard data");
  }
  const payload = await response.json();
  populateSelect(industrySectorSelect, payload.filters.industry_sectors, payload.filters.selected_industry_sector);
  populateSelect(companySelect, payload.filters.companies, payload.filters.selected_company);
  populateSelect(periodSelect, payload.filters.periods, payload.filters.selected_period);
  populateSelect(topicSelect, payload.filters.topics, payload.filters.selected_topic);
  articleCount.textContent = payload.summary.article_count;
  companyCount.textContent = payload.summary.company_count;
  avgPriority.textContent = payload.summary.avg_priority;
  topTopics.textContent = (payload.summary.top_topics || []).map((item) => item.index || item.key_topic).join(", ") || "None";
  newsMeta.textContent = `${payload.summary.article_count} article(s) loaded`;
  renderOverview(payload.rows || []);
  renderRows(payload.rows || []);
}

async function askChat() {
  const question = chatQuestion.value.trim();
  if (!question) {
    chatAnswer.textContent = "Type a question first.";
    chatSources.innerHTML = "";
    return;
  }
  chatMeta.textContent = "Thinking...";
  chatAnswer.textContent = "";
  chatSources.innerHTML = "";
  const response = await fetch("/api/dashboard/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      question,
      company_name: "ALL",
      period: "all",
    }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    chatMeta.textContent = "";
    chatAnswer.textContent = payload.detail || "Unable to answer right now.";
    chatSources.innerHTML = "";
    return;
  }
  const payload = await response.json();
  chatMeta.textContent = `${payload.article_count} article(s) used | model: ${payload.model}`;
  chatAnswer.textContent = payload.answer || "";
  renderChatSources(payload.sources || []);
}

runTokenInput.addEventListener("change", () => {
  persistToken();
  loadDashboard();
});
refreshButton.addEventListener("click", loadDashboard);
periodSelect.addEventListener("change", () => {
  industrySectorSelect.value = "ALL";
  companySelect.value = "ALL";
  topicSelect.value = "ALL";
  loadDashboard();
});
industrySectorSelect.addEventListener("change", () => {
  companySelect.value = "ALL";
  topicSelect.value = "ALL";
  loadDashboard();
});
companySelect.addEventListener("change", () => {
  topicSelect.value = "ALL";
  loadDashboard();
});
topicSelect.addEventListener("change", loadDashboard);
chatButton.addEventListener("click", askChat);
newsFeedToggle.addEventListener("click", () => {
  setNewsFeedVisibility(!newsFeedIsVisible());
});

restoreToken();
restoreNewsFeedVisibility();
initializeFilters();
loadDashboard().catch((error) => {
  newsRows.innerHTML = `<div class='news-row'><p class='meta-line'>${escapeHtml(error.message)}</p></div>`;
});
