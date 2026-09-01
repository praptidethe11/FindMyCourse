// Change this if your backend runs somewhere other than localhost:8000
const API_BASE = "http://localhost:8000";

const form = document.getElementById("search-form");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const durationInput = document.getElementById("duration");
const durationOut = document.getElementById("duration-out");
const paidToggle = document.getElementById("paid-toggle");

let paidValue = "";

durationInput.addEventListener("input", () => {
  durationOut.textContent = durationInput.value === "0" ? "No limit" : `${durationInput.value} weeks`;
});

paidToggle.querySelectorAll("button").forEach((btn) => {
  btn.addEventListener("click", () => {
    paidToggle.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    paidValue = btn.dataset.value;
  });
});
paidToggle.querySelector('button[data-value=""]').classList.add("active");

const RANK_BG = ["#9279BA", "#B9A5E2", "#D1C1F2", "#E7DDFF"];
const RANK_TEXT = ["#FFFFFF", "#241C33", "#241C33", "#241C33"];

function renderEmpty(message) {
  resultsEl.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
}

renderEmpty("Fill in the form and search to see your matches here.");

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    target_topic: document.getElementById("target-topic").value.trim(),
    degree: document.getElementById("degree").value || null,
    specialization: document.getElementById("specialization").value.trim() || null,
    is_paid: paidValue === "" ? null : paidValue === "true",
    max_duration_weeks: durationInput.value === "0" ? null : Number(durationInput.value),
    extra_description: document.getElementById("extra").value.trim(),
    top_k: 5,
  };

  if (!payload.target_topic) {
    statusEl.textContent = "Enter a target course topic to search.";
    statusEl.className = "status error";
    return;
  }

  statusEl.textContent = "Finding matches…";
  statusEl.className = "status";
  resultsEl.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Server responded with ${res.status}`);
    }

    const data = await res.json();
    statusEl.textContent = "";

    if (!data.results || data.results.length === 0) {
      renderEmpty("No courses matched those filters. Try loosening the duration or cost preference.");
      return;
    }

    resultsEl.innerHTML = data.results
      .map((course, i) => {
        const bg = RANK_BG[i % RANK_BG.length];
        const textColor = RANK_TEXT[i % RANK_TEXT.length];
        const meta = [
          course.platform,
          course.level,
          course.is_paid === false ? "Free" : course.is_paid === true ? "Paid" : null,
        ]
          .filter(Boolean)
          .join(" · ");
        const link = course.url
          ? `<a class="result-link" href="${escapeAttr(course.url)}" target="_blank" rel="noopener">View course</a>`
          : "";
        return `
        <li class="result-card">
          <div class="result-rank" style="background:${bg}; color:${textColor}">${i + 1}</div>
          <div class="result-body">
            <p class="result-title">${escapeHtml(course.title)}</p>
            <p class="result-meta">${escapeHtml(meta)}</p>
            <p class="result-desc">${escapeHtml(course.description)}</p>
            ${link}
          </div>
        </li>`;
      })
      .join("");
  } catch (err) {
    statusEl.textContent = `Couldn't reach the recommender service. Check that the backend is running at ${API_BASE}.`;
    statusEl.className = "status error";
    renderEmpty("Nothing to show yet.");
  }
});

function escapeHtml(str) {
  if (str == null) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/"/g, "&quot;");
}
