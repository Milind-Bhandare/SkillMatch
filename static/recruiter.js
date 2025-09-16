document.addEventListener("DOMContentLoaded", () => {
    const searchBtn = document.getElementById("searchBtn");
    const queryInput = document.getElementById("searchQuery");
    const candidateList = document.getElementById("candidate-list");
    const loader = document.getElementById("loader");

    searchBtn.addEventListener("click", () => {
        const query = queryInput.value.trim();
        if (!query) {
            alert("Enter a search query first!");
            return;
        }

        candidateList.innerHTML = "";
        loader.style.display = "block"; // show loader

        fetch(`/search_candidates?query=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(data => {
                candidateList.innerHTML = "";
                const results = data.results || [];

                if (!results || results.length === 0) {
                    candidateList.innerHTML = `<tr><td colspan="4">No candidates found for "${query}"</td></tr>`;
                    return;
                }

                results.forEach(r => {
                    const cand = r.candidate;
                    const stars = "★".repeat(Math.round(r.star)) + "☆".repeat(5 - Math.round(r.star));
                    const row = document.createElement("tr");
                    row.innerHTML = `
                        <td>${cand.name || "N/A"}</td>
                        <td>${cand.email || "N/A"}</td>
                        <td>${cand.experience || 0} yrs</td>
                        <td><span class="star">${stars}</span></td>
                    `;
                    candidateList.appendChild(row);
                });
            })
            .catch(() => {
                candidateList.innerHTML = `<tr><td colspan="4">No results found. Please refine your search.</td></tr>`;
            })
            .finally(() => {
                loader.style.display = "none"; // hide loader
            });
    });
});
