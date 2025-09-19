document.addEventListener("DOMContentLoaded", () => {
  const searchBtn = document.getElementById("searchBtn");
  const queryInput = document.getElementById("searchQuery");
  const candidateList = document.getElementById("candidate-list");
  const loader = document.getElementById("loader");

  function formatExperience(raw) {
    if (raw === null || raw === undefined || raw === "") return "N/A";
    const n = parseInt(raw, 10);
    if (!isNaN(n) && n >= 0) return `${n} yrs`;
    // if it's a string like "8 yrs" already
    return String(raw);
  }

  function formatSkills(cand) {
    // candidate may have skills array, skills_json, or a skills string
    if (Array.isArray(cand.skills) && cand.skills.length) return cand.skills.join(", ");
    if (cand.skills && typeof cand.skills === "string") {
      // maybe it's a comma separated string
      return cand.skills;
    }
    if (cand.skills_json) {
      try {
        const parsed = typeof cand.skills_json === "string" ? JSON.parse(cand.skills_json) : cand.skills_json;
        if (Array.isArray(parsed)) return parsed.join(", ");
        if (typeof parsed === "string") return parsed;
      } catch (e) {
        // fallback to raw string
        return String(cand.skills_json);
      }
    }
    return "N/A";
  }

  function formatMatchPercent(result) {
    // Prefer match_percent (backend refactor). Fallback to star -> percent conversion.
    if (result.match_percent !== undefined && result.match_percent !== null) {
      return `${Number(result.match_percent).toFixed(2)}%`;
    }
    // sometimes backend could still be returning 'star' out of 5
    if (result.star !== undefined && result.star !== null) {
      const star = Number(result.star) || 0;
      const pct = (star / 5) * 100;
      return `${pct.toFixed(2)}%`;
    }
    // fallback: maybe semantic/final_score present — normalize to percent if possible
    if (result.final_score !== undefined && result.final_score !== null) {
      // best-effort: we can't know max_score here, so show final_score*100 (not ideal)
      return `${(Number(result.final_score) * 100).toFixed(2)}%`;
    }
    return "0.00%";
  }

  function showNoResults(query) {
    candidateList.innerHTML = `<tr><td colspan="4">No candidates found for "${escapeHtml(query)}"</td></tr>`;
  }

  function escapeHtml(str) {
    if (!str && str !== 0) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  searchBtn.addEventListener("click", () => {
    const query = queryInput.value.trim();
    if (!query) {
      alert("Enter a search query first!");
      return;
    }

    candidateList.innerHTML = "";
    loader.style.display = "block"; // show loader

    fetch(`/search_candidates?query=${encodeURIComponent(query)}`)
      .then((res) => {
        if (!res.ok) throw new Error("Network response was not ok");
        return res.json();
      })
      .then((data) => {
        candidateList.innerHTML = "";
        const results = data.results || [];

        if (!results || results.length === 0) {
          showNoResults(query);
          return;
        }

        results.forEach((r) => {
          const cand = r.candidate || {};
          const name = escapeHtml(cand.name || cand.filename || "N/A");
          const experience = formatExperience(cand.experience);
          const skills = escapeHtml(formatSkills(cand));
          const matchPct = escapeHtml(formatMatchPercent(r));

          const row = document.createElement("tr");
          row.innerHTML = `
            <td>${name}</td>
            <td>${experience}</td>
            <td>${skills}</td>
            <td>${matchPct}</td>
          `;
          candidateList.appendChild(row);
        });
      })
      .catch((err) => {
        console.error("Search error:", err);
        candidateList.innerHTML = `<tr><td colspan="4">No results found. Please refine your search.</td></tr>`;
      })
      .finally(() => {
        loader.style.display = "none"; // hide loader
      });
  });
});
