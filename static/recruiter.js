document.addEventListener("DOMContentLoaded", () => {
  const searchBtn = document.getElementById("searchBtn");
  const queryInput = document.getElementById("searchQuery");
  const candidateList = document.getElementById("candidate-list");
  const loader = document.getElementById("loader");
  const modal = document.getElementById("detailsModal");
  const modalBody = document.getElementById("detailsBody");
  const closeModal = document.getElementById("closeModal");

  function formatExperience(raw) {
    if (raw === null || raw === undefined || raw === "") return "N/A";
    const n = parseInt(raw, 10);
    if (!isNaN(n) && n >= 0) return `${n} yrs`;
    return String(raw);
  }

  function formatSkills(cand) {
    if (Array.isArray(cand.skills) && cand.skills.length) return cand.skills.join(", ");
    if (cand.skills && typeof cand.skills === "string") return cand.skills;
    if (cand.skills_json) {
      try {
        const parsed = typeof cand.skills_json === "string" ? JSON.parse(cand.skills_json) : cand.skills_json;
        if (Array.isArray(parsed)) return parsed.join(", ");
        if (typeof parsed === "string") return parsed;
      } catch (e) {
        return String(cand.skills_json);
      }
    }
    return "N/A";
  }

  function formatMatchPercent(result) {
    if (result.match_percent !== undefined && result.match_percent !== null) {
      return `${Number(result.match_percent).toFixed(2)}%`;
    }
    if (result.star !== undefined && result.star !== null) {
      const star = Number(result.star) || 0;
      const pct = (star / 5) * 100;
      return `${pct.toFixed(2)}%`;
    }
    if (result.final_score !== undefined && result.final_score !== null) {
      return `${(Number(result.final_score) * 100).toFixed(2)}%`;
    }
    return "0.00%";
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

  function showNoResults(query) {
    candidateList.innerHTML = `<tr><td colspan="5">No candidates found for "${escapeHtml(query)}"</td></tr>`;
  }

  // Modal close
  closeModal.addEventListener("click", () => {
    modal.style.display = "none";
  });
  window.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });

  function attachViewHandlers() {
    document.querySelectorAll(".view-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cid = btn.getAttribute("data-id");
        fetch(`/candidate_details/${cid}`)
          .then((res) => res.json())
          .then((data) => {
            modalBody.innerHTML = `
              <h2>${escapeHtml(data.name || "N/A")}</h2>
              <p><b>Email:</b> ${escapeHtml(data.email || "N/A")}</p>
              <p><b>Location:</b> ${escapeHtml(data.location || "N/A")}</p>
              <p><b>Experience:</b> ${escapeHtml(formatExperience(data.experience))}</p>
              <p><b>Summary:</b> ${escapeHtml(data.summary || "N/A")}</p>
              <p><b>Skills:</b> ${(data.skills || []).map(escapeHtml).join(", ") || "N/A"}</p>
              <h3>Projects:</h3>
              <ul>
                ${(data.projects || []).map(p => `<li>${escapeHtml(JSON.stringify(p))}</li>`).join("") || "<li>N/A</li>"}
              </ul>
            `;
            modal.style.display = "block";
          })
          .catch((err) => {
            modalBody.innerHTML = `<p>Error fetching details: ${err}</p>`;
            modal.style.display = "block";
          });
      });
    });
  }

  searchBtn.addEventListener("click", () => {
    const query = queryInput.value.trim();
    if (!query) {
      alert("Enter a search query first!");
      return;
    }

    candidateList.innerHTML = "";
    loader.style.display = "block";

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
            <td><button class="view-btn" data-id="${cand.id}">View</button></td>
          `;
          candidateList.appendChild(row);
        });

        attachViewHandlers();
      })
      .catch((err) => {
        console.error("Search error:", err);
        candidateList.innerHTML = `<tr><td colspan="5">No results found. Please refine your search.</td></tr>`;
      })
      .finally(() => {
        loader.style.display = "none";
      });
  });
});
