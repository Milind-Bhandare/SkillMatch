document.addEventListener("DOMContentLoaded", () => {
  const searchBtn = document.getElementById("searchBtn");
  const queryInput = document.getElementById("searchQuery");
  const candidateList = document.getElementById("candidate-list");
  const loader = document.getElementById("loader");
  const modal = document.getElementById("detailsModal");
  const modalBody = document.getElementById("detailsBody");
  const closeModal = document.getElementById("closeModal");

  function formatExperience(raw) {
    if (raw == null || raw === "") return "N/A";
    const n = parseInt(raw, 10);
    return !isNaN(n) && n >= 0 ? `${n} yrs` : String(raw);
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
    if (result.match_percent != null) return `${Number(result.match_percent).toFixed(2)}%`;
    if (result.star != null) return `${((Number(result.star)||0)/5*100).toFixed(2)}%`;
    if (result.final_score != null) return `${(Number(result.final_score)*100).toFixed(2)}%`;
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
  closeModal.addEventListener("click", () => { modal.style.display = "none"; });
  window.addEventListener("click", (e) => { if (e.target === modal) modal.style.display = "none"; });

function attachViewHandlers() {
  document.querySelectorAll(".view-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cid = btn.getAttribute("data-id");

      fetch(`/candidate_details/${cid}`)
        .then((res) => res.json())
        .then((data) => {
          modalBody.innerHTML = `
            <div id="modalHeader" style="cursor:move;padding:5px;background:#003366;color:#fff;">
              <span>${escapeHtml(data.name || "N/A")}</span>
            </div>
            <div style="padding:10px;">
              <p><b>Email:</b> ${escapeHtml(data.email || "N/A")}</p>
              <p><b>Location:</b> ${escapeHtml(data.location || "N/A")}</p>
              <p><b>Experience:</b> ${escapeHtml(formatExperience(data.experience))}</p>
              <p><b>Skills:</b> ${(data.skills || []).map(escapeHtml).join(", ") || "N/A"}</p>
              <p><b><h3>AI Summary</h3><p></b>
              <div id="ai-summary" style="max-height:200px;overflow-y:auto;padding:5px;border:1px solid #ccc;border-radius:4px;font-family:sans-serif;line-height:1.4;">
                <span class="loader" style="display:inline-block;width:14px;height:14px;border:2px solid #999;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;"></span>
              </div>
            </div>
          `;
          modal.style.display = "block";

          const summaryEl = document.getElementById("ai-summary");

          fetch(`/candidate_ai/${cid}`)
            .then((res) => {
              if (!res.body) throw new Error("ReadableStream not supported");
              const reader = res.body.getReader();
              const decoder = new TextDecoder();
              let buffer = "";

              function readChunk() {
                reader.read().then(({ done, value }) => {
                  if (done) {
                    // Remove loader after stream finishes
                    const loader = summaryEl.querySelector(".loader");
                    if (loader) loader.remove();
                    // Final cleaned AI summary
                    summaryEl.innerHTML = escapeHtml(cleanAISummary(buffer)).replace(/\n/g, "<br>");
                    return;
                  }
                  buffer += decoder.decode(value, { stream: true });
                  // Update text without appending loader repeatedly
                  summaryEl.innerHTML = escapeHtml(cleanAISummary(buffer)).replace(/\n/g, "<br>");
                  readChunk();
                });
              }

              readChunk();
            })
            .catch((err) => {
              summaryEl.innerHTML = `<span style="color:red;">Error: ${escapeHtml(err.message)}</span>`;
            });
        })
        .catch((err) => {
          modalBody.innerHTML = `<p>Error fetching candidate details: ${escapeHtml(err.message)}</p>`;
          modal.style.display = "block";
        });
    });
  });
}

// Clean AI summary to remove repeated skill/project lines
function cleanAISummary(text) {
  if (!text) return "";
  const lines = text.split("\n").map(l => l.trim()).filter(Boolean);

  const filteredLines = lines.filter(line => {
    // Remove any repeated static info lines
    if (/^(Candidate:|Email:|Location:|Experience:|Skills:|Projects:)/i.test(line)) return false;
    if (/^AI Summary[:]?/i.test(line)) return false;
    return true;
  });

  return filteredLines.join("\n");
}

// CSS spinner + draggable modal
  const style = document.createElement("style");
  style.textContent = `
  @keyframes spin {
    0% { transform: rotate(0deg);}
    100% { transform: rotate(360deg);}
  }`;
  document.head.appendChild(style);



  function makeDraggable(modal, handle) {
    let offsetX=0, offsetY=0, isDown=false;
    handle.addEventListener("mousedown", e=>{
      isDown=true;
      offsetX=modal.offsetLeft-e.clientX;
      offsetY=modal.offsetTop-e.clientY;
      modal.classList.add("dragging");
    });
    document.addEventListener("mouseup", ()=>{isDown=false; modal.classList.remove("dragging");});
    document.addEventListener("mousemove", e=>{
      if(!isDown) return;
      modal.style.left = e.clientX+offsetX+"px";
      modal.style.top = e.clientY+offsetY+"px";
      modal.style.transform="none";
    });
  }
  new MutationObserver(()=>{
    const header = document.getElementById("modalHeader");
    if(header) makeDraggable(modal, header);
  }).observe(modal, {childList:true, subtree:true});

  // Search candidates
  searchBtn.addEventListener("click", ()=>{
    const query=queryInput.value.trim();
    if(!query){alert("Enter a search query first!"); return;}
    candidateList.innerHTML="";
    loader.style.display="block";

    fetch(`/search_candidates?query=${encodeURIComponent(query)}`)
      .then(res=>{if(!res.ok)throw new Error("Network response was not ok"); return res.json();})
      .then(data=>{
        candidateList.innerHTML="";
        const results = data.results || [];
        if(!results.length){showNoResults(query); return;}
        results.forEach(r=>{
          const cand = r.candidate || {};
          const row = document.createElement("tr");
          row.innerHTML=`
            <td>${escapeHtml(cand.name||cand.filename||"N/A")}</td>
            <td>${escapeHtml(formatExperience(cand.experience))}</td>
            <td>${escapeHtml(formatSkills(cand))}</td>
            <td>${escapeHtml(formatMatchPercent(r))}</td>
            <td><button class="view-btn" data-id="${cand.id}">View</button></td>
          `;
          candidateList.appendChild(row);
        });
        attachViewHandlers();
      })
      .catch(err=>{
        console.error("Search error:", err);
        candidateList.innerHTML=`<tr><td colspan="5">No results found. Please refine your search.</td></tr>`;
      })
      .finally(()=>{loader.style.display="none";});
  });
});
