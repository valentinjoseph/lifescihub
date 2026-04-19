const companySelect = document.getElementById("companySelect");
const periodSelect = document.getElementById("periodSelect");
const refreshButton = document.getElementById("refreshButton");
const runTokenInput = document.getElementById("runToken");
const articleCount = document.getElementById("articleCount");
const companyCount = document.getElementById("companyCount");
const avgPriority = document.getElementById("avgPriority");
const topTopics = document.getElementById("topTopics");
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
  "SERVIER": "#d97706",
  "PFIZER": "#0ea5a5",
  "MODERNA": "#6d28d9",
  "VIATRIS": "#2563eb",
  "OPELLA": "#c2410c",
  "IPSEN": "#047857",
  "GALDERMA": "#be185d",
  "ALLIANCE HEALTHCARE": "#374151",
  "CEVA SANTE": "#15803d",
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
