const companySelect = document.getElementById("companySelect");
const periodSelect = document.getElementById("periodSelect");
const refreshButton = document.getElementById("refreshButton");
const runTokenInput = document.getElementById("runToken");
const articleCount = document.getElementById("articleCount");
const companyCount = document.getElementById("companyCount");
const avgPriority = document.getElementById("avgPriority");
const topTopics = document.getElementById("topTopics");
const companyBars = document.getElementById("companyBars");
const topicPulse = document.getElementById("topicPulse");
const newsRows = document.getElementById("newsRows");
const newsMeta = document.getElementById("newsMeta");
const chatButton = document.getElementById("chatButton");
const chatQuestion = document.getElementById("chatQuestion");
const chatMeta = document.getElementById("chatMeta");
const chatAnswer = document.getElementById("chatAnswer");
const TOKEN_STORAGE_KEY = "liscihub_access_token";
const defaultPeriods = [
  { value: "week", label: "This week" },
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
  populateSelect(companySelect, ["ALL"], "ALL");
  populateSelect(periodSelect, defaultPeriods, "week");
}

function restoreToken() {
  const savedToken = window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
  if (savedToken) {
    runTokenInput.value = savedToken;
  }
}

function persistToken() {
  const token = getRunToken();
  if (token) {
    window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  }
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
    item.innerHTML = `
      <div class="news-row-head">
        <div>
          <h3>${row.title || "Untitled article"}</h3>
          <p class="meta-line">${row.company_name} | ${row.published_date || "No date"} | Priority ${row.priority_score ?? ""}</p>
        </div>
      </div>
      <p>${row.article_summary || ""}</p>
      <div class="tag-row">
        ${row.key_topic ? `<span class="tag">${row.key_topic}</span>` : ""}
        ${row.signal_type ? `<span class="tag">${row.signal_type}</span>` : ""}
        ${row.geography ? `<span class="tag">${row.geography}</span>` : ""}
      </div>
      ${row.business_impact ? `<p><strong>Impact:</strong> ${row.business_impact}</p>` : ""}
      <a class="news-link" href="${row.url}" target="_blank" rel="noreferrer">Open source</a>
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
            <span>${company}</span>
            <strong>${count}</strong>
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
          <span>${topic}</span>
          <strong>${count}</strong>
        </div>
      `).join("")
    : "<p class='helper'>No dominant topic detected for the current filter.</p>";
}

async function loadDashboard() {
  const company = companySelect.value || "ALL";
  const period = periodSelect.value || "week";
  const response = await fetch(`/api/dashboard/news?company=${encodeURIComponent(company)}&period=${encodeURIComponent(period)}`, {
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
  populateSelect(companySelect, payload.filters.companies, payload.filters.selected_company);
  populateSelect(periodSelect, payload.filters.periods, payload.filters.selected_period);
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
    return;
  }
  chatMeta.textContent = "Thinking...";
  chatAnswer.textContent = "";
  const response = await fetch("/api/dashboard/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      question,
      company_name: companySelect.value || "ALL",
      period: periodSelect.value || "week",
    }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    chatMeta.textContent = "";
    chatAnswer.textContent = payload.detail || "Unable to answer right now.";
    return;
  }
  const payload = await response.json();
  chatMeta.textContent = `${payload.article_count} article(s) used | model: ${payload.model}`;
  chatAnswer.textContent = payload.answer || "";
}

runTokenInput.addEventListener("change", () => {
  persistToken();
  loadDashboard();
});
refreshButton.addEventListener("click", loadDashboard);
chatButton.addEventListener("click", askChat);

restoreToken();
initializeFilters();
loadDashboard().catch((error) => {
  newsRows.innerHTML = `<div class='news-row'><p class='meta-line'>${error.message}</p></div>`;
});
